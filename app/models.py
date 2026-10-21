"""Modelos de datos: cada clase es una tabla de la base.

Los nombres siguen el diagrama de clases de la tesis, escritos en el estilo de
Python (fecha_hora_evaluacion en lugar de fechaHoraEvaluacion).
"""

from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Column,
    DateTime,
    ForeignKey,
    Numeric,
    String,
    Table,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

# Pesos de cada categoría para la cobertura ponderada (sección 4.6).
PESOS = {"alta": 3, "media": 2, "baja": 1}


class Usuario(Base):
    __tablename__ = "usuario"
    __table_args__ = (
        # La base rechaza cualquier rol que no sea uno de estos dos.
        CheckConstraint("rol IN ('lider', 'operador')", name="ck_usuario_rol"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    nombre: Mapped[str] = mapped_column(String(100))
    # unique=True: no puede haber dos usuarios con el mismo correo.
    email: Mapped[str] = mapped_column(String(255), unique=True)
    # Se guarda el hash de bcrypt, nunca la contraseña en claro.
    clave_hash: Mapped[str] = mapped_column(String(60))
    rol: Mapped[str] = mapped_column(String(20))


class Activo(Base):
    """Pozo, batería u otra instalación que se inspecciona (HU-002).

    Coordenadas en metros, Gauss-Krüger sobre POSGAR 2007, faja 2 (EPSG:5344).
    Convención del prototipo: coordenada_x = ESTE y coordenada_y = NORTE.
    Ojo: la definición de EPSG nombra los ejes al revés (X = norte), por eso las
    conversiones se hacen con always_xy=True (ver app/coordenadas.py).
    """

    __tablename__ = "activo"
    __table_args__ = (
        CheckConstraint("estado IN ('activo', 'inactivo')", name="ck_activo_estado"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    # Identificación con la que se lo conoce en el campo, por ejemplo "Pozo A-14".
    codigo: Mapped[str] = mapped_column(String(50), unique=True)
    tipo: Mapped[str] = mapped_column(String(50))
    coordenada_x: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    coordenada_y: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    estado: Mapped[str] = mapped_column(String(10), default="activo")
    telesupervision: Mapped[bool] = mapped_column(Boolean, default=False)
    condicion_acceso: Mapped[str] = mapped_column(String(100), default="")

    # Historial de evaluaciones, de la más nueva a la más vieja.
    evaluaciones: Mapped[list["CriticidadActivo"]] = relationship(
        back_populates="activo",
        order_by="(CriticidadActivo.fecha_hora_evaluacion.desc(), CriticidadActivo.id.desc())",
    )

    def criticidad_vigente(self) -> "CriticidadActivo | None":
        """La evaluación más reciente. None si el activo nunca se evaluó."""
        if self.evaluaciones:
            return self.evaluaciones[0]
        return None


class CriterioCriticidad(Base):
    """Factor que el responsable puede marcar al evaluar un activo (HU-003)."""

    __tablename__ = "criterio_criticidad"
    __table_args__ = (
        # Un criterio de probabilidad no tiene nivel; uno de consecuencia sí.
        CheckConstraint(
            "(dimension = 'probabilidad' AND nivel IS NULL) OR "
            "(dimension = 'consecuencia' AND nivel IN ('personas', 'ambiente', 'produccion'))",
            name="ck_criterio_dimension_nivel",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    nombre: Mapped[str] = mapped_column(String(200))
    descripcion: Mapped[str] = mapped_column(String(300), default="")
    habilitado: Mapped[bool] = mapped_column(Boolean, default=True)
    dimension: Mapped[str] = mapped_column(String(20))
    nivel: Mapped[str | None] = mapped_column(String(20), nullable=True)


# Tabla intermedia: qué criterios se marcaron en cada evaluación.
criticidad_activo_criterio = Table(
    "criticidad_activo_criterio",
    Base.metadata,
    Column(
        "criticidad_activo_id",
        ForeignKey("criticidad_activo.id", ondelete="CASCADE"),
        primary_key=True,
    ),
    Column("criterio_criticidad_id", ForeignKey("criterio_criticidad.id"), primary_key=True),
)


class CriticidadActivo(Base):
    """Una evaluación de criticidad de un activo (HU-004).

    Nunca se modifica: cada vez que se guarda una evaluación se crea una nueva
    fila y las anteriores quedan como historial.
    """

    __tablename__ = "criticidad_activo"
    __table_args__ = (
        CheckConstraint("categoria IN ('alta', 'media', 'baja')", name="ck_criticidad_categoria"),
        CheckConstraint("probabilidad IN ('alta', 'media', 'baja')", name="ck_criticidad_prob"),
        CheckConstraint("consecuencia IN ('alta', 'media', 'baja')", name="ck_criticidad_cons"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    activo_id: Mapped[int] = mapped_column(ForeignKey("activo.id"))
    usuario_id: Mapped[int] = mapped_column(ForeignKey("usuario.id"))
    categoria: Mapped[str] = mapped_column(String(10))
    probabilidad: Mapped[str] = mapped_column(String(10))
    consecuencia: Mapped[str] = mapped_column(String(10))
    fecha_hora_evaluacion: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    observaciones: Mapped[str] = mapped_column(Text, default="")

    activo: Mapped[Activo] = relationship(back_populates="evaluaciones")
    usuario: Mapped[Usuario] = relationship()
    criterios: Mapped[list[CriterioCriticidad]] = relationship(
        secondary=criticidad_activo_criterio
    )

    def peso(self) -> int:
        """Ponderador para la cobertura: alta = 3, media = 2, baja = 1."""
        return PESOS[self.categoria]
