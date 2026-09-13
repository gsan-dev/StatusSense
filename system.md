# 📡 StatusSense — Monitorización de Servicios con Detección Predictiva de Degradación

> Servicio ligero, autocontenido y desplegable con un solo `docker-compose up`, que monitoriza la disponibilidad de tus servicios (HTTP, TCP, DNS, ping) y, a diferencia de herramientas como Uptime Kuma, no solo te avisa cuando algo **ya se ha caído** — detecta patrones de **degradación progresiva** antes de que ocurra la caída total, usando análisis estadístico simple sobre el histórico de latencia.

---

## 📋 Tabla de contenidos

1. [Por qué este proyecto y no un clon de Uptime Kuma](#-por-qué-este-proyecto-y-no-un-clon-de-uptime-kuma)
2. [Problema que resuelve](#-problema-que-resuelve)
3. [Funcionalidades](#-funcionalidades)
4. [Arquitectura](#-arquitectura)
5. [Diseño del motor de detección predictiva](#-diseño-del-motor-de-detección-predictiva)
6. [Modelo de datos](#-modelo-de-datos)
7. [Diseño de la API](#-diseño-de-la-api)
8. [Stack tecnológico](#-stack-tecnológico)
9. [Estructura del repositorio](#-estructura-del-repositorio)
10. [Requisitos de diseño (ligereza y portabilidad)](#-requisitos-de-diseño-ligereza-y-portabilidad)
11. [Roadmap y plan de commits](#-roadmap-y-plan-de-commits)
12. [Guía de instalación y ejecución](#-guía-de-instalación-y-ejecución)
13. [Uso del panel](#-uso-del-panel)
14. [Testing](#-testing)
15. [Mejoras futuras](#-mejoras-futuras)
16. [Licencia](#-licencia)

---

## 🥊 Por qué este proyecto y no un clon de Uptime Kuma

Uptime Kuma ya resuelve muy bien la monitorización básica (multi-protocolo, notificaciones, páginas de estado públicas) y es un estándar consolidado en el mundo self-hosted. Clonarlo tal cual no aporta nada distinto en un portfolio.

**El ángulo diferenciador de StatusSense es la capa de análisis predictivo:**

- Uptime Kuma te dice "esto está caído" (estado binario: up/down).
- StatusSense analiza el histórico de latencia y tiempos de respuesta de cada servicio, y detecta **tendencias de deterioro** (aumento progresivo de latencia, incremento de varianza, errores intermitentes crecientes) para avisarte **antes** de que el servicio caiga del todo.

Esto convierte el proyecto de "otro dashboard de uptime" a "un sistema con inteligencia aplicada a un problema operativo real" — que es exactamente lo que distingue a un candidato intermedio de uno que ya piensa en términos de ingeniería de producto.

---

## 🎯 Problema que resuelve

En cualquier infraestructura (homelab o empresa pequeña), los servicios no suelen caerse de golpe sin avisar — normalmente hay una fase previa de degradación (latencia creciente, timeouts ocasionales, errores 5xx esporádicos) que nadie mira hasta que ya es una caída total. Las herramientas de monitorización clásicas solo actúan quando el umbral binario "arriba/abajo" se cruza, perdiendo esa ventana de aviso temprano.

StatusSense usa esa ventana de datos que normalmente se ignora para dar una alerta de "este servicio se está degradando" con tiempo suficiente para actuar antes del incidente.

---

## ⚙️ Funcionalidades

### Núcleo (equivalente a lo esperable en cualquier monitor de este tipo)
- Monitores de tipo HTTP(S), TCP, ping (ICMP) y DNS.
- Intervalos de comprobación configurables por monitor.
- Página de estado pública compartible.
- Notificaciones (Telegram y webhook genérico, ampliable).
- Histórico de uptime y tiempos de respuesta.

### Diferenciadores (el valor añadido real del proyecto)
- **Detección de tendencia de degradación**: regresión simple sobre la ventana móvil de latencia; si la pendiente supera un umbral configurable de forma sostenida, se dispara una alerta de "degradación" distinta de la de "caída".
- **Detección de varianza anómala**: un servicio con latencia estable que empieza a fluctuar mucho es una señal de alerta temprana, aunque la media no haya subido todavía.
- **Score de salud (0-100) por servicio**: combina uptime reciente, tendencia de latencia y varianza en un único número fácil de interpretar de un vistazo, en vez de solo un semáforo verde/rojo.
- **Clasificación de incidentes**: distingue automáticamente entre "caída súbita" (fallo binario inmediato) y "degradación progresiva" (score bajando gradualmente durante horas/días) en el histórico, con etiquetas visuales distintas.

---

## 🏗️ Arquitectura

```
┌─────────────────────────────────────────────────────────────┐
│                        SCHEDULER                             │
│         (ejecuta cada monitor según su intervalo)            │
└───────────────────────────┬────────────────────────────────┘
                             │
              ┌──────────────▼──────────────┐
              │        CHECK RUNNER          │
              │  HTTP / TCP / Ping / DNS      │
              │  (async, sin bloquear)        │
              └──────────────┬──────────────┘
                             │  resultado (latencia, éxito/fallo)
              ┌──────────────▼──────────────┐
              │     MOTOR DE ANÁLISIS        │
              │  - Umbral binario (up/down)  │
              │  - Regresión de tendencia    │
              │  - Varianza móvil            │
              │  - Cálculo de Health Score   │
              └──────────────┬──────────────┘
                             │
              ┌──────────────▼──────────────┐
              │      PERSISTENCIA            │
              │      (SQLite)                │
              └──────────────┬──────────────┘
                             │
        ┌────────────────────┼────────────────────┐
        │                    │                    │
┌───────▼───────┐  ┌─────────▼─────────┐ ┌────────▼────────┐
│  Backend API   │  │  Notificador       │ │  Página de      │
│  (FastAPI +    │  │  (Telegram/Webhook)│ │  estado pública │
│   WebSocket)   │  │                    │ │  (estática)     │
└───────┬───────┘  └───────────────────┘ └─────────────────┘
        │
┌───────▼───────┐
│   Frontend     │
│  (React+Vite)  │
│  Dashboard en  │
│  vivo          │
└───────────────┘
```

---

## 🧠 Diseño del motor de detección predictiva

Esta es la pieza central que diferencia el proyecto, así que merece su propio desglose técnico.

### Datos de entrada
Por cada comprobación (check), se registra: `timestamp`, `monitor_id`, `success` (bool), `latency_ms`, `http_status` (si aplica).

### 1. Detección de tendencia (regresión lineal simple)
Sobre una ventana móvil (por ejemplo, las últimas N comprobaciones o últimas X horas), se ajusta una regresión lineal de `latencia` frente a `tiempo`:

```python
import numpy as np

def calcular_tendencia(latencias: list[float]) -> float:
    """
    Devuelve la pendiente de la regresión lineal.
    Pendiente positiva y sostenida = degradación progresiva.
    """
    x = np.arange(len(latencias))
    y = np.array(latencias)
    pendiente, _ = np.polyfit(x, y, 1)
    return pendiente
```

Si la pendiente supera un umbral configurable (por ejemplo, +5ms por comprobación de forma sostenida durante varias ventanas consecutivas), se marca el servicio como "en degradación".

### 2. Detección de varianza anómala
Se calcula la desviación estándar de la ventana móvil y se compara contra la desviación histórica "normal" de ese mismo servicio (baseline calculado en periodos estables). Un incremento significativo de varianza sin cambio en la media es indicio de inestabilidad intermitente.

### 3. Cálculo del Health Score
Combina tres señales normalizadas (0-100 cada una) en un score ponderado:

```python
def calcular_health_score(uptime_pct: float, tendencia_normalizada: float, varianza_normalizada: float) -> float:
    """
    uptime_pct: % de éxito en la ventana reciente (0-100)
    tendencia_normalizada: 100 si no hay degradación, baja según pendiente
    varianza_normalizada: 100 si es estable, baja según inestabilidad
    """
    return round(
        uptime_pct * 0.5 +
        tendencia_normalizada * 0.3 +
        varianza_normalizada * 0.2,
        1
    )
```

Los pesos son configurables por el usuario según qué le importe más monitorizar (un servicio crítico de baja latencia puede querer dar más peso a la tendencia; un servicio tolerante a latencia puede priorizar solo el uptime).

### 4. Clasificación de incidentes en el histórico
Cuando el Health Score cruza un umbral bajo, el sistema etiqueta el incidente como:
- **"Caída súbita"**: si el score cae abruptamente en una sola ventana (>40 puntos de golpe).
- **"Degradación progresiva"**: si el score ha ido bajando de forma sostenida durante varias ventanas antes de cruzar el umbral.

Esta distinción es visible en el histórico y en la página de estado, y es la funcionalidad que más conviene enseñar en una demo: mostrar cómo el sistema "vio venir" una caída con horas de antelación.

---

## 🗃️ Modelo de datos

```sql
CREATE TABLE monitors (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    type TEXT NOT NULL CHECK(type IN ('http', 'tcp', 'ping', 'dns')),
    target TEXT NOT NULL,          -- URL, IP:puerto, dominio...
    interval_seconds INTEGER NOT NULL DEFAULT 60,
    degradation_weight REAL DEFAULT 0.3,
    variance_weight REAL DEFAULT 0.2,
    uptime_weight REAL DEFAULT 0.5,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE checks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    monitor_id INTEGER NOT NULL REFERENCES monitors(id),
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    success BOOLEAN NOT NULL,
    latency_ms REAL,
    http_status INTEGER,
    error_message TEXT
);

CREATE TABLE health_snapshots (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    monitor_id INTEGER NOT NULL REFERENCES monitors(id),
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    health_score REAL NOT NULL,
    trend_slope REAL,
    variance_ratio REAL
);

CREATE TABLE incidents (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    monitor_id INTEGER NOT NULL REFERENCES monitors(id),
    started_at TIMESTAMP NOT NULL,
    resolved_at TIMESTAMP,
    incident_type TEXT CHECK(incident_type IN ('sudden_outage', 'progressive_degradation')),
    min_health_score REAL
);

CREATE TABLE notification_channels (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    type TEXT NOT NULL CHECK(type IN ('telegram', 'webhook')),
    config_json TEXT NOT NULL
);
```

---

## 🔌 Diseño de la API

| Método | Endpoint | Descripción |
|---|---|---|
| `GET` | `/api/monitors` | Lista todos los monitores con su health score actual |
| `POST` | `/api/monitors` | Crea un nuevo monitor |
| `GET` | `/api/monitors/{id}` | Detalle de un monitor + histórico |
| `PUT` | `/api/monitors/{id}` | Edita configuración (intervalo, pesos del score) |
| `DELETE` | `/api/monitors/{id}` | Elimina un monitor |
| `GET` | `/api/monitors/{id}/checks` | Histórico de checks (paginado) |
| `GET` | `/api/monitors/{id}/incidents` | Histórico de incidentes clasificados |
| `GET` | `/api/status-page` | Datos públicos para la página de estado |
| `WS` | `/ws/live` | Stream de actualizaciones en vivo (nuevo check, cambio de score) |
| `POST` | `/api/notifications` | Configura un canal de notificación |

---

## 🧰 Stack tecnológico

| Capa | Tecnología | Por qué |
|---|---|---|
| Backend | FastAPI (Python) | Async nativo, ideal para hacer checks concurrentes sin bloquear, WebSockets fáciles |
| Scheduler | APScheduler | Ligero, sin necesitar un broker externo tipo Celery/Redis para un proyecto de este tamaño |
| Checks HTTP/TCP/DNS | httpx (async), socket, dnspython | Librerías estándar, sin dependencias pesadas |
| Análisis | NumPy | Suficiente para regresión lineal y varianza, sin necesitar un framework de ML completo |
| Base de datos | SQLite | Cero configuración, un único fichero, perfecto para "ligero y autocontenido" |
| Frontend | React + Vite + Recharts | Gráficos de latencia/health score en tiempo real de forma sencilla |
| Notificaciones | python-telegram-bot, requests (webhook genérico) | Cobertura amplia sin añadir muchas dependencias |
| Contenedor | Docker (imagen única multi-stage) | Un solo `docker run`, sin docker-compose obligatorio para el caso más simple |

---

## 🪶 Requisitos de diseño (ligereza y portabilidad)

Dado que el objetivo explícito es que sea **ligero** y se levante con Docker fácilmente, estas son las restricciones de diseño a respetar durante todo el desarrollo:

- **Una sola imagen Docker** para backend + frontend compilado (el frontend se sirve como estáticos desde FastAPI), para que el caso de uso más simple sea `docker run -p 8080:8080 statussense`.
- **SQLite como única dependencia de datos** — nada de requerir PostgreSQL/Redis para el caso básico (se puede ofrecer como opción avanzada, pero no obligatoria).
- **Imagen base mínima**: `python:3.12-slim` o similar, evitando imágenes pesadas innecesarias.
- **Sin dependencias de servicios externos** para la funcionalidad core (las notificaciones externas como Telegram son opcionales, no bloqueantes).
- Objetivo de tamaño de imagen: por debajo de 200MB.

---

## 🗺️ Roadmap y plan de commits

### Fase 0 — Setup
- [ ] `chore: inicializar repositorio con estructura de carpetas`
- [ ] `chore: .gitignore, README/project.md inicial y licencia`
- [ ] `chore: configurar entorno virtual y requirements.txt`

### Fase 1 — Núcleo de monitorización
- [ ] `feat: modelo de datos y migraciones SQLite`
- [ ] `feat: check runner HTTP asíncrono`
- [ ] `feat: check runner TCP, ping y DNS`
- [ ] `feat: scheduler con APScheduler por intervalo de monitor`
- [ ] `test: pruebas unitarias de los check runners`

### Fase 2 — Motor de análisis predictivo
- [ ] `feat: cálculo de tendencia con regresión lineal`
- [ ] `feat: cálculo de varianza móvil y baseline`
- [ ] `feat: cálculo de health score ponderado`
- [ ] `feat: clasificación de incidentes (súbito vs progresivo)`
- [ ] `test: pruebas del motor de análisis con datos sintéticos`

### Fase 3 — Backend API
- [ ] `feat: endpoints CRUD de monitores`
- [ ] `feat: endpoints de histórico de checks e incidentes`
- [ ] `feat: WebSocket de actualizaciones en vivo`
- [ ] `docs: documentación automática Swagger`

### Fase 4 — Notificaciones
- [ ] `feat: integración con Telegram`
- [ ] `feat: soporte de webhook genérico`
- [ ] `feat: reglas de cuándo notificar (caída vs degradación)`

### Fase 5 — Frontend
- [ ] `feat: scaffold React + Vite`
- [ ] `feat: dashboard de monitores con health score visual`
- [ ] `feat: gráfico de latencia y tendencia por monitor`
- [ ] `feat: vista de histórico de incidentes clasificados`
- [ ] `feat: página de estado pública`
- [ ] `style: pulido visual del dashboard`

### Fase 6 — Empaquetado y despliegue
- [ ] `feat: Dockerfile multi-stage (build frontend + backend en una imagen)`
- [ ] `perf: optimización de tamaño de imagen`
- [ ] `docs: guía de despliegue con docker run y docker-compose`

### Fase 7 — Cierre
- [ ] `docs: capturas del dashboard y de una degradación detectada en vivo`
- [ ] `chore: limpieza final de código`

---

## 🚀 Guía de instalación y ejecución

### Requisitos
- Docker (única dependencia real para el usuario final)
- Para desarrollo: Python 3.12+, Node.js 18+

### Opción A — Ejecución directa con Docker (caso de uso objetivo)

```bash
docker run -d \
  --name statussense \
  -p 8080:8080 \
  -v statussense_data:/app/data \
  ghcr.io/tu-usuario/statussense:latest
```

Accede al panel en `http://localhost:2424`.

### Opción B — Con docker-compose (si quieres separar servicios o añadir opciones avanzadas)

```yaml
version: "3.8"
services:
  statussense:
    image: ghcr.io/tu-usuario/statussense:latest
    ports:
      - "2424:2424"
    volumes:
      - statussense_data:/app/data
    environment:
      - CHECK_DEFAULT_INTERVAL=60
      - TELEGRAM_BOT_TOKEN=
      - TELEGRAM_CHAT_ID=

volumes:
  statussense_data:
```

```bash
docker-compose up -d
```

### Opción C — Modo desarrollo (sin Docker)

```bash
# Backend
cd backend
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt
uvicorn main:app --reload --port 8080

# Frontend (en otra terminal)
cd frontend
npm install
npm run dev
```

---

## 🖥️ Uso del panel

- **Vista general**: tarjetas por monitor con su Health Score actual, color según estado (verde/ámbar/rojo, no solo binario).
- **Detalle de monitor**: gráfico de latencia en el tiempo, con la línea de tendencia superpuesta y marcadores de cuándo se detectó degradación.
- **Historial de incidentes**: lista distinguiendo visualmente caídas súbitas de degradaciones progresivas, con duración y score mínimo alcanzado.
- **Página de estado pública**: vista simplificada y compartible, pensada para usuarios finales, no para el administrador.

---

## 🧪 Testing

```bash
cd backend
pytest tests/ -v
```

Incluye pruebas con series de latencia sintéticas (generadas con ruido controlado) para validar que el motor de tendencia y varianza detecta correctamente los casos de degradación simulada frente a ruido normal.

---

## 🔮 IMPRESCINDIBLE A CREAR

- Poder de alguna forma exportar e importar configuraciones para poder pasar configs entre maquinas.

---

## 📄 Licencia

MIT — usa, modifica y comparte libremente citando la fuente.