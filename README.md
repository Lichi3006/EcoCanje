<p align="center">
  <img src="media/Logo%20ECOCANJE.svg" alt="EcoCanje Logo" width="250">
</p>

<p align="center">
  <img src="https://img.shields.io/badge/Status-Work--In--Progress-orange" alt="Status">
  <img src="https://img.shields.io/badge/Stage-Etapa_2-yellow" alt="Stage">
</p>

<p align="center">
  <img src="https://img.shields.io/badge/Python-3776AB?style=for-the-badge&logo=python&logoColor=white" alt="Python">
  <img src="https://img.shields.io/badge/FastAPI-005571?style=for-the-badge&logo=fastapi" alt="FastAPI">
  <img src="https://img.shields.io/badge/MongoDB-4EA94B?style=for-the-badge&logo=mongodb&logoColor=white" alt="MongoDB">
  <img src="https://img.shields.io/badge/Redis-DC382D?style=for-the-badge&logo=redis&logoColor=white" alt="Redis">
  <img src="https://img.shields.io/badge/Cassandra-1287B1?style=for-the-badge&logo=apachecassandra&logoColor=white" alt="Cassandra">
  <img src="https://img.shields.io/badge/Docker-2496ED?style=for-the-badge&logo=docker&logoColor=white" alt="Docker">
</p>

---

## <img src="https://api.iconify.design/heroicons/document-text.svg?color=white" width="24" height="24" align="center"/> Sobre este Repositorio

**EcoCanje** es un ecosistema integral de reciclaje urbano. Sin embargo, este repositorio contiene **exclusivamente la capa de Ingeniería de Datos y el Backend** (API). No incluye el firmware C++ de los dispositivos IoT ni la interfaz visual de la aplicación móvil.

El objetivo central de este componente es actuar como el orquestador principal: procesar la telemetría de alta velocidad de los contenedores inteligentes y servir los datos transaccionales a la aplicación ciudadana con mínima latencia.

## <img src="https://api.iconify.design/heroicons/server-stack.svg?color=white" width="24" height="24" align="center"/> Arquitectura Políglota

El sistema está diseñado bajo el paradigma de persistencia políglota, aislando las cargas de trabajo según su naturaleza algorítmica:

- **MongoDB (Operacional / OLTP):** Estructura jerárquica desnormalizada para transacciones rápidas. Aloja el catálogo maestro de terminales y gestiona las búsquedas geoespaciales mediante índices `2dsphere`.
- **Redis (Caché / Telemetría IoT):** Base de datos en memoria para soportar el alto flujo de eventos físicos. Administra el estado de llenado de los contenedores (semáforo de disponibilidad) en tiempo real.
- **Apache Cassandra (Analítica / OLAP):** Motor columnar distribuido destinado a persistir el historial inmutable de depósitos para análisis analíticos a largo plazo.

## <img src="https://api.iconify.design/heroicons/rocket-launch.svg?color=white" width="24" height="24" align="center"/> Guía de Despliegue

Para ejecutar el entorno en una máquina local de forma aislada:

1. **Levantar la topología de red:**
   ```bash
   docker-compose up -d
   ```

2. **Inyectar índices y catálogo (Seeding):**
   Dentro del contenedor del backend, es mandatorio inicializar los índices espaciales para evitar el bloqueo por escaneo O(N) del motor de MongoDB.
   ```bash
   cd backend
   python seed.py
   ```

3. **Ejecutar el servidor API:**
   ```bash
   uvicorn main:app --reload --host 0.0.0.0
   ```
   *La documentación interactiva de las rutas estará expuesta en: `http://localhost:8000/docs`*

## <img src="https://api.iconify.design/heroicons/map.svg?color=white" width="24" height="24" align="center"/> Patrones de Acceso Implementados

- **[Q1] Búsqueda Geoespacial Dinámica:** Resolución matemática O(log N) mediante fórmula de Haversine (`$nearSphere`) y cuadrículas de GeoHashing.
- **[Q2] Validación de Materiales Autorizados:** Acceso atómico instantáneo O(1) vía índice B-Tree para control de UI en la aplicación móvil.