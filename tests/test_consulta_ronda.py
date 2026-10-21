"""Pruebas de la consulta de la ronda: estado de atención (HU-011), cobertura
(HU-012) y trazabilidad (HU-013)."""

from sqlalchemy import select

from app.models import Activo
from app.semilla import USUARIOS
from tests.ayudas import MOTIVO_024, ronda_programada
from tests.conftest import iniciar_sesion
from tests.test_registro import FOTO, preparar, registrar


def como_lider_de_nuevo(cliente):
    iniciar_sesion(cliente, USUARIOS[0]["email"], USUARIOS[0]["clave"])


def test_recien_programada_la_cobertura_es_cero(como_lider, semilla):
    ronda = ronda_programada(como_lider, semilla)
    pagina = como_lider.get(f"/rondas/{ronda.id}/detalle").text
    assert "Cobertura operativa" in pagina
    assert "0 de 5" in pagina  # 4 del recorrido + C-07, que quedó afuera
    assert pagina.count("Pendiente") >= 5


def test_estado_de_atencion_y_cobertura_despues_de_registrar(como_lider, semilla):
    ronda, paradas = preparar(como_lider, semilla)
    registrar(como_lider, ronda, paradas[0])  # A-14, alta: inspeccionado
    registrar(
        como_lider, ronda, paradas[1], uuid_envio="b2", estado="no_accesible",
        resultado="", observaciones="Camino cortado.",
    )  # Batería 2, media: no accesible
    como_lider_de_nuevo(como_lider)
    pagina = como_lider.get(f"/rondas/{ronda.id}/detalle").text
    assert "Inspeccionado" in pagina
    assert "No accesible" in pagina
    assert "Camino cortado." in pagina
    # Operativa 1/5 = 20 %. Ponderada 3/11 = 27 % (pesos 3+2+3+2+1 = 11).
    assert "20 %" in pagina
    assert "27 %" in pagina
    assert "3 de 11" in pagina


def test_la_cobertura_usa_la_criticidad_al_planificar(como_lider, semilla):
    ronda, paradas = preparar(como_lider, semilla)
    registrar(como_lider, ronda, paradas[0])  # A-14 (alta al planificar)
    como_lider_de_nuevo(como_lider)
    a14 = semilla.scalars(select(Activo).where(Activo.codigo == "Pozo A-14")).one()
    # Se reevalúa A-14 a Baja después de planificar: la cobertura no cambia.
    como_lider.post(f"/activos/{a14.id}/criticidad", data={}, follow_redirects=False)
    pagina = como_lider.get(f"/rondas/{ronda.id}/detalle").text
    # Sigue pesando 3 (alta) de un total de 11, aunque hoy A-14 sea Baja.
    assert "3 de 11" in pagina


def test_trazabilidad_muestra_propuesto_confirmado_ejecutado_y_motivo(como_lider, semilla):
    ronda, paradas = preparar(como_lider, semilla)
    # Se registra primero la parada 2 (Batería 2) y después la 1 (A-14).
    registrar(como_lider, ronda, paradas[1], uuid_envio="x1", fecha_hora="2026-11-05T09:00")
    registrar(como_lider, ronda, paradas[0], uuid_envio="x2", fecha_hora="2026-11-05T10:00")
    como_lider_de_nuevo(como_lider)
    pagina = como_lider.get(f"/rondas/{ronda.id}/detalle").text
    assert "Trazabilidad del orden" in pagina
    assert MOTIVO_024 in pagina
    semilla.expire_all()
    # El orden ejecutado sale de la hora de cada registro.
    atendidas = sorted(
        (ra for ra in ronda.activos if ra.fecha_hora_atencion), key=lambda ra: ra.fecha_hora_atencion
    )
    assert [ra.activo.codigo for ra in atendidas] == ["Batería 2", "Pozo A-14"]


def test_la_consulta_muestra_evidencia_y_hallazgos(como_lider, semilla):
    ronda, paradas = preparar(como_lider, semilla)
    registrar(
        como_lider, ronda, paradas[0], archivos=[FOTO], resultado="con_hallazgos",
        hallazgo_tipo="Derrame", hallazgo_descripcion="Mancha junto al cabezal.",
        atencion_inmediata="true",
    )
    como_lider_de_nuevo(como_lider)
    pagina = como_lider.get(f"/rondas/{ronda.id}/detalle").text
    assert "Hallazgo: Derrame." in pagina
    assert "Requiere atención inmediata" in pagina
    assert '<img src="/evidencia/' in pagina


def test_cerrar_la_ronda(como_lider, semilla):
    ronda, paradas = preparar(como_lider, semilla)
    registrar(como_lider, ronda, paradas[0])
    como_lider_de_nuevo(como_lider)
    respuesta = como_lider.post(f"/rondas/{ronda.id}/cerrar", follow_redirects=False)
    assert respuesta.status_code == 303
    semilla.expire_all()
    assert ronda.estado == "cerrada"
    # Cerrada, ya no aparece para registrar.
    iniciar_sesion(como_lider, USUARIOS[1]["email"], USUARIOS[1]["clave"])
    assert ronda.numero not in como_lider.get("/registro").text


def test_solo_se_cierra_una_ronda_en_ejecucion(como_lider, semilla):
    ronda = ronda_programada(como_lider, semilla)
    assert como_lider.post(f"/rondas/{ronda.id}/cerrar").status_code == 409
