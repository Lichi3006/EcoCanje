import sqlite3
import time
import os
import requests

class EdgeSyncDaemon:
    def __init__(self, db_path: str = None, backend_url: str = None):
        self.db_path = db_path or os.getenv("SQLITE_DB_PATH", "ecocanje_edge.db")
        self.backend_url = backend_url or os.getenv("BACKEND_URL", "http://backend:8000/telemetria/eventos")

    def ejecutar_sincronizacion_y_vaciamiento(self):
        """[Paso 8] Lee la telemetría pendiente, envía por WAN al backend cloud y purga SQLite"""
        print("[DAEMON] Iniciando verificación de conexión WAN celular...")
        
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            # 1. Buscar registros de telemetría que no se hayan subido a la nube
            cursor.execute("SELECT * FROM telemetria_local WHERE sincronizado = 0;")
            logs_pendientes = cursor.fetchall()
            
            if not logs_pendientes:
                print("[DAEMON] No hay eventos de telemetría nuevos para sincronizar. Base limpia.")
                return

            # Transformamos los resultados a una lista de diccionarios JSON para enviar por red
            payload_lote = []
            ids_a_actualizar = []
            for row in logs_pendientes:
                payload_lote.append({
                    "id_evento": row["id_evento"],
                    "id_terminal": row["id_terminal"],
                    "tipo_evento": row["tipo_evento"],
                    "valor_numerico": row["valor_numerico"],
                    "alerta_estado": row["alerta_estado"],
                    "timestamp_local": row["timestamp_local"]
                })
                ids_a_actualizar.append(row["id_evento"])

            print(f"[DAEMON] Se encontraron {len(payload_lote)} logs de hardware listos para subir.")
            print(f"[WAN-ENVÍO] Transmitiendo lote al backend ({self.backend_url})...")
            
            # Envío real al backend cloud con reintentos
            exito = False
            for intento in range(3):
                try:
                    respuesta = requests.post(self.backend_url, json=payload_lote, timeout=10)
                    if respuesta.status_code == 200:
                        datos = respuesta.json()
                        if "error" in datos:
                            print(f"[WAN-ERROR] Backend devolvió error lógico: {datos['error']}. Reintentando...")
                            time.sleep(5)
                            continue
                        print(f"[NUBE-ACK] Backend respondió HTTP 200: {datos.get('eventos_procesados_q8', 0)} eventos ingestados, "
                              f"{datos.get('saturaciones_enriquecidas_q7', 0)} saturaciones enriquecidas para Q7.")
                        exito = True
                        break
                    else:
                        print(f"[WAN-ERROR] Backend respondió HTTP {respuesta.status_code}. Reintentando...")
                except requests.exceptions.ConnectionError:
                    print(f"[WAN-ERROR] Sin conexión al backend (intento {intento + 1}/3). Reintentando en 5s...")
                    time.sleep(5)
                except Exception as e:
                    print(f"[WAN-ERROR] Error inesperado: {e}")
                    break
            
            if not exito:
                print("[DAEMON] No se pudo conectar al backend. Los datos quedan pendientes en SQLite para el próximo ciclo.")
                return

            # 2. Marcar localmente como sincronizados
            for id_ev in ids_a_actualizar:
                cursor.execute("UPDATE telemetria_local SET sincronizado = 1 WHERE id_evento = ?;", (id_ev,))
            
            # 3. PROCESO DE PURGA FISICA
            print("[PURGA] Iniciando vaciado y optimización de almacenamiento en el hardware local...")
            cursor.execute("DELETE FROM telemetria_local WHERE sincronizado = 1;")
            conn.commit()
            
            # Comando clave: Compacta el archivo .db en el disco de la terminal liberando espacio real
            cursor.execute("VACUUM;")
            conn.commit()
            
        print("[EDGE-SUCCESS] Proceso de sincronización terminado. SQLite purgado y optimizado.")

if __name__ == "__main__":
    daemon = EdgeSyncDaemon()
    daemon.ejecutar_sincronizacion_y_vaciamiento()