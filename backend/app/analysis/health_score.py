"""Calculo del Health Score (0-100) combinando uptime, tendencia y varianza."""
from __future__ import annotations


def normalizar_tendencia(pendiente_ms: float, umbral: float) -> float:
    """100 si no hay degradacion (pendiente <= 0), baja linealmente hasta 0
    cuando la pendiente alcanza 2x el umbral configurado o mas.
    """
    if pendiente_ms <= 0:
        return 100.0
    limite = umbral * 2
    if limite <= 0:
        return 100.0
    score = 100.0 * (1 - min(pendiente_ms, limite) / limite)
    return max(0.0, round(score, 1))


def normalizar_varianza(variance_ratio: float) -> float:
    """100 si la varianza es igual o menor que el baseline (ratio <= 1),
    baja linealmente hasta 0 cuando la varianza es 4x el baseline o mas.
    """
    if variance_ratio <= 1.0:
        return 100.0
    limite = 4.0
    score = 100.0 * (1 - min(variance_ratio - 1, limite - 1) / (limite - 1))
    return max(0.0, round(score, 1))


def calcular_health_score(
    uptime_pct: float,
    tendencia_normalizada: float,
    varianza_normalizada: float,
    uptime_weight: float = 0.5,
    degradation_weight: float = 0.3,
    variance_weight: float = 0.2,
) -> float:
    """Combina las tres senales normalizadas (0-100) en un score ponderado.

    uptime_pct: % de exito en la ventana reciente (0-100)
    tendencia_normalizada: 100 si no hay degradacion, baja segun pendiente
    varianza_normalizada: 100 si es estable, baja segun inestabilidad
    """
    total_weight = uptime_weight + degradation_weight + variance_weight
    if total_weight <= 0:
        total_weight = 1.0
    score = (
        uptime_pct * uptime_weight
        + tendencia_normalizada * degradation_weight
        + varianza_normalizada * variance_weight
    ) / total_weight
    return round(max(0.0, min(100.0, score)), 1)
