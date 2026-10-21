"""Carga los datos de ejemplo de la demo.

Uso (con los servicios en marcha):
    docker compose exec app python -m scripts.datos_semilla
"""

from app.database import SesionLocal
from app.semilla import USUARIOS, cargar_datos_semilla


def main() -> None:
    with SesionLocal() as db:
        cargar_datos_semilla(db)
    print("Datos semilla cargados. Usuarios de prueba:")
    for usuario in USUARIOS:
        print(f"  {usuario['email']} ({usuario['rol']})")
    print("Las contraseñas de prueba figuran en el README.")


if __name__ == "__main__":
    main()
