FROM python:3.12-slim

# iputils-ping: necesario para los monitores de tipo "ping" (comando del sistema,
# evita depender de sockets raw / privilegios especiales).
RUN apt-get update \
    && apt-get install -y --no-install-recommends iputils-ping \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY backend/requirements.txt backend/requirements.txt
RUN pip install --no-cache-dir -r backend/requirements.txt

COPY backend/app backend/app
COPY frontend frontend

ENV STATUSSENSE_DB_PATH=/app/data/statussense.db \
    STATUSSENSE_HOST=0.0.0.0 \
    STATUSSENSE_PORT=8080

EXPOSE 8080
VOLUME ["/app/data"]

WORKDIR /app/backend
CMD ["python", "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8080"]
