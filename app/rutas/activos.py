"""Pantallas de activos y de evaluación de criticidad (HU-002 consulta, HU-004)."""

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import RedirectResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.criticidad import MATRIZ, evaluar_factores
from app.database import obtener_db
from app.horario import ahora
from app.models import Activo, CriterioCriticidad, CriticidadActivo, Usuario
from app.plantillas import plantillas
from app.seguridad import ROL_LIDER, ROL_OPERADOR, requiere_rol

router = APIRouter()

solo_lider = requiere_rol(ROL_LIDER)
cualquier_rol = requiere_rol(ROL_LIDER, ROL_OPERADOR)


# ---------- Funciones auxiliares ----------


def buscar_activo(db: Session, activo_id: int) -> Activo:
    activo = db.get(Activo, activo_id)
    if activo is None:
        raise HTTPException(status_code=404, detail="El activo no existe.")
    return activo


def criterios_habilitados(db: Session) -> list[CriterioCriticidad]:
    consulta = (
        select(CriterioCriticidad)
        .where(CriterioCriticidad.habilitado.is_(True))
        .order_by(CriterioCriticidad.id)
    )
    return list(db.scalars(consulta))


def configuracion_completa(criterios: list[CriterioCriticidad]) -> bool:
    """HU-003 c3: hace falta al menos un criterio habilitado de cada dimensión."""
    dimensiones = {criterio.dimension for criterio in criterios}
    return {"probabilidad", "consecuencia"} <= dimensiones


def evaluar_marcados(criterios: list[CriterioCriticidad], ids_marcados: list[int]) -> dict:
    """Calcula probabilidad, consecuencia y categoría a partir de los ids marcados.

    Solo cuentan los criterios habilitados: un id desconocido se ignora.
    """
    marcados = [criterio for criterio in criterios if criterio.id in ids_marcados]
    cantidad_probabilidad = sum(1 for c in marcados if c.dimension == "probabilidad")
    niveles_consecuencia = [c.nivel for c in marcados if c.dimension == "consecuencia"]
    resultado = evaluar_factores(cantidad_probabilidad, niveles_consecuencia)
    resultado["marcados"] = marcados
    return resultado


def contexto_evaluacion(db: Session, activo: Activo, ids_marcados: list[int]) -> dict:
    criterios = criterios_habilitados(db)
    return {
        "activo": activo,
        "vigente": activo.criticidad_vigente(),
        "criterios_probabilidad": [c for c in criterios if c.dimension == "probabilidad"],
        "criterios_consecuencia": [c for c in criterios if c.dimension == "consecuencia"],
        "configuracion_completa": configuracion_completa(criterios),
        "ids_marcados": ids_marcados,
        "resultado": evaluar_marcados(criterios, ids_marcados),
        "matriz": MATRIZ,
    }


# ---------- Rutas ----------


@router.get("/activos")
def listar_activos(
    request: Request,
    usuario: Usuario = Depends(cualquier_rol),
    db: Session = Depends(obtener_db),
):
    activos = list(db.scalars(select(Activo).order_by(Activo.codigo)))
    return plantillas.TemplateResponse(
        request, "activos.html", {"usuario": usuario, "activos": activos}
    )


@router.get("/activos/{activo_id}/criticidad")
def ver_evaluacion(
    activo_id: int,
    request: Request,
    guardado: bool = False,
    usuario: Usuario = Depends(solo_lider),
    db: Session = Depends(obtener_db),
):
    activo = buscar_activo(db, activo_id)
    vigente = activo.criticidad_vigente()
    # Se parte de los factores de la evaluación vigente, si existe.
    ids_marcados = [criterio.id for criterio in vigente.criterios] if vigente else []
    contexto = contexto_evaluacion(db, activo, ids_marcados)
    contexto.update({"usuario": usuario, "guardado": guardado, "error": None})
    return plantillas.TemplateResponse(request, "criticidad.html", contexto)


@router.post("/activos/{activo_id}/criticidad/vista-previa")
def vista_previa(
    activo_id: int,
    request: Request,
    criterios: list[int] = Form(default=[]),
    usuario: Usuario = Depends(solo_lider),
    db: Session = Depends(obtener_db),
):
    """Recalcula el resultado mientras se marcan factores (HU-004 c2), sin guardar.

    La pide htmx cada vez que cambia una casilla, y devuelve solo el panel del
    resultado para reemplazarlo en la pantalla.
    """
    activo = buscar_activo(db, activo_id)
    contexto = contexto_evaluacion(db, activo, criterios)
    return plantillas.TemplateResponse(request, "_resultado_criticidad.html", contexto)


@router.post("/activos/{activo_id}/criticidad")
def guardar_evaluacion(
    activo_id: int,
    request: Request,
    criterios: list[int] = Form(default=[]),
    observaciones: str = Form(default=""),
    usuario: Usuario = Depends(solo_lider),
    db: Session = Depends(obtener_db),
):
    activo = buscar_activo(db, activo_id)
    contexto = contexto_evaluacion(db, activo, criterios)

    if not contexto["configuracion_completa"]:
        contexto.update(
            {
                "usuario": usuario,
                "guardado": False,
                "error": "La configuración de criterios no está completa: hace falta al "
                "menos un criterio habilitado de probabilidad y uno de consecuencia.",
            }
        )
        return plantillas.TemplateResponse(
            request, "criticidad.html", contexto, status_code=400
        )

    resultado = contexto["resultado"]
    # Siempre se crea una evaluación nueva: las anteriores quedan como historial.
    evaluacion = CriticidadActivo(
        activo=activo,
        usuario=usuario,
        categoria=resultado["categoria"],
        probabilidad=resultado["probabilidad"],
        consecuencia=resultado["consecuencia"],
        fecha_hora_evaluacion=ahora(),
        observaciones=observaciones.strip(),
        criterios=resultado["marcados"],
    )
    db.add(evaluacion)
    db.commit()
    return RedirectResponse(f"/activos/{activo.id}/criticidad?guardado=1", status_code=303)
