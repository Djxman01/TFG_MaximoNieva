"""Valores fijos que usan los formularios.

Las bases operativas no son una tabla del modelo de datos: la ronda guarda solo
las coordenadas del origen (origen_x, origen_y). Esta lista sirve para elegir el
origen en el formulario por su nombre y para mostrar ese nombre después.
Todos los datos son ficticios.
"""

# Coordenadas en metros, EPSG:5344: (este, norte).
BASES = {
    "Base Norte": (2_500_000.0, 6_515_000.0),
    "Base Sur": (2_506_000.0, 6_492_000.0),
}

MEDIOS_DE_INSPECCION = ["Vehículo terrestre", "A pie"]

# Valores que se proponen por defecto al crear una ronda.
VELOCIDAD_MEDIA_POR_DEFECTO = 40  # km/h
DURACION_INSPECCION_POR_DEFECTO = 30  # min


def nombre_de_base(x: float, y: float) -> str:
    """Devuelve el nombre de la base con esas coordenadas, o las coordenadas."""
    for nombre, (bx, by) in BASES.items():
        if abs(float(x) - bx) < 1 and abs(float(y) - by) < 1:
            return nombre
    return f"X {float(x):.0f} — Y {float(y):.0f}"
