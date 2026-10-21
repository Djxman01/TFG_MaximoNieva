"""Pruebas de la evaluación de criticidad por pantalla (HU-003 c3, HU-004)."""

from sqlalchemy import select

from app.models import Activo, CriterioCriticidad


def buscar(db, codigo):
    return db.scalars(select(Activo).where(Activo.codigo == codigo)).one()


def ids_de(db, *nombres_cortos):
    """Ids de los criterios semilla a partir de una palabra de su nombre."""
    ids = []
    for palabra in nombres_cortos:
        criterio = db.scalars(
            select(CriterioCriticidad).where(CriterioCriticidad.nombre.contains(palabra))
        ).first()
        ids.append(criterio.id)
    return ids


def test_el_lider_ve_los_factores_y_la_criticidad_vigente(como_lider, semilla):
    activo = buscar(semilla, "Pozo A-14")
    pagina = como_lider.get(f"/activos/{activo.id}/criticidad")
    assert pagina.status_code == 200
    assert "Registró hallazgos o incidentes" in pagina.text
    assert "ALTA" in pagina.text
    assert "Historial de evaluaciones" in pagina.text


def test_la_vista_previa_recalcula_sin_guardar(como_lider, semilla):
    activo = buscar(semilla, "Pozo A-21")  # sin evaluar
    marcados = ids_de(semilla, "hallazgos", "desvíos", "ambiental")
    respuesta = como_lider.post(
        f"/activos/{activo.id}/criticidad/vista-previa", data={"criterios": marcados}
    )
    assert respuesta.status_code == 200
    # Dos de probabilidad (alta) y ambiente (media): la matriz da alta.
    assert "ALTA" in respuesta.text
    semilla.expire_all()
    assert buscar(semilla, "Pozo A-21").evaluaciones == []


def test_guardar_crea_una_evaluacion_nueva_y_conserva_la_anterior(como_lider, semilla):
    activo = buscar(semilla, "Pozo A-14")
    antes = len(activo.evaluaciones)
    marcados = ids_de(semilla, "hallazgos")  # probabilidad media, consecuencia baja
    respuesta = como_lider.post(
        f"/activos/{activo.id}/criticidad",
        data={"criterios": marcados, "observaciones": "Reevaluación"},
        follow_redirects=False,
    )
    assert respuesta.status_code == 303

    semilla.expire_all()
    activo = buscar(semilla, "Pozo A-14")
    assert len(activo.evaluaciones) == antes + 1
    vigente = activo.criticidad_vigente()
    assert (vigente.probabilidad, vigente.consecuencia, vigente.categoria) == (
        "media", "baja", "baja",
    )
    assert vigente.observaciones == "Reevaluación"
    assert vigente.usuario.rol == "lider"
    # La evaluación anterior sigue ahí, sin cambios.
    assert activo.evaluaciones[1].categoria == "alta"


def test_guardar_sin_factores_da_baja(como_lider, semilla):
    activo = buscar(semilla, "Pozo C-02")
    como_lider.post(f"/activos/{activo.id}/criticidad", data={}, follow_redirects=False)
    semilla.expire_all()
    assert buscar(semilla, "Pozo C-02").criticidad_vigente().categoria == "baja"


def test_un_criterio_desconocido_se_ignora(como_lider, semilla):
    activo = buscar(semilla, "Pozo C-02")
    como_lider.post(
        f"/activos/{activo.id}/criticidad", data={"criterios": [99999]},
        follow_redirects=False,
    )
    semilla.expire_all()
    vigente = buscar(semilla, "Pozo C-02").criticidad_vigente()
    assert vigente.criterios == []
    assert vigente.categoria == "baja"


def test_sin_criterios_configurados_no_se_puede_evaluar(como_lider, semilla):
    # HU-003 c3: se deshabilitan todos los criterios de consecuencia.
    for criterio in semilla.scalars(select(CriterioCriticidad)):
        if criterio.dimension == "consecuencia":
            criterio.habilitado = False
    semilla.commit()

    activo = buscar(semilla, "Pozo A-21")
    pagina = como_lider.get(f"/activos/{activo.id}/criticidad")
    assert "configuración de criterios no está completa" in pagina.text

    respuesta = como_lider.post(f"/activos/{activo.id}/criticidad", data={})
    assert respuesta.status_code == 400
    semilla.expire_all()
    assert buscar(semilla, "Pozo A-21").evaluaciones == []


def test_el_operador_no_puede_evaluar(como_operador, semilla):
    activo = buscar(semilla, "Pozo A-14")
    assert como_operador.get(f"/activos/{activo.id}/criticidad").status_code == 403
    respuesta = como_operador.post(f"/activos/{activo.id}/criticidad", data={})
    assert respuesta.status_code == 403


def test_los_dos_perfiles_consultan_los_activos(como_operador):
    pagina = como_operador.get("/activos")
    assert pagina.status_code == 200
    assert "Pozo A-14" in pagina.text
    assert "Sin evaluar" in pagina.text


def test_activo_inexistente_da_404(como_lider):
    assert como_lider.get("/activos/99999/criticidad").status_code == 404
