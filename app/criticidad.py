def calcular_probabilidad(cantidad_factores: int) -> str:
    if cantidad_factores <= 0:
        return "baja"
    elif cantidad_factores == 1:
        return "media"
    else:
        return "alta"


def calcular_consecuencia(niveles: list) -> str:
    if "personas" in niveles:
        return "alta"
    elif "ambiente" in niveles or "produccion" in niveles:
        return "media"
    else:
        return "baja"

# Matriz de criticidad (sección 4.1 del documento).
# La clave es el par (probabilidad, consecuencia) y el valor es la categoría.
MATRIZ = {
    ("alta", "baja"): "media",
    ("alta", "media"): "alta",
    ("alta", "alta"): "alta",
    ("media", "baja"): "baja",
    ("media", "media"): "media",
    ("media", "alta"): "alta",
    ("baja", "baja"): "baja",
    ("baja", "media"): "baja",
    ("baja", "alta"): "media",
}


def calcular_criticidad(probabilidad: str, consecuencia: str) -> str:
    return MATRIZ[(probabilidad, consecuencia)]
