"""Punto de entrada de la aplicación web."""

from pathlib import Path

from fastapi import Depends, FastAPI, Form, Request
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from starlette.middleware.sessions import SessionMiddleware

from app.config import DURACION_SESION, SECRET_KEY
from app.database import obtener_db
from app.models import Usuario
from app.seguridad import (
    FUNCIONES_POR_ROL,
    NOMBRES_DE_ROL,
    NoAutenticado,
    autenticar,
    usuario_actual,
)

CARPETA_APP = Path(__file__).parent

app = FastAPI(title="Sistema de Rondas de Inspección")

# La sesión se guarda en una cookie firmada con SECRET_KEY: el navegador la
# puede leer, pero si la modifica la firma deja de coincidir y se descarta.
app.add_middleware(
    SessionMiddleware,
    secret_key=SECRET_KEY,
    max_age=DURACION_SESION,
    same_site="lax",
)

app.mount("/static", StaticFiles(directory=CARPETA_APP / "static"), name="static")
plantillas = Jinja2Templates(directory=CARPETA_APP / "templates")


@app.exception_handler(NoAutenticado)
def redirigir_al_ingreso(request: Request, error: NoAutenticado):
    """Quien no inició sesión es enviado a la pantalla de ingreso."""
    return RedirectResponse("/login", status_code=303)


@app.get("/login")
def mostrar_ingreso(request: Request):
    return plantillas.TemplateResponse(request, "login.html", {"error": None})


@app.post("/login")
def ingresar(
    request: Request,
    email: str = Form(),
    clave: str = Form(),
    db: Session = Depends(obtener_db),
):
    usuario = autenticar(db, email, clave)
    if usuario is None:
        return plantillas.TemplateResponse(
            request,
            "login.html",
            {"error": "Correo o contraseña incorrectos."},
            status_code=401,
        )
    # Se descarta cualquier sesión anterior antes de iniciar la nueva.
    request.session.clear()
    request.session["usuario_id"] = usuario.id
    return RedirectResponse("/", status_code=303)


@app.post("/logout")
def salir(request: Request):
    request.session.clear()
    return RedirectResponse("/login", status_code=303)


@app.get("/")
def inicio(request: Request, usuario: Usuario = Depends(usuario_actual)):
    return plantillas.TemplateResponse(
        request,
        "inicio.html",
        {
            "usuario": usuario,
            "nombre_rol": NOMBRES_DE_ROL[usuario.rol],
            "funciones": FUNCIONES_POR_ROL[usuario.rol],
        },
    )
