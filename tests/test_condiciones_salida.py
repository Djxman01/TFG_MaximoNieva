"""Pruebas de las condiciones de salida y la confirmación de la ronda (HU-014)."""

from tests.ayudas import CONDICIONES_APTAS, ronda_con_propuesta, ronda_con_recorrido, ronda_programada


def confirmar(cliente, ronda, **cambios):
    return cliente.post(
        f"/rondas/{ronda.id}/confirmacion", data={**CONDICIONES_APTAS, **cambios}
    )


def test_sin_recorrido_confirmado_vuelve_a_la_revision(como_lider, semilla):
    ronda = ronda_con_propuesta(como_lider, semilla)
    respuesta = como_lider.get(f"/rondas/{ronda.id}/confirmacion", follow_redirects=False)
    assert respuesta.status_code == 303
    assert respuesta.headers["location"].endswith("/revision")


def test_hay_que_registrar_las_tres_condiciones(como_lider, semilla):
    ronda = ronda_con_recorrido(como_lider, semilla)
    respuesta = confirmar(como_lider, ronda, condicion_acceso="", condicion_conectividad="")
    assert respuesta.status_code == 400
    assert "Estado de los accesos" in respuesta.text
    assert "Conectividad" in respuesta.text
    semilla.expire_all()
    assert ronda.estado == "borrador"


def test_una_condicion_no_apta_impide_confirmar_e_informa_cual(como_lider, semilla):
    ronda = ronda_con_recorrido(como_lider, semilla)
    respuesta = confirmar(como_lider, ronda, condicion_clima="no_apto")
    assert respuesta.status_code == 409
    assert "Clima está en No apto" in respuesta.text
    semilla.expire_all()
    assert ronda.estado == "borrador"
    # La condición queda registrada igual.
    assert ronda.condicion_clima == "no_apto"


def test_dos_condiciones_no_aptas_se_informan_juntas(como_lider, semilla):
    ronda = ronda_con_recorrido(como_lider, semilla)
    respuesta = confirmar(
        como_lider, ronda, condicion_clima="no_apto", condicion_conectividad="no_apto"
    )
    assert "Clima, Conectividad están en No apto" in respuesta.text


def test_condiciones_aptas_o_condicionadas_programan_la_ronda(como_lider, semilla):
    ronda = ronda_programada(como_lider, semilla)
    assert ronda.estado == "planificada"
    assert (ronda.condicion_clima, ronda.condicion_acceso, ronda.condicion_conectividad) == (
        "condicionado", "condicionado", "apto",
    )


def test_las_condiciones_no_cambian_el_orden(como_lider, semilla):
    from tests.ayudas import ORDEN_AJUSTADO_024, codigos_en_orden

    ronda = ronda_programada(como_lider, semilla)
    assert codigos_en_orden(ronda, "orden_planificado") == ORDEN_AJUSTADO_024


def test_la_ronda_programada_muestra_sus_condiciones(como_lider, semilla):
    ronda = ronda_programada(como_lider, semilla)
    pagina = como_lider.get(f"/rondas/{ronda.id}/detalle").text
    assert "Condicionado" in pagina
    assert "Lluvias previstas para la mañana." in pagina


def test_una_ronda_programada_ya_no_se_modifica(como_lider, semilla):
    ronda = ronda_programada(como_lider, semilla)
    assert como_lider.get(f"/rondas/{ronda.id}/revision").status_code == 409
    assert como_lider.post(f"/rondas/{ronda.id}/propuesta").status_code == 409
    assert confirmar(como_lider, ronda).status_code == 409
