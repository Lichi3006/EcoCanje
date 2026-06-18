import asyncio
from motor.motor_asyncio import AsyncIOMotorClient
import pymongo
import redis
import os

# URI de conexión para red de contenedores Docker
MONGO_URI = os.getenv("MONGO_URI", "mongodb://mongodb:27017/")
REDIS_HOST = os.getenv("REDIS_HOST", "redis")
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
                    "nivel_actual_kg": 120.50,
                    "timestamp_update": 1779951050,
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
                    "nivel_actual_kg": 285.0,
                    "timestamp_update": 1779951050,
                    "version_firmware": "v2.4.1",
                    "materiales_autorizados": ["MAT-CAR-003", "MAT-VID-004"] # Cartón y Vidrio
                }
            ]
        }
    ]

    print("Inyectando semillas de Puntos Verdes...")
    resultado = await coleccion.insert_many(nodos_falsos)
    print(f"¡Éxito! Se insertaron {len(resultado.inserted_ids)} nodos de recepción.")

    print("Conectando y sembrando datos en Redis...")
    try:
        r = redis.Redis(host=REDIS_HOST, port=6379, decode_responses=True)
        r.hset("cap:terminal:TERM-CABA-005", mapping={
            "nivel_actual": "120.50", "capacidad_max": "250.0", "estado_semaforo": "Verde", "timestamp_update": "1779951050"
        })
        r.hset("cap:terminal:TERM-CABA-012", mapping={
            "nivel_actual": "285.0", "capacidad_max": "300.0", "estado_semaforo": "Rojo", "timestamp_update": "1779951050"
        })
        print("[OK] Redis sembrado exitosamente.")
    except Exception as e:
        print(f"[ERROR] No se pudo conectar a Redis para sembrar: {e}")

    print("Sembrando Perfil de Usuario de prueba en MongoDB...")
    coleccion_perfiles = db["PerfilesUsuario"]
    await coleccion_perfiles.drop()
    await coleccion_perfiles.create_index("id_usuario", unique=True)
    from bson.decimal128 import Decimal128
    from decimal import Decimal
    from datetime import datetime, timezone
    
    await coleccion_perfiles.insert_many([
        {
            "id_usuario": "USR-1186420",
            "nombre_titular": "Lisandro Forgione",
            "cvu": "0000003100010000000001",
            "balance_incentivos": Decimal128(Decimal("1450.00")),
            "ultima_actualizacion": datetime.now(timezone.utc)
        },
        {
            "id_usuario": "USR-1190410",
            "nombre_titular": "Fernando Estevez",
            "cvu": "0000003100010000000002",
            "balance_incentivos": Decimal128(Decimal("0.00")),
            "ultima_actualizacion": datetime.now(timezone.utc)
        },
        {
            "id_usuario": "USR-1189034",
            "nombre_titular": "Delfina Garcia",
            "cvu": "0000003100010000000003",
            "balance_incentivos": Decimal128(Decimal("0.00")),
            "ultima_actualizacion": datetime.now(timezone.utc)
        },
        {
            "id_usuario": "USR-1201818",
            "nombre_titular": "Miguel Illanes",
            "cvu": "0000003100010000000004",
            "balance_incentivos": Decimal128(Decimal("0.00")),
            "ultima_actualizacion": datetime.now(timezone.utc)
        },
        {
            "id_usuario": "USR-1184761",
            "nombre_titular": "Joaquin Riusech",
            "cvu": "0000003100010000000005",
            "balance_incentivos": Decimal128(Decimal("0.00")),
            "ultima_actualizacion": datetime.now(timezone.utc)
        },
        {
            "id_usuario": "USR-PROFESOR",
            "nombre_titular": "Fernandez Alfonso Martin",
            "cvu": "0000003100010000000006",
            "balance_incentivos": Decimal128(Decimal("0.00")),
            "ultima_actualizacion": datetime.now(timezone.utc)
        }
    ])
    print("[OK] PerfilesUsuario creados para el equipo.")

    print("Sembrando Tarifas Base de Materiales en MongoDB...")
    coleccion_tarifas = db["TarifasMateriales"]
    await coleccion_tarifas.drop()
    await coleccion_tarifas.create_index("material", unique=True)
    await coleccion_tarifas.insert_many([
        {"material": "PET", "precio_kg": 150.0, "ultima_actualizacion": datetime.now(timezone.utc)},
        {"material": "VIDRIO", "precio_kg": 80.0, "ultima_actualizacion": datetime.now(timezone.utc)},
        {"material": "ALUMINIO", "precio_kg": 450.0, "ultima_actualizacion": datetime.now(timezone.utc)},
        {"material": "CARTON", "precio_kg": 50.0, "ultima_actualizacion": datetime.now(timezone.utc)}
    ])
    print("[OK] TarifasMateriales creadas en base de datos.")

    # Sembrando Token QR de prueba en Redis para el Patrón Q4
    print("Sembrando Token QR efímero de prueba en Redis (Q4)...")
    try:
        r_q4 = redis.Redis(host=REDIS_HOST, port=6379, decode_responses=True)
        r_q4.hset("handshake:QR-DEMO-001", mapping={
            "id_tx": "tx-demo-01",
            "id_terminal": "TERM-CABA-005",
            "material": "PET",
            "peso_gramos": "1500",
            "monto_liquidacion": "225.00",
            "firma": "a1b2c3d4e5f6demo"
        })
        # TTL de 10 minutos para que no expire durante la demo
        r_q4.expire("handshake:QR-DEMO-001", 600)
        print("[OK] Token QR de demo sembrado (handshake:QR-DEMO-001).")
    except Exception as e:
        print(f"[ERROR] No se pudo sembrar token QR en Redis: {e}")

    print("Datos maestros listos. Los datos de Cassandra (telemetría, saturaciones, ledger)")
    print("se alimentan orgánicamente desde la terminal IoT via sync_daemon → backend → Cassandra.")

if __name__ == "__main__":
    asyncio.run(sembrar_base_de_datos())
