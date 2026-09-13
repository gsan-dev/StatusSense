from app.analysis.health_score import calcular_health_score, normalizar_tendencia, normalizar_varianza


def test_normalizar_tendencia_sin_degradacion_es_100():
    assert normalizar_tendencia(0, 5) == 100.0
    assert normalizar_tendencia(-3, 5) == 100.0


def test_normalizar_tendencia_en_el_umbral_es_intermedia():
    score = normalizar_tendencia(5, 5)  # umbral = mitad del limite (2x umbral)
    assert 40 < score < 60


def test_normalizar_tendencia_muy_degradada_es_0():
    assert normalizar_tendencia(100, 5) == 0.0


def test_normalizar_varianza_estable_es_100():
    assert normalizar_varianza(1.0) == 100.0
    assert normalizar_varianza(0.5) == 100.0


def test_normalizar_varianza_muy_inestable_es_0():
    assert normalizar_varianza(4.0) == 0.0
    assert normalizar_varianza(10.0) == 0.0


def test_health_score_perfecto():
    assert calcular_health_score(100, 100, 100) == 100.0


def test_health_score_respeta_los_pesos():
    score = calcular_health_score(
        uptime_pct=100,
        tendencia_normalizada=0,
        varianza_normalizada=0,
        uptime_weight=0.5,
        degradation_weight=0.3,
        variance_weight=0.2,
    )
    assert score == 50.0


def test_health_score_esta_acotado_entre_0_y_100():
    assert calcular_health_score(0, 0, 0) == 0.0
    assert calcular_health_score(100, 100, 100) == 100.0
