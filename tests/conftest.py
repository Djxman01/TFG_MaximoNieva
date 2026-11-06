"""Preparación compartida por las pruebas.

Un "fixture" es una función que pytest ejecuta antes de una prueba para
entregarle algo ya preparado. La prueba lo pide poniendo el nombre del
fixture como parámetro.
"""

import functools
import os
import tempfile

# La aplicación exige estas variables al importarse. En las pruebas se usan
# valores propios: una base SQLite en memoria, una clave que no es la real y una
# carpeta temporal para los archivos de evidencia.
os.environ.setdefault("DATABASE_URL", "sqlite://")
os.environ.setdefault("SECRET_KEY", "clave-solo-para-pruebas")
os.environ.setdefault("EVIDENCIA_DIR", tempfile.mkdtemp(prefix="evidencia_pruebas_"))

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
    # La cookie de sesión es Secure: el navegador simulado tiene que usar HTTPS.
    yield TestClient(app, base_url="https://testserver")
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


# bcrypt es lento a propósito (costo 12). Para que las pruebas no tarden de más,
# el hash de cada contraseña de los datos semilla se calcula una sola vez.
_hash_en_cache = functools.cache(generar_hash)


@pytest.fixture
def semilla(db, monkeypatch):
    """Carga los datos de la demo (usuarios, criterios y activos) en la base de prueba."""
    import app.semilla

    monkeypatch.setattr(app.semilla, "generar_hash", _hash_en_cache)
    app.semilla.cargar_datos_semilla(db)
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
