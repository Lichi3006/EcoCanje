from fastapi import APIRouter
from database import db_clients

router = APIRouter(prefix="/telemetria", tags=["Dominio: Telemetría IoT (Cassandra)"])

# =========================================================================
# PATRONES DE CASSANDRA: Historial de estado y lecturas del borde
# =========================================================================
@router.post("/eventos")
async def registrar_evento_borde():
    """
    Ruta designada para interceptar el tráfico de los simuladores IoT y 
    almacenarlos en las particiones de Cassandra.
    """
    sesion_cassandra = db_clients["cassandra_session"]
    
    # Espacio reservado para la ejecución de consultas CQL por parte del alumno...
    # sesion_cassandra.execute("INSERT INTO ...")
    
    return {
        "estado": "Pendiente de programación",
        "mensaje": "Aquí el sistema reportará la escritura en Cassandra."
    }
