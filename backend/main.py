from fastapi import FastAPI
from motor.motor_asyncio import AsyncIOMotorClient
import redis.asyncio as redis
from cassandra.cluster import Cluster
import os

# Importamos nuestro diccionario de conexiones aislado y las rutas modulares
from database import db_clients
from rutas import terminales, telemetria, transacciones, perfiles

app = FastAPI(
    title="ECOCANJE API",
    description="Backend políglota para el sistema de reciclaje urbano",
    version="1.0.0"
)

# Unimos de forma limpia las subrutas al archivo maestro
app.include_router(terminales.router)
app.include_router(telemetria.router)
app.include_router(transacciones.router)
app.include_router(perfiles.router)

@app.on_event("startup")
async def startup_event():
    print("Iniciando infraestructura de datos de ECOCANJE...")
    
    mongo_uri = os.getenv("MONGO_URI", "mongodb://mongodb:27017/")
    db_clients["mongo_client"] = AsyncIOMotorClient(mongo_uri, serverSelectionTimeoutMS=2000)
    db_clients["mongodb"] = db_clients["mongo_client"]["ecocanje_db"]
    print("[OK] MongoDB Conectado")
    
    import redis.asyncio as redis_async
    redis_host = os.getenv("REDIS_HOST", "redis")
    db_clients["redis"] = redis_async.Redis(host=redis_host, port=6379, decode_responses=True)
    print("[OK] Redis Conectado")
    
    cassandra_hosts = os.getenv("CASSANDRA_HOSTS", "cassandra").split(",")
    try:
        db_clients["cassandra_cluster"] = Cluster(contact_points=cassandra_hosts)
        session = db_clients["cassandra_cluster"].connect()
        # Conectar los cables: Nos aseguramos de que el keyspace exista antes de arrancar
        session.execute("CREATE KEYSPACE IF NOT EXISTS ecocanje_ks WITH replication = {'class':'SimpleStrategy', 'replication_factor' : 1};")
        session.set_keyspace("ecocanje_ks")
        
        # Creamos las tablas si no existen (para que el edge pueda sincronizar sin depender del seed)
        session.execute("""
        CREATE TABLE IF NOT EXISTS depositos_ledger (
            id_usuario text, timestamp timestamp, id_deposito text, id_terminal text,
            tipo_material text, peso_kg float, monto_acreditado float, firma_ecdsa text,
            PRIMARY KEY (id_usuario, timestamp)
        ) WITH CLUSTERING ORDER BY (timestamp DESC);
        """)
        session.execute("""
        CREATE TABLE IF NOT EXISTS eventos_terminales (
            id_terminal text, id_evento text, tipo_evento text, valor_numerico float, alerta_estado text, timestamp_local text,
            PRIMARY KEY (id_terminal, id_evento)
        );
        """)
        session.execute("""
        CREATE TABLE IF NOT EXISTS saturaciones_por_comuna (
            comuna int, fecha_dia text, hora_saturacion text, id_terminal text, nombre_nodo text, tipo_material text, nivel_porcentaje float,
            PRIMARY KEY (comuna, fecha_dia, hora_saturacion)
        ) WITH CLUSTERING ORDER BY (fecha_dia DESC, hora_saturacion DESC);
        """)
        
        db_clients["cassandra_session"] = session
        print("[OK] Cassandra Conectado (Keyspace: ecocanje_ks, Tablas verificadas)")
    except Exception as e:
        print(f"[ADVERTENCIA] Cassandra aún inicializando: {e}")

@app.on_event("shutdown")
async def shutdown_event():
    if "mongo_client" in db_clients:
        db_clients["mongo_client"].close()
    if "redis" in db_clients:
        await db_clients["redis"].close()
    if "cassandra_cluster" in db_clients:
        db_clients["cassandra_cluster"].shutdown()

# =========================================================================
# RUTAS DE CAOS (CHAOS ENGINEERING / FAULT INJECTION)
# =========================================================================

@app.post("/caos/{container_name}/{action}", tags=["Ingeniería del Caos"])
async def caos_control_contenedor(container_name: str, action: str):
    """
    Ruta para Ingeniería de Caos. Permite apagar (stop) o prender (start) 
    contenedores específicos (ej. ecocanje_mongodb, ecocanje_cassandra)
    usando el SDK de Docker, para demostrar tolerancia a fallos en vivo.
    """
    import docker
    try:
        client = docker.from_env()
        container = client.containers.get(container_name)
        if action == "stop":
            container.stop()
            return {"mensaje": f"Servicio {container_name} detenido exitosamente (simulación de caída)."}
        elif action == "start":
            container.start()
            return {"mensaje": f"Servicio {container_name} iniciado correctamente (recuperación)."}
        else:
            return {"error": "Acción no válida. Usa 'stop' o 'start'."}
    except Exception as e:
        return {"error": f"Fallo al intentar aplicar ingeniería de caos: {str(e)}"}

from fastapi.responses import HTMLResponse

from panel_backend import panel_router
app.include_router(panel_router)

@app.get("/health", tags=["Infraestructura"])
async def health_check():
    return {
        "status": "online",
        "drivers": {
            "mongodb": "mongodb" in db_clients,
            "redis": "redis" in db_clients,
            "cassandra": "cassandra_session" in db_clients
        }
    }

@app.post("/sistema/reset", tags=["Infraestructura"])
async def factory_reset():
    """
    Ruta de pánico para limpiar todas las bases de datos y plantar las semillas originales.
    Ejecuta el script de inyección original.
    """
    import subprocess
    import sys
    try:
        # Purgar Redis
        if "redis" in db_clients and db_clients["redis"]:
            await db_clients["redis"].flushall()
            
        # Purgar Cassandra
        if "cassandra_session" in db_clients and db_clients["cassandra_session"]:
            session = db_clients["cassandra_session"]
            session.execute("TRUNCATE ecocanje_ks.eventos_terminales;")
            session.execute("TRUNCATE ecocanje_ks.saturaciones_por_comuna;")
            session.execute("TRUNCATE ecocanje_ks.depositos_ledger;")
            
        # Purgar MongoDB
        if "mongodb" in db_clients and db_clients["mongodb"] is not None:
            db = db_clients["mongodb"]
            await db.NodosDeRecepcion.drop()
            await db.PerfilesUsuario.drop()
            await db.CatalogoMateriales.drop()
            
        # Correr seed.py para plantar datos base limpios
        resultado = subprocess.run([sys.executable, "seed.py"], capture_output=True, text=True)
        if resultado.returncode == 0:
            # Reiniciar contenedores Docker automáticamente
            mensajes_docker = []
            try:
                import docker
                client = docker.from_env()
                contenedores = ["ecocanje_mongodb", "ecocanje_redis", "ecocanje_cassandra", "ecocanje_edge"]
                for c_name in contenedores:
                    try:
                        container = client.containers.get(c_name)
                        if c_name == "ecocanje_cassandra":
                            container.stop()
                            container.start()
                        else:
                            container.restart()
                        mensajes_docker.append(f"{c_name} OK")
                    except Exception as ce:
                        mensajes_docker.append(f"{c_name} FALLO: {str(ce)}")
            except Exception as e:
                mensajes_docker.append(f"No se pudo conectar al socket de Docker: {str(e)}")

            return {
                "status": "SUCCESS", 
                "message": "Bases de datos purgadas y reconstruidas a estado semilla.",
                "docker_restarts": mensajes_docker
            }
        else:
            return {"status": "ERROR", "message": "Fallo al correr seed.py", "logs": resultado.stderr}
    except Exception as e:
        return {"status": "CRITICAL_ERROR", "message": str(e)}
