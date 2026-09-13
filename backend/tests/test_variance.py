from app.analysis.variance import calcular_variance_ratio, calcular_varianza


def test_varianza_estable_es_cero():
    assert calcular_varianza([50, 50, 50, 50]) == 0.0


def test_varianza_alta_con_fluctuaciones():
    v = calcular_varianza([10, 90, 20, 95, 15])
    assert v > 30


def test_varianza_con_pocos_puntos_es_cero():
    assert calcular_varianza([50.0]) == 0.0
    assert calcular_varianza([]) == 0.0


def test_variance_ratio_sin_baseline_es_neutro():
    assert calcular_variance_ratio(10.0, 0.0) == 1.0


def test_variance_ratio_igual_al_baseline():
    assert calcular_variance_ratio(10.0, 10.0) == 1.0


def test_variance_ratio_mas_inestable_que_el_baseline():
    assert calcular_variance_ratio(20.0, 10.0) == 2.0
