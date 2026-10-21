"""Pruebas de la conversión de coordenadas (EPSG:5344 ↔ latitud y longitud)."""

import pytest

from app.coordenadas import a_lat_lon, desde_lat_lon


def test_el_meridiano_central_tiene_falso_este_de_2500000():
    # La faja 2 tiene meridiano central en −69° y falso este de 2.500.000 m.
    x_este, _ = desde_lat_lon(-31.5, -69.0)
    assert x_este == pytest.approx(2_500_000, abs=1)


def test_un_punto_al_oeste_del_meridiano_tiene_este_menor():
    x_oeste, _ = desde_lat_lon(-31.5, -69.3)
    assert x_oeste < 2_500_000


def test_x_es_el_este_y_y_es_el_norte():
    # Moverse hacia el sur baja el norte (y) y casi no cambia el este (x).
    x1, y1 = desde_lat_lon(-31.5, -69.0)
    x2, y2 = desde_lat_lon(-31.6, -69.0)
    assert y2 < y1
    assert x2 == pytest.approx(x1, abs=1)


def test_ida_y_vuelta_devuelve_el_mismo_punto():
    latitud, longitud = a_lat_lon(*desde_lat_lon(-31.45, -68.95))
    assert latitud == pytest.approx(-31.45, abs=1e-7)
    assert longitud == pytest.approx(-68.95, abs=1e-7)
