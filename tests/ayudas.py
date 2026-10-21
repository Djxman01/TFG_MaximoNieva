"""Funciones que reutilizan varias pruebas de rondas."""

from sqlalchemy import select

from app.models import Activo, Ronda

ACTIVOS_RONDA_024 = ["Pozo A-14", "Pozo A-08", "Pozo B-03", "Batería 2", "Pozo C-07"]

DATOS_RONDA_024 = {
    "fecha_planificada": "2026-11-05",
    "medio_inspeccion": "Vehículo terrestre",
    "origen": "Base Norte",
    "tiempo_disponible": "240",
    "velocidad_media": "40",
    "duracion_inspeccion": "30",
    "restricciones": "",
}


def ids_de_activos(db, codigos):
    return [db.scalars(select(Activo).where(Activo.codigo == c)).one().id for c in codigos]


def crear_ronda(cliente, db, codigos=ACTIVOS_RONDA_024, **cambios) -> Ronda:
    """Crea una ronda por la web y le asocia los activos indicados."""
    datos = {**DATOS_RONDA_024, **cambios}
    respuesta = cliente.post("/rondas", data=datos, follow_redirects=False)
    assert respuesta.status_code == 303, respuesta.text
    ronda_id = int(respuesta.headers["location"].rsplit("/", 1)[1])
    if codigos:
        cliente.post(
            f"/rondas/{ronda_id}/activos",
            data={"activos": ids_de_activos(db, codigos)},
            follow_redirects=False,
        )
    db.expire_all()
    return db.get(Ronda, ronda_id)


def codigos_en_orden(ronda, campo="orden_propuesto"):
    """Códigos de los activos ordenados por el campo indicado (sin los NULL)."""
    con_orden = [ra for ra in ronda.activos if getattr(ra, campo) is not None]
    con_orden.sort(key=lambda ra: getattr(ra, campo))
    return [ra.activo.codigo for ra in con_orden]
