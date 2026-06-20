from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
import sqlite3
import os
import subprocess
from contextlib import redirect_stdout
import io

app = FastAPI(title="Edge IoT Panel")

DB_PATH = os.getenv("SQLITE_DB_PATH", "ecocanje_edge.db")

@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    html_content = """
    <!DOCTYPE html>
    <html lang="es">
    <head>
        <meta charset="UTF-8">
        <title>Terminal IoT Edge (Puerto 8001)</title>
        <style>
            body { font-family: 'Courier New', Courier, monospace; background-color: #1e1e1e; color: #00ff00; margin: 0; padding: 20px; }
            h1 { color: #ffffff; border-bottom: 2px solid #555; padding-bottom: 10px; }
            .container { max-width: 1000px; margin: 0 auto; }
            .panel { background-color: #2d2d2d; border: 1px solid #444; border-radius: 5px; padding: 20px; margin-bottom: 20px; }
            .btn { background-color: #4CAF50; border: none; color: white; padding: 10px 20px; text-align: center; text-decoration: none; display: inline-block; font-size: 16px; margin: 4px 2px; cursor: pointer; border-radius: 4px; }
            .btn-blue { background-color: #008CBA; }
            .btn-red { background-color: #f44336; }
            .log-box { background-color: #000; color: #00ff00; padding: 10px; height: 300px; overflow-y: scroll; border: 1px solid #555; font-size: 14px; white-space: pre-wrap; }
            table { width: 100%; border-collapse: collapse; margin-top: 10px; color: #fff; }
            th, td { border: 1px solid #555; padding: 8px; text-align: left; }
            th { background-color: #444; }
        </style>
        <script>
            async function accion(endpoint) {
                const logBox = document.getElementById("log");
                logBox.innerHTML += `\\n[SYS] Ejecutando: ${endpoint}...\\n`;
                logBox.scrollTop = logBox.scrollHeight;
                
                const start_time = performance.now();
                try {
                    const response = await fetch(endpoint, { method: 'POST' });
                    const result = await response.json();
                    const end_time = performance.now();
                    const ms = (end_time - start_time).toFixed(2);
                    
                    if (result.log) {
                        logBox.innerHTML += `[Tardó: ${ms} ms]\n` + result.log + "\\n";
                    } else {
                        logBox.innerHTML += `[Tardó: ${ms} ms]\n` + JSON.stringify(result, null, 2) + "\\n";
                    }
                    logBox.scrollTop = logBox.scrollHeight;
                    actualizarEstado();
                } catch (e) {
                    const end_time = performance.now();
                    const ms = (end_time - start_time).toFixed(2);
                    logBox.innerHTML += `[ERROR - ${ms} ms] ${e}\\n`;
                }
            }

            async function actualizarEstado() {
                try {
                    const response = await fetch('/estado');
                    const data = await response.json();
                    document.getElementById('lbl-pendientes').innerText = data.pendientes;
                    document.getElementById('lbl-peso').innerText = data.peso_acumulado_kg.toFixed(2) + " kg";
                } catch (e) {
                    console.error("Error al actualizar estado:", e);
                }
            }
            
            // Actualizar estado al cargar
            window.onload = actualizarEstado;
        </script>
    </head>
    <body>
        <div class="container">
            <h1>Terminal IoT Edge</h1>
            <p style="color:#aaa;">Simulacion de hardware local. Los datos nacen aqui y luego se sincronizan con la nube.</p>
            
            <div class="panel">
                <h3>Panel de Control</h3>
                <button class="btn btn-blue" onclick="accion('/simular-carga')">Simular Carga de Material</button>
                <button class="btn btn-blue" onclick="accion('/simular-carga-masiva')">x10 Cargas Masivas (Forzar Saturacion)</button>
                <button class="btn btn-blue" onclick="accion('/generar-qr')" style="background-color: #ff9800; font-weight: bold;">Finalizar y Emitir QR</button>
                <button class="btn" onclick="accion('/sincronizar')">Sincronizar a Nube (Sync Daemon)</button>
                <button class="btn" onclick="accion('/estado-interno')" style="background-color: #673ab7;">Ver Datos Internos (SQLite)</button>
                <button class="btn btn-red" onclick="document.getElementById('log').innerHTML=''">Limpiar Logs</button>
                <button class="btn btn-red" onclick="accion('/limpiar-db-local')" style="background-color: #d32f2f;">Formatear Disco (Borrar SQLite)</button>
                
                <div style="margin-top: 20px; font-weight: bold; font-size: 18px; color: #ffeb3b;">
                    Eventos pendientes de sincronización (SQLite): <span id="lbl-pendientes">0</span><br>
                    Peso acumulado en contenedor: <span id="lbl-peso">0.00 kg</span>
                </div>
            </div>
            
            <div class="panel">
                <h3>Consola Serial del Dispositivo</h3>
                <div id="log" class="log-box">Bienvenido al SO de EcoCanje Edge. Esperando comandos...
</div>
            </div>
        </div>
    </body>
    </html>
    """
    return HTMLResponse(content=html_content)

@app.post("/simular-carga")
async def simular_carga():
    f = io.StringIO()
    with redirect_stdout(f):
        try:
            # Ejecutamos el script terminal.py internamente
            subprocess.run(["python", "terminal.py"], capture_output=True, text=True, check=True)
            print("[INFO] Simulación de carga ejecutada exitosamente.")
        except subprocess.CalledProcessError as e:
            print(f"[ERROR] falló la ejecución: {e.stderr}")
    return {"log": f.getvalue() or "[INFO] Ciclo de hardware completado sin errores."}

@app.post("/simular-carga-masiva")
async def simular_carga_masiva():
    f = io.StringIO()
    with redirect_stdout(f):
        print("[INFO] Iniciando 10 ciclos rápidos para saturar contenedor...")
        try:
            for _ in range(10):
                subprocess.run(["python", "terminal.py"], capture_output=True, text=True, check=True)
            print("[INFO] 10 simulaciones completadas. Revise el estado del peso.")
        except subprocess.CalledProcessError as e:
            print(f"[ERROR] falló la ejecución: {e.stderr}")
    return {"log": f.getvalue()}

@app.post("/sincronizar")
async def sincronizar():
    try:
        resultado = subprocess.run(["python", "sync_daemon.py"], capture_output=True, text=True, check=True)
        return {"log": resultado.stdout}
    except subprocess.CalledProcessError as e:
        return {"log": f"[ERROR] {e.stderr}\\n{e.stdout}"}

@app.post("/limpiar-db-local")
async def limpiar_db_local():
    """
    Formatea el disco duro virtual de la terminal (SQLite).
    Borra la telemetría local y reinicia los contadores de peso al estado de fábrica.
    """
    try:
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM telemetria_local")
            cursor.execute("DELETE FROM depositos_pendientes")
            conn.commit()
        return {"log": "[SISTEMA] Disco duro formateado. Tablas locales de SQLite vaciadas a cero."}
    except Exception as e:
        return {"log": f"[ERROR CRÍTICO] Fallo al formatear disco: {str(e)}"}

@app.post("/estado-interno")
async def ver_estado_interno_sqlite():
    import json
    try:
        with sqlite3.connect(DB_PATH) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            cursor.execute("SELECT * FROM depositos_pendientes;")
            depositos = [dict(row) for row in cursor.fetchall()]
            
            cursor.execute("SELECT * FROM telemetria_local;")
            telemetria = [dict(row) for row in cursor.fetchall()]
            
            radiografia = {
                "1_DEPOSITOS_PENDIENTES (Transacciones de Usuario)": depositos,
                "2_TELEMETRIA_LOCAL (Salud de Hardware)": telemetria
            }
            
            # Formatear para la consola
            formateado = json.dumps(radiografia, indent=2, ensure_ascii=False)
            mensaje = "<br>========================================<br>"
            mensaje += "<b>[ESTADO INTERNO DE DISCO SQLITE]</b><br>"
            mensaje += "========================================<br>"
            mensaje += f"<pre style='color: #00ff00; font-size: 13px; margin:0;'>{formateado}</pre><br>"
            
            return {"log": mensaje}
    except Exception as e:
        return {"log": f"[ERROR LECTURA DISCO] {str(e)}"}

@app.get("/estado")
async def get_estado():
    # Lee directamente de SQLite para mostrar el estado
    try:
        with sqlite3.connect(DB_PATH) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            cursor.execute("SELECT COUNT(*) as c FROM telemetria_local WHERE sincronizado = 0;")
            pendientes = cursor.fetchone()["c"]
            
            cursor.execute("SELECT SUM(peso_kg) as s FROM depositos_pendientes;")
            row = cursor.fetchone()
            peso = row["s"] if row and row["s"] else 0.0
            
            return {
                "pendientes": pendientes,
                "peso_acumulado_kg": peso
            }
    except Exception:
        return {"pendientes": 0, "peso_acumulado_kg": 0.0}

@app.post("/generar-qr")
async def generar_qr():
    import requests
    import io
    import subprocess
    from contextlib import redirect_stdout
    
    # 1. Ejecutar el ciclo de hardware local
    f = io.StringIO()
    with redirect_stdout(f):
        try:
            subprocess.run(["python", "terminal.py"], capture_output=True, text=True, check=True)
        except subprocess.CalledProcessError as e:
            return {"log": f"[ERROR] {e.stderr}"}
            
    # 2. Instanciar para sacar el payload
    from terminal import EcocanjeTerminal, MockHardwareService, ECDSACryptoService, SQLiteLocalStorage
    term = EcocanjeTerminal(id_terminal="TERM-CABA-005", hardware=MockHardwareService(), crypto=ECDSACryptoService(), db_local=SQLiteLocalStorage(DB_PATH))
    payload_qr = term.procesar_ciclo_carga()
    
    # 3. Mandar el payload al Backend (REST)
    try:
        respuesta = requests.post("http://backend:8000/transacciones/crear-token-qr", json=payload_qr, timeout=5)
        if respuesta.status_code == 200:
            token = respuesta.json().get("token_qr", "ERROR_TOKEN")
            
            # Generamos la URL de una API pública gratuita para renderizar visualmente el QR en HTML
            qr_img_url = f"https://api.qrserver.com/v1/create-qr-code/?size=250x250&data={token}&bgcolor=000000&color=00ff00&margin=10"
            
            # Formateamos un HTML interactivo para la consola web
            html_msg = "<br>========================================<br>"
            html_msg += "<b>[PANTALLA TFT: CÓDIGO QR GENERADO]</b><br>"
            html_msg += f"TOKEN: <span style='color:white; background:#333; padding:2px 5px;'>{token}</span><br>"
            html_msg += "Escanee este código con la aplicación móvil (Expira en 2 min):<br><br>"
            html_msg += f"<img src='{qr_img_url}' style='border: 3px solid #555; border-radius: 5px;'><br>"
            html_msg += "========================================<br>"
            
            return {"log": html_msg}
        else:
            return {"log": f"<br>[ERROR BACKEND] Respuesta: {respuesta.text}"}
    except Exception as e:
        return {"log": f"<br>[ERROR RED] Falló comunicación: {str(e)}"}


