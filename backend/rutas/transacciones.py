from fastapi import APIRouter
from pydantic import BaseModel
from typing import Dict, Any
from cassandra.cluster import NoHostAvailable
from database import db_clients, get_cassandra_session

router = APIRouter(prefix="/transacciones", tags=["Dominio: Transacciones y Canjes (Redis/Fallback)"])

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
    Audita: Capacidades de contenedores, Tokens QR efímeros vivos y la Cola de Compensación en Redis.
    """
    redis_client = db_clients.get("redis")
    if not redis_client:
         return {"error": "Servicio de Redis no disponible"}
         
    import json
    
    # 1. Capacidades (Q3)
    keys_capacidad = await redis_client.keys("cap:terminal:*")
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
        
    # 3. Cola Fallback (Q5)
    cola_fallback = await redis_client.lrange("cola_fallback_saldos_pendientes", 0, -1)
    fallback_parseada = [json.loads(item) for item in cola_fallback]
    
    return {
        "mensaje": "Estado en vivo de la memoria Redis",
        "1_capacidades_iot": capacidades,
        "2_tokens_qr_vivos": handshakes,
        "3_cola_fallback_mongo_caido": fallback_parseada
    }

# =========================================================================
# PATRÓN Q4
# =========================================================================

@router.post("/crear-token-qr")
async def crear_token_qr_iot(payload: dict):
    """
    Ruta interna para la Terminal IoT (Edge).
    Recibe el payload completo de la transacción (kilos, firmas, id_terminal),
    lo guarda en Redis con un TTL de 120s, y le devuelve un token corto a la máquina
    para que dibuje el código QR en pantalla.
    """
    import uuid
    redis_client = db_clients.get("redis")
    if not redis_client:
        return {"error": "Redis no disponible."}
        
    token = f"QR-{str(uuid.uuid4())[:6].upper()}"
    clave_redis = f"handshake:{token}"
    
    # Insertar el diccionario como un Hash en Redis
    await redis_client.hset(clave_redis, mapping=payload)
    # Configurar el TTL de 120 segundos (2 minutos para escanear)
    await redis_client.expire(clave_redis, 120)
    
    return {"token_qr": token}

@router.post("/crear-token-qr")
async def crear_token_qr_iot(payload: dict):
    """
    Ruta interna para la Terminal IoT (Edge).
    Recibe el payload completo de la transacción (kilos, firmas, id_terminal),
    lo guarda en Redis con un TTL de 120s, y le devuelve un token corto a la máquina
    para que dibuje el código QR en pantalla.
    """
    import uuid
    redis_client = db_clients.get("redis")
    if not redis_client:
        return {"error": "Redis no disponible."}
        
    token = f"QR-{str(uuid.uuid4())[:6].upper()}"
    clave_redis = f"handshake:{token}"
    
    # Insertar el diccionario como un Hash en Redis
    await redis_client.hset(clave_redis, mapping=payload)
    # Configurar el TTL de 120 segundos (2 minutos para escanear)
    await redis_client.expire(clave_redis, 120)
    
    return {"token_qr": token}

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
    monto_acreditado: float
    firma_ecdsa: str
    timestamp_local: int

@router.post("/registro-entrega")
async def Q5_registro_inmutable_entrega(payload: RegistroEntregaPayload):
    """
    Patrón Q5: Registro Inmutable de una Entrega (Escritura Dual y Compensación).
    """
    try:
        cassandra_session = get_cassandra_session()
    except ConnectionError:
        cassandra_session = None  # Cassandra caida: activa el fallback a Mongo/Redis

    mongo_db = db_clients.get("mongodb")
    redis_client = db_clients.get("redis")

    cassandra_ok = False
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
                payload.tipo_material, payload.peso_kg, payload.monto_acreditado, payload.firma_ecdsa
            ))
            cassandra_ok = True
        except Exception as e:
            print(f"[ERROR CASSANDRA] Falló escritura del ledger: {e}")
            
    if not cassandra_ok:
        print("[FALLBACK] Intentando guardar ticket Q5 en MongoDB...")
        if mongo_db is not None:
            try:
                await mongo_db["Q5_Fallback_Cassandra"].insert_one(payload.model_dump())
                print("[FALLBACK] Ticket Q5 guardado temporalmente en Mongo.")
            except Exception as e:
                print(f"[ERROR MONGODB] Falló guardado de fallback Q5: {e}")
    # 2. Actualización de Saldo en MongoDB (con Fallback Asíncrono a Redis)
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
                    "$inc": {"balance_incentivos": Decimal128(Decimal(str(payload.monto_acreditado)))},
                    "$set": {"ultima_actualizacion": datetime.now(timezone.utc)}
                }
            )
            
            # Consideramos exitoso si encontró al usuario (modificara o no el saldo si era 0)
            if resultado.matched_count > 0:
                saldo_actualizado = True
                
        except Exception as e:
            print(f"[ERROR MONGODB] Caída durante actualización de saldo: {e}")

    # 3. Compensación Asíncrona: Si Mongo falló, encolamos en Redis
    if not saldo_actualizado and redis_client:
        import json
        payload_fallback = payload.model_dump()
        payload_fallback["estado_compensacion"] = "PENDIENTE_DE_COBRO"
        
        # Encolamos en una lista de Redis para reintentos (LPUSH)
        await redis_client.lpush("cola_fallback_saldos_pendientes", json.dumps(payload_fallback))
        print(f"[FALLBACK] Saldo del usuario {payload.id_usuario} encolado en Redis para reintento automático.")
        
    # Determinamos la estrategia final ejecutada para retornar en la respuesta
    estrategia = "ESCRITURA DUAL (Cassandra + MongoDB)"
    if cassandra_ok and not saldo_actualizado:
        estrategia = "FALLBACK 1: CASSANDRA + REDIS (MongoDB caído)"
    elif not cassandra_ok and saldo_actualizado:
        estrategia = "FALLBACK 2: MONGODB TEMPORAL (Cassandra caída)"
    elif not cassandra_ok and not saldo_actualizado:
        estrategia = "FALLBACK 3: DEGRADACION EXTREMA A REDIS (Ambos discos caídos)"

    return {
        "estado": "REGISTRADO",
        "id_deposito": payload.id_deposito,
        "monto_acreditado": payload.monto_acreditado,
        "estrategia_ejecutada": estrategia,
        "fallback_status": "OK" if saldo_actualizado else "ENCOLADO"
    }

# =========================================================================
# PATRON Q9 - Job de Reconciliacion y Promocion Jerarquica de Datos
# =========================================================================

@router.post("/reconciliacion/{id_usuario}")
async def Q9_conciliacion_financiera(id_usuario: str):
    """
    Patron Q9: Reconciliacion Financiera y Promocion Jerarquica de Datos Pendientes.

    El job evalua el estado de disponibilidad de cada motor y ejecuta
    SOLO UNO de los siguientes caminos, en orden de prioridad:

    CAMINO 1 - Redis a Cassandra (maxima prioridad):
      Si Cassandra esta disponible y Redis tiene tickets pendientes en
      'cola_fallback_saldos_pendientes', los drena hacia el ledger
      inmutable de Cassandra y actualiza el saldo en MongoDB si esta vivo.

    CAMINO 2 - MongoDB a Cassandra:
      Si Cassandra esta disponible y MongoDB tiene depositos en
      'Q5_Fallback_Cassandra', los promueve al ledger inmutable y
      luego ejecuta la conciliacion financiera completa.

    CAMINO 3 - Redis a MongoDB (minimo viable):
      Si Cassandra no responde pero MongoDB y Redis estan activos,
      mueve los tickets de Redis hacia la coleccion 'Q5_Fallback_Cassandra'
      de MongoDB para preservar la durabilidad hasta que Cassandra vuelva.

    Si ninguno de los tres caminos es posible, reporta el estado de cada motor.
    """
    import json
    from decimal import Decimal
    from bson.decimal128 import Decimal128
    from datetime import datetime, timezone

    mongo_db      = db_clients.get("mongodb")
    redis_client  = db_clients.get("redis")

    # --- Verificamos disponibilidad de Cassandra (falla rapida) ---
    cassandra_session = None
    try:
        cassandra_session = get_cassandra_session()
    except (ConnectionError, Exception):
        cassandra_session = None

    # --- Verificamos disponibilidad real de MongoDB (Motor hace conexion lazy) ---
    mongo_vivo = False
    if mongo_db is not None:
        try:
            await mongo_db.command("ping")
            mongo_vivo = True
        except Exception:
            mongo_vivo = False

    # --- Verificamos disponibilidad de Redis ---
    redis_vivo = False
    if redis_client is not None:
        try:
            await redis_client.ping()
            redis_vivo = True
        except Exception:
            redis_vivo = False

    # =========================================================================
    # CAMINO 1: MongoDB → Cassandra
    # Depositos guardados en Mongo cuando Cassandra estaba caida (Q5_Fallback).
    # Los promovemos al ledger y ejecutamos la conciliacion completa.
    # =========================================================================
    if cassandra_session is not None and mongo_vivo:
        coleccion_fallback  = mongo_db["Q5_Fallback_Cassandra"]
        coleccion_perfiles  = mongo_db["PerfilesUsuario"]
        coleccion_pendientes = mongo_db["Q9_Pendientes_Conciliacion"]

        # Primero drenamos Q5_Fallback_Cassandra si tiene datos del usuario
        pendientes_mongo = await coleccion_fallback.find({"id_usuario": id_usuario}).to_list(length=None)
        drenados = 0
        if pendientes_mongo:
            cql_insert = """
                INSERT INTO depositos_ledger
                (id_usuario, timestamp, id_deposito, id_terminal, tipo_material, peso_kg, monto_acreditado, firma_ecdsa)
                VALUES (%s, toTimestamp(now()), %s, %s, %s, %s, %s, %s)
            """
            for doc in pendientes_mongo:
                try:
                    cassandra_session.execute(cql_insert, (
                        doc.get("id_usuario"),
                        doc.get("id_deposito", "RECUPERADO"),
                        doc.get("id_terminal", "DESCONOCIDO"),
                        doc.get("tipo_material", "DESCONOCIDO"),
                        float(doc.get("peso_kg", 0)),
                        float(doc.get("monto_acreditado", 0)),
                        doc.get("firma_ecdsa", "FALLBACK"),
                    ))
                    await coleccion_fallback.delete_one({"_id": doc["_id"]})
                    drenados += 1
                except Exception as e:
                    print(f"[Q9-CAMINO1] Error drenando deposito de Mongo a Cassandra: {e}")

        # Luego ejecutamos la conciliacion financiera completa
        cql_sum = "SELECT sum(monto_acreditado) AS total_ledger FROM depositos_ledger WHERE id_usuario = %s"
        resultado_cassandra = cassandra_session.execute(cql_sum, (id_usuario,))
        fila = resultado_cassandra.one()
        total_ledger = float(fila.total_ledger) if fila and fila.total_ledger is not None else 0.0

        perfil = await coleccion_perfiles.find_one({"id_usuario": id_usuario}, {"balance_incentivos": 1, "_id": 0})
        if not perfil:
            return {"error": f"Usuario {id_usuario} no encontrado en MongoDB."}

        balance_decimal128 = perfil.get("balance_incentivos")
        saldo_mongodb = float(balance_decimal128.to_decimal()) if balance_decimal128 else 0.0

        # Limpiamos el snapshot de Q9 si existia
        snapshot_previo = await coleccion_pendientes.find_one({"id_usuario": id_usuario})
        snapshot_drenado = False
        if snapshot_previo:
            await coleccion_pendientes.delete_one({"id_usuario": id_usuario})
            snapshot_drenado = True

        discrepancia = round(abs(total_ledger - saldo_mongodb), 2)
        reparado = False
        if discrepancia > 0:
            await coleccion_perfiles.update_one(
                {"id_usuario": id_usuario},
                {"$set": {
                    "balance_incentivos": Decimal128(Decimal(str(total_ledger))),
                    "ultima_actualizacion": datetime.now(timezone.utc)
                }}
            )
            reparado = True

        return {
            "id_usuario": id_usuario,
            "estado": "SUCCESS",
            "camino_ejecutado": "CAMINO 1: MongoDB a Cassandra (Reconciliacion Completa)",
            "mensaje": "Desvio detectado y reparado en MongoDB." if reparado else "Los saldos de ambas bases cuadran perfectamente.",
            "metricas": {
                "tickets_promovidos": drenados,
                "errores": 0,
                "saldo_ledger_cassandra": total_ledger,
                "saldo_vivo_mongodb": saldo_mongodb,
                "discrepancia_detectada": discrepancia,
                "items_restantes_en_redis": await redis_client.llen("cola_fallback_saldos_pendientes") if redis_vivo else 0
            },
            "estado_motores": {
                "cassandra": "disponible" if cassandra_session else "no disponible",
                "mongodb": "disponible" if mongo_vivo else "no disponible",
                "redis": "disponible" if redis_vivo else "no disponible"
            }
        }

    # =========================================================================
    # CAMINO 2: Redis → Cassandra
    # Tickets encolados por Q5 cuando MongoDB cayo. Los subimos al ledger
    # inmutable de Cassandra, que es la fuente de verdad definitiva.
    # =========================================================================
    if cassandra_session is not None and redis_vivo:
        items_redis = await redis_client.lrange("cola_fallback_saldos_pendientes", 0, -1)

        if items_redis:
            promovidos = 0
            errores    = 0
            cql_insert = """
                INSERT INTO depositos_ledger
                (id_usuario, timestamp, id_deposito, id_terminal, tipo_material, peso_kg, monto_acreditado, firma_ecdsa)
                VALUES (%s, toTimestamp(now()), %s, %s, %s, %s, %s, %s)
            """
            for item_raw in items_redis:
                try:
                    ticket = json.loads(item_raw)
                    if ticket.get("id_usuario") != id_usuario:
                        continue  # Solo procesamos tickets del usuario solicitado
                    cassandra_session.execute(cql_insert, (
                        ticket.get("id_usuario"),
                        ticket.get("id_deposito", "RECUPERADO"),
                        ticket.get("id_terminal", "DESCONOCIDO"),
                        ticket.get("tipo_material", "DESCONOCIDO"),
                        float(ticket.get("peso_kg", 0)),
                        float(ticket.get("monto_acreditado", 0)),
                        ticket.get("firma_ecdsa", "FALLBACK"),
                    ))
                    # Eliminamos el item procesado de Redis
                    await redis_client.lrem("cola_fallback_saldos_pendientes", 1, item_raw)
                    promovidos += 1

                    # Si MongoDB esta vivo, actualizamos el saldo incremental tambien
                    if mongo_vivo:
                        try:
                            monto = float(ticket.get("monto_acreditado", 0))
                            await mongo_db["PerfilesUsuario"].update_one(
                                {"id_usuario": ticket.get("id_usuario")},
                                {
                                    "$inc": {"balance_incentivos": Decimal128(Decimal(str(monto)))},
                                    "$set": {"ultima_actualizacion": datetime.now(timezone.utc)}
                                }
                            )
                        except Exception:
                            pass  # Redis->Cassandra es lo critico; Mongo es bonus

                except Exception as e:
                    errores += 1
                    print(f"[Q9-CAMINO2] Error procesando ticket: {e}")

            return {
                "id_usuario": id_usuario,
                "estado": "SUCCESS",
                "camino_ejecutado": "CAMINO 2: Redis a Cassandra",
                "mensaje": f"{promovidos} depositos promovidos de Redis al ledger inmutable de Cassandra.",
                "metricas": {
                    "tickets_promovidos": promovidos,
                    "errores": errores,
                    "saldo_ledger_cassandra": 0.0,
                    "saldo_vivo_mongodb": 0.0,
                    "discrepancia_detectada": 0.0,
                    "items_restantes_en_redis": await redis_client.llen("cola_fallback_saldos_pendientes")
                },
                "estado_motores": {
                    "cassandra": "disponible" if cassandra_session else "no disponible",
                    "mongodb": "disponible" if mongo_vivo else "no disponible",
                    "redis": "disponible" if redis_vivo else "no disponible"
                }
            }


    # =========================================================================
    # CAMINO 3: Redis → MongoDB
    # Cassandra no responde. Promovemos los tickets de Redis a MongoDB
    # para aumentar su durabilidad mientras Cassandra vuelve.
    # =========================================================================
    if redis_vivo and mongo_vivo:
        items_redis = await redis_client.lrange("cola_fallback_saldos_pendientes", 0, -1)
        promovidos = 0
        for item_raw in items_redis:
            try:
                ticket = json.loads(item_raw)
                if ticket.get("id_usuario") != id_usuario:
                    continue
                ticket["estado_compensacion"] = "PROMOVIDO_A_MONGO_DESDE_REDIS"
                ticket["timestamp_promocion"] = datetime.now(timezone.utc).isoformat()
                await mongo_db["Q5_Fallback_Cassandra"].insert_one(ticket)
                await redis_client.lrem("cola_fallback_saldos_pendientes", 1, item_raw)
                promovidos += 1
            except Exception as e:
                print(f"[Q9-CAMINO3] Error moviendo ticket Redis→Mongo: {e}")

        return {
            "id_usuario": id_usuario,
            "estado": "DEGRADADO",
            "camino_ejecutado": "CAMINO 3: Redis a MongoDB (Durabilidad Intermedia)",
            "mensaje": "Cassandra no disponible. Tickets movidos de RAM (Redis) a Disco (MongoDB) para mayor durabilidad. Ejecutar Q9 nuevamente al restaurar Cassandra.",
            "metricas": {
                "tickets_promovidos": promovidos,
                "errores": 0,
                "saldo_ledger_cassandra": 0.0,
                "saldo_vivo_mongodb": 0.0,
                "discrepancia_detectada": 0.0,
                "items_restantes_en_redis": await redis_client.llen("cola_fallback_saldos_pendientes") if redis_vivo else 0
            },
            "estado_motores": {
                "cassandra": "disponible" if cassandra_session else "no disponible",
                "mongodb": "disponible" if mongo_vivo else "no disponible",
                "redis": "disponible" if redis_vivo else "no disponible"
            }
        }

    # =========================================================================
    # SIN CAMINO POSIBLE - Reportamos estado de cada motor
    # =========================================================================
    return {
        "id_usuario": id_usuario,
        "estado": "ERROR",
        "camino_ejecutado": "NINGUNO",
        "mensaje": "No fue posible ejecutar ninguna operacion de reconciliacion. Levante al menos Cassandra + Mongo o Mongo + Redis.",
        "metricas": {
            "tickets_promovidos": 0,
            "errores": 0,
            "saldo_ledger_cassandra": 0.0,
            "saldo_vivo_mongodb": 0.0,
            "discrepancia_detectada": 0.0,
            "items_restantes_en_redis": 0
        },
        "estado_motores": {
            "cassandra": "disponible" if cassandra_session else "no disponible",
            "mongodb": "disponible" if mongo_vivo else "no disponible",
            "redis": "disponible" if redis_vivo else "no disponible"
        }
    }
