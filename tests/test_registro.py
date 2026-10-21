"""Pruebas del registro en campo (HU-009 verificación y evidencia, HU-010 hallazgos)."""

from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import func, select

from app.config import EVIDENCIA_DIR
from app.models import Evidencia, Hallazgo, Verificacion
from app.semilla import USUARIOS
from tests.ayudas import ronda_con_recorrido, ronda_programada
from tests.conftest import iniciar_sesion

FOTO = ("foto.jpg", b"\xff\xd8\xff contenido de prueba", "image/jpeg")


def preparar(cliente, db):
    """El Líder programa la Ronda #024 y después ingresa el Operador."""
    ronda = ronda_programada(cliente, db)
    iniciar_sesion(cliente, USUARIOS[1]["email"], USUARIOS[1]["clave"])
    paradas = sorted(
        (ra for ra in ronda.activos if ra.orden_planificado), key=lambda ra: ra.orden_planificado
    )
    return ronda, paradas


def registrar(cliente, ronda, parada, archivos=None, **campos):
    datos = {
        "uuid_envio": f"uuid-{parada.id}",
        "estado": "inspeccionado",
        "resultado": "sin_hallazgos",
        "observaciones": "",
        "fecha_hora": "2026-11-05T09:30",
        **campos,
    }
    return cliente.post(
        f"/registro/{ronda.id}/{parada.id}",
        data=datos,
        files=[("evidencias", archivo) for archivo in (archivos or [])],
        follow_redirects=False,
    )


def contar(db, modelo):
    return db.scalar(select(func.count()).select_from(modelo))


def test_el_operador_ve_la_ronda_programada(como_lider, semilla):
    ronda, _ = preparar(como_lider, semilla)
    pagina = como_lider.get("/registro").text
    assert f"Ronda {ronda.numero}" in pagina
    assert "0 de 4 activos registrados" in pagina


def test_el_formulario_trae_identificador_y_hora_actual(como_lider, semilla):
    ronda, paradas = preparar(como_lider, semilla)
    pagina = como_lider.get(f"/registro/{ronda.id}/{paradas[0].id}").text
    assert 'name="uuid_envio"' in pagina
    assert 'type="datetime-local"' in pagina
    assert "Parada 1 de 4" in pagina


def test_registrar_una_verificacion_con_evidencia(como_lider, semilla):
    ronda, paradas = preparar(como_lider, semilla)
    respuesta = registrar(como_lider, ronda, paradas[0], archivos=[FOTO])
    assert respuesta.status_code == 303
    # Después de guardar se abre la siguiente parada pendiente.
    assert respuesta.headers["location"].startswith(f"/registro/{ronda.id}/{paradas[1].id}")

    semilla.expire_all()
    assert ronda.estado == "en_ejecucion"
    assert paradas[0].estado_atencion == "inspeccionado"
    verificacion = paradas[0].verificacion
    assert verificacion.resultado == "sin_hallazgos"
    assert verificacion.usuario.rol == "operador"
    evidencia = verificacion.evidencias[0]
    assert (Path(EVIDENCIA_DIR) / evidencia.ruta_archivo).read_bytes() == FOTO[1]


def test_la_hora_de_la_inspeccion_la_indica_el_operador(como_lider, semilla):
    ronda, paradas = preparar(como_lider, semilla)
    registrar(como_lider, ronda, paradas[0], fecha_hora="2026-11-05T09:30")
    semilla.expire_all()
    verificacion = paradas[0].verificacion
    momento = verificacion.fecha_hora.replace(tzinfo=timezone.utc)
    # 09:30 en Argentina (UTC−3) son las 12:30 UTC.
    assert momento == datetime(2026, 11, 5, 12, 30, tzinfo=timezone.utc)
    # La hora de recepción del servidor se guarda aparte.
    assert verificacion.fecha_hora_recepcion != verificacion.fecha_hora


def test_un_reintento_no_duplica_el_registro(como_lider, semilla):
    ronda, paradas = preparar(como_lider, semilla)
    registrar(como_lider, ronda, paradas[0], archivos=[FOTO])
    segunda = registrar(como_lider, ronda, paradas[0], archivos=[FOTO])  # mismo uuid
    assert segunda.status_code == 303
    assert contar(semilla, Verificacion) == 1
    assert contar(semilla, Evidencia) == 1


def test_un_segundo_registro_distinto_del_mismo_activo_se_rechaza(como_lider, semilla):
    ronda, paradas = preparar(como_lider, semilla)
    registrar(como_lider, ronda, paradas[0])
    otra = registrar(como_lider, ronda, paradas[0], uuid_envio="otro-uuid")
    assert otra.status_code == 409
    assert contar(semilla, Verificacion) == 1


def test_no_accesible_se_registra_sin_verificacion(como_lider, semilla):
    ronda, paradas = preparar(como_lider, semilla)
    respuesta = registrar(
        como_lider, ronda, paradas[1], estado="no_accesible", resultado="",
        observaciones="Camino cortado por crecida.",
    )
    assert respuesta.status_code == 303
    semilla.expire_all()
    assert paradas[1].estado_atencion == "no_accesible"
    assert paradas[1].observacion_atencion == "Camino cortado por crecida."
    assert paradas[1].fecha_hora_atencion is not None
    assert paradas[1].verificacion is None
    assert contar(semilla, Verificacion) == 0


def test_no_accesible_exige_observacion(como_lider, semilla):
    ronda, paradas = preparar(como_lider, semilla)
    respuesta = registrar(como_lider, ronda, paradas[1], estado="no_accesible", resultado="")
    assert respuesta.status_code == 400
    assert "indicá el motivo" in respuesta.text


def test_con_hallazgos_hay_que_describir_el_hallazgo(como_lider, semilla):
    ronda, paradas = preparar(como_lider, semilla)
    respuesta = registrar(como_lider, ronda, paradas[0], resultado="con_hallazgos")
    assert respuesta.status_code == 400
    assert "tipo de hallazgo" in respuesta.text
    assert contar(semilla, Verificacion) == 0


def test_hallazgo_con_atencion_inmediata(como_lider, semilla):
    ronda, paradas = preparar(como_lider, semilla)
    registrar(
        como_lider, ronda, paradas[0], resultado="con_hallazgos",
        hallazgo_tipo="Derrame de hidrocarburo",
        hallazgo_descripcion="Mancha en suelo junto al cabezal.",
        atencion_inmediata="true",
    )
    hallazgo = semilla.scalars(select(Hallazgo)).one()
    assert hallazgo.tipo == "Derrame de hidrocarburo"
    assert hallazgo.requiere_atencion_inmediata is True


def test_sin_hallazgos_no_pide_hallazgo(como_lider, semilla):
    ronda, paradas = preparar(como_lider, semilla)
    registrar(como_lider, ronda, paradas[0], resultado="sin_hallazgos")
    assert contar(semilla, Hallazgo) == 0
    assert contar(semilla, Verificacion) == 1


def test_un_archivo_que_no_es_foto_se_rechaza_y_no_guarda_nada(como_lider, semilla):
    ronda, paradas = preparar(como_lider, semilla)
    respuesta = registrar(
        como_lider, ronda, paradas[0], archivos=[("planilla.pdf", b"%PDF", "application/pdf")]
    )
    assert respuesta.status_code == 400
    assert contar(semilla, Verificacion) == 0
    semilla.expire_all()
    assert paradas[0].estado_atencion == "pendiente"


def test_la_evidencia_se_ve_solo_con_sesion(como_lider, semilla):
    ronda, paradas = preparar(como_lider, semilla)
    registrar(como_lider, ronda, paradas[0], archivos=[FOTO])
    evidencia = semilla.scalars(select(Evidencia)).one()
    assert como_lider.get(f"/evidencia/{evidencia.id}").content == FOTO[1]
    como_lider.post("/logout")
    assert como_lider.get(f"/evidencia/{evidencia.id}", follow_redirects=False).status_code == 303


def test_el_lider_no_registra_verificaciones(como_lider, semilla):
    ronda = ronda_programada(como_lider, semilla)
    parada = next(ra for ra in ronda.activos if ra.orden_planificado == 1)
    assert registrar(como_lider, ronda, parada).status_code == 403


def test_una_ronda_en_borrador_no_se_registra(como_lider, semilla):
    ronda = ronda_con_recorrido(como_lider, semilla)
    iniciar_sesion(como_lider, USUARIOS[1]["email"], USUARIOS[1]["clave"])
    assert como_lider.get(f"/registro/{ronda.id}").status_code == 409
