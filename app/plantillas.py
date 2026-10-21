"""Configuración de las plantillas Jinja2, compartida por todas las rutas."""

from pathlib import Path

from fastapi.templating import Jinja2Templates

from app.horario import formato_fecha, formato_fecha_hora
from app.seguridad import NOMBRES_DE_ROL

plantillas = Jinja2Templates(directory=Path(__file__).parent / "templates")

# Funciones que se pueden usar dentro de las plantillas con la forma {{ valor | filtro }}.
plantillas.env.filters["fecha_hora"] = formato_fecha_hora
plantillas.env.filters["fecha"] = formato_fecha
plantillas.env.filters["titulo"] = lambda texto: (texto or "").capitalize()
plantillas.env.filters["metros"] = lambda valor: f"{float(valor):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
plantillas.env.globals["NOMBRES_DE_ROL"] = NOMBRES_DE_ROL
