"""Pantalla de criterios de criticidad (HU-003).

El Líder de Operaciones da de alta y edita los factores que después se marcan al
evaluar un activo (HU-004).
"""

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import RedirectResponse
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.database import obtener_db
from app.models import CriterioCriticidad, Usuario, criticidad_activo_criterio
from app.plantillas import plantillas
from app.rutas.activos import configuracion_completa
from app.seguridad import ROL_LIDER, requiere_rol

router = APIRouter()
solo_lider = requiere_rol(ROL_LIDER)

DIMENSIONES = {"probabilidad": "Probabilidad", "consecuencia": "Consecuencia"}
NIVELES = {"personas": "Personas", "ambiente": "Ambiente", "produccion": "Producción"}

plantillas.env.globals["DIMENSIONES"] = DIMENSIONES
plantillas.env.globals["NIVELES"] = NIVELES


def buscar_criterio(db: Session, criterio_id: int) -> CriterioCriticidad:
    criterio = db.get(CriterioCriticidad, criterio_id)
    if criterio is None:
        raise HTTPException(status_code=404, detail="El criterio no existe.")
    return criterio


def veces_usado(db: Session, criterio_id: int) -> int:
    """Cuántas evaluaciones de criticidad marcaron este criterio."""
    return db.scalar(
        select(func.count())
        .select_from(criticidad_activo_criterio)
        .where(criticidad_activo_criterio.c.criterio_criticidad_id == criterio_id)
    )


def validar_criterio(datos: dict, usado: bool, criterio: CriterioCriticidad | None):
    """Revisa el formulario (HU-003 c4 y c5). Devuelve los valores y los errores."""
    errores = []
    valores = {
        "nombre": datos["nombre"].strip(),
        "descripcion": datos["descripcion"].strip(),
        "habilitado": bool(datos["habilitado"]),
    }
    if not valores["nombre"]:
        errores.append("Falta el nombre del criterio.")

    if usado:
        # Si el criterio ya se usó en evaluaciones, su dimensión y su nivel no
        # cambian: si cambiaran, el historial se leería distinto de como se calculó.
        valores["dimension"], valores["nivel"] = criterio.dimension, criterio.nivel
        return valores, errores

    dimension = datos["dimension"]
    if dimension not in DIMENSIONES:
        errores.append("Indicá la dimensión del criterio: probabilidad o consecuencia.")
    valores["dimension"] = dimension

    if dimension == "consecuencia":
        if datos["nivel"] not in NIVELES:
            errores.append(
                "Un criterio de consecuencia tiene que indicar si afecta a personas, "
                "ambiente o producción."
            )
        valores["nivel"] = datos["nivel"]
    else:
        valores["nivel"] = None  # la probabilidad no tiene nivel
    return valores, errores


def leer_formulario_criterio(
    nombre: str = Form(default=""),
    descripcion: str = Form(default=""),
    dimension: str = Form(default=""),
    nivel: str = Form(default=""),
    habilitado: bool = Form(default=False),
) -> dict:
    return {
        "nombre": nombre, "descripcion": descripcion, "dimension": dimension,
        "nivel": nivel, "habilitado": habilitado,
    }


def mostrar_formulario(request, usuario, criterio, datos, errores, usado, status_code=200):
    return plantillas.TemplateResponse(
        request,
        "criterio_formulario.html",
        {
            "usuario": usuario, "criterio": criterio, "datos": datos,
            "errores": errores, "usado": usado,
        },
        status_code=status_code,
    )


@router.get("/criterios")
def listar_criterios(
    request: Request,
    guardado: int | None = None,
    usuario: Usuario = Depends(solo_lider),
    db: Session = Depends(obtener_db),
):
    criterios = list(
        db.scalars(
            select(CriterioCriticidad).order_by(
                CriterioCriticidad.dimension.desc(), CriterioCriticidad.id
            )
        )
    )
    habilitados = [c for c in criterios if c.habilitado]
    return plantillas.TemplateResponse(
        request,
        "criterios.html",
        {
            "usuario": usuario,
            "criterios": criterios,
            "usos": {c.id: veces_usado(db, c.id) for c in criterios},
            "configuracion_completa": configuracion_completa(habilitados),
            "guardado": db.get(CriterioCriticidad, guardado) if guardado else None,
        },
    )


@router.get("/criterios/nuevo")
def formulario_nuevo(request: Request, usuario: Usuario = Depends(solo_lider)):
    datos = {"nombre": "", "descripcion": "", "dimension": "", "nivel": "", "habilitado": True}
    return mostrar_formulario(request, usuario, None, datos, [], False)


@router.post("/criterios")
def crear_criterio(
    request: Request,
    datos: dict = Depends(leer_formulario_criterio),
    usuario: Usuario = Depends(solo_lider),
    db: Session = Depends(obtener_db),
):
    valores, errores = validar_criterio(datos, False, None)
    if errores:
        return mostrar_formulario(request, usuario, None, datos, errores, False, 400)
    criterio = CriterioCriticidad(**valores)
    db.add(criterio)
    db.commit()
    return RedirectResponse(f"/criterios?guardado={criterio.id}", status_code=303)


@router.get("/criterios/{criterio_id}/editar")
def formulario_editar(
    criterio_id: int,
    request: Request,
    usuario: Usuario = Depends(solo_lider),
    db: Session = Depends(obtener_db),
):
    criterio = buscar_criterio(db, criterio_id)
    datos = {
        "nombre": criterio.nombre, "descripcion": criterio.descripcion,
        "dimension": criterio.dimension, "nivel": criterio.nivel or "",
        "habilitado": criterio.habilitado,
    }
    usado = veces_usado(db, criterio.id) > 0
    return mostrar_formulario(request, usuario, criterio, datos, [], usado)


@router.post("/criterios/{criterio_id}")
def guardar_criterio(
    criterio_id: int,
    request: Request,
    datos: dict = Depends(leer_formulario_criterio),
    usuario: Usuario = Depends(solo_lider),
    db: Session = Depends(obtener_db),
):
    criterio = buscar_criterio(db, criterio_id)
    usado = veces_usado(db, criterio.id) > 0
    valores, errores = validar_criterio(datos, usado, criterio)
    if errores:
        return mostrar_formulario(request, usuario, criterio, datos, errores, usado, 400)
    for campo, valor in valores.items():
        setattr(criterio, campo, valor)
    db.commit()
    return RedirectResponse(f"/criterios?guardado={criterio.id}", status_code=303)
