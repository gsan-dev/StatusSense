"""Clasificacion de incidentes: caida subita vs degradacion progresiva."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, Optional

IncidentType = Literal["sudden_outage", "progressive_degradation"]


@dataclass
class IncidentEvaluation:
    should_open: bool = False
    should_resolve: bool = False
    incident_type: Optional[IncidentType] = None


def evaluate_incident(
    score_history: list[float],
    current_score: float,
    incident_threshold: float,
    sudden_drop_threshold: float,
    currently_open: bool,
) -> IncidentEvaluation:
    """Decide si hay que abrir, mantener o resolver un incidente.

    score_history: health scores previos (mas antiguo -> mas reciente),
        sin incluir `current_score`.
    """
    if currently_open:
        if current_score >= incident_threshold:
            return IncidentEvaluation(should_resolve=True)
        return IncidentEvaluation()

    if current_score >= incident_threshold:
        return IncidentEvaluation()

    previous_score = score_history[-1] if score_history else 100.0
    drop = previous_score - current_score

    if drop >= sudden_drop_threshold:
        return IncidentEvaluation(should_open=True, incident_type="sudden_outage")

    # Degradacion progresiva: la serie reciente muestra un descenso sostenido
    # (no hace falta que sea estrictamente monotono) antes de cruzar el umbral.
    window = score_history[-4:] + [current_score]
    if len(window) >= 3:
        deltas = [window[i + 1] - window[i] for i in range(len(window) - 1)]
        declining_steps = sum(1 for d in deltas if d < 0)
        if declining_steps >= max(2, len(deltas) - 1):
            return IncidentEvaluation(should_open=True, incident_type="progressive_degradation")

    # No hubo caida brusca puntual: por descarte se clasifica como progresiva.
    return IncidentEvaluation(should_open=True, incident_type="progressive_degradation")
