"""Pantallas de planificación de la ronda.

HU-005 crear ronda · HU-006 seleccionar activos.
"""

from datetime import date
from decimal import Decimal, InvalidOperation

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import RedirectResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.catalogos import (
    BASES,
    DURACION_INSPECCION_POR_DEFECTO,
    MEDIOS_DE_INSPECCION,
    VELOCIDAD_MEDIA_POR_DEFECTO,
    nombre_de_base,
)
from app.database import obtener_db
from app.models import CONDICIONES, ESTADOS_RONDA, Activo, Ronda, RondaActivo, Usuario
from app.plantillas import plantillas
from app.seguridad import ROL_LIDER, requiere_rol

router = APIRouter()
solo_lider = requiere_rol(ROL_LIDER)

plantillas.env.globals["ESTADOS_RONDA"] = ESTADOS_RONDA
plantillas.env.globals["CONDICIONES"] = CONDICIONES
plantillas.env.globals["nombre_de_base"] = nombre_de_base


# ---------- Funciones auxiliares ----------


def buscar_ronda(db: Session, ronda_id: int) -> Ronda:
    ronda = db.get(Ronda, ronda_id)
    if ronda is None:
        raise HTTPException(status_code=404, detail="La ronda no existe.")
    return ronda


def exigir_borrador(ronda: Ronda) -> None:
    """La planificación solo se puede cambiar mientras la ronda está en borrador."""
    if ronda.estado != "borrador":
        raise HTTPException(
            status_code=409,
            detail=f"La ronda {ronda.numero} ya está {ESTADOS_RONDA[ronda.estado].lower()}: "
            "su planificación no se puede modificar.",
        )


def leer_numero(texto: str, entero: bool = False):
    """Convierte el texto de un campo en número. Devuelve None si no es válido."""
    try:
        valor = Decimal(texto.strip().replace(",", "."))
    except (InvalidOperation, AttributeError):
        return None
    if valor <= 0:
        return None
    if entero:
        return int(valor) if valor == int(valor) else None
    return valor


def validar_ronda(datos: dict) -> tuple[dict, list[str]]:
    """Revisa el formulario de nueva ronda (HU-005 c3).

    Devuelve los valores convertidos y la lista de lo que falta o está mal.
    """
    errores = []
    valores = {}

    try:
        valores["fecha_planificada"] = date.fromisoformat(datos["fecha_planificada"])
    except ValueError:
        errores.append("Falta la fecha planificada.")

    if datos["medio_inspeccion"] in MEDIOS_DE_INSPECCION:
        valores["medio_inspeccion"] = datos["medio_inspeccion"]
    else:
        errores.append("Falta el medio de inspección.")

    if datos["origen"] in BASES:
        valores["origen_x"], valores["origen_y"] = BASES[datos["origen"]]
    else:
        errores.append("Falta el origen del recorrido.")

    campos_numericos = [
        ("tiempo_disponible", "el tiempo disponible (minutos)", True),
        ("velocidad_media", "la velocidad media (km/h)", False),
        ("duracion_inspeccion", "la duración de cada inspección (minutos)", True),
    ]
    for campo, descripcion, entero in campos_numericos:
        numero = leer_numero(datos[campo], entero)
        if numero is None:
            errores.append(f"Falta {descripcion} o no es un número mayor que cero.")
        else:
            valores[campo] = numero

    valores["restricciones"] = datos["restricciones"].strip()
    return valores, errores


def activos_seleccionables(db: Session) -> list[Activo]:
    """Activos que se pueden agregar a una ronda: solo los que están en servicio."""
    consulta = select(Activo).where(Activo.estado == "activo").order_by(Activo.codigo)
    return list(db.scalars(consulta))


def anular_propuesta(ronda: Ronda) -> None:
    """Borra la propuesta y el ajuste: hay que volver a generarlos."""
    for ronda_activo in ronda.activos:
        ronda_activo.orden_propuesto = None
        ronda_activo.orden_planificado = None
        ronda_activo.motivo_ajuste = None
        ronda_activo.criticidad_activo_id = None


def tiene_propuesta(ronda: Ronda) -> bool:
    return any(ra.criticidad_activo_id is not None for ra in ronda.activos)


def contexto_planificacion(db: Session, ronda: Ronda, usuario: Usuario) -> dict:
    return {
        "usuario": usuario,
        "ronda": ronda,
        "seleccionables": activos_seleccionables(db),
        "ids_en_ronda": {ra.activo_id for ra in ronda.activos},
        "propuesta": None,
        "aviso": None,
        "error": None,
    }


# ---------- HU-005: rondas ----------


@router.get("/rondas")
def listar_rondas(
    request: Request,
    usuario: Usuario = Depends(solo_lider),
    db: Session = Depends(obtener_db),
):
    rondas = list(db.scalars(select(Ronda).order_by(Ronda.id.desc())))
    return plantillas.TemplateResponse(
        request, "rondas.html", {"usuario": usuario, "rondas": rondas}
    )


def contexto_formulario(usuario: Usuario, datos: dict, errores: list[str]) -> dict:
    return {
        "usuario": usuario,
        "datos": datos,
        "errores": errores,
        "bases": BASES,
        "medios": MEDIOS_DE_INSPECCION,
    }


@router.get("/rondas/nueva")
def formulario_ronda(request: Request, usuario: Usuario = Depends(solo_lider)):
    datos = {
        "fecha_planificada": "",
        "medio_inspeccion": MEDIOS_DE_INSPECCION[0],
        "origen": "",
        "tiempo_disponible": "",
        "velocidad_media": str(VELOCIDAD_MEDIA_POR_DEFECTO),
        "duracion_inspeccion": str(DURACION_INSPECCION_POR_DEFECTO),
        "restricciones": "",
    }
    return plantillas.TemplateResponse(
        request, "ronda_nueva.html", contexto_formulario(usuario, datos, [])
    )


@router.post("/rondas")
def crear_ronda(
    request: Request,
    fecha_planificada: str = Form(default=""),
    medio_inspeccion: str = Form(default=""),
    origen: str = Form(default=""),
    tiempo_disponible: str = Form(default=""),
    velocidad_media: str = Form(default=""),
    duracion_inspeccion: str = Form(default=""),
    restricciones: str = Form(default=""),
    usuario: Usuario = Depends(solo_lider),
    db: Session = Depends(obtener_db),
):
    datos = {
        "fecha_planificada": fecha_planificada,
        "medio_inspeccion": medio_inspeccion,
        "origen": origen,
        "tiempo_disponible": tiempo_disponible,
        "velocidad_media": velocidad_media,
        "duracion_inspeccion": duracion_inspeccion,
        "restricciones": restricciones,
    }
    valores, errores = validar_ronda(datos)
    if errores:
        return plantillas.TemplateResponse(
            request,
            "ronda_nueva.html",
            contexto_formulario(usuario, datos, errores),
            status_code=400,
        )
    ronda = Ronda(usuario=usuario, estado="borrador", **valores)
    db.add(ronda)
    db.commit()
    return RedirectResponse(f"/rondas/{ronda.id}", status_code=303)


# ---------- HU-006: selección de activos ----------


@router.get("/rondas/{ronda_id}")
def ver_planificacion(
    ronda_id: int,
    request: Request,
    usuario: Usuario = Depends(solo_lider),
    db: Session = Depends(obtener_db),
):
    ronda = buscar_ronda(db, ronda_id)
    contexto = contexto_planificacion(db, ronda, usuario)
    return plantillas.TemplateResponse(request, "planificacion.html", contexto)


@router.post("/rondas/{ronda_id}/activos")
def guardar_seleccion(
    ronda_id: int,
    request: Request,
    activos: list[int] = Form(default=[]),
    usuario: Usuario = Depends(solo_lider),
    db: Session = Depends(obtener_db),
):
    """Asocia a la ronda los activos marcados y quita los desmarcados (HU-006)."""
    ronda = buscar_ronda(db, ronda_id)
    exigir_borrador(ronda)

    # Un conjunto (set) no admite repetidos: aunque llegue dos veces el mismo id,
    # el activo se agrega una sola vez (HU-006 c3).
    elegidos = {activo.id for activo in activos_seleccionables(db) if activo.id in activos}
    actuales = {ra.activo_id for ra in ronda.activos}

    if elegidos != actuales:
        for ronda_activo in list(ronda.activos):
            if ronda_activo.activo_id not in elegidos:
                ronda.activos.remove(ronda_activo)  # HU-006 c4: quitar antes de la ronda
        for activo_id in sorted(elegidos - actuales):
            ronda.activos.append(RondaActivo(activo_id=activo_id))
        # Cambió la selección: la propuesta anterior ya no corresponde.
        anular_propuesta(ronda)
        db.commit()

    return RedirectResponse(f"/rondas/{ronda.id}", status_code=303)
