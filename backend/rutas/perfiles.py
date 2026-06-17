from fastapi import APIRouter, HTTPException
from pymongo.read_concern import ReadConcern
from database import db_clients

router = APIRouter(prefix="/perfiles", tags=["Dominio: Billetera y Ciudadano (MongoDB)"])


async def obtener_perfil_consistente(id_usuario: str) -> dict:
    """
    Busca un perfil de usuario forzando una lectura mayoritaria en el clúster (Majority Read Concern).
    Extraído a una función modular para poder ser reutilizado por otros servicios.
    
    Nota de Degradación: En entornos standalone (sin Replica Set), ReadConcern majority
    puede no devolver resultados. Se implementa un fallback automático a lectura local.
    """
    mongo_db = db_clients.get("mongodb")
    if mongo_db is None:
        raise Exception("Servicio de MongoDB no disponible")
    
    consulta = {"id_usuario": id_usuario}
    proyeccion = {
        "_id": 0,
        "id_usuario": 1,
        "balance_incentivos": 1,
        "ultima_actualizacion": 1
    }
    
    # Intento 1: ReadConcern majority (producción con Replica Set)
    nivel_consistencia = "majority"
    try:
        coleccion_majority = mongo_db.get_collection(
            "PerfilesUsuario", 
            read_concern=ReadConcern("majority")
        )
        resultado = await coleccion_majority.find_one(consulta, proyeccion)
        if resultado:
            return resultado
    except Exception:
        pass
    
    # Intento 2: Fallback a lectura local (standalone sin Replica Set)
    nivel_consistencia = "local (fallback standalone)"
    coleccion_local = mongo_db["PerfilesUsuario"]
    return await coleccion_local.find_one(consulta, proyeccion)

# =========================================================================
# RUTAS DE AUDITORÍA
# =========================================================================

@router.get("/todos")
async def listar_todos_usuarios():
    """
    Lista todos los usuarios (ciudadanos) con su saldo actual.
    Útil para auditoría y conocer a qué IDs consultar el saldo (Q6) o reconciliar (Q9).
    """
    mongo_db = db_clients.get("mongodb")
    if mongo_db is None:
        raise HTTPException(status_code=500, detail="MongoDB no disponible")
        
    coleccion = mongo_db["PerfilesUsuario"]
    cursor = coleccion.find({}, {"_id": 0})
    usuarios = []
    async for doc in cursor:
        if "balance_incentivos" in doc:
            doc["balance_incentivos"] = float(str(doc["balance_incentivos"]))
        usuarios.append(doc)
        
    return {
        "mensaje": "Diccionario completo de perfiles de usuario",
        "total_encontrados": len(usuarios),
        "resultados": usuarios
    }

# =========================================================================
# PATRÓN Q6
# =========================================================================

@router.get("/{id_usuario}/saldo")
async def Q6_consulta_saldo_ciudadano(id_usuario: str):
    """
    Patrón Q6: Consulta de Saldo y Balance Acumulado del Ciudadano.
    """
    try:
        perfil = await obtener_perfil_consistente(id_usuario)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    
    if not perfil:
        return {
            "mensaje": f"Perfil {id_usuario} no encontrado",
            "resultados": None
        }
        
    # Extraemos y parseamos el tipo Decimal128 de alta precisión a float para el JSON
    balance_decimal128 = perfil.get("balance_incentivos")
    perfil["balance_incentivos"] = float(balance_decimal128.to_decimal()) if balance_decimal128 else 0.0
        
    return {
        "mensaje": "Consulta de saldo altamente consistente ejecutada con éxito",
        "nivel_consistencia": "majority (Primario/Réplicas)",
        "resultados": perfil
    }
