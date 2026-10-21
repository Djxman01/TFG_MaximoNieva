"""Seguridad de acceso (HU-001): contraseñas, autenticación y roles."""

import bcrypt
from fastapi import Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import obtener_db
from app.models import Usuario

# ---------- Roles ----------

ROL_SUPERVISOR = "supervisor"
ROL_OPERADOR = "operador"
ROLES = [ROL_SUPERVISOR, ROL_OPERADOR]

NOMBRES_DE_ROL = {
    ROL_SUPERVISOR: "Supervisor de campo",
    ROL_OPERADOR: "Operador",
}

# Funciones del sistema que corresponden a cada rol.
FUNCIONES_POR_ROL = {
    ROL_SUPERVISOR: [
        "Registrar y consultar activos",
        "Definir los criterios de criticidad",
        "Evaluar la criticidad de los activos",
        "Planificar rondas y confirmar el orden de inspección",
        "Consultar el estado de atención, la cobertura y la trazabilidad",
    ],
    ROL_OPERADOR: [
        "Consultar activos",
        "Registrar verificaciones, evidencia y hallazgos",
    ],
}

# ---------- Contraseñas ----------

LARGO_MINIMO = 8
# bcrypt solo procesa los primeros 72 bytes de una contraseña.
LARGO_MAXIMO_BYTES = 72


def validar_clave(clave: str) -> list[str]:
    """Devuelve los requisitos que la contraseña NO cumple.

    Si la lista vuelve vacía, la contraseña es válida.
    """
    faltantes = []
    if len(clave) < LARGO_MINIMO:
        faltantes.append(f"Debe tener al menos {LARGO_MINIMO} caracteres.")
    if not any(letra.isupper() for letra in clave):
        faltantes.append("Debe incluir al menos una letra mayúscula.")
    if not any(letra.islower() for letra in clave):
        faltantes.append("Debe incluir al menos una letra minúscula.")
    if not any(letra.isdigit() for letra in clave):
        faltantes.append("Debe incluir al menos un número.")
    if len(clave.encode("utf-8")) > LARGO_MAXIMO_BYTES:
        faltantes.append(f"No puede superar los {LARGO_MAXIMO_BYTES} bytes.")
    return faltantes


def generar_hash(clave: str) -> str:
    """Transforma la contraseña en un hash de bcrypt, que es lo que se guarda."""
    sal = bcrypt.gensalt()
    return bcrypt.hashpw(clave.encode("utf-8"), sal).decode("utf-8")


def verificar_clave(clave: str, clave_hash: str) -> bool:
    """Indica si la contraseña escrita corresponde al hash guardado."""
    clave_en_bytes = clave.encode("utf-8")
    if len(clave_en_bytes) > LARGO_MAXIMO_BYTES:
        return False
    return bcrypt.checkpw(clave_en_bytes, clave_hash.encode("utf-8"))


def normalizar_email(email: str) -> str:
    """El correo se compara siempre sin espacios y en minúsculas."""
    return email.strip().lower()


def autenticar(db: Session, email: str, clave: str) -> Usuario | None:
    """Devuelve el usuario si el correo y la contraseña son correctos.

    Si algo no coincide devuelve None, sin distinguir cuál de los dos falló.
    """
    consulta = select(Usuario).where(Usuario.email == normalizar_email(email))
    usuario = db.scalars(consulta).first()
    if usuario is None:
        return None
    if not verificar_clave(clave, usuario.clave_hash):
        return None
    return usuario


# ---------- Control de acceso en las rutas ----------


class NoAutenticado(Exception):
    """Se lanza cuando alguien pide una página sin haber iniciado sesión."""


def usuario_actual(request: Request, db: Session = Depends(obtener_db)) -> Usuario:
    """Devuelve el usuario que inició sesión. Se usa como dependencia de una ruta."""
    usuario_id = request.session.get("usuario_id")
    if usuario_id is None:
        raise NoAutenticado()
    usuario = db.get(Usuario, usuario_id)
    if usuario is None:
        # La sesión apunta a un usuario que ya no existe.
        request.session.clear()
        raise NoAutenticado()
    return usuario


def requiere_rol(*roles_permitidos: str):
    """Crea una dependencia que solo deja pasar a los roles indicados.

    Ejemplo de uso en una ruta:
        usuario: Usuario = Depends(requiere_rol(ROL_SUPERVISOR))
    """

    def verificar(usuario: Usuario = Depends(usuario_actual)) -> Usuario:
        if usuario.rol not in roles_permitidos:
            raise HTTPException(
                status_code=403,
                detail="Tu rol no tiene acceso a esta función.",
            )
        return usuario

    return verificar
