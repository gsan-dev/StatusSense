from app.analysis.trend import calcular_tendencia


def test_tendencia_estable_es_cero():
    latencias = [50.0] * 10
    assert abs(calcular_tendencia(latencias)) < 0.01


def test_tendencia_degradacion_progresiva():
    latencias = [50 + i * 5 for i in range(10)]  # pendiente real = 5
    pendiente = calcular_tendencia(latencias)
    assert pendiente > 4.5


def test_tendencia_mejora_es_negativa():
    latencias = [100 - i * 5 for i in range(10)]
    pendiente = calcular_tendencia(latencias)
    assert pendiente < -4.5


def test_tendencia_con_pocos_puntos_es_neutra():
    assert calcular_tendencia([50.0]) == 0.0
    assert calcular_tendencia([]) == 0.0


def test_tendencia_con_ruido_normal_no_dispara_falso_positivo():
    import random

    random.seed(42)
    latencias = [50 + random.uniform(-3, 3) for _ in range(30)]
    pendiente = calcular_tendencia(latencias)
    assert abs(pendiente) < 1.0
