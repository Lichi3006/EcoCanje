from fastapi import APIRouter
from fastapi.responses import HTMLResponse

panel_router = APIRouter()

@panel_router.get("/", tags=["UI Básica MVP"])
async def interfaz_basica_profesor():
    """Interfaz súper básica inyectada en Python para testear la API sin usar un Framework Frontend"""
    html_content = """
    <!DOCTYPE html>
    <html lang="es">
    <head>
        <meta charset="UTF-8">
        <title>EcoCanje - Panel de Pruebas de consultas</title>
        <style>
            * { box-sizing: border-box; margin: 0; padding: 0; }
            body { font-family: 'Courier New', Courier, monospace; background-color: #1e1e1e; color: #00ff00; padding: 30px 20px; }
            h1 { color: #ffffff; border-bottom: 2px solid #555; padding-bottom: 10px; margin-bottom: 10px; }
            .subtitle { color: #aaaaaa; margin-bottom: 25px; font-size: 0.95em; }
            .container { max-width: 1000px; margin: auto; }
            .grid { display: grid; grid-template-columns: 1fr 1fr; gap: 14px; margin-bottom: 20px; }
            .card { background-color: #2d2d2d; padding: 16px; border: 2px solid #444; border-radius: 5px; color: #ffffff; }
            .card.mongo { border-color: #4CAF50; }
            .card.redis { border-color: #3b82f6; }
            .card.cassandra { border-color: #f97316; }
            .card.multi { border-color: #a855f7; }
            .card h3 { font-size: 0.95em; margin-bottom: 8px; color: #ffffff; }
            .card .db-tag { display: inline-block; font-size: 0.7em; padding: 2px 8px; border-radius: 10px; margin-bottom: 8px; font-weight: bold; }
            .db-tag.mongo { background: #1a3a1a; color: #4CAF50; border: 1px solid #4CAF50; }
            .db-tag.redis { background: #1a2a3a; color: #3b82f6; border: 1px solid #3b82f6; }
            .db-tag.cassandra { background: #3a2a1a; color: #f97316; border: 1px solid #f97316; }
            .db-tag.multi { background: #2a1a3a; color: #a855f7; border: 1px solid #a855f7; }
            .card p { font-size: 0.78em; color: #aaaaaa; margin-bottom: 10px; line-height: 1.4; }
            button { background-color: #4CAF50; color: white; border: none; padding: 8px 16px; cursor: pointer; border-radius: 4px; font-family: 'Courier New', Courier, monospace; font-weight: bold; font-size: 0.82em; width: 100%; transition: background 0.2s; }
            button:hover { background-color: #45a049; }
            button:active { transform: scale(0.98); }
            .output-card { background-color: #000000; padding: 16px; border-radius: 5px; border: 1px solid #555; }
            .output-card h3 { margin-bottom: 10px; color: #ffffff; font-size: 0.9em; border-bottom: 1px solid #333; padding-bottom: 5px; }
            pre { background: #000000; padding: 14px; overflow-x: auto; color: #00ff00; font-size: 0.82em; max-height: 400px; overflow-y: auto; line-height: 1.5; white-space: pre-wrap; word-break: break-word; }
            .legend { display: flex; gap: 16px; margin-bottom: 20px; flex-wrap: wrap; }
            .legend-item { display: flex; align-items: center; gap: 6px; font-size: 0.78em; color: #aaaaaa; }
            .legend-dot { width: 10px; height: 10px; border-radius: 50%; }
            .legend-dot.mongo { background: #4CAF50; }
            .legend-dot.redis { background: #3b82f6; }
            .legend-dot.cassandra { background: #f97316; }
            .legend-dot.multi { background: #a855f7; }
            .card-full { grid-column: 1 / -1; }
            @media (max-width: 700px) { .grid { grid-template-columns: 1fr; } }
        </style>
    </head>
    <body>
        <div class="container">

            <div style="display: flex; justify-content: space-between; align-items: center; border-bottom: 2px solid #555; padding-bottom: 10px; margin-bottom: 10px;">
                <h1 style="border: none; margin: 0; padding: 0;">EcoCanje - Panel de Pruebas de consultas</h1>
                <button onclick="llamarAPI('/sistema/reset', 'POST', {})" style="background-color: #f44336; width: auto; font-size: 0.9em; padding: 10px 20px;">Restaurar a Semilla Cero</button>
            </div>
            
            <div class="legend">
                <div class="legend-item"><div class="legend-dot mongo"></div> MongoDB</div>
                <div class="legend-item"><div class="legend-dot redis"></div> Redis</div>
                <div class="legend-item"><div class="legend-dot cassandra"></div> Cassandra</div>
                <div class="legend-item"><div class="legend-dot multi"></div> Multi-Motor</div>
            </div>
            
            <div class="grid" style="margin-bottom: 20px;">
                <div class="card multi card-full" style="border-color: #ff0000; background-color: #2d2d2d;">
                    <span class="db-tag" style="background: #ff0000; color: #fff;">[!] Simulación de Fallos</span>
                    <h3>Control de Servicios (Apagado Forzado)</h3>
                    <p>Permite detener o reiniciar los contenedores de bases de datos para evaluar el comportamiento del sistema ante cortes de red o caídas.</p>
                    <div style="display: flex; gap: 10px; margin-top: 10px;">
                        <button style="background: #cc0000;" onclick="llamarAPI('/caos/ecocanje_mongodb/stop', 'POST')">Detener MongoDB</button>
                        <button style="background: #006600;" onclick="llamarAPI('/caos/ecocanje_mongodb/start', 'POST')">Iniciar MongoDB</button>
                        <button style="background: #cc4400;" onclick="llamarAPI('/caos/ecocanje_cassandra/stop', 'POST')">Detener Cassandra</button>
                        <button style="background: #006600;" onclick="llamarAPI('/caos/ecocanje_cassandra/start', 'POST')">Iniciar Cassandra</button>
                    </div>
                </div>
            </div>
            
            <div class="grid">
                <div class="card mongo card-full">
                    <span class="db-tag mongo">MongoDB</span>
                    <h3>Diccionario de Nodos (Raw JSON)</h3>
                    <p>Auditoria: Consulta el JSON crudo con la configuracion fisica y logica de todos los Puntos Verdes y sus Terminales IoT.</p>
                    <button onclick="llamarAPI('/terminales/todas', 'GET')">Consultar Todos los Nodos</button>
                </div>
                
                <div class="card mongo card-full">
                    <span class="db-tag mongo">MongoDB</span>
                    <h3>Perfiles de Usuario (Raw JSON)</h3>
                    <p>Auditoria: Consulta el saldo actual y los metadatos de todos los usuarios registrados en el sistema.</p>
                    <button onclick="llamarAPI('/perfiles/todos', 'GET')">Consultar Perfiles</button>
                </div>
                
                <div class="card cassandra card-full">
                    <span class="db-tag cassandra">Cassandra</span>
                    <h3>Ledger Inmutable de Transacciones (Raw JSON)</h3>
                    <p>Auditoria: Volcado directo de las transacciones almacenadas en Cassandra (las que impactan el saldo de la Billetera).</p>
                    <button onclick="llamarAPI('/transacciones/ledger', 'GET')">Volcar Ledger Cassandra</button>
                </div>
                
                <div class="card redis card-full">
                    <span class="db-tag redis">Redis</span>
                    <h3>Estado en Vivo de Memoria Efímera (Raw JSON)</h3>
                    <p>Auditoria: Estado Interno de la RAM. Muestra colas SAGA pendientes, tokens QR vivos y caché de IoT.</p>
                    <button onclick="llamarAPI('/transacciones/auditoria_redis', 'GET')">Volcar Estado Redis</button>
                </div>
                <div class="card mongo">
                    <span class="db-tag mongo">MongoDB</span>
                    <h3>Q1 - Busqueda Geoespacial</h3>
                    <p>Busca Puntos Verdes cercanos a coordenadas GPS.</p>
                    <div style="display: flex; gap: 10px; margin-bottom: 10px;">
                        <div>
                            <label style="font-size: 0.75em; color: #888;">Latitud</label>
                            <input type="text" id="q1-lat" value="-34.6044" style="width: 100%; padding: 5px; background: #000; color: #0f0; border: 1px solid #444;">
                        </div>
                        <div>
                            <label style="font-size: 0.75em; color: #888;">Longitud</label>
                            <input type="text" id="q1-lon" value="-58.4208" style="width: 100%; padding: 5px; background: #000; color: #0f0; border: 1px solid #444;">
                        </div>
                    </div>
                    <button onclick="llamarAPI(`/terminales/cercanas?latitud=${document.getElementById('q1-lat').value}&longitud=${document.getElementById('q1-lon').value}`, 'GET')">Ejecutar Q1</button>
                </div>
                
                <div class="card mongo">
                    <span class="db-tag mongo">MongoDB</span>
                    <h3>Q2 - Materiales Autorizados</h3>
                    <p>Consulta que materiales recibe un Punto Verde.</p>
                    <label style="font-size: 0.75em; color: #888;">ID del Nodo</label>
                    <input type="text" id="q2-id" value="NODE-CABA-001" style="width: 100%; padding: 5px; background: #000; color: #0f0; border: 1px solid #444; margin-bottom: 10px;">
                    <button onclick="llamarAPI(`/terminales/materiales/${document.getElementById('q2-id').value}`, 'GET')">Ejecutar Q2</button>
                </div>
                
                <div class="card redis">
                    <span class="db-tag redis">Redis + MongoDB</span>
                    <h3>Q3 - Capacidad en Tiempo Real</h3>
                    <p>Nivel de llenado y semaforo de un contenedor.</p>
                    <label style="font-size: 0.75em; color: #888;">ID de Terminal</label>
                    <input type="text" id="q3-id" value="TERM-CABA-012" style="width: 100%; padding: 5px; background: #000; color: #0f0; border: 1px solid #444; margin-bottom: 10px;">
                    <button onclick="llamarAPI(`/terminales/capacidad/${document.getElementById('q3-id').value}`, 'GET')">Ejecutar Q3</button>
                </div>
                
                <div class="card redis">
                    <span class="db-tag redis">Redis (Lua/EVAL)</span>
                    <h3>Q4 - Canje QR Atomico</h3>
                    <p>Simula el escaneo y consumo instantaneo de un QR efimero.</p>
                    <div style="display: flex; gap: 5px; margin-bottom: 10px;">
                        <div>
                            <label style="font-size: 0.75em; color: #888;">ID Token QR</label>
                            <input type="text" id="q4-qr" value="QR-DEMO-001" style="width: 100%; padding: 5px; background: #000; color: #0f0; border: 1px solid #444;">
                        </div>
                        <div>
                            <label style="font-size: 0.75em; color: #888;">ID Usuario</label>
                            <input type="text" id="q4-usr" value="USR-PROFESOR" style="width: 100%; padding: 5px; background: #000; color: #0f0; border: 1px solid #444;">
                        </div>
                    </div>
                    <button onclick="llamarAPI('/transacciones/canje-qr', 'POST', {id_qr_transaccional: document.getElementById('q4-qr').value, id_usuario: document.getElementById('q4-usr').value})">Ejecutar Q4</button>
                </div>
                
                <div class="card multi">
                    <span class="db-tag multi">Cassandra + MongoDB + Redis</span>
                    <h3>Q5 - Registro Inmutable (Ledger)</h3>
                    <p>Registra una entrega de material (ej. 1.5kg de PET) e impacta el saldo.</p>
                    <div style="display: flex; gap: 5px; margin-bottom: 5px;">
                        <div>
                            <label style="font-size: 0.75em; color: #888;">ID Usuario</label>
                            <input type="text" id="q5-usr" value="USR-PROFESOR" style="width: 100%; padding: 5px; background: #000; color: #0f0; border: 1px solid #444;">
                        </div>
                        <div>
                            <label style="font-size: 0.75em; color: #888;">ID Terminal</label>
                            <input type="text" id="q5-term" value="TERM-CABA-005" style="width: 100%; padding: 5px; background: #000; color: #0f0; border: 1px solid #444;">
                        </div>
                    </div>
                    <div style="display: flex; gap: 5px; margin-bottom: 10px;">
                        <div>
                            <label style="font-size: 0.75em; color: #888;">Material</label>
                            <input type="text" id="q5-mat" value="PET" style="width: 100%; padding: 5px; background: #000; color: #0f0; border: 1px solid #444;">
                        </div>
                        <div>
                            <label style="font-size: 0.75em; color: #888;">Kg</label>
                            <input type="text" id="q5-kg" value="1.5" style="width: 100%; padding: 5px; background: #000; color: #0f0; border: 1px solid #444;">
                        </div>
                        <div>
                            <label style="font-size: 0.75em; color: #888;">$ Monto</label>
                            <input type="text" id="q5-monto" value="225.0" style="width: 100%; padding: 5px; background: #000; color: #0f0; border: 1px solid #444;">
                        </div>
                    </div>
                    <button onclick="llamarAPI('/transacciones/registro-entrega', 'POST', {id_deposito: 'DEP-UI-' + Math.floor(Math.random() * 10000), id_usuario: document.getElementById('q5-usr').value, id_terminal: document.getElementById('q5-term').value, tipo_material: document.getElementById('q5-mat').value, peso_kg: parseFloat(document.getElementById('q5-kg').value), monto_acreditado: parseFloat(document.getElementById('q5-monto').value), firma_ecdsa: 'firma_demo_ui', timestamp_local: Math.floor(Date.now()/1000)})">Ejecutar Q5</button>
                </div>
                
                <div class="card mongo">
                    <span class="db-tag mongo">MongoDB (Majority)</span>
                    <h3>Q6 - Saldo Billetera</h3>
                    <p>Consulta el balance actual de un ciudadano.</p>
                    <label style="font-size: 0.75em; color: #888;">ID de Usuario</label>
                    <input type="text" id="q6-id" value="USR-PROFESOR" style="width: 100%; padding: 5px; background: #000; color: #0f0; border: 1px solid #444; margin-bottom: 10px;">
                    <button onclick="llamarAPI(`/perfiles/${document.getElementById('q6-id').value}/saldo`, 'GET')">Ejecutar Q6</button>
                </div>
                
                <div class="card multi">
                    <span class="db-tag multi">Cassandra + MongoDB + Redis</span>
                    <h3>Q7 - Saturaciones por Comuna</h3>
                    <p>Historial analitico de contenedores llenos.</p>
                    <div style="display: flex; gap: 5px; margin-bottom: 10px;">
                        <div>
                            <label style="font-size: 0.75em; color: #888;">Nro. Comuna</label>
                            <input type="text" id="q7-comuna" value="5" style="width: 100%; padding: 5px; background: #000; color: #0f0; border: 1px solid #444;">
                        </div>
                        <div>
                            <label style="font-size: 0.75em; color: #888;">Desde</label>
                            <input type="text" id="q7-desde" value="2026-06-01" style="width: 100%; padding: 5px; background: #000; color: #0f0; border: 1px solid #444;">
                        </div>
                        <div>
                            <label style="font-size: 0.75em; color: #888;">Hasta</label>
                            <input type="text" id="q7-hasta" value="2026-06-30" style="width: 100%; padding: 5px; background: #000; color: #0f0; border: 1px solid #444;">
                        </div>
                    </div>
                    <button onclick="llamarAPI(`/telemetria/saturaciones/comuna/${document.getElementById('q7-comuna').value}?fecha_desde=${document.getElementById('q7-desde').value}&fecha_hasta=${document.getElementById('q7-hasta').value}`, 'GET')">Ejecutar Q7</button>
                </div>
                
                <div class="card cassandra">
                    <span class="db-tag cassandra">SQLite (Edge) + Cassandra</span>
                    <h3>Q8 - Telemetria IoT</h3>
                    <p>Historial de mediciones tecnicas de una terminal (temperatura, peso, etc).</p>
                    <label style="font-size: 0.75em; color: #888;">ID de Terminal</label>
                    <input type="text" id="q8-id" value="TERM-CABA-005" style="width: 100%; padding: 5px; background: #000; color: #0f0; border: 1px solid #444; margin-bottom: 10px;">
                    <button onclick="llamarAPI(`/telemetria/eventos/${document.getElementById('q8-id').value}`, 'GET')">Ejecutar Q8</button>
                </div>
                
                <div class="card multi card-full">
                    <span class="db-tag multi">Cassandra + MongoDB</span>
                    <h3>Q9 - Reconciliacion Financiera</h3>
                    <p>Compara Cassandra vs MongoDB y repara saldos desincronizados.</p>
                    <label style="font-size: 0.75em; color: #888;">ID de Usuario</label>
                    <input type="text" id="q9-id" value="USR-PROFESOR" style="width: 100%; padding: 5px; background: #000; color: #0f0; border: 1px solid #444; margin-bottom: 10px;">
                    <button onclick="llamarAPI(`/transacciones/reconciliacion/${document.getElementById('q9-id').value}`, 'POST')">Ejecutar Q9</button>
                </div>
            </div>

            <div class="output-card">
                <h3>Respuesta de consola:</h3>
                <pre id="resultado">[SYS] Esperando accion... Seleccione un patron de consulta de arriba.</pre>
            </div>
        </div>

        <script>
            async function llamarAPI(ruta, metodo, body) {
                const pre = document.getElementById('resultado');
                pre.style.color = '#aaaaaa';
                pre.innerText = "[SYS] Ejecutando consulta contra la base de datos...";
                const start_time = performance.now();
                try {
                    const opciones = { method: metodo };
                    if (body) {
                        opciones.headers = { 'Content-Type': 'application/json' };
                        opciones.body = JSON.stringify(body);
                    }
                    const response = await fetch(ruta, opciones);
                    const data = await response.json();
                    const end_time = performance.now();
                    const tiempo_ms = (end_time - start_time).toFixed(2);
                    
                    pre.style.color = response.ok ? '#00ff00' : '#ff3333';
                    let output = `[LATENCIA RED Y MOTOR]: ${tiempo_ms} ms\n`;
                    output += `--------------------------------------------------\n`;
                    output += JSON.stringify(data, null, 4);
                    pre.innerText = output;
                } catch (error) {
                    const end_time = performance.now();
                    const tiempo_ms = (end_time - start_time).toFixed(2);
                    pre.style.color = '#ff3333';
                    pre.innerText = `[FALLO - ${tiempo_ms} ms]\n[ERROR] Error de conexion: ` + error;
                }
            }
        </script>
    </body>
    </html>
    """
    return HTMLResponse(content=html_content)
