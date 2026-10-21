"""Datos semilla para la demo: usuarios, criterios de criticidad y activos.

La consigna permite no programar altas y bajas de tablas generales: los activos
(HU-002) y los criterios (HU-003) se cargan desde acá. Todos los datos son
ficticios: los nombres de los activos, las personas y las coordenadas no
corresponden a ninguna operación real.

La carga se puede repetir: lo que ya existe no se duplica.
"""

from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.criticidad import evaluar_factores
from app.models import Activo, CriterioCriticidad, CriticidadActivo, Usuario
from app.seguridad import generar_hash

# Usuarios de prueba, uno por perfil. Sus contraseñas cumplen la política NIST
# y están publicadas en el README: son solo para la demo.
USUARIOS = [
    {"nombre": "Laura Medina", "email": "lider@rondas.demo", "rol": "lider",
     "clave": "laura planifica las rondas"},
    {"nombre": "Pablo Ríos", "email": "operador@rondas.demo", "rol": "operador",
     "clave": "pablo recorre los pozos"},
]

# Factores de evaluación (HU-003). La clave corta sirve para referirlos abajo.
CRITERIOS = {
    "hallazgos": ("probabilidad", None,
                  "Registró hallazgos o incidentes en los últimos 12 meses", ""),
    "desvios": ("probabilidad", None,
                "Registró desvíos de parámetros en la última ronda", ""),
    "presion": ("probabilidad", None,
                "Opera con presión por encima del rango de referencia", ""),
    "personas": ("consecuencia", "personas",
                 "Riesgo para las personas por las características del fluido",
                 "Por ejemplo, pozos de gas con presión relevante"),
    "ambiente": ("consecuencia", "ambiente",
                 "Potencial de afectación ambiental ante pérdida de contención", ""),
    "produccion": ("consecuencia", "produccion",
                   "Su salida de servicio reduce la producción del área", ""),
    "concentradora": ("consecuencia", "produccion",
                      "Instalación concentradora: su falla afecta a otros activos",
                      "Aplica a baterías, manifolds y plantas"),
}

# Activos. Coordenadas en metros, EPSG:5344 (x = este, y = norte).
# Los cinco primeros son los de la Ronda #024 de las pantallas de la tesis: con
# origen en Base Norte, 40 km/h y 30 min por inspección, la regla propone
# A-14, A-08, B-03 y Batería 2 (215 min) y deja afuera a C-07 por tiempo.
ACTIVOS = [
    # código, tipo, x, y, telesupervisión, acceso, estado
    ("Pozo A-14", "Pozo de petróleo", 2_512_000, 6_515_000, False, "Camino de tierra", "activo"),
    ("Pozo A-08", "Pozo de gas", 2_512_000, 6_535_000, False, "Camino de tierra", "activo"),
    ("Pozo B-03", "Pozo de petróleo", 2_525_947, 6_540_522, True, "Camino consolidado", "activo"),
    ("Batería 2", "Batería", 2_531_033, 6_525_000, True, "Camino consolidado", "activo"),
    ("Pozo C-07", "Pozo de petróleo", 2_497_000, 6_519_000, False, "Huella", "activo"),
    ("Pozo A-21", "Pozo de gas", 2_518_400, 6_509_300, False, "Camino de tierra", "activo"),
    ("Pozo B-11", "Pozo de petróleo", 2_521_700, 6_531_800, True, "Camino consolidado", "activo"),
    ("Pozo C-02", "Pozo de petróleo", 2_493_600, 6_526_400, False, "Huella", "activo"),
    ("Manifold M-1", "Manifold", 2_515_200, 6_522_600, True, "Camino consolidado", "activo"),
    ("Pozo D-05", "Pozo de petróleo", 2_508_300, 6_497_800, False, "Camino de tierra", "inactivo"),
]

# Evaluaciones de criticidad de ejemplo: (activo, fecha, factores marcados).
# Las de un mismo activo van de la más vieja a la más nueva. Los activos que no
# figuran quedan sin evaluar, para mostrar la evaluación en la demo.
EVALUACIONES = [
    ("Pozo A-14", "2026-06-02", ["hallazgos", "ambiente"]),                         # media
    ("Pozo A-14", "2026-09-22", ["hallazgos", "desvios", "ambiente", "produccion"]),  # alta
    ("Pozo A-08", "2026-09-22", ["desvios", "personas"]),                           # alta
    ("Pozo B-03", "2026-09-22", ["hallazgos", "ambiente"]),                         # media
    ("Batería 2", "2026-09-22", ["hallazgos", "concentradora"]),                    # media
    ("Pozo C-07", "2026-09-22", ["produccion"]),                                    # baja
    ("Pozo B-11", "2026-09-23", []),                                                # baja
    ("Manifold M-1", "2026-09-23", ["presion", "concentradora"]),                   # media
]


def cargar_datos_semilla(db: Session) -> None:
    usuarios = {}
    for datos in USUARIOS:
        usuario = db.scalars(select(Usuario).where(Usuario.email == datos["email"])).first()
        if usuario is None:
            usuario = Usuario(
                nombre=datos["nombre"],
                email=datos["email"],
                rol=datos["rol"],
                clave_hash=generar_hash(datos["clave"]),
            )
            db.add(usuario)
        usuarios[datos["rol"]] = usuario

    criterios = {}
    for clave, (dimension, nivel, nombre, descripcion) in CRITERIOS.items():
        criterio = db.scalars(
            select(CriterioCriticidad).where(CriterioCriticidad.nombre == nombre)
        ).first()
        if criterio is None:
            criterio = CriterioCriticidad(
                nombre=nombre, descripcion=descripcion, habilitado=True,
                dimension=dimension, nivel=nivel,
            )
            db.add(criterio)
        criterios[clave] = criterio

    activos = {}
    activos_nuevos = set()
    for codigo, tipo, x, y, telesupervision, acceso, estado in ACTIVOS:
        activo = db.scalars(select(Activo).where(Activo.codigo == codigo)).first()
        if activo is None:
            activo = Activo(
                codigo=codigo, tipo=tipo, coordenada_x=x, coordenada_y=y,
                telesupervision=telesupervision, condicion_acceso=acceso, estado=estado,
            )
            db.add(activo)
            activos_nuevos.add(codigo)
        activos[codigo] = activo

    # Las evaluaciones de ejemplo se cargan solo para los activos recién creados.
    for codigo, fecha, claves in EVALUACIONES:
        if codigo not in activos_nuevos:
            continue
        marcados = [criterios[clave] for clave in claves]
        resultado = evaluar_factores(
            sum(1 for c in marcados if c.dimension == "probabilidad"),
            [c.nivel for c in marcados if c.dimension == "consecuencia"],
        )
        db.add(
            CriticidadActivo(
                activo=activos[codigo],
                usuario=usuarios["lider"],
                categoria=resultado["categoria"],
                probabilidad=resultado["probabilidad"],
                consecuencia=resultado["consecuencia"],
                # 13:00 UTC = 10:00 en Argentina.
                fecha_hora_evaluacion=datetime.fromisoformat(fecha + "T13:00:00").replace(
                    tzinfo=timezone.utc
                ),
                observaciones="Evaluación de ejemplo (datos semilla).",
                criterios=marcados,
            )
        )

    db.commit()
