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
                
                try {
                    const response = await fetch(endpoint, { method: 'POST' });
                    const result = await response.json();
                    if (result.log) {
                        logBox.innerHTML += result.log + "\\n";
                    } else {
                        logBox.innerHTML += JSON.stringify(result, null, 2) + "\\n";
                    }
                    logBox.scrollTop = logBox.scrollHeight;
                    actualizarEstado();
                } catch (e) {
                    logBox.innerHTML += `[ERROR] ${e}\\n`;
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
            <h1>Terminal IoT Edge - Modo Mantenimiento</h1>
            <p style="color:#aaa;">Simulacion de hardware local. Los datos nacen aqui y luego se sincronizan con la nube.</p>
            
            <div class="panel">
                <h3>Panel de Control</h3>
                <button class="btn btn-blue" onclick="accion('/simular-carga')">Simular Carga de Material</button>
                <button class="btn btn-blue" onclick="accion('/simular-carga-masiva')">x10 Cargas Masivas (Forzar Saturacion)</button>
                <button class="btn" onclick="accion('/sincronizar')">Sincronizar a Nube (Sync Daemon)</button>
                <button class="btn btn-red" onclick="document.getElementById('log').innerHTML=''">Limpiar Logs</button>
                
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

@app.get("/estado")
async def get_estado():
    # Lee directamente de SQLite para mostrar el estado
    try:
        with sqlite3.connect(DB_PATH) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            cursor.execute("SELECT COUNT(*) as c FROM telemetria_local WHERE sincronizado = 0;")
            pendientes = cursor.fetchone()["c"]
            
            cursor.execute("SELECT SUM(valor_numerico) as s FROM telemetria_local WHERE tipo_evento = 'PESO_ACUMULADO_KG';")
            row = cursor.fetchone()
            peso = row["s"] if row and row["s"] else 0.0
            
            return {
                "pendientes": pendientes,
                "peso_acumulado_kg": peso
            }
    except Exception:
        return {"pendientes": 0, "peso_acumulado_kg": 0.0}
