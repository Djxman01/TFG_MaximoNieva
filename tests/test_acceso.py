"""Pruebas del ingreso por la web y del acceso según el rol (HU-001)."""

import pytest
from fastapi import Depends
from sqlalchemy.exc import IntegrityError

from app.main import app
from app.models import Usuario
from app.seguridad import ROL_SUPERVISOR, requiere_rol
from tests.conftest import CLAVE_DE_PRUEBA


# Ruta que existe solo para estas pruebas: sirve para comprobar que
# requiere_rol deja pasar a un rol y frena al otro.
@app.get("/prueba/solo-supervisor")
def ruta_solo_supervisor(usuario: Usuario = Depends(requiere_rol(ROL_SUPERVISOR))):
    return {"rol": usuario.rol}


def ingresar(cliente, email, clave=CLAVE_DE_PRUEBA):
    return cliente.post(
        "/login",
        data={"email": email, "clave": clave},
        follow_redirects=False,
    )


def test_sin_sesion_el_inicio_redirige_al_ingreso(cliente):
    respuesta = cliente.get("/", follow_redirects=False)
    assert respuesta.status_code == 303
    assert respuesta.headers["location"] == "/login"


def test_ingreso_correcto_lleva_al_inicio(cliente, crear_usuario):
    crear_usuario("supervisor@ejemplo.com", "supervisor", nombre="Ana Pérez")
    respuesta = ingresar(cliente, "supervisor@ejemplo.com")
    assert respuesta.status_code == 303
    assert respuesta.headers["location"] == "/"

    inicio = cliente.get("/")
    assert inicio.status_code == 200
    assert "Ana Pérez" in inicio.text
    assert "Supervisor de campo" in inicio.text


def test_ingreso_con_clave_incorrecta_es_rechazado(cliente, crear_usuario):
    crear_usuario("supervisor@ejemplo.com", "supervisor")
    respuesta = ingresar(cliente, "supervisor@ejemplo.com", clave="Incorrecta1")
    assert respuesta.status_code == 401
    assert "Correo o contraseña incorrectos" in respuesta.text
    # No quedó sesión iniciada.
    assert cliente.get("/", follow_redirects=False).status_code == 303


def test_el_mensaje_de_error_no_revela_si_el_correo_existe(cliente, crear_usuario):
    crear_usuario("supervisor@ejemplo.com", "supervisor")
    clave_mal = ingresar(cliente, "supervisor@ejemplo.com", clave="Incorrecta1")
    correo_mal = ingresar(cliente, "nadie@ejemplo.com")
    assert clave_mal.status_code == correo_mal.status_code == 401
    assert "Correo o contraseña incorrectos" in correo_mal.text


def test_salir_cierra_la_sesion(cliente, crear_usuario):
    crear_usuario("operador@ejemplo.com", "operador")
    ingresar(cliente, "operador@ejemplo.com")
    assert cliente.get("/", follow_redirects=False).status_code == 200

    cliente.post("/logout", follow_redirects=False)
    assert cliente.get("/", follow_redirects=False).status_code == 303


def test_cada_rol_ve_sus_propias_funciones(cliente, crear_usuario):
    crear_usuario("operador@ejemplo.com", "operador")
    ingresar(cliente, "operador@ejemplo.com")
    inicio = cliente.get("/")
    assert "Registrar verificaciones" in inicio.text
    assert "Planificar rondas" not in inicio.text


def test_ruta_de_supervisor_acepta_al_supervisor(cliente, crear_usuario):
    crear_usuario("supervisor@ejemplo.com", "supervisor")
    ingresar(cliente, "supervisor@ejemplo.com")
    assert cliente.get("/prueba/solo-supervisor").status_code == 200


def test_ruta_de_supervisor_rechaza_al_operador(cliente, crear_usuario):
    crear_usuario("operador@ejemplo.com", "operador")
    ingresar(cliente, "operador@ejemplo.com")
    assert cliente.get("/prueba/solo-supervisor").status_code == 403


def test_ruta_de_supervisor_sin_sesion_redirige_al_ingreso(cliente):
    respuesta = cliente.get("/prueba/solo-supervisor", follow_redirects=False)
    assert respuesta.status_code == 303


def test_no_puede_haber_dos_usuarios_con_el_mismo_correo(db, crear_usuario):
    crear_usuario("supervisor@ejemplo.com", "supervisor")
    with pytest.raises(IntegrityError):
        crear_usuario("supervisor@ejemplo.com", "operador")


def test_la_base_rechaza_un_rol_desconocido(db, crear_usuario):
    with pytest.raises(IntegrityError):
        crear_usuario("otro@ejemplo.com", "administrador")
