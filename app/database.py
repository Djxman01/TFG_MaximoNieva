"""Conexión a la base de datos con SQLAlchemy."""

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from app.config import DATABASE_URL

# El motor es el objeto que sabe cómo conectarse a la base.
motor = create_engine(DATABASE_URL)

# Cada pedido web abre una sesión de base de datos propia a partir de acá.
SesionLocal = sessionmaker(bind=motor)


class Base(DeclarativeBase):
    """Clase de la que heredan todos los modelos (las tablas)."""


def obtener_db():
    """Entrega una sesión de base de datos y la cierra al terminar el pedido."""
    db = SesionLocal()
    try:
        yield db
    finally:
        db.close()
