"""Modelos de datos: cada clase es una tabla de la base."""

from sqlalchemy import CheckConstraint, String
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class Usuario(Base):
    __tablename__ = "usuario"
    __table_args__ = (
        # La base rechaza cualquier rol que no sea uno de estos dos.
        CheckConstraint("rol IN ('supervisor', 'operador')", name="ck_usuario_rol"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    nombre: Mapped[str] = mapped_column(String(100))
    # unique=True: no puede haber dos usuarios con el mismo correo.
    email: Mapped[str] = mapped_column(String(255), unique=True)
    # Se guarda el hash de bcrypt, nunca la contraseña en claro.
    clave_hash: Mapped[str] = mapped_column(String(60))
    rol: Mapped[str] = mapped_column(String(20))
