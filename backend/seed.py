import asyncio
from motor.motor_asyncio import AsyncIOMotorClient
import pymongo

# URI de conexión para red de contenedores Docker
MONGO_URI = "mongodb://mongodb:27017/"
DB_NAME = "ecocanje_db"

async def sembrar_base_de_datos():
    print("Conectando a MongoDB...")
    cliente = AsyncIOMotorClient(MONGO_URI)
    db = cliente[DB_NAME]
    coleccion = db["NodosDeRecepcion"]

    print("Limpiando colección anterior...")
    await coleccion.drop()

    print("Creando índice 2dsphere para permitir búsquedas espaciales...")
    # MongoDB exige este índice para que el Patrón Q1 ($nearSphere) funcione
    await coleccion.create_index([("geolocalizacion", pymongo.GEOSPHERE)])
    
    print("Creando índice B-Tree para búsquedas por ID (Patrón Q2)...")
    await coleccion.create_index("id_nodo", unique=True)

    nodos_falsos = [
        {
            "id_nodo": "NODE-CABA-001",
            "nombre": "Punto Verde Plaza Almagro",
            "comuna": 5,
            "geolocalizacion": {
                "type": "Point",
                "coordinates": [-58.4208, -34.6044] # Longitud, Latitud
            },
            "direccion": {
                "calle": "Sarmiento",
                "altura": 3900,
                "barrio": "Almagro"
            },
            "franjas_operativas": [
                { "dias": "Lunes a Viernes", "horario_apertura": "08:00", "horario_cierre": "18:00" }
            ],
            "terminales_fisicas": [
                {
                    "id_terminal": "TERM-CABA-005",
                    "estado_operativo": "Activa",
                    "capacidad_maxima_kg": 250.0,
                    "version_firmware": "v2.4.1",
                    "materiales_autorizados": ["MAT-PET-001", "MAT-ALU-002"]
                }
            ]
        },
        {
            "id_nodo": "NODE-CABA-002",
            "nombre": "Punto Verde Parque Centenario",
            "comuna": 6,
            "geolocalizacion": {
                "type": "Point",
                "coordinates": [-58.4356, -34.6061] # Longitud, Latitud
            },
            "direccion": {
                "calle": "Av. Díaz Vélez",
                "altura": 4800,
                "barrio": "Caballito"
            },
            "franjas_operativas": [
                { "dias": "Lunes a Viernes", "horario_apertura": "08:00", "horario_cierre": "20:00" }
            ],
            "terminales_fisicas": [
                {
                    "id_terminal": "TERM-CABA-012",
                    "estado_operativo": "Activa",
                    "capacidad_maxima_kg": 300.0,
                    "version_firmware": "v2.4.1",
                    "materiales_autorizados": ["MAT-CAR-003", "MAT-VID-004"] # Cartón y Vidrio
                }
            ]
        }
    ]

    print("Inyectando semillas de Puntos Verdes...")
    resultado = await coleccion.insert_many(nodos_falsos)
    
    print(f"¡Éxito! Se insertaron {len(resultado.inserted_ids)} nodos de recepción.")
    print("La base de datos está lista para ser consultada por FastAPI.")

if __name__ == "__main__":
    asyncio.run(sembrar_base_de_datos())
