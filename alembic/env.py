"""Configuración de Alembic, la herramienta que versiona el esquema de la base.

Cada cambio en los modelos se guarda como una "migración" en alembic/versions.
"alembic upgrade head" aplica en orden las que todavía no se aplicaron.
"""

from logging.config import fileConfig

from alembic import context
from sqlalchemy import create_engine

from app import models  # noqa: F401  (hace que los modelos queden registrados)
from app.config import DATABASE_URL
from app.database import Base

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Alembic compara estos modelos con la base para generar las migraciones.
target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """Escribe el SQL de las migraciones sin conectarse a la base."""
    context.configure(
        url=DATABASE_URL,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Se conecta a la base y aplica las migraciones."""
    motor = create_engine(DATABASE_URL)
    with motor.connect() as conexion:
        context.configure(connection=conexion, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
