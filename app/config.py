"""Configuración de la aplicación.

Los valores se leen de variables de entorno. Así las contraseñas y las claves
no quedan escritas en el código: en Docker las aporta el archivo .env.
"""

import os


def leer_variable(nombre: str) -> str:
    valor = os.environ.get(nombre)
    if not valor:
        raise RuntimeError(f"Falta definir la variable de entorno {nombre}")
    return valor


# Dirección de la base de datos, por ejemplo:
# postgresql+psycopg://usuario:clave@db:5432/rondas
DATABASE_URL = leer_variable("DATABASE_URL")

# Clave con la que se firma la cookie de sesión.
SECRET_KEY = leer_variable("SECRET_KEY")

# Carpeta donde se guardan los archivos de evidencia (en Docker es un volumen).
EVIDENCIA_DIR = os.environ.get("EVIDENCIA_DIR", "evidencia")

# Duración de la sesión iniciada, en segundos (8 horas).
DURACION_SESION = 8 * 60 * 60
