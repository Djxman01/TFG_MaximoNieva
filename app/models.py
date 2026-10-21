"""Modelos de datos: cada clase es una tabla de la base.

Los nombres siguen el diagrama de clases de la tesis, escritos en el estilo de
Python (fecha_hora_evaluacion en lugar de fechaHoraEvaluacion).
"""

from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Column,
    Date,
    DateTime,
    ForeignKey,
    Numeric,
    String,
    Table,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

# Pesos de cada categoría para la cobertura ponderada (sección 4.6).
PESOS = {"alta": 3, "media": 2, "baja": 1}

# Valores posibles de los estados. En la base se guardan sin espacios ni tildes;
# a la derecha, el texto que se muestra en pantalla.
ESTADOS_RONDA = {
    "borrador": "Borrador",
    "planificada": "Planificada",
    "en_ejecucion": "En ejecución",
    "cerrada": "Cerrada",
}
CONDICIONES = {"apto": "Apto", "condicionado": "Condicionado", "no_apto": "No apto"}
ESTADOS_ATENCION = {
    "pendiente": "Pendiente",
    "inspeccionado": "Inspeccionado",
    "no_accesible": "No accesible",
}


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


class Ronda(Base):
    """Ronda de inspección (HU-005).

    Recorre los estados borrador → planificada → en_ejecucion → cerrada.
    """

    __tablename__ = "ronda"
    __table_args__ = (
        CheckConstraint(
            "estado IN ('borrador', 'planificada', 'en_ejecucion', 'cerrada')",
            name="ck_ronda_estado",
        ),
        CheckConstraint(
            "condicion_clima IN ('apto', 'condicionado', 'no_apto')", name="ck_ronda_clima"
        ),
        CheckConstraint(
            "condicion_acceso IN ('apto', 'condicionado', 'no_apto')", name="ck_ronda_acceso"
        ),
        CheckConstraint(
            "condicion_conectividad IN ('apto', 'condicionado', 'no_apto')",
            name="ck_ronda_conectividad",
        ),
        CheckConstraint("tiempo_disponible > 0", name="ck_ronda_tiempo"),
        CheckConstraint("velocidad_media > 0", name="ck_ronda_velocidad"),
        CheckConstraint("duracion_inspeccion > 0", name="ck_ronda_duracion"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    usuario_id: Mapped[int] = mapped_column(ForeignKey("usuario.id"))
    fecha_planificada: Mapped[date] = mapped_column(Date)
    medio_inspeccion: Mapped[str] = mapped_column(String(50))
    tiempo_disponible: Mapped[int]  # minutos
    origen_x: Mapped[Decimal] = mapped_column(Numeric(12, 2))  # este, en metros
    origen_y: Mapped[Decimal] = mapped_column(Numeric(12, 2))  # norte, en metros
    velocidad_media: Mapped[Decimal] = mapped_column(Numeric(6, 2))  # km/h
    duracion_inspeccion: Mapped[int]  # minutos por activo
    restricciones: Mapped[str] = mapped_column(Text, default="")
    estado: Mapped[str] = mapped_column(String(20), default="borrador")
    # Condiciones de salida (HU-014). Vacías hasta que se registran.
    condicion_clima: Mapped[str | None] = mapped_column(String(15), nullable=True)
    condicion_acceso: Mapped[str | None] = mapped_column(String(15), nullable=True)
    condicion_conectividad: Mapped[str | None] = mapped_column(String(15), nullable=True)

    usuario: Mapped[Usuario] = relationship()
    activos: Mapped[list["RondaActivo"]] = relationship(
        back_populates="ronda", cascade="all, delete-orphan", order_by="RondaActivo.id"
    )

    @property
    def numero(self) -> str:
        """Número para mostrar, por ejemplo "#024"."""
        return f"#{self.id:03d}"


class RondaActivo(Base):
    """Un activo dentro de una ronda (HU-006 en adelante).

    Guarda el orden propuesto por el sistema, el orden planificado que confirmó
    el Líder y lo que pasó al ejecutar la ronda.
    """

    __tablename__ = "ronda_activo"
    __table_args__ = (
        # Un activo no puede estar dos veces en la misma ronda (HU-006 c3).
        UniqueConstraint("ronda_id", "activo_id", name="uq_ronda_activo"),
        # Dos activos no pueden ocupar la misma posición del recorrido.
        UniqueConstraint("ronda_id", "orden_propuesto", name="uq_ronda_orden_propuesto"),
        UniqueConstraint("ronda_id", "orden_planificado", name="uq_ronda_orden_planificado"),
        CheckConstraint(
            "estado_atencion IN ('pendiente', 'inspeccionado', 'no_accesible')",
            name="ck_ronda_activo_estado",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    ronda_id: Mapped[int] = mapped_column(ForeignKey("ronda.id", ondelete="CASCADE"))
    activo_id: Mapped[int] = mapped_column(ForeignKey("activo.id"))
    # Evaluación de criticidad vigente al generar la propuesta: queda congelada
    # para la ronda aunque el activo se reevalúe después (cobertura, HU-012).
    criticidad_activo_id: Mapped[int | None] = mapped_column(
        ForeignKey("criticidad_activo.id"), nullable=True
    )
    # NULL en orden_propuesto = quedó fuera del recorrido por tiempo (HU-007 c5).
    orden_propuesto: Mapped[int | None] = mapped_column(nullable=True)
    orden_planificado: Mapped[int | None] = mapped_column(nullable=True)
    estado_atencion: Mapped[str] = mapped_column(String(20), default="pendiente")
    fecha_hora_atencion: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    motivo_ajuste: Mapped[str | None] = mapped_column(Text, nullable=True)
    observacion_atencion: Mapped[str | None] = mapped_column(Text, nullable=True)

    ronda: Mapped[Ronda] = relationship(back_populates="activos")
    activo: Mapped[Activo] = relationship()
    criticidad: Mapped[CriticidadActivo | None] = relationship()
    verificacion: Mapped["Verificacion | None"] = relationship(
        back_populates="ronda_activo", cascade="all, delete-orphan"
    )


RESULTADOS = {"sin_hallazgos": "Sin hallazgos", "con_hallazgos": "Con hallazgos"}


class Verificacion(Base):
    """Verificación de un activo inspeccionado durante la ronda (HU-009).

    Un activo "no accesible" no tiene verificación: eso se registra en RondaActivo.
    """

    __tablename__ = "verificacion"
    __table_args__ = (
        CheckConstraint(
            "resultado IN ('sin_hallazgos', 'con_hallazgos')", name="ck_verificacion_resultado"
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    # unique=True: una sola verificación por activo de la ronda.
    ronda_activo_id: Mapped[int] = mapped_column(
        ForeignKey("ronda_activo.id", ondelete="CASCADE"), unique=True
    )
    usuario_id: Mapped[int] = mapped_column(ForeignKey("usuario.id"))
    # Fecha y hora en que el operador hizo la inspección. La indica él mismo
    # (por defecto, "ahora"), porque puede cargarla después si no tenía conexión.
    fecha_hora: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    # Fecha y hora en que el registro llegó al servidor.
    fecha_hora_recepcion: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    resultado: Mapped[str] = mapped_column(String(20))
    observaciones: Mapped[str] = mapped_column(Text, default="")
    # Identificador generado al abrir el formulario: si el mismo envío llega dos
    # veces (por ejemplo, un reintento), la segunda vez no se duplica.
    uuid_cliente: Mapped[str] = mapped_column(String(36), unique=True)

    ronda_activo: Mapped[RondaActivo] = relationship(back_populates="verificacion")
    usuario: Mapped[Usuario] = relationship()
    evidencias: Mapped[list["Evidencia"]] = relationship(
        back_populates="verificacion", cascade="all, delete-orphan", order_by="Evidencia.id"
    )
    hallazgos: Mapped[list["Hallazgo"]] = relationship(
        back_populates="verificacion", cascade="all, delete-orphan", order_by="Hallazgo.id"
    )


class Evidencia(Base):
    """Archivo (fotografía) que respalda una verificación (HU-009 c2).

    El archivo se guarda en el volumen de evidencia; acá queda su ruta relativa.
    """

    __tablename__ = "evidencia"

    id: Mapped[int] = mapped_column(primary_key=True)
    verificacion_id: Mapped[int] = mapped_column(
        ForeignKey("verificacion.id", ondelete="CASCADE")
    )
    tipo: Mapped[str] = mapped_column(String(20), default="foto")
    ruta_archivo: Mapped[str] = mapped_column(String(300))
    fecha_hora: Mapped[datetime] = mapped_column(DateTime(timezone=True))

    verificacion: Mapped[Verificacion] = relationship(back_populates="evidencias")


class Hallazgo(Base):
    """Anomalía observada en una verificación (HU-010)."""

    __tablename__ = "hallazgo"

    id: Mapped[int] = mapped_column(primary_key=True)
    verificacion_id: Mapped[int] = mapped_column(
        ForeignKey("verificacion.id", ondelete="CASCADE")
    )
    tipo: Mapped[str] = mapped_column(String(100))
    descripcion: Mapped[str] = mapped_column(Text)
    # Marca la derivación al procedimiento correctivo. El sistema la registra;
    # no gestiona la emergencia.
    requiere_atencion_inmediata: Mapped[bool] = mapped_column(Boolean, default=False)

    verificacion: Mapped[Verificacion] = relationship(back_populates="hallazgos")
