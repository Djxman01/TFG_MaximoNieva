"""Seguridad de acceso (HU-001): contraseñas, autenticación y roles."""

import unicodedata
from pathlib import Path

import bcrypt
from fastapi import Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import obtener_db
from app.models import Usuario

# ---------- Roles ----------

ROL_LIDER = "lider"
ROL_OPERADOR = "operador"
ROLES = [ROL_LIDER, ROL_OPERADOR]

NOMBRES_DE_ROL = {
    ROL_LIDER: "Líder de Operaciones",
    ROL_OPERADOR: "Operador",
}

# Funciones del sistema que corresponden a cada rol.
FUNCIONES_POR_ROL = {
    ROL_LIDER: [
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
# Política según NIST SP 800-63B-4, sección 3.1.1.2 (contraseña como único factor):
# largo mínimo 15, máximo 64, sin reglas de composición (no se exige mayúscula,
# número, etc.), se aceptan espacios y cualquier carácter, y se rechazan las
# contraseñas de una lista de bloqueo. No vencen.

LARGO_MINIMO = 15
LARGO_MAXIMO = 64
# bcrypt solo procesa los primeros 72 bytes. Con letras acentuadas u otros
# caracteres no ASCII, 64 caracteres pueden ocupar más de 72 bytes: en ese caso
# la contraseña se rechaza, nunca se recorta en silencio.
LARGO_MAXIMO_BYTES = 72

ARCHIVO_BLOQUEO = Path(__file__).parent / "datos" / "claves_bloqueadas.txt"


def normalizar_clave(clave: str) -> str:
    """Lleva la contraseña a la forma Unicode NFC.

    Una misma letra acentuada se puede escribir con uno o con dos códigos
    (por ejemplo "é" o "e" + tilde). NFC las unifica, para que la contraseña
    coincida sin importar el teclado con el que se escribió.
    """
    return unicodedata.normalize("NFC", clave)


def cargar_lista_de_bloqueo() -> set[str]:
    """Lee el archivo de contraseñas prohibidas, en minúsculas."""
    bloqueadas = set()
    for linea in ARCHIVO_BLOQUEO.read_text(encoding="utf-8").splitlines():
        linea = linea.strip()
        if linea and not linea.startswith("#"):
            bloqueadas.add(normalizar_clave(linea).casefold())
    return bloqueadas


CLAVES_BLOQUEADAS = cargar_lista_de_bloqueo()


def validar_clave(clave: str) -> list[str]:
    """Devuelve los requisitos que la contraseña NO cumple.

    Si la lista vuelve vacía, la contraseña es válida.
    """
    clave = normalizar_clave(clave)
    faltantes = []
    # len() cuenta caracteres (puntos de código Unicode), no bytes.
    if len(clave) < LARGO_MINIMO:
        faltantes.append(f"Debe tener al menos {LARGO_MINIMO} caracteres.")
    if len(clave) > LARGO_MAXIMO:
        faltantes.append(f"No puede tener más de {LARGO_MAXIMO} caracteres.")
    elif len(clave.encode("utf-8")) > LARGO_MAXIMO_BYTES:
        faltantes.append(
            "Es demasiado larga para el formato de almacenamiento: usá menos "
            "letras acentuadas o símbolos, o una frase más corta."
        )
    if clave.casefold() in CLAVES_BLOQUEADAS:
        faltantes.append("Es una contraseña común o fácil de adivinar: elegí otra.")
    return faltantes


def generar_hash(clave: str) -> str:
    """Transforma la contraseña en un hash de bcrypt, que es lo que se guarda."""
    sal = bcrypt.gensalt(rounds=12)
    clave_en_bytes = normalizar_clave(clave).encode("utf-8")
    return bcrypt.hashpw(clave_en_bytes, sal).decode("utf-8")


def verificar_clave(clave: str, clave_hash: str) -> bool:
    """Indica si la contraseña escrita corresponde al hash guardado."""
    clave_en_bytes = normalizar_clave(clave).encode("utf-8")
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
        usuario: Usuario = Depends(requiere_rol(ROL_LIDER))
    """

    def verificar(usuario: Usuario = Depends(usuario_actual)) -> Usuario:
        if usuario.rol not in roles_permitidos:
            raise HTTPException(
                status_code=403,
                detail="Tu rol no tiene acceso a esta función.",
            )
        return usuario

    return verificar
