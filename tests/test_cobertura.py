"""Pruebas del cálculo de cobertura (HU-012), sin base de datos."""

import pytest

from app.cobertura import ActivoParaCobertura as A
from app.cobertura import calcular_cobertura


def test_ronda_sin_inspecciones_tiene_cobertura_cero():
    cobertura = calcular_cobertura([A("alta", "pendiente"), A("baja", "pendiente")])
    assert cobertura.operativa == 0
    assert cobertura.ponderada == 0


def test_todo_inspeccionado_da_cien_por_ciento():
    cobertura = calcular_cobertura([A("alta", "inspeccionado"), A("baja", "inspeccionado")])
    assert cobertura.operativa == 1
    assert cobertura.ponderada == 1


def test_operativa_y_ponderada_difieren_segun_la_criticidad():
    # Se inspeccionó el alta (peso 3) y no el bajo (peso 1).
    cobertura = calcular_cobertura([A("alta", "inspeccionado"), A("baja", "pendiente")])
    assert cobertura.operativa == pytest.approx(0.5)
    assert cobertura.ponderada == pytest.approx(3 / 4)


def test_inspeccionar_el_de_menor_criticidad_pesa_menos():
    cobertura = calcular_cobertura([A("alta", "pendiente"), A("baja", "inspeccionado")])
    assert cobertura.operativa == pytest.approx(0.5)
    assert cobertura.ponderada == pytest.approx(1 / 4)


def test_no_accesible_queda_en_el_total_y_se_informa_aparte():
    cobertura = calcular_cobertura(
        [A("alta", "inspeccionado"), A("media", "no_accesible"), A("media", "pendiente")]
    )
    assert cobertura.total == 3
    assert cobertura.no_accesibles == 1
    assert cobertura.pendientes == 1
    assert cobertura.operativa == pytest.approx(1 / 3)
    assert cobertura.ponderada == pytest.approx(3 / 7)


def test_ronda_024_completa_menos_el_excluido():
    # Ronda #024: A-14 y A-08 (alta), B-03 y Batería 2 (media) inspeccionados;
    # C-07 (baja) quedó fuera por tiempo y sigue pendiente.
    activos = [
        A("alta", "inspeccionado"), A("alta", "inspeccionado"),
        A("media", "inspeccionado"), A("media", "inspeccionado"),
        A("baja", "pendiente"),
    ]
    cobertura = calcular_cobertura(activos)
    assert cobertura.operativa == pytest.approx(4 / 5)
    assert cobertura.ponderada == pytest.approx(10 / 11)
    assert cobertura.por_criticidad["alta"] == {"total": 2, "inspeccionados": 2}


def test_ronda_vacia_no_divide_por_cero():
    cobertura = calcular_cobertura([])
    assert (cobertura.operativa, cobertura.ponderada) == (0, 0)
