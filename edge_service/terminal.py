import sqlite3
import json
import time
import uuid
import random
from abc import ABC, abstractmethod
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives import hashes

# =====================================================================
# INDICE 1: INTERFACES (Contratos del Proceso de Desarrollo)
# =====================================================================

class IHardwareService(ABC):
    """Interfaz para el control de los componentes físicos de la RVM"""
    @abstractmethod
    def clasificar_material_optico(self) -> str:
        pass

    @abstractmethod
    def obtener_peso_neto(self) -> int:
        pass


class ICryptoService(ABC):
    """Interfaz para el manejo de la seguridad criptográfica asimétrica"""
    @abstractmethod
    def firmar_datos(self, datos_json: str) -> str:
        pass


class ILocalStorage(ABC):
    """Interfaz para la persistencia de datos local en el borde (Edge)"""
    @abstractmethod
    def guardar_deposito_offline(self, id_tx: str, terminal_id: str, material: str, peso_kg: float, monto: float, firma: str, timestamp: str) -> None:
        pass

    @abstractmethod
    def guardar_telemetria(self, id_evento: str, id_terminal: str, tipo_evento: str, valor_numerico: float, alerta_estado: str, timestamp: str) -> None:
        pass

    @abstractmethod
    def obtener_peso_acumulado_kg(self) -> float:
        pass


# =====================================================================
# INDICE 2: IMPLEMENTACIONES (Lógica del MVP)
# =====================================================================

class MockHardwareService(IHardwareService):
    """Implementación simulada del hardware (Fake de IA y Báscula)"""
    def clasificar_material_optico(self) -> str:
        # Simula la visión computacional autorizada según el caso
        return random.choice(["PET", "ALUM"])

    def obtener_peso_neto(self) -> int:
        # Retorna el peso de la balanza en gramos
        return random.randint(200, 3000)


class ECDSACryptoService(ICryptoService):
    """Implementación real de firmas ECDSA P-256 para el Edge"""
    def __init__(self):
        # Generación de la clave privada asimétrica local de la terminal
        self._private_key = ec.generate_private_key(ec.SECP256R1())

    def firmar_datos(self, datos_json: str) -> str:
        string_bytes = datos_json.encode('utf-8')
        signature = self._private_key.sign(string_bytes, ec.ECDSA(hashes.SHA256()))
        return signature.hex()


class SQLiteLocalStorage(ILocalStorage):
    """Implementación de persistencia local en SQLite con garantías ACID WAL"""
    def __init__(self, db_path: str = None):
        import os
        self.db_path = db_path or os.getenv("SQLITE_DB_PATH", "ecocanje_edge.db")
        self._configurar_entorno_wal()

    def _configurar_entorno_wal(self):
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            # [Requerimiento CAP/ACID] Activación del diario WAL contra cortes de energía
            cursor.execute("PRAGMA journal_mode=WAL;")
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS depositos_pendientes (
                    id_deposito TEXT PRIMARY KEY,
                    id_terminal TEXT NOT NULL,
                    tipo_material TEXT NOT NULL,
                    peso_kg REAL NOT NULL,
                    monto_calculado NUMERIC NOT NULL,
                    firma_ecdsa TEXT NOT NULL,
                    timestamp_local TEXT NOT NULL,
                    sincronizado INTEGER DEFAULT 0
                );
            """)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS telemetria_local (
                    id_evento TEXT PRIMARY KEY,
                    id_terminal TEXT NOT NULL,
                    tipo_evento TEXT NOT NULL,
                    valor_numerico REAL NOT NULL,
                    alerta_estado TEXT NOT NULL,
                    timestamp_local TEXT NOT NULL,
                    sincronizado INTEGER DEFAULT 0
                );
            """)
            conn.commit()

    def guardar_deposito_offline(self, id_tx: str, terminal_id: str, material: str, peso_kg: float, monto: float, firma: str, timestamp: str) -> None:
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO depositos_pendientes (id_deposito, id_terminal, tipo_material, peso_kg, monto_calculado, firma_ecdsa, timestamp_local, sincronizado)
                VALUES (?, ?, ?, ?, ?, ?, ?, 0)
            """, (id_tx, terminal_id, material, peso_kg, monto, firma, timestamp))
            conn.commit()

    def guardar_telemetria(self, id_evento: str, id_terminal: str, tipo_evento: str, valor_numerico: float, alerta_estado: str, timestamp: str) -> None:
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO telemetria_local (id_evento, id_terminal, tipo_evento, valor_numerico, alerta_estado, timestamp_local, sincronizado)
                VALUES (?, ?, ?, ?, ?, ?, 0)
            """, (id_evento, id_terminal, tipo_evento, valor_numerico, alerta_estado, timestamp))
            conn.commit()

    def obtener_peso_acumulado_kg(self) -> float:
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT SUM(peso_kg) FROM depositos_pendientes;")
            res = cursor.fetchone()[0]
            return float(res) if res is not None else 0.0


# =====================================================================
# INDICE 3: ORQUESTADOR PRINCIPAL (Inyección de Dependencias)
# =====================================================================

class EcocanjeTerminal:
    def __init__(self, id_terminal: str, hardware: IHardwareService, crypto: ICryptoService, db_local: ILocalStorage):
        self.id_terminal = id_terminal
        # Inyección de dependencias a través de las interfaces abstractas
        self.hardware = hardware
        self.crypto = crypto
        self.db_local = db_local

    def procesar_ciclo_carga(self) -> dict:
        """Orquesta los pasos 1 al 4 del ciclo de vida del dato en la terminal"""
        # 1. Entrada de datos desde el hardware fakeado
        material = self.hardware.clasificar_material_optico()
        peso_g = self.hardware.obtener_peso_neto()
        
        id_tx = str(uuid.uuid4())[:8] # Genera id transaccional corto
        timestamp = str(int(time.time()))
        
        # Cotización rápida local para cálculo del incentivo
        precio_por_kg = 150.0 if material == "PET" else 300.0
        monto_estimado = round((peso_g / 1000.0) * precio_por_kg, 2)
        
        # 2. Armar JSON plano para firmar criptográficamente (¡SIN ID_USUARIO!)
        payload_base = {
            "id_tx": id_tx,
            "id_terminal": self.id_terminal,
            "material": material,
            "peso_gramos": peso_g,
            "timestamp_creacion": timestamp
        }
        
        # 3. Firmar el string JSON ordenado por keys para evitar fallas de verificación
        json_estricto = json.dumps(payload_base, sort_keys=True)
        firma_hex = self.crypto.firmar_datos(json_estricto)
        
        # 4. Guardar localmente en SQLite WAL usando abstracción de persistencia
        peso_en_kg = peso_g / 1000.0
        self.db_local.guardar_deposito_offline(
            id_tx, self.id_terminal, material, peso_en_kg, monto_estimado, firma_hex, timestamp
        )

        # 4b. Registrar telemetría de salud de hardware y estado local en SQLite WAL
        # Log 1: Temperatura de la CPU/Placa (Simulado)
        temp_val = round(random.uniform(37.5, 48.2), 1)
        temp_alerta = "OK" if temp_val < 46.0 else "WARNING"
        self.db_local.guardar_telemetria(
            str(uuid.uuid4())[:8], self.id_terminal, "TEMPERATURA_CPU_C", temp_val, temp_alerta, timestamp
        )
        
        # Log 2: Latencia de la IA de visión computacional local (Simulado)
        ia_latency = round(random.uniform(90.0, 180.0), 1)
        self.db_local.guardar_telemetria(
            str(uuid.uuid4())[:8], self.id_terminal, "IA_LATENCIA_CLASIFICACION_MS", ia_latency, "OK", timestamp
        )

        # Log 3: Nivel de saturación del contenedor (Simulado con peso acumulado)
        # Asumimos una capacidad máxima de 100 kg en el contenedor.
        peso_total = self.db_local.obtener_peso_acumulado_kg()
        saturacion_pct = min(100.0, round((peso_total / 100.0) * 100.0, 2))
        sat_alerta = "OK" if saturacion_pct < 80.0 else "CRITICAL"
        self.db_local.guardar_telemetria(
            str(uuid.uuid4())[:8], self.id_terminal, "SATURACION_CONTENEDOR_PORCENTAJE", saturacion_pct, sat_alerta, timestamp
        )
        
        # 5. Formatear salida para el dibujo físico del Código QR dinámico
        payload_final_qr = {
            "id_tx": id_tx,
            "id_terminal": self.id_terminal,
            "material": material,
            "peso_gramos": peso_g,
            "monto_liquidacion": str(monto_estimado),
            "firma": firma_hex
        }
        
        return payload_final_qr


# =====================================================================
# INDICE 4: PUNTO DE ENTRADA (Una sola carga por ejecución)
# =====================================================================

if __name__ == "__main__":
    # Instanciamos los componentes desacoplados respetando los contratos de las interfaces
    hw_simulado = MockHardwareService()
    crypto_service = ECDSACryptoService()
    sqlite_storage = SQLiteLocalStorage()
    
    # Construcción de la terminal IoT por inyección
    import os
    terminal = EcocanjeTerminal(
        id_terminal=os.getenv("TERMINAL_ID", "TERM-CABA-005"), 
        hardware=hw_simulado, 
        crypto=crypto_service, 
        db_local=sqlite_storage
    )
    
    # EJECUCIÓN: Genera exactamente UNA carga única por llamada al script
    resultado_qr = terminal.procesar_ciclo_carga()
    
    # Imprime el payload final generado por el Edge en consola
    print("\n[PANTALLA TFT TERMINAL: EMISIÓN DE CÓDIGO QR DINÁMICO]")
    print(json.dumps(resultado_qr, indent=2))
    print("-----------------------------------------------------------------")
    
    # Renderizar el Código QR en la consola de forma interactiva/visual
    try:
        import qrcode
        qr = qrcode.QRCode(version=1, box_size=1, border=1)
        # Se incrusta el JSON completo exacto en los módulos del QR
        qr.add_data(json.dumps(resultado_qr))
        qr.make(fit=True)
        print("\[ESCANEAME CON LA APP (CÓDIGO QR REAL EMITIDO EN PANTALLA TFT)]")
        qr.print_ascii(invert=True)
        print("-----------------------------------------------------------------\n")
    except ImportError:
        print("[AVISO] Instale la librería 'qrcode' para visualizar el QR real en consola.")