"""Configuracion de StatusSense via variables de entorno.

Sin dependencias externas de configuracion: todo tiene un valor por defecto
razonable para que `docker run` funcione sin flags adicionales.
"""
from __future__ import annotations

import os
from pathlib import Path


def _env_int(name: str, default: int) -> int:
    raw = os.environ.get(name)
    if raw is None or raw == "":
        return default
    try:
        return int(raw)
    except ValueError:
        return default


def _env_float(name: str, default: float) -> float:
    raw = os.environ.get(name)
    if raw is None or raw == "":
        return default
    try:
        return float(raw)
    except ValueError:
        return default


class Settings:
    # Base de datos
    DB_PATH: str = os.environ.get("STATUSSENSE_DB_PATH", "data/statussense.db")

    # Servidor
    HOST: str = os.environ.get("STATUSSENSE_HOST", "0.0.0.0")
    PORT: int = _env_int("STATUSSENSE_PORT", 8080)

    # Scheduler / checks
    CHECK_DEFAULT_INTERVAL: int = _env_int("CHECK_DEFAULT_INTERVAL", 60)
    CHECK_TIMEOUT_SECONDS: float = _env_float("CHECK_TIMEOUT_SECONDS", 10.0)

    # Motor de analisis: tamano de la ventana movil (numero de checks)
    ANALYSIS_WINDOW_SIZE: int = _env_int("ANALYSIS_WINDOW_SIZE", 20)
    # Pendiente (ms por check) a partir de la cual se considera degradacion
    TREND_SLOPE_THRESHOLD: float = _env_float("TREND_SLOPE_THRESHOLD", 5.0)
    # Caida de health score en una sola ventana para considerarla "subita"
    SUDDEN_DROP_THRESHOLD: float = _env_float("SUDDEN_DROP_THRESHOLD", 40.0)
    # Umbral de health score por debajo del cual se abre un incidente
    INCIDENT_HEALTH_THRESHOLD: float = _env_float("INCIDENT_HEALTH_THRESHOLD", 60.0)

    # Notificaciones
    TELEGRAM_BOT_TOKEN: str = os.environ.get("TELEGRAM_BOT_TOKEN", "")
    TELEGRAM_CHAT_ID: str = os.environ.get("TELEGRAM_CHAT_ID", "")

    @property
    def db_path(self) -> Path:
        path = Path(self.DB_PATH)
        path.parent.mkdir(parents=True, exist_ok=True)
        return path


settings = Settings()
