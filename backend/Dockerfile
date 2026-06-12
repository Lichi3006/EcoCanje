FROM python:3.12-slim

WORKDIR /app

# Instalar dependencias del sistema para compilar drivers nativos (Cassandra)
RUN apt-get update && apt-get install -y gcc g++ libssl-dev && rm -rf /var/lib/apt/lists/*

# Copiar solo dependencias primero para optimizar caché
COPY requirements.txt .

# Instalar librerías de forma limpia
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]
