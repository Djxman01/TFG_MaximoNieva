import pytest

from app.criticidad import calcular_probabilidad
from app.criticidad import calcular_consecuencia
from app.criticidad import calcular_criticidad


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


# Las nueve celdas de la matriz. Cada línea es un caso:
# probabilidad, consecuencia y la criticidad que se espera.
@pytest.mark.parametrize(
    "probabilidad, consecuencia, esperada",
    [
        ("alta", "baja", "media"),
        ("alta", "media", "alta"),
        ("alta", "alta", "alta"),
        ("media", "baja", "baja"),
        ("media", "media", "media"),
        ("media", "alta", "alta"),
        ("baja", "baja", "baja"),
        ("baja", "media", "baja"),
        ("baja", "alta", "media"),
    ],
)
def test_matriz_de_criticidad(probabilidad, consecuencia, esperada):
    assert calcular_criticidad(probabilidad, consecuencia) == esperada
