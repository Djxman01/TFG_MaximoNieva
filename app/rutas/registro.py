"""Registro de la ronda en campo (pantalla 05, formato tableta).

HU-009 verificación y evidencia · HU-010 hallazgos · HU-011 estado de atención.
"""

import uuid
from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, RedirectResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import EVIDENCIA_DIR
from app.database import obtener_db
from app.horario import ZONA_ARGENTINA, a_hora_local, ahora
from app.models import (
    ESTADOS_ATENCION,
    RESULTADOS,
    Evidencia,
    Hallazgo,
    Ronda,
    RondaActivo,
    Usuario,
    Verificacion,
)
from app.plantillas import plantillas
from app.seguridad import ROL_LIDER, ROL_OPERADOR, requiere_rol

router = APIRouter()
solo_operador = requiere_rol(ROL_OPERADOR)
cualquier_rol = requiere_rol(ROL_LIDER, ROL_OPERADOR)

plantillas.env.globals["ESTADOS_ATENCION"] = ESTADOS_ATENCION
plantillas.env.globals["RESULTADOS"] = RESULTADOS

# Evidencia: solo imágenes, hasta 10 archivos de 10 MB cada uno.
EXTENSIONES_PERMITIDAS = {".jpg", ".jpeg", ".png", ".webp", ".heic"}
TAMANO_MAXIMO = 10 * 1024 * 1024
MAXIMO_ARCHIVOS = 10
LARGO_OBSERVACIONES = 500


# ---------- Funciones auxiliares ----------


def buscar_ronda_en_campo(db: Session, ronda_id: int) -> Ronda:
    """Solo se registran rondas programadas (planificada) o en ejecución."""
    ronda = db.get(Ronda, ronda_id)
    if ronda is None:
        raise HTTPException(status_code=404, detail="La ronda no existe.")
    if ronda.estado not in ("planificada", "en_ejecucion"):
        raise HTTPException(
            status_code=409, detail=f"La ronda {ronda.numero} no está disponible para registrar."
        )
    return ronda


def paradas_de(ronda: Ronda) -> list[RondaActivo]:
    """Activos del recorrido confirmado, en el orden planificado."""
    paradas = [ra for ra in ronda.activos if ra.orden_planificado is not None]
    return sorted(paradas, key=lambda ra: ra.orden_planificado)


def buscar_parada(ronda: Ronda, ronda_activo_id: int) -> RondaActivo:
    for parada in paradas_de(ronda):
        if parada.id == ronda_activo_id:
            return parada
    raise HTTPException(status_code=404, detail="El activo no forma parte del recorrido.")


def avance(ronda: Ronda) -> dict:
    paradas = paradas_de(ronda)
    atendidas = [ra for ra in paradas if ra.estado_atencion != "pendiente"]
    total = len(paradas)
    return {
        "total": total,
        "atendidas": len(atendidas),
        "porcentaje": round(100 * len(atendidas) / total) if total else 0,
    }


def leer_fecha_hora_local(texto: str) -> datetime | None:
    """Convierte "AAAA-MM-DDTHH:MM" (hora de Argentina) a UTC, que es como se guarda."""
    try:
        local = datetime.fromisoformat(texto).replace(tzinfo=ZONA_ARGENTINA)
    except ValueError:
        return None
    return local.astimezone(timezone.utc)


def extension_de(archivo: UploadFile) -> str:
    return Path(archivo.filename or "").suffix.lower()


def contexto_formulario(ronda: Ronda, parada: RondaActivo, usuario: Usuario, datos: dict) -> dict:
    paradas = paradas_de(ronda)
    return {
        "usuario": usuario,
        "ronda": ronda,
        "parada": parada,
        "posicion": paradas.index(parada) + 1,
        "avance": avance(ronda),
        "datos": datos,
        "errores": [],
    }


# ---------- Rutas del operador ----------


@router.get("/registro")
def rondas_a_ejecutar(
    request: Request,
    usuario: Usuario = Depends(solo_operador),
    db: Session = Depends(obtener_db),
):
    consulta = (
        select(Ronda)
        .where(Ronda.estado.in_(["planificada", "en_ejecucion"]))
        .order_by(Ronda.fecha_planificada, Ronda.id)
    )
    rondas = [(ronda, avance(ronda)) for ronda in db.scalars(consulta)]
    return plantillas.TemplateResponse(
        request, "registro_rondas.html", {"usuario": usuario, "rondas": rondas}
    )


@router.get("/registro/{ronda_id}")
def paradas_de_la_ronda(
    ronda_id: int,
    request: Request,
    registrado: str = "",
    usuario: Usuario = Depends(solo_operador),
    db: Session = Depends(obtener_db),
):
    ronda = buscar_ronda_en_campo(db, ronda_id)
    paradas = paradas_de(ronda)
    siguiente = next((ra for ra in paradas if ra.estado_atencion == "pendiente"), None)
    return plantillas.TemplateResponse(
        request,
        "registro_paradas.html",
        {
            "usuario": usuario,
            "ronda": ronda,
            "paradas": paradas,
            "siguiente": siguiente,
            "avance": avance(ronda),
            "registrado": registrado,
        },
    )


@router.get("/registro/{ronda_id}/{ronda_activo_id}")
def formulario_verificacion(
    ronda_id: int,
    ronda_activo_id: int,
    request: Request,
    registrado: str = "",
    usuario: Usuario = Depends(solo_operador),
    db: Session = Depends(obtener_db),
):
    ronda = buscar_ronda_en_campo(db, ronda_id)
    parada = buscar_parada(ronda, ronda_activo_id)
    if parada.estado_atencion != "pendiente":
        return RedirectResponse(f"/registro/{ronda.id}", status_code=303)
    datos = {
        # Identificador de este envío, generado al abrir el formulario.
        "uuid": str(uuid.uuid4()),
        "estado": "inspeccionado",
        "resultado": "",
        "observaciones": "",
        "fecha_hora": a_hora_local(ahora()).strftime("%Y-%m-%dT%H:%M"),
        "hallazgo_tipo": "",
        "hallazgo_descripcion": "",
        "atencion_inmediata": False,
    }
    contexto = contexto_formulario(ronda, parada, usuario, datos)
    contexto["registrado"] = registrado
    return plantillas.TemplateResponse(request, "registro_verificacion.html", contexto)


@router.post("/registro/{ronda_id}/{ronda_activo_id}")
def guardar_verificacion(
    ronda_id: int,
    ronda_activo_id: int,
    request: Request,
    uuid_envio: str = Form(default=""),
    estado: str = Form(default=""),
    resultado: str = Form(default=""),
    observaciones: str = Form(default=""),
    fecha_hora: str = Form(default=""),
    hallazgo_tipo: str = Form(default=""),
    hallazgo_descripcion: str = Form(default=""),
    atencion_inmediata: bool = Form(default=False),
    evidencias: list[UploadFile] = File(default=[]),
    usuario: Usuario = Depends(solo_operador),
    db: Session = Depends(obtener_db),
):
    ronda = buscar_ronda_en_campo(db, ronda_id)
    parada = buscar_parada(ronda, ronda_activo_id)

    # Protección contra duplicados: si este mismo envío ya se guardó (por un
    # reintento), no se vuelve a guardar y se sigue como si hubiera salido bien.
    ya_guardada = db.scalars(
        select(Verificacion).where(Verificacion.uuid_cliente == uuid_envio)
    ).first()
    if ya_guardada is not None:
        return RedirectResponse(siguiente_destino(ronda), status_code=303)
    if parada.estado_atencion != "pendiente":
        raise HTTPException(
            status_code=409, detail=f"{parada.activo.codigo} ya tiene su registro en esta ronda."
        )

    datos = {
        "uuid": uuid_envio,
        "estado": estado,
        "resultado": resultado,
        "observaciones": observaciones.strip(),
        "fecha_hora": fecha_hora,
        "hallazgo_tipo": hallazgo_tipo.strip(),
        "hallazgo_descripcion": hallazgo_descripcion.strip(),
        "atencion_inmediata": atencion_inmediata,
    }
    # Los navegadores mandan un archivo vacío cuando no se eligió ninguno.
    archivos = [archivo for archivo in evidencias if archivo.filename]
    errores, contenidos = validar_registro(datos, archivos)
    if errores:
        contexto = contexto_formulario(ronda, parada, usuario, datos)
        contexto["errores"] = errores
        return plantillas.TemplateResponse(
            request, "registro_verificacion.html", contexto, status_code=400
        )

    momento = leer_fecha_hora_local(fecha_hora)
    recepcion = ahora()
    parada.fecha_hora_atencion = momento
    parada.estado_atencion = estado
    if ronda.estado == "planificada":
        ronda.estado = "en_ejecucion"

    if estado == "no_accesible":
        # HU-009 c4: se registra sin verificación, con su observación.
        parada.observacion_atencion = datos["observaciones"]
        db.commit()
        return RedirectResponse(siguiente_destino(ronda, parada), status_code=303)

    verificacion = Verificacion(
        ronda_activo=parada,
        usuario=usuario,
        fecha_hora=momento,
        fecha_hora_recepcion=recepcion,
        resultado=resultado,
        observaciones=datos["observaciones"],
        uuid_cliente=uuid_envio,
    )
    if resultado == "con_hallazgos":
        verificacion.hallazgos.append(
            Hallazgo(
                tipo=datos["hallazgo_tipo"],
                descripcion=datos["hallazgo_descripcion"],
                requiere_atencion_inmediata=atencion_inmediata,
            )
        )
    db.add(verificacion)

    # Los archivos se escriben y la base se confirma juntos: si algo falla, se
    # borran los archivos escritos y no queda nada a medias.
    escritos = []
    try:
        db.flush()  # asigna el id de la verificación
        carpeta = Path(EVIDENCIA_DIR) / f"ronda_{ronda.id}"
        carpeta.mkdir(parents=True, exist_ok=True)
        for numero, (extension, contenido) in enumerate(contenidos, start=1):
            nombre = f"verificacion_{verificacion.id}_{numero}{extension}"
            destino = carpeta / nombre
            destino.write_bytes(contenido)
            escritos.append(destino)
            verificacion.evidencias.append(
                Evidencia(
                    tipo="foto",
                    ruta_archivo=f"ronda_{ronda.id}/{nombre}",
                    fecha_hora=recepcion,
                )
            )
        db.commit()
    except Exception:
        db.rollback()
        for archivo in escritos:
            archivo.unlink(missing_ok=True)
        raise

    return RedirectResponse(siguiente_destino(ronda, parada), status_code=303)


def validar_registro(datos: dict, archivos: list[UploadFile]) -> tuple[list[str], list]:
    """Revisa el formulario. Devuelve los errores y el contenido de las fotos."""
    errores = []
    if not datos["uuid"]:
        errores.append("Falta el identificador del registro: volvé a abrir el formulario.")
    if datos["estado"] not in ESTADOS_ATENCION or datos["estado"] == "pendiente":
        errores.append("Elegí si el activo fue inspeccionado o no fue accesible.")
    if leer_fecha_hora_local(datos["fecha_hora"]) is None:
        errores.append("Falta la fecha y hora de la inspección.")
    if len(datos["observaciones"]) > LARGO_OBSERVACIONES:
        errores.append(f"Las observaciones no pueden superar los {LARGO_OBSERVACIONES} caracteres.")

    if datos["estado"] == "no_accesible":
        if not datos["observaciones"]:
            errores.append("Si el activo no fue accesible, indicá el motivo en las observaciones.")
        return errores, []  # sin verificación no hay resultado ni evidencia

    if datos["resultado"] not in RESULTADOS:
        errores.append("Elegí el resultado: sin hallazgos o con hallazgos.")
    if datos["resultado"] == "con_hallazgos":
        if not datos["hallazgo_tipo"]:
            errores.append("Indicá el tipo de hallazgo.")
        if not datos["hallazgo_descripcion"]:
            errores.append("Describí el hallazgo.")

    contenidos = []
    if len(archivos) > MAXIMO_ARCHIVOS:
        errores.append(f"Se pueden adjuntar hasta {MAXIMO_ARCHIVOS} fotografías.")
    for archivo in archivos[:MAXIMO_ARCHIVOS]:
        extension = extension_de(archivo)
        if extension not in EXTENSIONES_PERMITIDAS:
            errores.append(f"{archivo.filename}: solo se aceptan fotografías (JPG, PNG, WEBP o HEIC).")
            continue
        contenido = archivo.file.read(TAMANO_MAXIMO + 1)
        if len(contenido) > TAMANO_MAXIMO:
            errores.append(f"{archivo.filename}: supera los 10 MB.")
            continue
        contenidos.append((extension, contenido))
    return errores, contenidos


def siguiente_destino(ronda: Ronda, registrada: RondaActivo | None = None) -> str:
    """Después de guardar, se abre la siguiente parada pendiente."""
    siguiente = next((ra for ra in paradas_de(ronda) if ra.estado_atencion == "pendiente"), None)
    aviso = f"?registrado={registrada.activo.codigo}" if registrada else ""
    if siguiente is None:
        return f"/registro/{ronda.id}{aviso}"
    return f"/registro/{ronda.id}/{siguiente.id}{aviso}"


# ---------- Archivos de evidencia ----------


@router.get("/evidencia/{evidencia_id}")
def ver_evidencia(
    evidencia_id: int,
    usuario: Usuario = Depends(cualquier_rol),
    db: Session = Depends(obtener_db),
):
    """Entrega una foto de evidencia. Solo a usuarios que iniciaron sesión."""
    evidencia = db.get(Evidencia, evidencia_id)
    if evidencia is None:
        raise HTTPException(status_code=404, detail="La evidencia no existe.")
    carpeta = Path(EVIDENCIA_DIR).resolve()
    ruta = (carpeta / evidencia.ruta_archivo).resolve()
    # La ruta tiene que quedar dentro de la carpeta de evidencia.
    if carpeta not in ruta.parents or not ruta.is_file():
        raise HTTPException(status_code=404, detail="El archivo de evidencia no está disponible.")
    return FileResponse(ruta)
