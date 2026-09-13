# 📡 StatusSense — Monitorización de Servicios con Detección Predictiva de Degradación

> Servicio ligero, autocontenido y desplegable con un solo `docker run` (o `docker-compose up`), que monitoriza la disponibilidad de tus servicios (HTTP, TCP, DNS, ping) y, a diferencia de herramientas como Uptime Kuma, no solo avisa cuando algo **ya se ha caído** — detecta patrones de **degradación progresiva** antes de que ocurra la caída total, usando análisis estadístico simple sobre el histórico de latencia.

---

## 📋 Tabla de contenidos

1. [Por qué este proyecto](#-por-qué-este-proyecto-y-no-un-clon-de-uptime-kuma)
2. [Problema que resuelve](#-problema-que-resuelve)
3. [Funcionalidades](#-funcionalidades)
4. [Arquitectura](#-arquitectura)
5. [Motor de detección predictiva](#-motor-de-detección-predictiva)
6. [Modelo de datos](#-modelo-de-datos)
7. [API](#-api)
8. [Stack tecnológico](#-stack-tecnológico)
9. [Estructura del repositorio](#-estructura-del-repositorio)
10. [Guía de instalación y ejecución](#-guía-de-instalación-y-ejecución)
11. [Exportar / importar configuración](#-exportar--importar-configuración)
12. [Testing](#-testing)
13. [Licencia](#-licencia)

---

## 🥊 Por qué este proyecto y no un clon de Uptime Kuma

Uptime Kuma resuelve muy bien la monitorización básica (multi-protocolo, notificaciones, páginas de estado públicas). Clonarlo tal cual no aporta nada distinto.

**El ángulo diferenciador de StatusSense es la capa de análisis predictivo:**

- Uptime Kuma te dice "esto está caído" (estado binario: up/down).
- StatusSense analiza el histórico de latencia de cada servicio y detecta **tendencias de deterioro** (aumento progresivo de latencia, incremento de varianza, errores intermitentes crecientes) para avisar **antes** de que el servicio caiga del todo.

## 🎯 Problema que resuelve

Los servicios no suelen caerse de golpe: normalmente hay una fase previa de degradación (latencia creciente, timeouts ocasionales) que nadie mira hasta que ya es una caída total. StatusSense usa esa ventana de datos, normalmente ignorada, para avisar de "este servicio se está degradando" con tiempo suficiente para actuar.

## ⚙️ Funcionalidades

### Núcleo
- Monitores HTTP(S), TCP, ping (ICMP vía comando del sistema) y DNS.
- Intervalos de comprobación configurables por monitor.
- Página de estado pública compartible.
- Notificaciones por Telegram y webhook genérico.
- Histórico de uptime y tiempos de respuesta.

### Diferenciadores
- **Detección de tendencia de degradación**: regresión lineal sobre la ventana móvil de latencia.
- **Detección de varianza anómala**: un servicio estable que empieza a fluctuar es una señal de alerta temprana.
- **Health Score (0-100)** por servicio: combina uptime, tendencia y varianza en un único número, con desglose consultable de cada señal.
- **Clasificación de incidentes**: distingue "caída súbita" de "degradación progresiva" en el histórico.
- **Timeline de fallos**: un vistazo (heatbar) a exactamente qué comprobaciones fallaron y por qué, con hora y motivo al pasar el ratón.
- **Notificaciones con verificación**: Telegram, webhook genérico y Discord (autodetectado por URL), con botón de prueba antes de depender de ellas en una caída real.
- **Comprobación manual y reinicio de histórico**: fuerza un check inmediato o borra el histórico de un monitor (sin perder su configuración) desde el propio panel.

## 🏗️ Arquitectura

```
Scheduler (APScheduler) --> Check Runner (HTTP/TCP/Ping/DNS, async)
       --> Motor de análisis (tendencia, varianza, health score)
       --> SQLite
       --> Backend API (FastAPI + WebSocket) --> Frontend (dashboard estático servido por FastAPI)
       --> Notificador (Telegram / Webhook)
```

## 🧠 Motor de detección predictiva

- **Tendencia**: regresión lineal (`numpy.polyfit`) de latencia frente al tiempo sobre una ventana móvil. Pendiente sostenida por encima de un umbral ⇒ "en degradación".
- **Varianza anómala**: desviación estándar de la ventana reciente comparada contra un baseline histórico estable del mismo monitor.
- **Health Score**: `uptime*0.5 + tendencia_normalizada*0.3 + varianza_normalizada*0.2` (pesos configurables por monitor).
- **Clasificación de incidentes**: caída de más de 40 puntos en una sola ventana ⇒ *sudden_outage*; descenso sostenido en varias ventanas antes de cruzar el umbral ⇒ *progressive_degradation*.

## 🗃️ Modelo de datos

SQLite con tablas `monitors`, `checks`, `health_snapshots`, `incidents` y `notification_channels`. Ver [backend/app/database.py](backend/app/database.py) para el esquema completo.

## 🔌 API

| Método | Endpoint | Descripción |
|---|---|---|
| `GET` | `/api/monitors` | Lista monitores con su health score actual |
| `POST` | `/api/monitors` | Crea un monitor |
| `GET` | `/api/monitors/{id}` | Detalle + histórico resumido |
| `PUT` | `/api/monitors/{id}` | Edita configuración |
| `DELETE` | `/api/monitors/{id}` | Elimina un monitor |
| `GET` | `/api/monitors/{id}/checks` | Histórico de checks (paginado) |
| `GET` | `/api/monitors/{id}/incidents` | Incidentes clasificados |
| `GET` | `/api/monitors/{id}/health-snapshots` | Desglose histórico del health score (uptime/tendencia/varianza) |
| `POST` | `/api/monitors/{id}/check-now` | Fuerza una comprobación inmediata |
| `DELETE` | `/api/monitors/{id}/history` | Reinicia el histórico del monitor (mantiene su configuración) |
| `GET` | `/api/status-page` | Datos públicos de la página de estado |
| `WS` | `/ws/live` | Stream en vivo de nuevos checks / health scores |
| `GET`/`POST` | `/api/notifications` | Canales de notificación (Telegram, webhook, Discord vía webhook) |
| `POST` | `/api/notifications/{id}/test` | Envía una notificación de prueba al canal |
| `GET` | `/api/export` | Exporta la configuración completa (monitores + canales) en JSON |
| `POST` | `/api/import` | Importa una configuración exportada previamente |

Documentación interactiva autogenerada en `/docs` (Swagger UI).

## 🧰 Stack tecnológico

| Capa | Tecnología |
|---|---|
| Backend | FastAPI (Python 3.12) + Uvicorn |
| Scheduler | APScheduler (AsyncIOScheduler) |
| Checks | httpx (HTTP async), socket (TCP), `ping`/`ping6` del sistema (ICMP), dnspython (DNS) |
| Análisis | NumPy (regresión lineal, varianza) |
| Base de datos | SQLite (sin dependencias externas) |
| Frontend | HTML/CSS/JS vanilla + Chart.js (vía CDN), servido como estáticos por FastAPI |
| Notificaciones | `httpx` (Telegram Bot API y webhooks genéricos) |
| Contenedor | Docker, imagen única `python:3.12-slim` |

> Nota: el documento de diseño original (`system.md`) proponía React + Vite + Recharts para el frontend. Se optó por HTML/JS vanilla + Chart.js para mantener el requisito de **ligereza** (una sola imagen, sin etapa de build de Node, panel servido directamente como estáticos), sin renunciar a gráficos en vivo ni a la actualización por WebSocket.

## 📁 Estructura del repositorio

```
StatusSense/
├── backend/
│   ├── app/
│   │   ├── main.py            # App FastAPI, montaje de estáticos, arranque scheduler
│   │   ├── config.py          # Configuración vía variables de entorno
│   │   ├── database.py        # Esquema SQLite y helpers de conexión
│   │   ├── models.py          # Esquemas Pydantic
│   │   ├── scheduler.py       # Orquestación de checks periódicos
│   │   ├── websocket_manager.py
│   │   ├── checks/            # Runners HTTP / TCP / Ping / DNS
│   │   ├── analysis/          # Tendencia, varianza, health score, incidentes
│   │   ├── notifications/     # Telegram, webhook, reglas de disparo
│   │   └── api/                # Routers FastAPI
│   ├── tests/                  # pytest
│   └── requirements.txt
├── frontend/
│   ├── index.html
│   ├── status.html              # Página de estado pública
│   └── static/{css,js}/
├── Dockerfile
├── docker-compose.yml
└── docs/
```

## 🚀 Guía de instalación y ejecución

### Docker (recomendado)

```bash
docker build -t statussense .
docker run -d --name statussense -p 8080:8080 -v statussense_data:/app/data statussense
```

Panel en `http://localhost:8080`, página de estado pública en `http://localhost:8080/status.html`.

### docker-compose

```bash
docker-compose up -d
```

### Modo desarrollo (sin Docker)

```bash
cd backend
python -m venv venv
venv\Scripts\activate   # Windows (usar `source venv/bin/activate` en Linux/Mac)
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8080
```

Abre `frontend/index.html` servido automáticamente en `http://localhost:8080/`.

### Configuración por variables de entorno

| Variable | Descripción | Default |
|---|---|---|
| `STATUSSENSE_DB_PATH` | Ruta del fichero SQLite | `data/statussense.db` |
| `CHECK_DEFAULT_INTERVAL` | Intervalo por defecto (segundos) | `60` |
| `TELEGRAM_BOT_TOKEN` | Token del bot para notificaciones | *(vacío)* |
| `TELEGRAM_CHAT_ID` | Chat destino de las notificaciones | *(vacío)* |

## 📤 Exportar / importar configuración

`GET /api/export` devuelve un JSON con todos los monitores y canales de notificación (sin histórico). `POST /api/import` acepta ese mismo JSON para recrear la configuración en otra máquina — pensado para migrar StatusSense entre hosts sin perder los monitores configurados.

## 🧪 Testing

```bash
cd backend
pip install -r requirements.txt
pytest tests/ -v
```

Incluye pruebas del motor de análisis con series de latencia sintéticas (degradación simulada frente a ruido normal), de los check runners y de la API.

## 📄 Licencia

MIT — usa, modifica y comparte libremente citando la fuente.
