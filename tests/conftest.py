"""Preparación compartida por las pruebas.

Un "fixture" es una función que pytest ejecuta antes de una prueba para
entregarle algo ya preparado. La prueba lo pide poniendo el nombre del
fixture como parámetro.
"""

import os

# La aplicación exige estas variables al importarse. En las pruebas se usan
# valores propios: una base SQLite en memoria y una clave que no es la real.
os.environ.setdefault("DATABASE_URL", "sqlite://")
os.environ.setdefault("SECRET_KEY", "clave-solo-para-pruebas")

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base, obtener_db
from app.main import app
from app.models import Usuario
from app.seguridad import generar_hash

# Cumple la política NIST: 15 caracteres o más y no está en la lista de bloqueo.
CLAVE_DE_PRUEBA = "frase de prueba del prototipo"


@pytest.fixture
def db():
    """Una base de datos vacía y nueva para cada prueba."""
    motor = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(motor)
    sesion = sessionmaker(bind=motor)()
    yield sesion
    sesion.close()


@pytest.fixture
def cliente(db):
    """Un navegador simulado que habla con la aplicación usando la base de prueba."""
    app.dependency_overrides[obtener_db] = lambda: db
    yield TestClient(app)
    app.dependency_overrides.clear()


@pytest.fixture
def crear_usuario(db):
    """Devuelve una función para dar de alta usuarios dentro de una prueba."""

    def _crear(email: str, rol: str, nombre: str = "Usuario de prueba") -> Usuario:
        usuario = Usuario(
            nombre=nombre,
            email=email,
            clave_hash=generar_hash(CLAVE_DE_PRUEBA),
            rol=rol,
        )
        db.add(usuario)
        db.commit()
        return usuario

    return _crear


@pytest.fixture
def semilla(db):
    """Carga los datos de la demo (usuarios, criterios y activos) en la base de prueba."""
    from app.semilla import cargar_datos_semilla

    cargar_datos_semilla(db)
    return db


def iniciar_sesion(cliente, email, clave=CLAVE_DE_PRUEBA):
    """Ingresa al sistema con el navegador simulado."""
    respuesta = cliente.post(
        "/login", data={"email": email, "clave": clave}, follow_redirects=False
    )
    assert respuesta.status_code == 303, "no se pudo iniciar sesión"


@pytest.fixture
def como_lider(cliente, semilla):
    """Navegador con la sesión del Líder de Operaciones de los datos semilla."""
    from app.semilla import USUARIOS

    iniciar_sesion(cliente, USUARIOS[0]["email"], USUARIOS[0]["clave"])
    return cliente


@pytest.fixture
def como_operador(cliente, semilla):
    """Navegador con la sesión del Operador de los datos semilla."""
    from app.semilla import USUARIOS

    iniciar_sesion(cliente, USUARIOS[1]["email"], USUARIOS[1]["clave"])
    return cliente
