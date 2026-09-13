"""Deteccion de tendencia de degradacion mediante regresion lineal simple."""
from __future__ import annotations

import numpy as np


def calcular_tendencia(latencias: list[float]) -> float:
    """Devuelve la pendiente (ms por check) de la regresion lineal de la
    latencia frente al tiempo. Una pendiente positiva y sostenida indica
    degradacion progresiva; una pendiente cercana a 0 o negativa indica
    estabilidad o mejora.

    Requiere al menos 2 puntos; con menos, se asume estabilidad (0.0).
    """
    if len(latencias) < 2:
        return 0.0
    x = np.arange(len(latencias))
    y = np.array(latencias, dtype=float)
    pendiente, _ = np.polyfit(x, y, 1)
    return float(pendiente)
