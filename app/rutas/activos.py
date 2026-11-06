"""Pantallas de activos y de evaluación de criticidad (HU-002, HU-004)."""

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import RedirectResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.coordenadas import a_lat_lon, desde_lat_lon
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


# ---------- HU-002: alta y edición de activos ----------

TIPOS_DE_ACTIVO = ["Pozo de petróleo", "Pozo de gas", "Batería", "Manifold", "Planta"]

# Rango aproximado de la faja 2 de POSGAR 2007 (EPSG:5344), en metros.
ESTE_MINIMO, ESTE_MAXIMO = 2_300_000, 2_700_000
NORTE_MINIMO, NORTE_MAXIMO = 3_800_000, 7_400_000


def leer_decimal(texto: str) -> float | None:
    """Convierte "2512000,50" o "2512000.50" en número. None si está vacío o no es número."""
    texto = (texto or "").strip().replace(" ", "").replace(",", ".")
    if not texto:
        return None
    try:
        return float(texto)
    except ValueError:
        return None


def datos_de_activo(activo: Activo | None) -> dict:
    """Valores iniciales del formulario: vacío para un activo nuevo."""
    if activo is None:
        return {
            "codigo": "", "tipo": "", "coordenada_x": "", "coordenada_y": "",
            "latitud": "", "longitud": "", "estado": "activo",
            "telesupervision": False, "condicion_acceso": "",
        }
    return {
        "codigo": activo.codigo,
        "tipo": activo.tipo,
        "coordenada_x": f"{float(activo.coordenada_x):.2f}",
        "coordenada_y": f"{float(activo.coordenada_y):.2f}",
        "latitud": "",
        "longitud": "",
        "estado": activo.estado,
        "telesupervision": activo.telesupervision,
        "condicion_acceso": activo.condicion_acceso,
    }


def validar_activo(db: Session, datos: dict, activo_id: int | None) -> tuple[dict, list[str]]:
    """Revisa el formulario de activo (HU-002 c3). Devuelve los valores y los errores.

    La ubicación se carga en metros (Gauss-Krüger, faja 2) o, si se tiene la
    posición de un GPS, en latitud y longitud: en ese caso se convierte con pyproj.
    """
    errores = []
    valores = {}

    codigo = datos["codigo"].strip()
    if not codigo:
        errores.append("Falta el código del activo.")
    else:
        existente = db.scalars(select(Activo).where(Activo.codigo == codigo)).first()
        if existente is not None and existente.id != activo_id:
            errores.append(f"Ya existe un activo con el código {codigo}.")
        valores["codigo"] = codigo

    tipo = datos["tipo"].strip()
    if not tipo:
        errores.append("Falta el tipo de activo.")
    valores["tipo"] = tipo

    x, y = leer_decimal(datos["coordenada_x"]), leer_decimal(datos["coordenada_y"])
    latitud, longitud = leer_decimal(datos["latitud"]), leer_decimal(datos["longitud"])
    if x is None and y is None and latitud is not None and longitud is not None:
        # Posición de GPS: se pasa a metros en la faja 2.
        x, y = desde_lat_lon(latitud, longitud)
    if x is None or y is None:
        errores.append(
            "Falta la ubicación: X (este) e Y (norte) en metros, o latitud y longitud del GPS."
        )
    elif not (ESTE_MINIMO <= x <= ESTE_MAXIMO and NORTE_MINIMO <= y <= NORTE_MAXIMO):
        errores.append(
            "La ubicación queda fuera de la faja 2 (POSGAR 2007): revisá que X sea el este "
            "(alrededor de 2.500.000) e Y el norte."
        )
    else:
        valores["coordenada_x"], valores["coordenada_y"] = round(x, 2), round(y, 2)

    if datos["estado"] not in ("activo", "inactivo"):
        errores.append("Elegí el estado del activo.")
    valores["estado"] = datos["estado"]
    valores["telesupervision"] = bool(datos["telesupervision"])
    valores["condicion_acceso"] = datos["condicion_acceso"].strip()
    return valores, errores


def mostrar_formulario_activo(request, usuario, activo, datos, errores, status_code=200):
    # Para un activo existente se muestra también su posición en latitud y longitud.
    posicion_gps = a_lat_lon(activo.coordenada_x, activo.coordenada_y) if activo else None
    return plantillas.TemplateResponse(
        request,
        "activo_formulario.html",
        {
            "usuario": usuario,
            "activo": activo,
            "datos": datos,
            "errores": errores,
            "tipos": TIPOS_DE_ACTIVO,
            "posicion_gps": posicion_gps,
        },
        status_code=status_code,
    )


def leer_formulario_activo(
    codigo: str = Form(default=""),
    tipo: str = Form(default=""),
    coordenada_x: str = Form(default=""),
    coordenada_y: str = Form(default=""),
    latitud: str = Form(default=""),
    longitud: str = Form(default=""),
    estado: str = Form(default="activo"),
    telesupervision: bool = Form(default=False),
    condicion_acceso: str = Form(default=""),
) -> dict:
    """Junta los campos del formulario en un diccionario (se usa como dependencia)."""
    return {
        "codigo": codigo, "tipo": tipo, "coordenada_x": coordenada_x,
        "coordenada_y": coordenada_y, "latitud": latitud, "longitud": longitud,
        "estado": estado, "telesupervision": telesupervision,
        "condicion_acceso": condicion_acceso,
    }


@router.get("/activos/nuevo")
def formulario_activo_nuevo(request: Request, usuario: Usuario = Depends(solo_lider)):
    return mostrar_formulario_activo(request, usuario, None, datos_de_activo(None), [])


@router.post("/activos")
def crear_activo(
    request: Request,
    datos: dict = Depends(leer_formulario_activo),
    usuario: Usuario = Depends(solo_lider),
    db: Session = Depends(obtener_db),
):
    valores, errores = validar_activo(db, datos, None)
    if errores:
        return mostrar_formulario_activo(request, usuario, None, datos, errores, 400)
    activo = Activo(**valores)
    db.add(activo)
    db.commit()
    return RedirectResponse(f"/activos?guardado={activo.id}", status_code=303)


@router.get("/activos/{activo_id}/editar")
def formulario_activo_editar(
    activo_id: int,
    request: Request,
    usuario: Usuario = Depends(solo_lider),
    db: Session = Depends(obtener_db),
):
    activo = buscar_activo(db, activo_id)
    return mostrar_formulario_activo(request, usuario, activo, datos_de_activo(activo), [])


@router.post("/activos/{activo_id}")
def guardar_activo(
    activo_id: int,
    request: Request,
    datos: dict = Depends(leer_formulario_activo),
    usuario: Usuario = Depends(solo_lider),
    db: Session = Depends(obtener_db),
):
    activo = buscar_activo(db, activo_id)
    valores, errores = validar_activo(db, datos, activo.id)
    if errores:
        return mostrar_formulario_activo(request, usuario, activo, datos, errores, 400)
    for campo, valor in valores.items():
        setattr(activo, campo, valor)
    db.commit()
    return RedirectResponse(f"/activos?guardado={activo.id}", status_code=303)


# ---------- Rutas ----------


@router.get("/activos")
def listar_activos(
    request: Request,
    guardado: int | None = None,
    usuario: Usuario = Depends(cualquier_rol),
    db: Session = Depends(obtener_db),
):
    activos = list(db.scalars(select(Activo).order_by(Activo.codigo)))
    guardado_activo = db.get(Activo, guardado) if guardado else None
    return plantillas.TemplateResponse(
        request,
        "activos.html",
        {"usuario": usuario, "activos": activos, "guardado": guardado_activo},
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
