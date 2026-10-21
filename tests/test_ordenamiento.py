"""Pruebas de la regla de ordenamiento (HU-007), sin base de datos.

Las posiciones están en metros sobre un plano: el origen es (0, 0).
Con 60 km/h, cada kilómetro lleva 1 minuto de viaje, y así las cuentas son fáciles.
"""

import pytest

from app.ordenamiento import Candidato, minutos_de_tramo, proponer_orden, tiempo_de_recorrido


def activo(id, criticidad, x_km, y_km=0, telesupervision=False):
    return Candidato(id, f"A{id}", x_km * 1000, y_km * 1000, criticidad, telesupervision)


def ordenar(candidatos, disponible=10_000, velocidad=60, duracion=10):
    propuesta = proponer_orden(candidatos, 0, 0, velocidad, duracion, disponible)
    return propuesta, [paso.candidato.id for paso in propuesta.pasos]


# ---------- Unidades ----------


def test_tiempo_de_tramo_en_minutos():
    # 20 km a 40 km/h = media hora de viaje + 30 min de inspección.
    assert minutos_de_tramo(20_000, 40, 30) == pytest.approx(60)


# ---------- Criterio principal ----------


def test_la_criticidad_prevalece_sobre_la_distancia():
    # El de criticidad alta está a 50 km y el de media a 1 km: va primero el alta.
    _, orden = ordenar([activo(1, "media", 1), activo(2, "alta", 50)])
    assert orden == [2, 1]


def test_niveles_de_mayor_a_menor():
    _, orden = ordenar([activo(1, "baja", 1), activo(2, "media", 2), activo(3, "alta", 3)])
    assert orden == [3, 2, 1]


def test_dentro_del_nivel_el_mas_cercano_a_la_posicion_actual():
    # Desde el origen el más cercano es el 1 (2 km). Desde el 1, el más cercano es
    # el 3 (está a 1 km del 1), aunque el 2 esté más cerca del origen que el 3.
    candidatos = [activo(1, "alta", 2), activo(2, "alta", -2.5), activo(3, "alta", 3)]
    _, orden = ordenar(candidatos)
    assert orden == [1, 3, 2]


def test_desempate_primero_el_que_no_tiene_telesupervision():
    # Los dos están a 5 km del origen, en lados opuestos.
    con_tele = activo(1, "alta", 5, telesupervision=True)
    sin_tele = activo(2, "alta", -5, telesupervision=False)
    _, orden = ordenar([con_tele, sin_tele])
    assert orden == [2, 1]


# ---------- Tiempo disponible ----------


def test_un_activo_que_no_entra_queda_excluido_sin_orden():
    # Cada uno: 10 km (10 min) + 10 min de inspección = 20 min. Hay 30 min.
    propuesta, orden = ordenar([activo(1, "alta", 10), activo(2, "alta", 20)], disponible=30)
    assert orden == [1]
    assert [c.id for c in propuesta.excluidos] == [2]


def test_se_saltea_el_que_no_entra_y_sigue_con_el_siguiente():
    # Decisión del 12/10: saltear. El 2 (alta, lejos) no entra, pero el 3 (media,
    # cerca) sí, aunque sea de un nivel menor.
    candidatos = [activo(1, "alta", 5), activo(2, "alta", 200), activo(3, "media", 6)]
    propuesta, orden = ordenar(candidatos, disponible=40)
    assert orden == [1, 3]
    assert [c.id for c in propuesta.excluidos] == [2]


def test_dentro_del_nivel_entran_los_que_alcanzan():
    # 1: 10 km + 10 min = 20 min. Quedan 15 min: desde el 1, el 3 (a 5 km) lleva
    # 15 min y entra; el 2 (a 15 km) llevaría 25 y queda afuera.
    candidatos = [activo(1, "alta", 10), activo(2, "alta", 25), activo(3, "alta", 15)]
    propuesta, orden = ordenar(candidatos, disponible=35)
    assert orden == [1, 3]
    assert [c.id for c in propuesta.excluidos] == [2]


def test_el_tiempo_acumulado_puede_ser_igual_al_disponible():
    # "No superar" incluye el caso de igualdad: 10 km + 10 min = 20 min exactos.
    _, orden = ordenar([activo(1, "alta", 10)], disponible=20)
    assert orden == [1]


def test_sin_tiempo_suficiente_no_entra_ninguno():
    propuesta, orden = ordenar([activo(1, "alta", 1)], disponible=5)
    assert orden == []
    assert propuesta.minutos_totales == 0


def test_no_se_vuelve_a_un_nivel_mas_alto():
    # El 1 (alta) no entra desde el origen. Después de ir al 2 (media), el 1
    # quedaría más cerca, pero no se vuelve: la criticidad alta ya se procesó.
    candidatos = [activo(1, "alta", 30), activo(2, "media", 20)]
    propuesta, orden = ordenar(candidatos, disponible=39)
    assert orden == [2]
    assert [c.id for c in propuesta.excluidos] == [1]


def test_tiempos_acumulados_de_cada_paso():
    propuesta, _ = ordenar([activo(1, "alta", 10), activo(2, "alta", 30)])
    assert [p.minutos_acumulados for p in propuesta.pasos] == pytest.approx([20, 50])
    assert propuesta.minutos_totales == pytest.approx(50)


def test_tiempo_de_un_recorrido_en_orden_dado():
    # Ir primero al lejano y volver al cercano cuesta más.
    cercano, lejano = activo(1, "alta", 10), activo(2, "alta", 30)
    directo = tiempo_de_recorrido([cercano, lejano], 0, 0, 60, 10)
    ida_y_vuelta = tiempo_de_recorrido([lejano, cercano], 0, 0, 60, 10)
    assert directo == pytest.approx(50)
    assert ida_y_vuelta == pytest.approx(70)
