from app.criticidad import calcular_probabilidad


def test_sin_factores_la_probabilidad_es_baja():
    assert calcular_probabilidad(0) == "baja"

def test_sin_factores_la_probabilidad_es_media():
    assert calcular_probabilidad(1) == "media"

def test_sin_factores_la_probabilidad_es_alta():
    assert calcular_probabilidad(2) == "alta"

def test_sin_factores_la_probabilidad_es_muyalta():
    assert calcular_probabilidad(3) == "alta"
