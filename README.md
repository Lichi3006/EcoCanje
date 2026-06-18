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

## <img src="https://api.iconify.design/heroicons/document-text.svg?color=white" width="24" height="24" align="center"/> Sobre este Repositorio

**EcoCanje** es un ecosistema integral de reciclaje urbano diseñado bajo el paradigma de computación distribuida (Edge-to-Cloud). Este repositorio contiene la implementación técnica completa de la **Etapa 2**, abarcando la orquestación de bases de datos políglotas en la nube y el simulador de hardware (Edge) que opera en las calles.

El sistema fue diseñado con alta tolerancia a fallos, asincronía de datos y consistencia eventual para soportar desconexiones de red, evitando el bloqueo de terminales IoT y asegurando una trazabilidad inmutable mediante auditorías cruzadas.

---

## <img src="https://api.iconify.design/heroicons/server-stack.svg?color=white" width="24" height="24" align="center"/> Arquitectura de Datos y Lógica del Sistema

El sistema implementa una **Persistencia Políglota** estricta, derivando cada carga de trabajo transaccional al motor de base de datos que está matemáticamente optimizado para la tarea.

### 1. El Borde (Edge Computing y SQLite)
La terminal física ("El Tacho") no depende de una conexión a internet constante para operar. 
- Utiliza **SQLite** como una "caja negra" inmutable a nivel local para retener firmas criptográficas y acumular peso.
- Si la nube se cae, la terminal continúa recibiendo reciclaje de los usuarios.
- Implementa un proceso tipo daemon (`sync_daemon.py`) que purga el SQLite local únicamente cuando confirma la llegada de la telemetría a la nube.

### 2. Flujo de Emisión de QR y Redis
Para prevenir la saturación óptica del código QR impreso y mitigar ataques de doble gasto (Double-Spending):
- **Short-Lived Handshake:** La terminal sube la carga pesada (JSON con firmas ECDSA y métricas) a **Redis**, recibiendo a cambio un Token corto. 
- Al escanear el QR, el backend extrae el JSON usando un script atómico **Lua** e inmediatamente elimina la clave (TTL de 120s), impidiendo definitivamente que el mismo papel físico pueda ser reclamado dos veces.
- **Redis** también actúa como un semáforo de latencia ultra-baja (sub-milisegundo) para reportar la capacidad física actual de los contenedores a los camiones recolectores sin congestionar los motores pesados.

### 3. Escritura Dual (Patrón SAGA)
Una vez validado el QR efímero en la capa caché, el sistema impacta financieramente el registro bifurcando los datos:
- **MongoDB (Operacional / OLTP):** Incrementa el saldo de incentivos del usuario de forma casi instantánea (`$inc`) y permite las consultas geoespaciales (`2dsphere`) para ubicar terminales cercanas.
- **Apache Cassandra (Analítica / OLAP / Ledger):** Actúa como el gran libro mayor de contabilidad inmutable gubernamental. Registra anexos secuenciales (Append-Only) del peso, terminal y firma criptográfica. Nunca se borra una fila.

### 4. Reconciliación Financiera (Chaos Engineering)
Si el Datacenter sufriese una desincronización abrupta (ej. caída de MongoDB durante una escritura dual), el sistema cuenta con un algoritmo asíncrono de Reconciliación (Patrón Q9) que recalcula el saldo exacto del ciudadano cruzando los balances en memoria contra la sumatoria de todas las transacciones históricas en Cassandra.

---

## <img src="https://api.iconify.design/heroicons/rocket-launch.svg?color=white" width="24" height="24" align="center"/> Guía de Despliegue y Ejecución

Para levantar la infraestructura completa en cualquier computadora (Windows/Linux/Mac) con Docker instalado:

### Paso 1: Inicialización
Posicionarse en el directorio raíz del proyecto y compilar los contenedores en modo asilado:
```bash
docker compose up -d --build
```
*Nota Técnica: Apache Cassandra (JVM) requiere de 40 a 60 segundos de inicialización en memoria antes de aceptar conexiones. Se recomienda esperar este lapso.*

### Paso 2: Sembrado de Datos Base (Seeding)
Para inicializar el catálogo base (terminales, usuarios y tarifas), ejecutar:
```bash
docker compose exec backend python seed.py
```

### Paso 3: Interfaces de Interacción (Mocks)
Una vez estabilizada la red, los nodos de interacción quedan mapeados al Host principal:
- **[Panel IoT Edge]**: Acceder a `http://localhost:8001`. Representa físicamente a la terminal inteligente ubicada en la vía pública. Permite generar cargas asíncronas y emitir Tokens.
- **[Panel Nube Backend]**: Acceder a `http://localhost:8000`. Representa el clúster central del Datacenter. Contiene todos los métodos expuestos de los Patrones de Consulta (Q1 a Q9).

## <img src="https://api.iconify.design/heroicons/map.svg?color=white" width="24" height="24" align="center"/> Patrones de Acceso Implementados

- **[Q1] Búsqueda Geoespacial Dinámica:** Resolución matemática O(log N) mediante fórmula de Haversine (`$nearSphere`) y cuadrículas de GeoHashing.
- **[Q2] Validación de Materiales Autorizados:** Acceso atómico instantáneo O(1) vía índice B-Tree para control de UI en la aplicación móvil.