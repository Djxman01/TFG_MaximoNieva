"""Fechas y horas.

En la base se guarda todo en UTC. Para mostrar, se pasa a la hora de Argentina.
"""

from datetime import datetime, timezone
from zoneinfo import ZoneInfo

ZONA_ARGENTINA = ZoneInfo("America/Argentina/Buenos_Aires")


def ahora() -> datetime:
    """Fecha y hora actual en UTC."""
    return datetime.now(timezone.utc)


def a_hora_local(momento: datetime | None) -> datetime | None:
    if momento is None:
        return None
    if momento.tzinfo is None:
        # SQLite (que se usa en las pruebas) devuelve las fechas sin zona: son UTC.
        momento = momento.replace(tzinfo=timezone.utc)
    return momento.astimezone(ZONA_ARGENTINA)


def formato_fecha_hora(momento: datetime | None) -> str:
    local = a_hora_local(momento)
    return local.strftime("%d/%m/%Y %H:%M") if local else "—"


def formato_fecha(momento) -> str:
    if momento is None:
        return "—"
    if isinstance(momento, datetime):
        momento = a_hora_local(momento)
    return momento.strftime("%d/%m/%Y")
