"""Alta de un usuario desde la terminal.

Uso:
    python -m scripts.crear_usuario --nombre "Ana Pérez" --email ana@ejemplo.com --rol supervisor

La contraseña se pide por teclado y no queda escrita en el historial de comandos.
"""

import argparse
import getpass
import sys

from sqlalchemy import select

from app.database import SesionLocal
from app.models import Usuario
from app.seguridad import ROLES, generar_hash, normalizar_email, validar_clave


def pedir_clave() -> str:
    if sys.stdin.isatty():
        clave = getpass.getpass("Contraseña: ")
        repeticion = getpass.getpass("Repetir contraseña: ")
        if clave != repeticion:
            sys.exit("Las contraseñas no coinciden.")
        return clave
    # Sin teclado conectado (por ejemplo, desde otro script) se lee una línea.
    return sys.stdin.readline().rstrip("\n")


def main() -> None:
    parser = argparse.ArgumentParser(description="Crea un usuario del sistema.")
    parser.add_argument("--nombre", required=True)
    parser.add_argument("--email", required=True)
    parser.add_argument("--rol", required=True, choices=ROLES)
    argumentos = parser.parse_args()

    email = normalizar_email(argumentos.email)
    clave = pedir_clave()

    faltantes = validar_clave(clave)
    if faltantes:
        sys.exit("La contraseña no es válida:\n- " + "\n- ".join(faltantes))

    with SesionLocal() as db:
        existente = db.scalars(select(Usuario).where(Usuario.email == email)).first()
        if existente is not None:
            sys.exit(f"Ya existe un usuario con el correo {email}.")

        usuario = Usuario(
            nombre=argumentos.nombre,
            email=email,
            clave_hash=generar_hash(clave),
            rol=argumentos.rol,
        )
        db.add(usuario)
        db.commit()

    print(f"Usuario creado: {email} ({argumentos.rol})")


if __name__ == "__main__":
    main()
