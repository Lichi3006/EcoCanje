from fastapi import FastAPI
from motor.motor_asyncio import AsyncIOMotorClient
import redis.asyncio as redis
from cassandra.cluster import Cluster
import os

# Importamos nuestro diccionario de conexiones aislado y las rutas modulares
from database import db_clients
from rutas import terminales, telemetria

app = FastAPI(
    title="ECOCANJE API",
    description="Backend políglota para el sistema de reciclaje urbano",
    version="1.0.0"
)

# Unimos de forma limpia las subrutas al archivo maestro
app.include_router(terminales.router)
app.include_router(telemetria.router)

@app.on_event("startup")
async def startup_event():
    print("Iniciando infraestructura de datos de ECOCANJE...")
    
    mongo_uri = os.getenv("MONGO_URI", "mongodb://mongodb:27017/")
    db_clients["mongo_client"] = AsyncIOMotorClient(mongo_uri)
    db_clients["mongodb"] = db_clients["mongo_client"]["ecocanje_db"]
    print("[OK] MongoDB Conectado")
    
    redis_host = os.getenv("REDIS_HOST", "redis")
    db_clients["redis"] = redis.Redis(host=redis_host, port=6379, decode_responses=True)
    print("[OK] Redis Conectado")
    
    cassandra_hosts = os.getenv("CASSANDRA_HOSTS", "cassandra").split(",")
    db_clients["cassandra_cluster"] = Cluster(contact_points=cassandra_hosts)
    try:
        db_clients["cassandra_session"] = db_clients["cassandra_cluster"].connect()
        print("[OK] Cassandra Conectado")
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
