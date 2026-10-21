"""Pruebas de la propuesta de orden en la aplicación (HU-007)."""

from sqlalchemy import select

from app.models import Activo
from tests.ayudas import codigos_en_orden, crear_ronda, ids_de_activos


def generar(cliente, db, ronda):
    respuesta = cliente.post(f"/rondas/{ronda.id}/propuesta", follow_redirects=False)
    db.expire_all()
    return respuesta


def test_ronda_024_reproduce_el_orden_del_documento(como_lider, semilla):
    ronda = crear_ronda(como_lider, semilla)
    assert generar(como_lider, semilla, ronda).status_code == 303
    assert codigos_en_orden(ronda) == ["Pozo A-14", "Pozo A-08", "Pozo B-03", "Batería 2"]


def test_c07_queda_en_la_ronda_sin_orden(como_lider, semilla):
    ronda = crear_ronda(como_lider, semilla)
    generar(como_lider, semilla, ronda)
    c07 = next(ra for ra in ronda.activos if ra.activo.codigo == "Pozo C-07")
    assert c07.orden_propuesto is None
    assert c07.criticidad.categoria == "baja"


def test_la_pantalla_muestra_215_minutos_y_el_excluido(como_lider, semilla):
    ronda = crear_ronda(como_lider, semilla)
    generar(como_lider, semilla, ronda)
    pagina = como_lider.get(f"/rondas/{ronda.id}").text
    assert "215 min" in pagina
    assert "fuera por tiempo disponible" in pagina
    assert "Revisar y confirmar" in pagina


def test_la_criticidad_queda_congelada_al_generar(como_lider, semilla):
    ronda = crear_ronda(como_lider, semilla)
    generar(como_lider, semilla, ronda)
    a14 = semilla.scalars(select(Activo).where(Activo.codigo == "Pozo A-14")).one()
    # Se reevalúa el activo después de planificar: pasa a Baja.
    como_lider.post(f"/activos/{a14.id}/criticidad", data={}, follow_redirects=False)
    semilla.expire_all()
    assert a14.criticidad_vigente().categoria == "baja"
    ra_a14 = next(ra for ra in ronda.activos if ra.activo_id == a14.id)
    assert ra_a14.criticidad.categoria == "alta"  # la de la ronda no cambia


def test_activo_sin_evaluar_impide_generar_la_propuesta(como_lider, semilla):
    ronda = crear_ronda(como_lider, semilla, codigos=["Pozo A-14", "Pozo A-21"])
    respuesta = generar(como_lider, semilla, ronda)
    assert respuesta.status_code == 400
    assert "información incompleta" in respuesta.text
    assert "Pozo A-21" in respuesta.text
    assert all(ra.orden_propuesto is None for ra in ronda.activos)


def test_cambiar_la_seleccion_anula_la_propuesta(como_lider, semilla):
    ronda = crear_ronda(como_lider, semilla)
    generar(como_lider, semilla, ronda)
    como_lider.post(
        f"/rondas/{ronda.id}/activos",
        data={"activos": ids_de_activos(semilla, ["Pozo A-14", "Pozo A-08"])},
    )
    semilla.expire_all()
    assert all(ra.orden_propuesto is None for ra in ronda.activos)
    assert all(ra.criticidad_activo_id is None for ra in ronda.activos)


def test_con_mas_tiempo_entran_todos(como_lider, semilla):
    ronda = crear_ronda(como_lider, semilla, tiempo_disponible="400")
    generar(como_lider, semilla, ronda)
    assert codigos_en_orden(ronda)[-1] == "Pozo C-07"


def test_el_operador_no_puede_generar(como_operador):
    # El permiso se controla antes de buscar la ronda.
    assert como_operador.post("/rondas/1/propuesta").status_code == 403


def datos_del_mapa(html):
    import json
    import re

    bloque = re.search(r'<script id="datos-mapa" type="application/json">(.*?)</script>', html, re.S)
    return json.loads(bloque.group(1))


def test_el_mapa_ubica_los_activos_y_el_recorrido_propuesto(como_lider, semilla):
    ronda = crear_ronda(como_lider, semilla)
    generar(como_lider, semilla, ronda)
    mapa = datos_del_mapa(como_lider.get(f"/rondas/{ronda.id}").text)
    assert mapa["origen"]["nombre"] == "Base Norte"
    assert len(mapa["puntos"]) == 5
    assert len(mapa["ruta"]) == 4  # C-07 no forma parte del recorrido
    c07 = next(p for p in mapa["puntos"] if p["codigo"] == "Pozo C-07")
    assert c07["excluido"] is True
    # Coordenadas convertidas a latitud y longitud dentro de la faja 2.
    assert -32 < mapa["origen"]["lat"] < -31
    assert -69.5 < mapa["origen"]["lon"] < -68.5


def test_sin_propuesta_el_mapa_muestra_los_activos_sin_numero(como_lider, semilla):
    ronda = crear_ronda(como_lider, semilla)
    mapa = datos_del_mapa(como_lider.get(f"/rondas/{ronda.id}").text)
    assert mapa["ruta"] == []
    assert all(p["orden"] is None and not p["excluido"] for p in mapa["puntos"])
