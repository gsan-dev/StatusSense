from app.analysis.incidents import evaluate_incident

THRESHOLD = 60
SUDDEN_DROP = 40


def test_sin_incidente_si_el_score_es_saludable():
    ev = evaluate_incident([90, 92, 95], 96, THRESHOLD, SUDDEN_DROP, currently_open=False)
    assert not ev.should_open


def test_caida_subita_se_clasifica_correctamente():
    ev = evaluate_incident([95, 96, 94], 10, THRESHOLD, SUDDEN_DROP, currently_open=False)
    assert ev.should_open
    assert ev.incident_type == "sudden_outage"


def test_degradacion_progresiva_se_clasifica_correctamente():
    history = [95, 88, 80, 72, 65]
    ev = evaluate_incident(history, 55, THRESHOLD, SUDDEN_DROP, currently_open=False)
    assert ev.should_open
    assert ev.incident_type == "progressive_degradation"


def test_incidente_abierto_se_resuelve_al_recuperar_el_umbral():
    ev = evaluate_incident([40, 45, 50], 65, THRESHOLD, SUDDEN_DROP, currently_open=True)
    assert ev.should_resolve


def test_incidente_abierto_continua_si_sigue_por_debajo_del_umbral():
    ev = evaluate_incident([40, 45, 50], 55, THRESHOLD, SUDDEN_DROP, currently_open=True)
    assert not ev.should_resolve
    assert not ev.should_open


def test_primer_check_por_debajo_del_umbral_sin_historico():
    ev = evaluate_incident([], 30, THRESHOLD, SUDDEN_DROP, currently_open=False)
    assert ev.should_open
    assert ev.incident_type == "sudden_outage"  # cae desde el 100 implicito
