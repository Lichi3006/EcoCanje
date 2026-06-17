FROM python:3.12-slim

WORKDIR /app

# Instalar dependencias del sistema mínimas
RUN apt-get update && apt-get install -y gcc && rm -rf /var/lib/apt/lists/*

# Copiar requirements e instalar
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Copiar el código del servicio
COPY . .

CMD ["uvicorn", "Panel_IoT:app", "--host", "0.0.0.0", "--port", "8001"]
