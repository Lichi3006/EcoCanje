from fastapi import APIRouter
from pydantic import BaseModel
from typing import List, Dict, Any
from database import db_clients

router = APIRouter(prefix="/terminales", tags=["Dominio: Nodos de Recepción (MongoDB)"])

# =========================================================================
# GESTIÓN DE LA API (Mi responsabilidad como tu ingeniero de backend)
# =========================================================================
# Esquemas alineados estrictamente al Documento de Diseño (Etapa 1 - Punto 5.1.1)

class GeoJSONPoint(BaseModel):
    type: str = "Point"
    coordinates: List[float]

class NodoDeRecepcion(BaseModel):
    id_nodo: str
    nombre: str
    comuna: int
    geolocalizacion: GeoJSONPoint
    direccion: Dict[str, Any]
    franjas_operativas: List[Dict[str, Any]] = []
    terminales_fisicas: List[Dict[str, Any]] = []

@router.post("/inyectar-prueba")
async def inyectar_nodo_de_prueba(nodo: NodoDeRecepcion):
    """
    Ruta auxiliar para inyectar datos de prueba respetando el esquema de la Etapa 1.
    """
    diccionario_crudo = nodo.model_dump()
    coleccion = db_clients["mongodb"]["NodosDeRecepcion"]
    resultado = await coleccion.insert_one(diccionario_crudo)
    return {"mensaje": "Nodo de recepción inyectado exitosamente", "id": str(resultado.inserted_id)}

async def busqueda_mongo(consulta, mensaje: str, proyeccion = None):
    coleccion_mongo = db_clients["mongodb"]["NodosDeRecepcion"]

    # Si nos pasan proyección la usamos, sino buscamos todo
    if proyeccion:
        cursor = coleccion_mongo.find(consulta, proyeccion)
    else:
        cursor = coleccion_mongo.find(consulta)

    ubicacionesEncontradas = []

    async for doc in cursor: 
        ubicacionesEncontradas.append(doc)

    return {
        "mensaje": mensaje,
        "total_encontrados": len(ubicacionesEncontradas),
        "resultados": ubicacionesEncontradas
    }

# =========================================================================
# RUTAS DE AUDITORÍA
# =========================================================================

@router.get("/todas")
async def listar_todas():
    """
    Lista todos los nodos de recepción y sus terminales.
    Útil para auditoría y para conocer los IDs disponibles.
    """
    return await busqueda_mongo(
        consulta={},
        proyeccion={"_id": 0},
        mensaje="Diccionario completo de nodos de recepción y terminales."
    )

# =========================================================================
# PATRÓN Q1
# =========================================================================

@router.get("/cercanas")
async def Q1_buscar_terminales_cercanas( longitud: float, latitud: float):
    """
    Patrón Q1: Búsqueda geoespacial de terminales cercanas (Paginación Espacial).
    
    Nota Arquitectónica de Integración (Frontend-Backend):
    Esta ruta está diseñada para resolver consultas espaciales en tiempo real. 
    Se espera que la aplicación móvil cliente actualice las coordenadas bajo 
    demanda, enviando el GPS físico de la persona, o bien, capturando la 
    ubicación (X,Y) del centro de la pantalla mientras el usuario arrastra 
    el dedo por el mapa de manera libre. Se delega en el frontend el uso de 
    temporizadores (Debouncing) en milisegundos para evitar la saturación 
    de la red durante los arrastres prolongados.
    """

    consulta = {
        "geolocalizacion": {
            "$nearSphere": {
                "$geometry": {
                    "type": "Point",
                    "coordinates": [longitud, latitud]
                },
                "$maxDistance": 1500
            }
        }
    }
    
    proyeccion = {
        "_id": 0, 
        "nombre": 1,
        "geolocalizacion.coordinates": 1,
        "direccion": 1,
        "franjas_operativas": 1,
        "terminales_fisicas.id_terminal": 1,
        "terminales_fisicas.materiales_autorizados": 1
    }
    
    return await busqueda_mongo(consulta=consulta, proyeccion=proyeccion, mensaje="La consulta geoespacial fue exitosa")

# =========================================================================
# PATRÓN Q2
# =========================================================================

@router.get("/materiales/{id_nodo}")
async def Q2_consultar_materiales_autorizados(id_nodo: str):
    """
    Patrón Q2: Consulta de Materiales Autorizados por Nodo (Búsqueda Transaccional).

    Nota Arquitectónica (Motor de Extracción):
    Esta ruta está diseñada para la validación de negocio en tiempo real.
    Cuando el usuario selecciona un Punto Verde en el mapa o interactúa con él, 
    la aplicación móvil necesita conocer instantáneamente qué materiales físicos 
    (PET, Vidrio, Cartón, etc.) admite esa terminal específica para habilitar 
    o bloquear la interfaz de usuario.
    
    A nivel de motor de datos, la extracción se apoya en un índice B-Tree 
    alfanumérico sobre el campo `id_nodo`. Gracias a la arquitectura BSON 
    desnormalizada (embebida), se evita instanciar un pipeline analítico 
    ($lookup) en favor de un comando operacional atómico (.find). Se aplica 
    una proyección dura en memoria para transferir por red estrictamente el 
    vector de materiales y el estado operativo, bloqueando la filtración del 
    metadato físico de infraestructura (`_id: 0`).
    """

    consulta = {
        "id_nodo": id_nodo
    }
    
    proyeccion = {
        "_id": 0,
        "id_nodo": 1,
        "nombre": 1,
        "terminales_fisicas.id_terminal": 1,
        "terminales_fisicas.estado_operativo": 1,
        "terminales_fisicas.materiales_autorizados": 1
    }
    
    return await busqueda_mongo(consulta=consulta, proyeccion=proyeccion, mensaje="La consulta de materiales autorizados fue exitosa")

# =========================================================================
# PATRÓN Q3
# =========================================================================

@router.get("/capacidad/{id_terminal}")
async def Q3_consultar_capacidad(id_terminal: str):
    """
    Patrón Q3: Capacidad en Tiempo Real (Redis + MongoDB)
    Combina metadata estática de MongoDB con memoria efímera de Redis para
    mostrar un semáforo de estado de la terminal.
    """
    from fastapi import HTTPException
    
    coleccion = db_clients["mongodb"]["NodosDeRecepcion"]
    nodo = await coleccion.find_one(
        {"terminales_fisicas.id_terminal": id_terminal},
        {
            "_id": 0, 
            "id_nodo": 1, 
            "nombre": 1, 
            "terminales_fisicas": {"$elemMatch": {"id_terminal": id_terminal}}
        }
    )
    
    if not nodo or not nodo.get("terminales_fisicas"):
        raise HTTPException(status_code=404, detail="Terminal no encontrada")
        
    terminal = nodo["terminales_fisicas"][0]
    
    redis_client = db_clients.get("redis")
    capacidad_viva = None
    if redis_client:
        capacidad_viva = await redis_client.hgetall(f"cap:terminal:{id_terminal}")
        
    if not capacidad_viva:
        capacidad_viva = {
            "nivel_actual": "0.0",
            "capacidad_max": "250.0",
            "estado_semaforo": "Verde",
            "timestamp_update": "Sin telemetría reciente"
        }
        
    return {
        "mensaje": "Consulta de capacidad en tiempo real exitosa",
        "id_nodo": nodo.get("id_nodo"),
        "nombre_nodo": nodo.get("nombre"),
        "id_terminal": terminal.get("id_terminal"),
        "estado_hardware": terminal.get("estado_operativo"),
        "estado_saturacion": capacidad_viva
    }
