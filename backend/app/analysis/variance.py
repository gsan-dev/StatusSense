"""Deteccion de varianza anomala en la latencia reciente."""
from __future__ import annotations

import numpy as np


def calcular_varianza(latencias: list[float]) -> float:
    """Desviacion estandar de una serie de latencias."""
    if len(latencias) < 2:
        return 0.0
    return float(np.std(np.array(latencias, dtype=float)))


def calcular_variance_ratio(varianza_actual: float, varianza_baseline: float) -> float:
    """Ratio entre la varianza reciente y un baseline historico estable.

    1.0 = igual que el baseline, >1.0 = mas inestable de lo habitual.
    Si no hay baseline (servicio nuevo), se asume 1.0 (neutro).
    """
    if varianza_baseline <= 0:
        return 1.0
    return varianza_actual / varianza_baseline
