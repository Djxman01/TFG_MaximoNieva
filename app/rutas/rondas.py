"""Pantallas de planificación de la ronda.

HU-005 crear ronda · HU-006 seleccionar activos · HU-007 propuesta de orden.
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
from app.coordenadas import a_lat_lon
from app.cobertura import ActivoParaCobertura, calcular_cobertura
from app.ordenamiento import Candidato, minutos_de_tramo, distancia, proponer_orden
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


def candidato_de(ronda_activo: RondaActivo, categoria: str) -> Candidato:
    """Arma lo que necesita la regla de ordenamiento a partir de un activo de la ronda."""
    activo = ronda_activo.activo
    return Candidato(
        id=ronda_activo.id,
        codigo=activo.codigo,
        x=float(activo.coordenada_x),
        y=float(activo.coordenada_y),
        criticidad=categoria,
        telesupervision=activo.telesupervision,
    )


def recorrido(ronda: Ronda, campo: str) -> list[dict]:
    """Los activos ordenados por `orden_propuesto` u `orden_planificado`, con sus tiempos.

    Para cada parada calcula el tiempo del tramo (viaje + inspección) y el acumulado.
    """
    con_orden = [ra for ra in ronda.activos if getattr(ra, campo) is not None]
    con_orden.sort(key=lambda ra: getattr(ra, campo))

    paradas = []
    x, y = float(ronda.origen_x), float(ronda.origen_y)
    acumulado = 0.0
    for ronda_activo in con_orden:
        activo = ronda_activo.activo
        metros = distancia(x, y, float(activo.coordenada_x), float(activo.coordenada_y))
        tramo = minutos_de_tramo(
            metros, float(ronda.velocidad_media), ronda.duracion_inspeccion
        )
        acumulado += tramo
        paradas.append(
            {
                "ra": ronda_activo,
                "orden": getattr(ronda_activo, campo),
                "km": metros / 1000,
                "minutos_tramo": tramo,
                "minutos_acumulados": acumulado,
            }
        )
        x, y = float(activo.coordenada_x), float(activo.coordenada_y)
    return paradas


def datos_propuesta(ronda: Ronda) -> dict | None:
    """Lo que muestra la tarjeta "Orden propuesto por el sistema"."""
    if not tiene_propuesta(ronda):
        return None
    paradas = recorrido(ronda, "orden_propuesto")
    return {
        "paradas": paradas,
        "excluidos": [ra for ra in ronda.activos if ra.orden_propuesto is None],
        "total": paradas[-1]["minutos_acumulados"] if paradas else 0.0,
    }


def datos_mapa(ronda: Ronda, campo: str | None) -> dict:
    """Datos para el mapa de Leaflet, ya convertidos a latitud y longitud.

    `campo` indica qué orden se dibuja: "orden_propuesto", "orden_planificado" o
    None (todavía no hay propuesta: solo se ubican los activos).
    """
    latitud, longitud = a_lat_lon(ronda.origen_x, ronda.origen_y)
    puntos = []
    for ronda_activo in ronda.activos:
        activo = ronda_activo.activo
        if ronda_activo.criticidad is not None:
            categoria = ronda_activo.criticidad.categoria
        else:
            vigente = activo.criticidad_vigente()
            categoria = vigente.categoria if vigente else "sin"
        orden = getattr(ronda_activo, campo) if campo else None
        lat, lon = a_lat_lon(activo.coordenada_x, activo.coordenada_y)
        puntos.append(
            {
                "codigo": activo.codigo,
                "lat": lat,
                "lon": lon,
                "categoria": categoria,
                "orden": orden,
                "excluido": campo is not None and orden is None,
            }
        )
    con_orden = sorted((p for p in puntos if p["orden"]), key=lambda p: p["orden"])
    titulos = {"orden_propuesto": "orden propuesto", "orden_planificado": "orden confirmado"}
    return {
        "titulo_ruta": titulos.get(campo, ""),
        "datos": {
            "origen": {
                "nombre": nombre_de_base(ronda.origen_x, ronda.origen_y),
                "lat": latitud,
                "lon": longitud,
            },
            "puntos": puntos,
            "ruta": [[p["lat"], p["lon"]] for p in con_orden],
        },
    }


def contexto_planificacion(db: Session, ronda: Ronda, usuario: Usuario) -> dict:
    return {
        "mapa": datos_mapa(ronda, "orden_propuesto" if tiene_propuesta(ronda) else None),
        "usuario": usuario,
        "ronda": ronda,
        "seleccionables": activos_seleccionables(db),
        "ids_en_ronda": {ra.activo_id for ra in ronda.activos},
        "propuesta": datos_propuesta(ronda),
        "recorrido_confirmado": any(ra.orden_planificado is not None for ra in ronda.activos),
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


# ---------- HU-007: propuesta de orden ----------


@router.post("/rondas/{ronda_id}/propuesta")
def generar_propuesta(
    ronda_id: int,
    request: Request,
    usuario: Usuario = Depends(solo_lider),
    db: Session = Depends(obtener_db),
):
    ronda = buscar_ronda(db, ronda_id)
    exigir_borrador(ronda)

    if not ronda.activos:
        contexto = contexto_planificacion(db, ronda, usuario)
        contexto["error"] = "La ronda no tiene activos: elegilos antes de generar la propuesta."
        return plantillas.TemplateResponse(
            request, "planificacion.html", contexto, status_code=400
        )

    # HU-007 c4: sin criticidad vigente no se puede ordenar. Se informa cuáles faltan.
    sin_evaluar = [ra.activo.codigo for ra in ronda.activos if ra.activo.criticidad_vigente() is None]
    if sin_evaluar:
        contexto = contexto_planificacion(db, ronda, usuario)
        contexto["error"] = (
            "Hay activos con información incompleta: no tienen criticidad evaluada ("
            + ", ".join(sin_evaluar)
            + "). Evaluálos o quitálos de la ronda para generar la propuesta."
        )
        return plantillas.TemplateResponse(
            request, "planificacion.html", contexto, status_code=400
        )

    # Se congela la criticidad vigente de cada activo para esta ronda.
    anular_propuesta(ronda)
    db.flush()  # se escriben los NULL antes de asignar las posiciones nuevas
    candidatos = []
    for ronda_activo in ronda.activos:
        vigente = ronda_activo.activo.criticidad_vigente()
        ronda_activo.criticidad = vigente
        candidatos.append(candidato_de(ronda_activo, vigente.categoria))

    propuesta = proponer_orden(
        candidatos,
        float(ronda.origen_x),
        float(ronda.origen_y),
        float(ronda.velocidad_media),
        ronda.duracion_inspeccion,
        ronda.tiempo_disponible,
    )
    por_id = {ra.id: ra for ra in ronda.activos}
    for paso in propuesta.pasos:
        por_id[paso.candidato.id].orden_propuesto = paso.orden
    # Los excluidos quedan en la ronda con orden_propuesto = NULL (HU-007 c5).
    db.commit()
    return RedirectResponse(f"/rondas/{ronda.id}", status_code=303)


# ---------- HU-008: revisión, ajuste y confirmación del recorrido ----------
#
# El orden ajustado viaja en el formulario como una lista de ids (campo "orden").
# Las flechas ↑ ↓ le piden al servidor, con htmx, la columna reordenada; recién al
# confirmar se guarda en la base. Así no hace falta JavaScript propio ni guardar
# borradores intermedios.


def exigir_propuesta(ronda: Ronda) -> None:
    if not tiene_propuesta(ronda):
        raise HTTPException(
            status_code=409, detail="Primero hay que generar la propuesta de orden."
        )


def orden_inicial(ronda: Ronda) -> list[int]:
    """Ids de los activos del recorrido: el planificado si existe, si no el propuesto."""
    campo = (
        "orden_planificado"
        if any(ra.orden_planificado is not None for ra in ronda.activos)
        else "orden_propuesto"
    )
    con_orden = [ra for ra in ronda.activos if getattr(ra, campo) is not None]
    con_orden.sort(key=lambda ra: getattr(ra, campo))
    return [ra.id for ra in con_orden]


def orden_valido(ronda: Ronda, orden: list[int]) -> bool:
    """El orden ajustado tiene que contener exactamente los activos propuestos.

    El ajuste cambia la posición de las paradas; no agrega ni quita activos.
    """
    propuestos = {ra.id for ra in ronda.activos if ra.orden_propuesto is not None}
    return len(orden) == len(propuestos) and set(orden) == propuestos


def mover(orden: list[int], movimiento: str) -> list[int]:
    """Aplica un movimiento "arriba:ID" o "abajo:ID" y devuelve el orden nuevo."""
    direccion, _, texto_id = movimiento.partition(":")
    if not texto_id.isdigit() or int(texto_id) not in orden:
        return orden
    nuevo = list(orden)
    i = nuevo.index(int(texto_id))
    j = i - 1 if direccion == "arriba" else i + 1
    if 0 <= j < len(nuevo):
        nuevo[i], nuevo[j] = nuevo[j], nuevo[i]
    return nuevo


def contexto_revision(ronda: Ronda, orden: list[int], usuario: Usuario | None = None) -> dict:
    por_id = {ra.id: ra for ra in ronda.activos}
    propuesta = datos_propuesta(ronda)

    # Recorrido ajustado con sus tiempos y cuánto subió o bajó cada parada.
    ajustado = []
    x, y = float(ronda.origen_x), float(ronda.origen_y)
    acumulado = 0.0
    for posicion, ronda_activo_id in enumerate(orden, start=1):
        ronda_activo = por_id[ronda_activo_id]
        activo = ronda_activo.activo
        metros = distancia(x, y, float(activo.coordenada_x), float(activo.coordenada_y))
        acumulado += minutos_de_tramo(
            metros, float(ronda.velocidad_media), ronda.duracion_inspeccion
        )
        ajustado.append(
            {
                "ra": ronda_activo,
                "orden": posicion,
                # Positivo = subió (está más adelante que en la propuesta).
                "desplazamiento": ronda_activo.orden_propuesto - posicion,
                "minutos_acumulados": acumulado,
            }
        )
        x, y = float(activo.coordenada_x), float(activo.coordenada_y)

    return {
        "usuario": usuario,
        "ronda": ronda,
        "propuesta": propuesta,
        "orden": orden,
        "ajustado": ajustado,
        "total_ajustado": acumulado,
        "difiere": any(parada["desplazamiento"] != 0 for parada in ajustado),
        "motivo": "",
        "error": None,
    }


@router.get("/rondas/{ronda_id}/revision")
def ver_revision(
    ronda_id: int,
    request: Request,
    usuario: Usuario = Depends(solo_lider),
    db: Session = Depends(obtener_db),
):
    ronda = buscar_ronda(db, ronda_id)
    exigir_borrador(ronda)
    exigir_propuesta(ronda)
    contexto = contexto_revision(ronda, orden_inicial(ronda), usuario)
    # Si ya se había confirmado un ajuste, se muestra su motivo.
    motivos = {ra.motivo_ajuste for ra in ronda.activos if ra.motivo_ajuste}
    contexto["motivo"] = motivos.pop() if motivos else ""
    return plantillas.TemplateResponse(request, "revision.html", contexto)


@router.post("/rondas/{ronda_id}/revision/mover")
def mover_parada(
    ronda_id: int,
    request: Request,
    orden: list[int] = Form(default=[]),
    movimiento: str = Form(default=""),
    usuario: Usuario = Depends(solo_lider),
    db: Session = Depends(obtener_db),
):
    """Devuelve solo la columna "Recorrido ajustado" con una parada movida (htmx)."""
    ronda = buscar_ronda(db, ronda_id)
    exigir_borrador(ronda)
    if not orden_valido(ronda, orden):
        orden = orden_inicial(ronda)
    contexto = contexto_revision(ronda, mover(orden, movimiento), usuario)
    return plantillas.TemplateResponse(request, "_recorrido_ajustado.html", contexto)


@router.post("/rondas/{ronda_id}/revision")
def confirmar_recorrido(
    ronda_id: int,
    request: Request,
    orden: list[int] = Form(default=[]),
    motivo: str = Form(default=""),
    usuario: Usuario = Depends(solo_lider),
    db: Session = Depends(obtener_db),
):
    ronda = buscar_ronda(db, ronda_id)
    exigir_borrador(ronda)
    exigir_propuesta(ronda)
    if not orden_valido(ronda, orden):
        raise HTTPException(status_code=400, detail="El orden enviado no es válido.")

    contexto = contexto_revision(ronda, orden, usuario)
    motivo = motivo.strip()
    contexto["motivo"] = motivo

    # HU-008 c5: si el orden ajustado difiere del propuesto, el motivo es obligatorio.
    if contexto["difiere"] and not motivo:
        contexto["error"] = (
            "El recorrido ajustado difiere de la propuesta: indicá el motivo del ajuste."
        )
        return plantillas.TemplateResponse(
            request, "revision.html", contexto, status_code=400
        )

    # Se guarda la secuencia confirmada junto con la propuesta original (HU-008 c2).
    for ronda_activo in ronda.activos:
        ronda_activo.orden_planificado = None
        ronda_activo.motivo_ajuste = None
    db.flush()  # se liberan las posiciones antes de asignar las nuevas
    for parada in contexto["ajustado"]:
        ronda_activo = parada["ra"]
        ronda_activo.orden_planificado = parada["orden"]
        # El motivo queda registrado en las paradas que cambiaron de lugar.
        if parada["desplazamiento"] != 0:
            ronda_activo.motivo_ajuste = motivo
    db.commit()
    return RedirectResponse(f"/rondas/{ronda.id}/confirmacion", status_code=303)


# ---------- HU-014: condiciones de salida y confirmación de la ronda ----------

NOMBRES_DE_CONDICION = {
    "condicion_clima": "Clima",
    "condicion_acceso": "Estado de los accesos",
    "condicion_conectividad": "Conectividad",
}


def recorrido_confirmado(ronda: Ronda) -> bool:
    return any(ra.orden_planificado is not None for ra in ronda.activos)


def contexto_confirmacion(ronda: Ronda, usuario: Usuario, valores: dict | None = None) -> dict:
    paradas = recorrido(ronda, "orden_planificado")
    if valores is None:
        valores = {campo: getattr(ronda, campo) or "" for campo in NOMBRES_DE_CONDICION}
        valores["restricciones"] = ronda.restricciones
    return {
        "usuario": usuario,
        "ronda": ronda,
        "paradas": paradas,
        "excluidos": [ra for ra in ronda.activos if ra.orden_planificado is None],
        "total": paradas[-1]["minutos_acumulados"] if paradas else 0.0,
        "ajustado": any(ra.motivo_ajuste for ra in ronda.activos),
        "condiciones": NOMBRES_DE_CONDICION,
        "valores": valores,
        "errores": [],
    }


@router.get("/rondas/{ronda_id}/confirmacion")
def ver_confirmacion(
    ronda_id: int,
    request: Request,
    usuario: Usuario = Depends(solo_lider),
    db: Session = Depends(obtener_db),
):
    ronda = buscar_ronda(db, ronda_id)
    exigir_borrador(ronda)
    if not recorrido_confirmado(ronda):
        return RedirectResponse(f"/rondas/{ronda.id}/revision", status_code=303)
    return plantillas.TemplateResponse(
        request, "confirmacion.html", contexto_confirmacion(ronda, usuario)
    )


@router.post("/rondas/{ronda_id}/confirmacion")
def programar_ronda(
    ronda_id: int,
    request: Request,
    condicion_clima: str = Form(default=""),
    condicion_acceso: str = Form(default=""),
    condicion_conectividad: str = Form(default=""),
    restricciones: str = Form(default=""),
    usuario: Usuario = Depends(solo_lider),
    db: Session = Depends(obtener_db),
):
    ronda = buscar_ronda(db, ronda_id)
    exigir_borrador(ronda)
    if not recorrido_confirmado(ronda):
        raise HTTPException(status_code=409, detail="Primero hay que confirmar el recorrido.")

    valores = {
        "condicion_clima": condicion_clima,
        "condicion_acceso": condicion_acceso,
        "condicion_conectividad": condicion_conectividad,
        "restricciones": restricciones.strip(),
    }
    errores = [
        f"Falta registrar el estado de: {nombre}."
        for campo, nombre in NOMBRES_DE_CONDICION.items()
        if valores[campo] not in CONDICIONES
    ]
    if errores:
        contexto = contexto_confirmacion(ronda, usuario, valores)
        contexto["errores"] = errores
        return plantillas.TemplateResponse(
            request, "confirmacion.html", contexto, status_code=400
        )

    # Las condiciones se registran siempre, aunque impidan confirmar: así queda
    # constancia de por qué la ronda no salió.
    for campo, valor in valores.items():
        setattr(ronda, campo, valor)

    # HU-014 c2: una condición en "No apto" impide confirmar, y se dice cuál.
    no_aptas = [
        nombre for campo, nombre in NOMBRES_DE_CONDICION.items() if valores[campo] == "no_apto"
    ]
    if no_aptas:
        db.commit()
        contexto = contexto_confirmacion(ronda, usuario, valores)
        contexto["errores"] = [
            "La ronda no se puede confirmar: "
            + ", ".join(no_aptas)
            + (" está" if len(no_aptas) == 1 else " están")
            + " en No apto. Reprogramá la salida cuando las condiciones lo permitan."
        ]
        return plantillas.TemplateResponse(
            request, "confirmacion.html", contexto, status_code=409
        )

    ronda.estado = "planificada"
    db.commit()
    return RedirectResponse(f"/rondas/{ronda.id}/detalle?programada=1", status_code=303)


# ---------- Consulta de la ronda: estado de atención, cobertura y trazabilidad ----------
# HU-011 estado de atención · HU-012 cobertura · HU-013 trazabilidad.


def cobertura_de(ronda: Ronda):
    """Cobertura con la criticidad congelada al planificar (no la actual del activo)."""
    return calcular_cobertura(
        [
            ActivoParaCobertura(ra.criticidad.categoria, ra.estado_atencion)
            for ra in ronda.activos
            if ra.criticidad is not None
        ]
    )


@router.get("/rondas/{ronda_id}/detalle")
def ver_detalle(
    ronda_id: int,
    request: Request,
    programada: bool = False,
    usuario: Usuario = Depends(solo_lider),
    db: Session = Depends(obtener_db),
):
    ronda = buscar_ronda(db, ronda_id)
    if ronda.estado == "borrador":
        return RedirectResponse(f"/rondas/{ronda.id}", status_code=303)
    contexto = contexto_confirmacion(ronda, usuario)
    atendidas = [ra for ra in ronda.activos if ra.fecha_hora_atencion is not None]
    contexto.update(
        {
            "programada": programada,
            "propuesta": datos_propuesta(ronda),
            "cobertura": cobertura_de(ronda),
            # Orden en que la ronda se ejecutó realmente (HU-011, sección 4.5).
            "ejecucion": sorted(atendidas, key=lambda ra: ra.fecha_hora_atencion),
            "verificaciones": [ra.verificacion for ra in ronda.activos if ra.verificacion],
            "mapa": datos_mapa(ronda, "orden_planificado"),
        }
    )
    return plantillas.TemplateResponse(request, "detalle_ronda.html", contexto)


@router.post("/rondas/{ronda_id}/cerrar")
def cerrar_ronda(
    ronda_id: int,
    usuario: Usuario = Depends(solo_lider),
    db: Session = Depends(obtener_db),
):
    """Da por terminada la ronda. Los activos sin registro quedan como pendientes."""
    ronda = buscar_ronda(db, ronda_id)
    if ronda.estado != "en_ejecucion":
        raise HTTPException(
            status_code=409, detail="Solo se puede cerrar una ronda en ejecución."
        )
    ronda.estado = "cerrada"
    db.commit()
    return RedirectResponse(f"/rondas/{ronda.id}/detalle", status_code=303)
