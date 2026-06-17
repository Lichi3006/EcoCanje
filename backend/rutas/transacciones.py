from fastapi import APIRouter
from pydantic import BaseModel
from typing import Dict, Any
from database import db_clients

router = APIRouter(prefix="/transacciones", tags=["Dominio: Transacciones y Canjes (Redis/Saga)"])

# =========================================================================
# ESQUEMAS DE ENTRADA
# =========================================================================

class QRHandshakePayload(BaseModel):
    id_qr_transaccional: str
    id_usuario: str

# =========================================================================
# RUTAS DE AUDITORÍA (CASSANDRA)
# =========================================================================

@router.get("/ledger")
async def listar_ledger():
    """
    Lista las últimas 50 transacciones del Ledger Inmutable de Cassandra.
    Útil para auditoría cruda y para saber qué usuarios tienen saldo a reconciliar.
    """
    cassandra_session = db_clients.get("cassandra_session")
    if not cassandra_session:
         return {"error": "Servicio de Cassandra no disponible"}
         
    query = "SELECT * FROM ecocanje_ks.depositos_ledger LIMIT 50"
    filas = cassandra_session.execute(query)
    
    resultados = []
    for f in filas:
        resultados.append({
            "id_deposito": str(f.id_deposito),
            "id_usuario": f.id_usuario,
            "id_terminal": f.id_terminal,
            "timestamp": f.timestamp.isoformat() if f.timestamp else None,
            "monto_acreditado": float(f.monto_acreditado),
            "peso_kg": float(f.peso_kg),
            "tipo_material": f.tipo_material,
            "firma_ecdsa": f.firma_ecdsa
        })
        
    return {
        "mensaje": "Volcado del Ledger en Cassandra exitoso",
        "total_registros_mostrados": len(resultados),
        "ledger": resultados
    }

@router.get("/auditoria_redis")
async def volcado_redis_crudo():
    """
    Volcado crudo de la memoria efímera de Redis.
    Audita: Capacidades de contenedores, Tokens QR efímeros vivos y la Cola SAGA de compensación.
    """
    redis_client = db_clients.get("redis")
    if not redis_client:
         return {"error": "Servicio de Redis no disponible"}
         
    import json
    
    # 1. Capacidades (Q3)
    keys_capacidad = await redis_client.keys("capacidad:*")
    capacidades = {}
    for k in keys_capacidad:
        capacidades[k] = await redis_client.hgetall(k)
        
    # 2. Handshakes QR Vivos (Q4)
    keys_handshake = await redis_client.keys("handshake:*")
    handshakes = {}
    for k in keys_handshake:
        ttl = await redis_client.ttl(k)
        datos = await redis_client.hgetall(k)
        handshakes[k] = {"ttl_restante_segundos": ttl, "datos": datos}
        
    # 3. Cola SAGA (Q5 Fallback)
    cola_saga = await redis_client.lrange("cola_saga_saldos_pendientes", 0, -1)
    saga_parseada = [json.loads(item) for item in cola_saga]
    
    return {
        "mensaje": "Radiografía en vivo de la memoria Redis",
        "1_capacidades_iot": capacidades,
        "2_tokens_qr_vivos": handshakes,
        "3_cola_saga_mongo_caido": saga_parseada
    }

# =========================================================================
# PATRÓN Q4
# =========================================================================

@router.post("/canje-qr")
async def Q4_validacion_atomica_qr(payload: QRHandshakePayload):
    """
    Patrón Q4: Validación Atómica y Canje de Token QR Efímero (QR Handshake).
    
    Nota Arquitectónica de Seguridad:
    Esta ruta está diseñada para mitigar ataques de doble gasto.
    Se espera utilizar un script Lua ejecutado de forma atómica en Redis
    para recuperar el contenido del QR y destruirlo en el mismo microsegundo.
    """
    
    redis_client = db_clients.get("redis")
    if not redis_client:
        return {"error": "Servicio de Redis no disponible en el backend."}

    # Definimos el script Lua. 
    # Hace 3 cosas atómicas: pregunta si existe (EXISTS), lee los datos (HGETALL) y borra el token (DEL)
    lua_script = """
    if redis.call('EXISTS', KEYS[1]) == 1 then
        local val = redis.call('HGETALL', KEYS[1])
        redis.call('DEL', KEYS[1])
        return val
    else
        return nil
    end
    """
    
    # La clave en Redis tiene el formato 'handshake:<uuid>'
    clave_redis = f"handshake:{payload.id_qr_transaccional}"
    
    # Ejecutamos el script Lua usando el comando EVAL
    # 1 indica que le pasamos 1 sola key (clave_redis)
    resultado = await redis_client.eval(lua_script, 1, clave_redis)
    
    if resultado is None:
        return {
            "estado": "RECHAZADO",
            "mensaje": "El token QR ya fue utilizado, no existe o expiró por tiempo límite (120s)."
        }
        
    # Redis en Lua devuelve un arreglo intercalado para los hashes: [clave1, valor1, clave2, valor2...]
    # Lo convertimos a un diccionario de Python iterando de a 2 elementos para mayor legibilidad.
    datos_qr = {}
    for i in range(0, len(resultado), 2):
        clave = resultado[i]
        valor = resultado[i+1]
        datos_qr[clave] = valor
    
    return {
        "estado": "APROBADO",
        "mensaje": "Handshake QR validado y destruido exitosamente para prevenir doble gasto.",
        "id_usuario_vinculado": payload.id_usuario,
        "payload_terminal": datos_qr
    }

# =========================================================================
# PATRÓN Q5
# =========================================================================

class RegistroEntregaPayload(BaseModel):
    id_deposito: str
    id_usuario: str
    id_terminal: str
    tipo_material: str
    peso_kg: float
    firma_ecdsa: str
    timestamp_local: int

@router.post("/registro-entrega")
async def Q5_registro_inmutable_entrega(payload: RegistroEntregaPayload):
    """
    Patrón Q5: Registro Inmutable de una Entrega (Escritura Dual y Patrón SAGA).
    """
    cassandra_session = db_clients.get("cassandra_session")
    mongo_db = db_clients.get("mongodb")
    redis_client = db_clients.get("redis")
    
    # 0. Lógica de Negocio Segura: El Backend calcula el precio, NO la terminal IoT.
    precio_base = 10.0 # fallback
    material_upper = payload.tipo_material.upper()
    
    # Intentamos leer la tarifa de Redis (caché)
    if redis_client:
        tarifa_cacheada = await redis_client.get(f"tarifa:{material_upper}")
        if tarifa_cacheada:
            precio_base = float(tarifa_cacheada)
        elif mongo_db is not None:
            # Si no está en Redis, la traemos de MongoDB
            coleccion_tarifas = mongo_db["TarifasMateriales"]
            tarifa_db = await coleccion_tarifas.find_one({"material": material_upper})
            if tarifa_db:
                precio_base = float(tarifa_db.get("precio_kg", 10.0))
                # Guardamos en caché Redis por 1 hora
                await redis_client.setex(f"tarifa:{material_upper}", 3600, precio_base)
                
    monto_calculado = float(payload.peso_kg * precio_base)

    # 1. Escritura Principal en Cassandra (Ledger inmutable)
    if cassandra_session:
        try:
            # Query preparada
            cql = """
                INSERT INTO depositos_ledger 
                (id_usuario, timestamp, id_deposito, id_terminal, tipo_material, peso_kg, monto_acreditado, firma_ecdsa) 
                VALUES (%s, toTimestamp(now()), %s, %s, %s, %s, %s, %s)
            """
            cassandra_session.execute_async(cql, (
                payload.id_usuario, payload.id_deposito, payload.id_terminal,
                payload.tipo_material, payload.peso_kg, monto_calculado, payload.firma_ecdsa
            ))
        except Exception as e:
            print(f"[ERROR CASSANDRA] Falló escritura del ledger: {e}")
            
    # 2. Actualización de Saldo en MongoDB (con Fallback SAGA a Redis)
    saldo_actualizado = False
    if mongo_db is not None:
        try:
            from decimal import Decimal
            from bson.decimal128 import Decimal128
            from datetime import datetime, timezone
            
            coleccion_perfiles = mongo_db["PerfilesUsuario"]
            
            # Buscamos el usuario y sumamos el monto con $inc
            resultado = await coleccion_perfiles.update_one(
                {"id_usuario": payload.id_usuario},
                {
                    "$inc": {"balance_incentivos": Decimal128(Decimal(str(monto_calculado)))},
                    "$set": {"ultima_actualizacion": datetime.now(timezone.utc)}
                }
            )
            
            # Consideramos exitoso si encontró al usuario (modificara o no el saldo si era 0)
            if resultado.matched_count > 0:
                saldo_actualizado = True
        except Exception as e:
            print(f"[ERROR MONGODB] Caída durante actualización de saldo: {e}")

    # 3. Compensación Asíncrona (Patrón SAGA): Si Mongo falló, encolamos en Redis
    if not saldo_actualizado and redis_client:
        import json
        payload_saga = payload.model_dump()
        payload_saga["monto_acreditado"] = monto_calculado
        payload_saga["estado_saga"] = "PENDIENTE_DE_COBRO"
        
        # Encolamos en una lista de Redis para reintentos (LPUSH)
        await redis_client.lpush("cola_saga_saldos_pendientes", json.dumps(payload_saga))
        print(f"[SAGA] Saldo del usuario {payload.id_usuario} encolado en Redis para reintento automático.")

    return {
        "mensaje": "Proceso Q5 ejecutado.",
        "ledger_cassandra": "Enviado",
        "saldo_billetera_actualizado": saldo_actualizado,
        "saga_redis_activado": not saldo_actualizado
    }

# =========================================================================
# PATRÓN Q9
# =========================================================================

@router.post("/reconciliacion/{id_usuario}")
async def Q9_conciliacion_financiera(id_usuario: str):
    """
    Patrón Q9: Conciliación Financiera entre el Ledger e Incentivos Acumulados (Reconciliation Job).
    Auditoría asíncrona que compara la suma inmutable en Cassandra con el saldo vivo en MongoDB,
    reparando cualquier desvío en caso de inconsistencia.
    """
    cassandra_session = db_clients.get("cassandra_session")
    mongo_db = db_clients.get("mongodb")
    
    if cassandra_session is None or mongo_db is None:
        return {"error": "Bases de datos requeridas no disponibles para la conciliación."}
        
    try:
        # 1. Obtenemos la sumatoria total (La "Verdad Absoluta" del Ledger en Cassandra)
        cql_sum = "SELECT sum(monto_acreditado) AS total_ledger FROM depositos_ledger WHERE id_usuario = %s"
        resultado_cassandra = cassandra_session.execute(cql_sum, (id_usuario,))
        fila = resultado_cassandra.one()
        
        total_ledger = float(fila.total_ledger) if fila and fila.total_ledger is not None else 0.0
        
        # 2. Obtenemos el saldo vivo actual (Lo que el usuario ve en la App desde MongoDB)
        coleccion_perfiles = mongo_db["PerfilesUsuario"]
        perfil = await coleccion_perfiles.find_one({"id_usuario": id_usuario}, {"balance_incentivos": 1, "_id": 0})
        
        if not perfil:
            return {"error": f"Usuario {id_usuario} no encontrado en MongoDB."}
            
        balance_decimal128 = perfil.get("balance_incentivos")
        saldo_mongodb = float(balance_decimal128.to_decimal()) if balance_decimal128 else 0.0
        
        # 3. Comparamos y Reparamos (Patrón Reconciliation Job)
        discrepancia = round(abs(total_ledger - saldo_mongodb), 2)
        reparado = False
        
        if discrepancia > 0:
            from decimal import Decimal
            from bson.decimal128 import Decimal128
            from datetime import datetime, timezone
            
            # Reparación: Pisamos el saldo desactualizado de Mongo ($set) con el total del Ledger
            await coleccion_perfiles.update_one(
                {"id_usuario": id_usuario},
                {
                    "$set": {
                        "balance_incentivos": Decimal128(Decimal(str(total_ledger))),
                        "ultima_actualizacion": datetime.now(timezone.utc)
                    }
                }
            )
            reparado = True
            
        return {
            "id_usuario": id_usuario,
            "auditoria": {
                "saldo_ledger_cassandra": total_ledger,
                "saldo_vivo_mongodb": saldo_mongodb,
                "discrepancia_detectada": discrepancia
            },
            "estado_conciliacion": "REPARADO" if reparado else "CONSISTENTE",
            "mensaje": "Se detectó desvío y se reparó el saldo en MongoDB." if reparado else "Los saldos de ambas bases cuadran perfectamente."
        }

    except Exception as e:
        return {"error": f"Fallo crítico en el job de reconciliación: {e}"}
