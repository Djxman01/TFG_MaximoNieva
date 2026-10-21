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
