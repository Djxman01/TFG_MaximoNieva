"""Pruebas de la pantalla de criterios de criticidad (HU-003)."""

from sqlalchemy import select

from app.models import Activo, CriterioCriticidad


def buscar(db, nombre):
    return db.scalars(select(CriterioCriticidad).where(CriterioCriticidad.nombre == nombre)).first()


def test_listado_de_criterios(como_lider, semilla):
    pagina = como_lider.get("/criterios").text
    assert "Registró hallazgos o incidentes" in pagina
    assert "Personas" in pagina


def test_alta_de_un_criterio_de_probabilidad(como_lider, semilla):
    datos = {"nombre": "Supera la vida útil de diseño", "dimension": "probabilidad",
             "nivel": "personas", "habilitado": "true"}
    respuesta = como_lider.post("/criterios", data=datos, follow_redirects=False)
    assert respuesta.status_code == 303
    criterio = buscar(semilla, "Supera la vida útil de diseño")
    assert criterio.dimension == "probabilidad"
    assert criterio.nivel is None  # la probabilidad no lleva nivel


def test_la_dimension_es_obligatoria(como_lider, semilla):
    respuesta = como_lider.post("/criterios", data={"nombre": "Sin dimensión"})
    assert respuesta.status_code == 400
    assert "Indicá la dimensión" in respuesta.text


def test_la_consecuencia_exige_el_nivel(como_lider, semilla):
    respuesta = como_lider.post("/criterios", data={"nombre": "Algo", "dimension": "consecuencia"})
    assert respuesta.status_code == 400
    assert "personas, ambiente o producción" in respuesta.text


def test_alta_de_un_criterio_de_consecuencia_aparece_en_la_evaluacion(como_lider, semilla):
    datos = {"nombre": "Cercanía a un curso de agua", "dimension": "consecuencia",
             "nivel": "ambiente", "habilitado": "true"}
    como_lider.post("/criterios", data=datos)
    activo = semilla.scalars(select(Activo)).first()
    assert "Cercanía a un curso de agua" in como_lider.get(f"/activos/{activo.id}/criticidad").text


def test_deshabilitar_un_criterio_lo_saca_de_la_evaluacion(como_lider, semilla):
    criterio = buscar(semilla, "Opera con presión por encima del rango de referencia")
    como_lider.post(f"/criterios/{criterio.id}", data={"nombre": criterio.nombre,
                                                       "dimension": "probabilidad"})
    activo = semilla.scalars(select(Activo)).first()
    assert "Opera con presión por encima" not in como_lider.get(f"/activos/{activo.id}/criticidad").text


def test_un_criterio_usado_no_cambia_de_dimension(como_lider, semilla):
    criterio = buscar(semilla, "Registró hallazgos o incidentes en los últimos 12 meses")
    como_lider.post(
        f"/criterios/{criterio.id}",
        data={"nombre": "Registró hallazgos (12 meses)", "dimension": "consecuencia",
              "nivel": "personas", "habilitado": "true"},
    )
    semilla.expire_all()
    criterio = semilla.get(CriterioCriticidad, criterio.id)
    assert criterio.nombre == "Registró hallazgos (12 meses)"  # el nombre sí cambia
    assert criterio.dimension == "probabilidad"
    assert criterio.nivel is None


def test_un_criterio_sin_usar_se_puede_reclasificar(como_lider, semilla):
    como_lider.post("/criterios", data={"nombre": "Nuevo", "dimension": "probabilidad",
                                       "habilitado": "true"})
    criterio = buscar(semilla, "Nuevo")
    como_lider.post(f"/criterios/{criterio.id}", data={"nombre": "Nuevo", "dimension": "consecuencia",
                                                       "nivel": "produccion", "habilitado": "true"})
    semilla.expire_all()
    criterio = semilla.get(CriterioCriticidad, criterio.id)
    assert (criterio.dimension, criterio.nivel) == ("consecuencia", "produccion")


def test_aviso_de_configuracion_incompleta(como_lider, semilla):
    for criterio in semilla.scalars(select(CriterioCriticidad)):
        if criterio.dimension == "probabilidad":
            criterio.habilitado = False
    semilla.commit()
    assert "configuración de criterios no está completa" in como_lider.get("/criterios").text


def test_el_operador_no_gestiona_criterios(como_operador):
    assert como_operador.get("/criterios").status_code == 403
    assert como_operador.post("/criterios", data={"nombre": "x"}).status_code == 403
