"""Consulta del registro de intentos de ingreso (para el Líder de Operaciones)."""

from fastapi import APIRouter, Depends, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import obtener_db
from app.models import IntentoIngreso, Usuario
from app.plantillas import plantillas
from app.seguridad import ROL_LIDER, esta_bloqueado, requiere_rol

router = APIRouter()
solo_lider = requiere_rol(ROL_LIDER)

RESULTADOS_DE_INGRESO = {"correcto": "Correcto", "fallido": "Fallido", "bloqueado": "Bloqueado"}


@router.get("/ingresos")
def ver_ingresos(
    request: Request,
    usuario: Usuario = Depends(solo_lider),
    db: Session = Depends(obtener_db),
):
    intentos = list(
        db.scalars(
            select(IntentoIngreso)
            .order_by(IntentoIngreso.fecha_hora.desc(), IntentoIngreso.id.desc())
            .limit(200)
        )
    )
    bloqueados = [u for u in db.scalars(select(Usuario).order_by(Usuario.email)) if esta_bloqueado(u)]
    return plantillas.TemplateResponse(
        request,
        "ingresos.html",
        {
            "usuario": usuario,
            "intentos": intentos,
            "bloqueados": bloqueados,
            "resultados": RESULTADOS_DE_INGRESO,
        },
    )
