"""Pruebas del alta y la edición de activos (HU-002)."""

import pytest
from sqlalchemy import select

from app.models import Activo

DATOS = {
    "codigo": "Pozo Z-01",
    "tipo": "Pozo de gas",
    "coordenada_x": "2510000,50",
    "coordenada_y": "6520000",
    "estado": "activo",
    "telesupervision": "true",
    "condicion_acceso": "Camino de tierra",
}


def buscar(db, codigo):
    return db.scalars(select(Activo).where(Activo.codigo == codigo)).first()


def test_el_lider_da_de_alta_un_activo(como_lider, semilla):
    respuesta = como_lider.post("/activos", data=DATOS, follow_redirects=False)
    assert respuesta.status_code == 303
    activo = buscar(semilla, "Pozo Z-01")
    assert activo.tipo == "Pozo de gas"
    assert float(activo.coordenada_x) == pytest.approx(2_510_000.50)
    assert activo.telesupervision is True
    # Queda disponible para consulta (HU-002 c1 y c2).
    assert "Pozo Z-01" in como_lider.get("/activos").text


def test_faltan_datos_obligatorios(como_lider, semilla):
    datos = {**DATOS, "codigo": "", "tipo": "", "coordenada_x": "", "coordenada_y": ""}
    respuesta = como_lider.post("/activos", data=datos)
    assert respuesta.status_code == 400
    assert "Falta el código" in respuesta.text
    assert "Falta el tipo" in respuesta.text
    assert "Falta la ubicación" in respuesta.text


def test_no_se_repite_el_codigo(como_lider, semilla):
    respuesta = como_lider.post("/activos", data={**DATOS, "codigo": "Pozo A-14"})
    assert respuesta.status_code == 400
    assert "Ya existe un activo con el código Pozo A-14" in respuesta.text


def test_coordenadas_fuera_de_la_faja_se_rechazan(como_lider, semilla):
    # X e Y invertidos: es el error típico con la convención de EPSG.
    datos = {**DATOS, "coordenada_x": "6520000", "coordenada_y": "2510000"}
    respuesta = como_lider.post("/activos", data=datos)
    assert respuesta.status_code == 400
    assert "fuera de la faja 2" in respuesta.text


def test_la_ubicacion_se_puede_cargar_desde_gps(como_lider, semilla):
    datos = {**DATOS, "coordenada_x": "", "coordenada_y": "", "latitud": "-31,5", "longitud": "-69"}
    como_lider.post("/activos", data=datos, follow_redirects=False)
    activo = buscar(semilla, "Pozo Z-01")
    # En el meridiano central (−69°) el este es 2.500.000 m.
    assert float(activo.coordenada_x) == pytest.approx(2_500_000, abs=1)


def test_editar_un_activo(como_lider, semilla):
    activo = buscar(semilla, "Pozo C-02")
    datos = {
        **DATOS,
        "codigo": "Pozo C-02",
        "coordenada_x": "2493600",
        "coordenada_y": "6526400",
        "estado": "inactivo",
    }
    respuesta = como_lider.post(f"/activos/{activo.id}", data=datos, follow_redirects=False)
    assert respuesta.status_code == 303
    semilla.expire_all()
    activo = buscar(semilla, "Pozo C-02")
    assert activo.estado == "inactivo"
    assert activo.tipo == "Pozo de gas"


def test_al_editar_se_puede_dejar_el_mismo_codigo(como_lider, semilla):
    activo = buscar(semilla, "Pozo A-21")
    pagina = como_lider.get(f"/activos/{activo.id}/editar").text
    assert 'value="Pozo A-21"' in pagina
    assert "Posición actual: latitud" in pagina


def test_el_operador_no_gestiona_activos(como_operador, semilla):
    assert como_operador.get("/activos/nuevo").status_code == 403
    assert como_operador.post("/activos", data=DATOS).status_code == 403
    assert "Nuevo activo" not in como_operador.get("/activos").text
