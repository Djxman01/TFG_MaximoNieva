"""Pruebas del bloqueo de la cuenta y del registro de intentos de ingreso.

El paso del tiempo se simula reemplazando la función que da la hora actual.
"""

from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import select

import app.seguridad
from app.models import IntentoIngreso, Usuario
from app.seguridad import INTENTOS_MAXIMOS, autenticar
from tests.conftest import CLAVE_DE_PRUEBA

MALA = "una clave que no es la correcta"
INICIO = datetime(2026, 11, 6, 15, 0, tzinfo=timezone.utc)


@pytest.fixture
def reloj(monkeypatch):
    """Un reloj que se puede adelantar a mano: reloj.avanzar(minutos=...)."""

    class Reloj:
        ahora = INICIO

        def avanzar(self, **tiempo):
            self.ahora += timedelta(**tiempo)

    r = Reloj()
    monkeypatch.setattr(app.seguridad, "ahora", lambda: r.ahora)
    return r


def resultados(db):
    return [i.resultado for i in db.scalars(select(IntentoIngreso).order_by(IntentoIngreso.id))]


def fallar(db, veces, email="lider@ejemplo.com"):
    for _ in range(veces):
        assert autenticar(db, email, MALA) is None


def test_la_cuenta_se_bloquea_al_decimo_intento_fallido(db, crear_usuario, reloj):
    crear_usuario("lider@ejemplo.com", "lider")
    fallar(db, INTENTOS_MAXIMOS - 1)
    # Con 9 fallidos todavía entra.
    assert autenticar(db, "lider@ejemplo.com", CLAVE_DE_PRUEBA) is not None
    fallar(db, INTENTOS_MAXIMOS)
    # Con 10 seguidos queda bloqueada: ni la contraseña correcta sirve.
    assert autenticar(db, "lider@ejemplo.com", CLAVE_DE_PRUEBA) is None
    assert resultados(db)[-1] == "bloqueado"


def test_un_ingreso_correcto_reinicia_el_contador(db, crear_usuario, reloj):
    crear_usuario("lider@ejemplo.com", "lider")
    fallar(db, 9)
    autenticar(db, "lider@ejemplo.com", CLAVE_DE_PRUEBA)
    fallar(db, 9)  # 9 + 9, pero no seguidos: no se bloquea
    assert autenticar(db, "lider@ejemplo.com", CLAVE_DE_PRUEBA) is not None


def test_el_bloqueo_dura_15_minutos(db, crear_usuario, reloj):
    crear_usuario("lider@ejemplo.com", "lider")
    fallar(db, INTENTOS_MAXIMOS)
    reloj.avanzar(minutes=14, seconds=59)
    assert autenticar(db, "lider@ejemplo.com", CLAVE_DE_PRUEBA) is None
    reloj.avanzar(seconds=2)  # 15 minutos y 1 segundo
    assert autenticar(db, "lider@ejemplo.com", CLAVE_DE_PRUEBA) is not None


def test_despues_del_bloqueo_vuelve_a_tener_diez_intentos(db, crear_usuario, reloj):
    crear_usuario("lider@ejemplo.com", "lider")
    fallar(db, INTENTOS_MAXIMOS)
    reloj.avanzar(minutes=16)
    fallar(db, 1)  # un fallido después del bloqueo no vuelve a bloquear
    assert autenticar(db, "lider@ejemplo.com", CLAVE_DE_PRUEBA) is not None


def test_durante_el_bloqueo_los_intentos_no_suman(db, crear_usuario, reloj):
    crear_usuario("lider@ejemplo.com", "lider")
    fallar(db, INTENTOS_MAXIMOS)
    fallar(db, 5)  # quedan registrados como "bloqueado", no alargan el bloqueo
    usuario = db.scalars(select(Usuario)).one()
    assert usuario.intentos_fallidos == 0
    assert resultados(db)[-5:] == ["bloqueado"] * 5
    reloj.avanzar(minutes=15, seconds=1)
    assert autenticar(db, "lider@ejemplo.com", CLAVE_DE_PRUEBA) is not None


def test_se_registra_cada_intento(db, crear_usuario, reloj):
    crear_usuario("lider@ejemplo.com", "lider")
    autenticar(db, "lider@ejemplo.com", MALA)
    autenticar(db, " Lider@Ejemplo.com ", CLAVE_DE_PRUEBA)
    autenticar(db, "nadie@ejemplo.com", MALA)
    intentos = list(db.scalars(select(IntentoIngreso).order_by(IntentoIngreso.id)))
    assert [i.resultado for i in intentos] == ["fallido", "correcto", "fallido"]
    assert intentos[1].email == "lider@ejemplo.com"  # se guarda normalizado
    assert intentos[1].usuario.email == "lider@ejemplo.com"
    assert intentos[2].usuario is None  # el correo no existe
    assert intentos[0].fecha_hora.replace(tzinfo=timezone.utc) == INICIO


def test_un_correo_inexistente_no_bloquea_nada(db, crear_usuario, reloj):
    crear_usuario("lider@ejemplo.com", "lider")
    fallar(db, 20, email="nadie@ejemplo.com")
    assert autenticar(db, "lider@ejemplo.com", CLAVE_DE_PRUEBA) is not None


def test_la_pantalla_de_ingreso_no_revela_el_bloqueo(cliente, crear_usuario, reloj):
    crear_usuario("lider@ejemplo.com", "lider")
    for _ in range(INTENTOS_MAXIMOS):
        cliente.post("/login", data={"email": "lider@ejemplo.com", "clave": MALA})
    respuesta = cliente.post(
        "/login", data={"email": "lider@ejemplo.com", "clave": CLAVE_DE_PRUEBA},
        follow_redirects=False,
    )
    assert respuesta.status_code == 401
    assert "Correo o contraseña incorrectos" in respuesta.text
    assert "bloque" not in respuesta.text.lower()


def test_el_lider_consulta_el_registro_de_ingresos(como_lider):
    pagina = como_lider.get("/ingresos").text
    assert "Registro de ingresos" in pagina
    assert "lider@rondas.demo" in pagina
    assert "Correcto" in pagina


def test_el_operador_no_ve_el_registro_de_ingresos(como_operador):
    assert como_operador.get("/ingresos").status_code == 403
