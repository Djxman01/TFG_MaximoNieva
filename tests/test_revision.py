"""Pruebas de la revisión, el ajuste y la confirmación del recorrido (HU-008)."""

from tests.ayudas import (
    MOTIVO_024,
    ORDEN_AJUSTADO_024,
    codigos_en_orden,
    ids_en_orden,
    ronda_con_propuesta,
    ronda_con_recorrido,
)

PROPUESTO_024 = ["Pozo A-14", "Pozo A-08", "Pozo B-03", "Batería 2"]


def test_la_revision_muestra_la_propuesta_y_el_recorrido_ajustado(como_lider, semilla):
    ronda = ronda_con_propuesta(como_lider, semilla)
    pagina = como_lider.get(f"/rondas/{ronda.id}/revision")
    assert pagina.status_code == 200
    assert "Propuesta del sistema" in pagina.text
    assert "Recorrido ajustado" in pagina.text
    assert "subió" not in pagina.text


def test_mover_una_parada_con_las_flechas(como_lider, semilla):
    ronda = ronda_con_propuesta(como_lider, semilla)
    orden = ids_en_orden(ronda, PROPUESTO_024)
    bateria = orden[3]
    respuesta = como_lider.post(
        f"/rondas/{ronda.id}/revision/mover",
        data={"orden": orden, "movimiento": f"arriba:{bateria}"},
    )
    assert respuesta.status_code == 200
    assert "subió 1" in respuesta.text
    # Mover no guarda nada: la base sigue sin orden planificado.
    semilla.expire_all()
    assert all(ra.orden_planificado is None for ra in ronda.activos)


def test_confirmar_sin_cambios_no_pide_motivo(como_lider, semilla):
    ronda = ronda_con_recorrido(como_lider, semilla, codigos=PROPUESTO_024, motivo="")
    assert codigos_en_orden(ronda, "orden_planificado") == PROPUESTO_024
    assert all(ra.motivo_ajuste is None for ra in ronda.activos)


def test_confirmar_un_ajuste_sin_motivo_es_rechazado(como_lider, semilla):
    ronda = ronda_con_propuesta(como_lider, semilla)
    respuesta = como_lider.post(
        f"/rondas/{ronda.id}/revision",
        data={"orden": ids_en_orden(ronda, ORDEN_AJUSTADO_024), "motivo": "   "},
    )
    assert respuesta.status_code == 400
    assert "indicá el motivo del ajuste" in respuesta.text
    semilla.expire_all()
    assert all(ra.orden_planificado is None for ra in ronda.activos)


def test_confirmar_un_ajuste_guarda_las_dos_secuencias_y_el_motivo(como_lider, semilla):
    ronda = ronda_con_recorrido(como_lider, semilla)
    assert codigos_en_orden(ronda, "orden_planificado") == ORDEN_AJUSTADO_024
    # La propuesta original se conserva (HU-008 c2).
    assert codigos_en_orden(ronda, "orden_propuesto") == PROPUESTO_024
    motivos = {ra.activo.codigo: ra.motivo_ajuste for ra in ronda.activos}
    assert motivos["Batería 2"] == MOTIVO_024
    assert motivos["Pozo A-14"] is None  # no cambió de lugar


def test_el_ajuste_de_la_ronda_024_tarda_225_minutos(como_lider, semilla):
    ronda = ronda_con_recorrido(como_lider, semilla)
    pagina = como_lider.get(f"/rondas/{ronda.id}/confirmacion").text
    assert "225 min" in pagina


def test_no_se_puede_agregar_un_activo_excluido_al_ajustar(como_lider, semilla):
    ronda = ronda_con_propuesta(como_lider, semilla)
    orden = ids_en_orden(ronda, PROPUESTO_024 + ["Pozo C-07"])
    respuesta = como_lider.post(
        f"/rondas/{ronda.id}/revision", data={"orden": orden, "motivo": "x"}
    )
    assert respuesta.status_code == 400


def test_sin_propuesta_no_hay_revision(como_lider, semilla):
    from tests.ayudas import crear_ronda

    ronda = crear_ronda(como_lider, semilla)
    assert como_lider.get(f"/rondas/{ronda.id}/revision").status_code == 409


def test_se_puede_volver_a_revisar_antes_de_programar(como_lider, semilla):
    ronda = ronda_con_recorrido(como_lider, semilla)
    pagina = como_lider.get(f"/rondas/{ronda.id}/revision").text
    # Muestra el ajuste ya confirmado y su motivo.
    assert "subió 2" in pagina
    assert MOTIVO_024 in pagina
