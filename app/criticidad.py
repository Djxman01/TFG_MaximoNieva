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