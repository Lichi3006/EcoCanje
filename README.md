<p align="center">
  <img src="media/Logo%20ECOCANJE.svg" alt="EcoCanje Logo" width="250">
</p>

<p align="center">
  <img src="https://img.shields.io/badge/Status-Etapa_2_Completada-success" alt="Status">
  <img src="https://img.shields.io/badge/Materia-Ingenier%C3%ADa_de_Datos_II-blue" alt="Stage">
</p>

<p align="center">
  <img src="https://img.shields.io/badge/Python-3776AB?style=for-the-badge&logo=python&logoColor=white" alt="Python">
  <img src="https://img.shields.io/badge/FastAPI-005571?style=for-the-badge&logo=fastapi" alt="FastAPI">
  <img src="https://img.shields.io/badge/MongoDB-4EA94B?style=for-the-badge&logo=mongodb&logoColor=white" alt="MongoDB">
  <img src="https://img.shields.io/badge/Redis-DC382D?style=for-the-badge&logo=redis&logoColor=white" alt="Redis">
  <img src="https://img.shields.io/badge/Cassandra-1287B1?style=for-the-badge&logo=apachecassandra&logoColor=white" alt="Cassandra">
  <img src="https://img.shields.io/badge/SQLite-003B57?style=for-the-badge&logo=sqlite&logoColor=white" alt="SQLite">
  <img src="https://img.shields.io/badge/Docker-2496ED?style=for-the-badge&logo=docker&logoColor=white" alt="Docker">
</p>

---

## <img src="https://api.iconify.design/heroicons/document-text.svg?color=white" width="24" height="24" align="center"/> Contexto Académico

Este repositorio constituye la implementación técnica final para la cátedra de **Ingeniería de Datos II**. Su objetivo académico principal es demostrar el dominio práctico de la **Persistencia Políglota**, diseñando una arquitectura donde cada patrón de consulta o carga de trabajo (Workload) se asigne estrictamente al motor de base de datos que resulte matemáticamente y algorítmicamente más eficiente para ese fin específico.

---

## <img src="https://api.iconify.design/heroicons/beaker.svg?color=white" width="24" height="24" align="center"/> Alcance de la Prueba de Concepto (PoC)

Debido a que este repositorio constituye una arquitectura de validación académica (Prueba de Concepto), ciertos procesos del ecosistema físico y visual se encuentran virtualizados (Mocking) o fuera de alcance para focalizar el desarrollo estrictamente en la Ingeniería de Datos:

- **Hardware y Botoneras Físicas:** Reemplazados por el Panel web del Edge IoT, el cual dispara los eventos lógicos del microcontrolador simulando la interacción ciudadana con la terminal.
- **Cámaras de Inteligencia Artificial:** La latencia y certeza de clasificación de materiales (PET/Aluminio) está simulada mediante retardos matemáticos aleatorios en el código de la terminal, generando telemetría sintética.
- **Escaneo de Código QR:** La interacción óptica de la cámara del teléfono celular se abstrajo en una carga REST directa enviando el token (ej. `QR-A1B2C3`) contra el endpoint transaccional del backend.
- **Aplicación Móvil Ciudadana:** El front-end del celular (iOS/Android) no está implementado. El consumo de sus rutas (Mapas, Catálogo de Materiales e Historial de la Billetera) se audita puramente a nivel API a través del Panel del Backend.
- **Tableros Logísticos (Recolectores):** Las pantallas y ruteos GPS de los camiones de basura están fuera de alcance. El sistema se limita a calcular y exponer matemáticamente el semáforo de estado (Verde/Amarillo/Rojo) de los contenedores utilizando Redis, el cual es consumido crudo tanto por el sistema logístico como por la app móvil.

---

## <img src="https://api.iconify.design/heroicons/map.svg?color=white" width="24" height="24" align="center"/> Patrones de Acceso Implementados

El orquestador en la nube consolida los 9 patrones transaccionales definidos en el diseño conceptual, mapeados a su motor físico correspondiente:

- **[Q1] Búsqueda Geoespacial (MongoDB):** Resolución O(log N) mediante índices `2dsphere` para ubicar terminales cercanas por proximidad matemática (Haversine).
- **[Q2] Validación de Materiales (MongoDB):** Acceso atómico de ultra-baja latencia para consultar tarifas y materiales aceptados en el Edge.
- **[Q3] Semáforo de Capacidad en Vivo (Redis):** Caché en memoria operando en microsegundos para reportar si la terminal física está en estado Verde, Amarillo o Rojo, dictando el ruteo logístico y alertando a los ciudadanos.
- **[Q4] Validación Atómica QR (Redis):** Ejecución de scripts `Lua` para resolver la lógica de un solo uso (Anti-Replay) destruyendo el token efímero instantáneamente.
- **[Q5] Escritura Dual Inmutable (Cassandra + Mongo):** Patrón de persistencia que registra la transacción de reciclaje inmutablemente en el motor columnar y simultáneamente acredita el saldo económico en la billetera virtual.
- **[Q6] Historial Ciudadano (Cassandra):** Recuperación paginada del ledger físico ordenado cronológicamente para mostrar el extracto de entregas en la aplicación.
- **[Q7] Analítica de Saturaciones por Comuna (Cassandra):** Ingesta enriquecida de incidentes para que el Gobierno diagnostique cuellos de botella geográficos a gran escala.
- **[Q8] Ingesta de Telemetría IoT (Edge + Cassandra):** Sincronización masiva de eventos por lotes (Sync Daemon) desde la base SQLite del contenedor inteligente hacia la nube.
- **[Q9] Reconciliación Auditada (Mongo vs Cassandra):** Algoritmo de reparación de estado (Chaos Engineering). Recalcula el saldo actual comparando el estado vivo en RAM contra el registro inmutable histórico para sanear desincronizaciones de red.

---

## <img src="https://api.iconify.design/heroicons/server-stack.svg?color=white" width="24" height="24" align="center"/> Arquitectura de Datos y Lógica del Sistema

El sistema implementa una **Persistencia Políglota** estricta, derivando cada carga de trabajo transaccional al motor de base de datos que está matemáticamente optimizado para la tarea. Además, el Borde (Terminal Física) y la Nube (Backend) operan como **entidades arquitectónicamente independientes y desacopladas**; la caída o saturación de un lado no bloquea las operaciones vitales del otro.

### 1. El Borde (Edge Computing y SQLite)
La terminal física ("El Tacho") no depende de una conexión a internet constante para operar. 
- Utiliza **SQLite** como una bitácora de registro local de alta disponibilidad (análogo a la "caja negra" de un avión) para retener firmas criptográficas y acumular peso de forma persistente ante cortes de energía o caídas de red.
- Si la nube se cae, la terminal continúa recibiendo reciclaje de los usuarios con total normalidad.
- Implementa un proceso tipo daemon (`sync_daemon.py`) que purga el SQLite local únicamente cuando confirma la llegada exitosa de la telemetría al servidor en la nube **(Resolviendo el patrón Q8)**.

### 2. Flujo de Emisión de QR y Redis
Para prevenir la saturación óptica del código impreso y mitigar ataques de doble gasto (Double-Spending):
- **Short-Lived Handshake:** La terminal Edge, mediante una petición HTTP, envía la carga pesada (JSON con firmas ECDSA y métricas de los sensores) **al orquestador del Backend en la nube**. El backend guarda temporalmente este JSON en **Redis** y, como respuesta a esa misma petición HTTP, le devuelve a la terminal un Token efímero y ultra-liviano (ej. `QR-A1B2C3`), el cual es el único dato que finalmente la máquina física imprime como Código QR.
- **Validación Atómica (Q4):** Cuando el ciudadano escanea ese código y su celular envía el token (`QR-A1B2C3`) de regreso al backend, el servidor extrae el JSON original desde la clave de Redis (`handshake:QR-A1B2C3`) utilizando un script atómico **Lua** e inmediatamente la elimina (la cual tiene un TTL de 120 segundos). Esto impide matemáticamente que un mismo código físico pueda ser cobrado dos veces por distintos usuarios.
- **Semáforo Multi-Consumo (Q3):** A medida que la IoT sincroniza su telemetría con la Nube, el sistema actualiza de forma atómica la capacidad del tacho en la memoria RAM de **Redis** (ej. `HSET capacidad:T1`). Esto genera un semáforo de estado (Verde: Vacío, Amarillo: Alerta, Rojo: Lleno) que opera con latencia sub-milisegundo (O(1)). Gracias a esta arquitectura *In-Memory*, miles de teléfonos celulares y camiones recolectores pueden consultar frenéticamente si el tacho está lleno sin sobrecargar jamás los motores de base de datos en disco (Mongo/Cassandra), asegurando una experiencia fluida al usuario final.

### 3. Escritura Dual y Desacople
Una vez validado el código efímero en la capa caché, el sistema impacta financieramente el registro bifurcando los datos resolviendo el patrón de **Escritura Inmutable (Q5)**:
- **MongoDB (Operacional / OLTP):** Incrementa el saldo de incentivos del usuario de forma casi instantánea (`$inc`).
- **Apache Cassandra (Analítica / OLAP / Ledger):** Actúa como el gran libro mayor de contabilidad inmutable gubernamental. Registra anexos secuenciales (Append-Only) del peso, terminal y firma criptográfica. Nunca se borra una fila.

### 4. Reconciliación Financiera (Chaos Engineering)
Si el Datacenter sufriese una desincronización abrupta (ej. caída de MongoDB durante una escritura dual), el sistema cuenta con un algoritmo asíncrono de **Reconciliación (Q9)** que recalcula el saldo exacto del ciudadano cruzando los balances en memoria contra la sumatoria de todas las transacciones históricas en Cassandra.

---

## <img src="https://api.iconify.design/heroicons/device-phone-mobile.svg?color=white" width="24" height="24" align="center"/> Integración Externa (Aplicación Móvil)

Fuera del dominio central (Core Backend) se contempla la existencia de una Aplicación Móvil Ciudadana externa que consume los patrones expuestos por la API para proveer una experiencia fluida al usuario final:

- **Mapas en Vivo (Q1):** La App consulta el backend para renderizar marcadores de los tachos más cercanos en un radio métrico utilizando las coordenadas GPS del celular del usuario.
- **Catálogo y Tarifas (Q2):** La App muestra los materiales permitidos y el valor de canje actual consultando a MongoDB.
- **Disponibilidad de Tachos (Q3):** La App consume el semáforo en tiempo real alojado en Redis para advertirle al ciudadano si el contenedor destino se encuentra con saturación crítica (Rojo) antes de desplazarse hacia él.
- **Billetera y Extracto (Q6):** La App extrae desde Apache Cassandra la lista inmutable histórica de depósitos realizados por el ciudadano para generar su ticket y ver su evolución financiera.

---

## <img src="https://api.iconify.design/heroicons/folder-open.svg?color=white" width="24" height="24" align="center"/> Estructura de Directorios

El código fuente está segmentado en dos dominios lógicos principales, imitando la arquitectura distribuida del mundo real:

```text
📦 EcoCanje
 ┣ 📂 backend/               # Nube: Orquestador Central (FastAPI)
 ┃  ┣ 📂 rutas/              # Endpoints divididos por dominio (telemetria.py, transacciones.py)
 ┃  ┣ 📜 main.py             # Punto de entrada de la API y conexiones a DBs
 ┃  ┣ 📜 panel_backend.py    # UI HTML/JS para simular consultas del analista
 ┃  ┗ 📜 seed.py             # Script de inyección del catálogo maestro
 ┣ 📂 edge_service/          # Borde: Firmware simulado de la Terminal IoT
 ┃  ┣ 📜 Panel_IoT.py        # UI HTML/JS para simular la botonera de hardware
 ┃  ┣ 📜 terminal.py         # Lógica core C++/Python (Sensores, ECDSA, QR)
 ┃  ┗ 📜 sync_daemon.py      # Proceso en segundo plano para sincronizar a la nube
 ┗ 📜 docker-compose.yml     # Orquestación de infraestructura (Redis, Mongo, Cassandra)
```

---

## <img src="https://api.iconify.design/heroicons/rocket-launch.svg?color=white" width="24" height="24" align="center"/> Guía de Despliegue y Ejecución

Para levantar la infraestructura completa en cualquier computadora (Windows/Linux/Mac) con Docker instalado:

### Paso 1: Inicialización
Posicionarse en el directorio raíz del proyecto y compilar los contenedores en modo aislado:
```bash
docker compose up -d --build
```
*Nota Técnica: Apache Cassandra (JVM) requiere de 40 a 60 segundos de inicialización en memoria antes de aceptar conexiones. Se recomienda esperar este lapso.*

### Paso 2: Sembrado de Datos Base (Seeding)
Para inicializar el catálogo base (terminales, usuarios y tarifas), ejecutar:
```bash
docker compose exec backend python seed.py
```

### Paso 3: Interfaces de Interacción (Paneles Mock)
En un entorno de producción, las terminales no tendrían una página web y el backend solo respondería JSON. Sin embargo, para fines de auditoría y demostración académica, se construyeron dos **Paneles de Control (Mocks)** que permiten disparar los eventos y observar las bases de datos en tiempo real:

- **[Panel IoT Edge] (`http://localhost:8001`)**: 
  - *¿Para qué sirve?* Reemplaza la botonera física de chapa y la impresora de la máquina en la calle. 
  - Te permite simular que un ciudadano tira botellas (Sensores), emitir un Token y ejecutar el Daemon de sincronización manual para ver cómo el SQLite se vacía.
- **[Panel Nube Backend] (`http://localhost:8000`)**: 
  - *¿Para qué sirve?* Reemplaza a las aplicaciones móviles de los ciudadanos y a los tableros analíticos del gobierno. 
  - Te permite probar los 8 Patrones de Consulta (Q1-Q9) apretando un botón, además de incluir herramientas de Ingeniería de Caos (como apagar MongoDB en vivo para probar la resiliencia).