from app.criticidad import calcular_probabilidad
from app.criticidad import calcular_consecuencia


def test_sin_factores_la_probabilidad_es_baja():
    assert calcular_probabilidad(0) == "baja"
    

def test_un_factor_la_probabilidad_es_media():
    assert calcular_probabilidad(1) == "media"


def test_dos_factores_la_probabilidad_es_alta():
    assert calcular_probabilidad(2) == "alta"


def test_tres_factores_la_probabilidad_sigue_siendo_alta():
    assert calcular_probabilidad(3) == "alta"


def test_personas_la_consecuencia_es_alta():
    assert calcular_consecuencia(["personas"]) == "alta"


def test_ambiente_la_consecuencia_es_media():
    assert calcular_consecuencia(["ambiente"]) == "media"


def test_produccion_la_consecuencia_es_media():
    assert calcular_consecuencia(["produccion"]) == "media"


def test_dos_factores_la_consecuencia_es_alta():
    assert calcular_consecuencia(["ambiente", "personas"]) == "alta"


def test_sin_factores_la_consecuencia_es_baja():
    assert calcular_consecuencia([]) == "baja"
