"""Pruebas de creación de rondas (HU-005) y selección de activos (HU-006)."""

from decimal import Decimal

from app.catalogos import BASES
from tests.ayudas import DATOS_RONDA_024, crear_ronda, ids_de_activos


# ---------- HU-005 ----------


def test_crear_una_ronda(como_lider, semilla):
    ronda = crear_ronda(como_lider, semilla, codigos=[])
    assert ronda.estado == "borrador"
    assert ronda.tiempo_disponible == 240
    assert ronda.velocidad_media == Decimal("40")
    # El origen se guarda como coordenadas de la base elegida.
    assert (float(ronda.origen_x), float(ronda.origen_y)) == BASES["Base Norte"]
    assert ronda.usuario.rol == "lider"


def test_la_ronda_creada_aparece_en_la_lista(como_lider, semilla):
    ronda = crear_ronda(como_lider, semilla, codigos=[])
    pagina = como_lider.get("/rondas")
    assert ronda.numero in pagina.text
    assert "Base Norte" in pagina.text
    assert "240 min" in pagina.text


def test_faltan_datos_al_crear_la_ronda(como_lider, semilla):
    datos = {**DATOS_RONDA_024, "fecha_planificada": "", "origen": "", "tiempo_disponible": "0"}
    respuesta = como_lider.post("/rondas", data=datos)
    assert respuesta.status_code == 400
    assert "Falta la fecha planificada" in respuesta.text
    assert "Falta el origen del recorrido" in respuesta.text
    assert "tiempo disponible" in respuesta.text
    assert como_lider.get("/rondas").text.count("Planificar") == 0


def test_el_operador_no_puede_crear_rondas(como_operador):
    assert como_operador.get("/rondas").status_code == 403
    assert como_operador.post("/rondas", data=DATOS_RONDA_024).status_code == 403


# ---------- HU-006 ----------


def test_seleccionar_activos(como_lider, semilla):
    ronda = crear_ronda(como_lider, semilla, codigos=["Pozo A-14", "Pozo A-08"])
    assert sorted(ra.activo.codigo for ra in ronda.activos) == ["Pozo A-08", "Pozo A-14"]
    assert all(ra.estado_atencion == "pendiente" for ra in ronda.activos)


def test_un_activo_no_se_agrega_dos_veces(como_lider, semilla):
    ronda = crear_ronda(como_lider, semilla, codigos=[])
    id_a14 = ids_de_activos(semilla, ["Pozo A-14"])[0]
    como_lider.post(f"/rondas/{ronda.id}/activos", data={"activos": [id_a14, id_a14]})
    como_lider.post(f"/rondas/{ronda.id}/activos", data={"activos": [id_a14]})
    semilla.expire_all()
    assert len(ronda.activos) == 1


def test_quitar_un_activo_antes_de_la_ronda(como_lider, semilla):
    ronda = crear_ronda(como_lider, semilla, codigos=["Pozo A-14", "Pozo A-08"])
    como_lider.post(
        f"/rondas/{ronda.id}/activos", data={"activos": ids_de_activos(semilla, ["Pozo A-14"])}
    )
    semilla.expire_all()
    assert [ra.activo.codigo for ra in ronda.activos] == ["Pozo A-14"]


def test_un_activo_inactivo_no_se_puede_seleccionar(como_lider, semilla):
    ronda = crear_ronda(como_lider, semilla, codigos=["Pozo D-05"])  # inactivo
    assert ronda.activos == []


def test_la_planificacion_muestra_los_activos(como_lider, semilla):
    ronda = crear_ronda(como_lider, semilla)
    pagina = como_lider.get(f"/rondas/{ronda.id}")
    assert pagina.status_code == 200
    assert "Pozo C-07" in pagina.text
    assert "5 activos seleccionados" in pagina.text


def test_no_se_modifica_una_ronda_que_no_esta_en_borrador(como_lider, semilla):
    ronda = crear_ronda(como_lider, semilla, codigos=["Pozo A-14"])
    ronda.estado = "planificada"
    semilla.commit()
    respuesta = como_lider.post(f"/rondas/{ronda.id}/activos", data={"activos": []})
    assert respuesta.status_code == 409
    semilla.expire_all()
    assert len(ronda.activos) == 1
