from fastapi import APIRouter, HTTPException
from typing import List
from pydantic import BaseModel
from database import db_clients, get_cassandra_session

router = APIRouter(prefix="/telemetria", tags=["Dominio: Telemetría IoT (Cassandra)"])

class EventoTelemetria(BaseModel):
    id_evento: str
    id_terminal: str
    tipo_evento: str
    valor_numerico: float
    alerta_estado: str
    timestamp_local: str

# =========================================================================
# PATRÓN Q8: Ingesta de Telemetría (Edge a Cloud)
# =========================================================================
@router.post("/eventos")
async def Q8_ingesta_telemetria_iot(eventos: List[EventoTelemetria]):
    """
    Patrón Q8: Ingesta y Consulta de Telemetría IoT y Eventos de Terminal.
    Recibe el lote (batch) de eventos del daemon local de la terminal (SQLite)
    y los almacena secuencialmente en Cassandra.
    """
    try:
        sesion_cassandra = get_cassandra_session()
    except ConnectionError:
        sesion_cassandra = None
    try:
        sesion_cassandra = get_cassandra_session()
    except ConnectionError:
        sesion_cassandra = None

    mongo_db = db_clients.get("mongodb")
    redis_client = db_clients.get("redis")

    eventos_insertados = 0
    saturaciones_detectadas = 0
    
    for evento in eventos:
        try:
            # 1. Inserción estándar de telemetría global (Q8)
            if sesion_cassandra:
                cql_q8 = """
                    INSERT INTO eventos_terminales 
                    (id_terminal, id_evento, tipo_evento, valor_numerico, alerta_estado, timestamp_local) 
                    VALUES (%s, %s, %s, %s, %s, %s)
                """
                sesion_cassandra.execute_async(cql_q8, (
                    evento.id_terminal, evento.id_evento, evento.tipo_evento, 
                    evento.valor_numerico, evento.alerta_estado, evento.timestamp_local
                ))
                eventos_insertados += 1
            else:
                print(f"[FALLBACK Q8] Cassandra caída. Omitiendo guardado histórico de evento {evento.id_evento}.")
            
            # -------------------------------------------------------------
            # INTEGRACIÓN CON PATRÓN Q3 (Semáforo de Capacidad en Redis)
            # -------------------------------------------------------------
            if evento.tipo_evento == "SATURACION_CONTENEDOR_PORCENTAJE" and redis_client:
                color = "Rojo" if evento.alerta_estado == "CRITICAL" else ("Amarillo" if evento.alerta_estado == "WARNING" else "Verde")
                capacidad_maxima = 250.0
                nivel_en_kg = (evento.valor_numerico / 100.0) * capacidad_maxima
                await redis_client.hset(f"cap:terminal:{evento.id_terminal}", mapping={
                    "nivel_actual": str(round(nivel_en_kg, 2)),
                    "capacidad_max": str(capacidad_maxima),
                    "estado_semaforo": color,
                    "timestamp_update": evento.timestamp_local
                })

            # -------------------------------------------------------------
            # INTEGRACIÓN CON PATRÓN Q7 (Enriquecimiento en tiempo de ingesta)
            # -------------------------------------------------------------
            # Si el evento es una saturación crítica del tacho, lo enviamos a 
            # la tabla analítica particionada por comunas para el Patrón Q7.
            if evento.tipo_evento == "SATURACION_CONTENEDOR_PORCENTAJE" and evento.alerta_estado == "CRITICAL":
                if mongo_db is not None:
                    # Enriquecemos la telemetría cruda buscando los datos geográficos en MongoDB
                    coleccion_nodos = mongo_db["NodosDeRecepcion"]
                    nodo = await coleccion_nodos.find_one({"terminales_fisicas.id_terminal": evento.id_terminal})
                    
                    if nodo:
                        comuna = nodo.get("comuna", 0)
                        nombre_nodo = nodo.get("nombre", "Desconocido")
                        
                        # Extraemos fecha y hora del timestamp local (Epoch)
                        from datetime import datetime
                        dt = datetime.fromtimestamp(int(evento.timestamp_local))
                        fecha_dia = dt.strftime('%Y-%m-%d')
                        hora_saturacion = dt.strftime('%H:%M:%S')
                        
                        cql_q7 = """
                            INSERT INTO saturaciones_por_comuna 
                            (comuna, fecha_dia, hora_saturacion, id_terminal, nombre_nodo, tipo_material, nivel_porcentaje) 
                            VALUES (%s, %s, %s, %s, %s, %s, %s)
                        """
                        cassandra_q7_ok = False
                        if sesion_cassandra:
                            try:
                                sesion_cassandra.execute(cql_q7, (
                                    comuna, fecha_dia, hora_saturacion, evento.id_terminal, nombre_nodo, "RECICLABLES", evento.valor_numerico
                                ))
                                saturaciones_detectadas += 1
                                cassandra_q7_ok = True
                            except Exception as e_cass:
                                print(f"[FALLBACK Q7] Cassandra falló al ingestarlo: {e_cass}")
                                
                        if not cassandra_q7_ok:
                            print("[FALLBACK Q7] Cassandra caída, guardando saturación pendiente en Mongo...")
                            await mongo_db["Q7_Fallback_Cassandra"].insert_one({
                                "comuna": comuna, "fecha_dia": fecha_dia, "hora_saturacion": hora_saturacion, 
                                "id_terminal": evento.id_terminal, "nombre_nodo": nombre_nodo, 
                                "tipo_material": "RECICLABLES", "nivel_porcentaje": evento.valor_numerico
                            })
                            saturaciones_detectadas += 1
        except Exception as e:
            print(f"[ERROR CASSANDRA] Fallo ingestando evento {evento.id_evento}: {e}")
            
    return {
        "estado": "APROBADO",
        "mensaje": "Lote de telemetría asíncrona procesado exitosamente.",
        "eventos_procesados_q8": eventos_insertados,
        "saturaciones_enriquecidas_q7": saturaciones_detectadas
    }

# =========================================================================
# PATRÓN Q7: Consulta Analítica de Saturaciones por Comuna
# =========================================================================
@router.get("/saturaciones/comuna/{numero_comuna}")
async def Q7_deteccion_saturaciones_por_comuna(numero_comuna: int, fecha_desde: str, fecha_hasta: str):
    """
    Patrón Q7: Detección de Nodos con Saturación Frecuente.
    Realiza un análisis histórico de telemetría cruzada por comuna para planificar
    el recorrido logístico de vaciado de los camiones en la ciudad.
    (Ejemplo formato de fecha: '2026-05-01')
    """
    try:
        try:
            sesion_cassandra = get_cassandra_session()
        except ConnectionError:
            sesion_cassandra = None
            
        if not sesion_cassandra:
            raise Exception("Servicio de Cassandra no disponible al iniciar Q7")
        # Primero revisamos si hay datos pendientes en Mongo (Fallback) y los subimos a Cassandra
        mongo_db = db_clients.get("mongodb")
        if mongo_db is not None:
            pendientes = await mongo_db["Q7_Fallback_Cassandra"].find({"comuna": numero_comuna}).to_list(length=None)
            for p in pendientes:
                cql_insert = """
                    INSERT INTO saturaciones_por_comuna 
                    (comuna, fecha_dia, hora_saturacion, id_terminal, nombre_nodo, tipo_material, nivel_porcentaje) 
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                """
                sesion_cassandra.execute(cql_insert, (
                    p["comuna"], p["fecha_dia"], p["hora_saturacion"], 
                    p["id_terminal"], p["nombre_nodo"], p["tipo_material"], p["nivel_porcentaje"]
                ))
                await mongo_db["Q7_Fallback_Cassandra"].delete_one({"_id": p["_id"]})
            if pendientes:
                print(f"[RECUPERACION Q7] Se subieron {len(pendientes)} registros pendientes desde Mongo hacia Cassandra.")

        # Consulta CQL para series temporales. 
        # Utiliza la partition key (comuna) y clustering keys (fecha_dia).
        cql = """
            SELECT id_terminal, nombre_nodo, tipo_material, nivel_porcentaje, hora_saturacion, fecha_dia 
            FROM saturaciones_por_comuna 
            WHERE comuna = %s AND fecha_dia >= %s AND fecha_dia <= %s
        """
        # Las lecturas en Cassandra son síncronas nativamente a través del driver
        resultados = sesion_cassandra.execute(cql, (numero_comuna, fecha_desde, fecha_hasta))
        
        # Parseo simple de los registros columnares a JSON
        lista_resultados = []
        for fila in resultados:
            lista_resultados.append({
                "id_terminal": fila.id_terminal,
                "nombre_nodo": fila.nombre_nodo,
                "tipo_material": fila.tipo_material,
                "nivel_porcentaje": fila.nivel_porcentaje,
                "hora_saturacion": fila.hora_saturacion,
                "fecha_dia": fila.fecha_dia
            })
            
        return {
            "mensaje": f"Análisis de saturaciones para comuna {numero_comuna} ejecutado con éxito.",
            "filtro_temporal": f"{fecha_desde} a {fecha_hasta}",
            "total_incidentes": len(lista_resultados),
            "resultados": lista_resultados
        }
    except Exception as e:
        db_clients["cassandra_session"] = None  # Invalida la sesion vieja para forzar reconexion
        print(f"[FALLBACK Q7] Cassandra fallo ({e}). Consultando semaforos en Redis...")
        redis_client = db_clients.get("redis")
        if not redis_client:
            raise HTTPException(status_code=500, detail=f"Error ejecutando analitica en Cassandra y sin Redis: {e}")
            
        try:
            lista_resultados = []
            async for key in redis_client.scan_iter("cap:terminal:*"):
                datos = await redis_client.hgetall(key)
                if datos and datos.get("estado_semaforo") in ["Rojo", "CRITICAL"]:
                    lista_resultados.append({
                        "id_terminal": key.replace("cap:terminal:", ""),
                        "nombre_nodo": "Fallback Redis (Vivo)",
                        "tipo_material": "N/A",
                        "nivel_porcentaje": float(datos.get("nivel_actual", 0)),
                        "hora_saturacion": "EN VIVO",
                        "fecha_dia": "EN VIVO"
                    })
            return {
                "mensaje": "FALLBACK ACTIVADO: Cassandra offline. Mostrando saturaciones vivas en RAM (Redis).",
                "filtro_temporal": "Tiempo Real",
                "total_incidentes": len(lista_resultados),
                "resultados": lista_resultados
            }
        except Exception as fallback_error:
            raise HTTPException(status_code=500, detail=f"Caída catastrófica (Cassandra y Redis out): {fallback_error}")
# =========================================================================
# PATRÓN Q8 (Lectura): Consulta de Telemetría por Terminal
# =========================================================================
@router.get("/eventos/{id_terminal}")
async def Q8_consulta_telemetria_terminal(id_terminal: str):
    """
    Patrón Q8 (Lectura Cloud): Consulta los eventos de telemetría IoT
    almacenados en Cassandra para una terminal específica.
    """
    try:
        sesion_cassandra = get_cassandra_session()
    except ConnectionError as e:
        raise HTTPException(status_code=503, detail=str(e))
    if not sesion_cassandra:
        raise HTTPException(status_code=503, detail="Servicio de Cassandra no disponible")
        
    try:
        cql = """
            SELECT id_terminal, id_evento, tipo_evento, valor_numerico, alerta_estado, timestamp_local 
            FROM eventos_terminales 
            WHERE id_terminal = %s
        """
        resultados = sesion_cassandra.execute(cql, (id_terminal,))
        
        lista_resultados = []
        for fila in resultados:
            lista_resultados.append({
                "id_terminal": fila.id_terminal,
                "id_evento": fila.id_evento,
                "tipo_evento": fila.tipo_evento,
                "valor_numerico": fila.valor_numerico,
                "alerta_estado": fila.alerta_estado,
                "timestamp_local": fila.timestamp_local
            })
            
        return {
            "mensaje": f"Telemetría de terminal {id_terminal} consultada con éxito.",
            "total_eventos": len(lista_resultados),
            "resultados": lista_resultados
        }
    except Exception as e:
        db_clients["cassandra_session"] = None  # Invalida sesion para forzar reconexion
        raise HTTPException(status_code=500, detail=f"Error consultando telemetria en Cassandra: {e}")

