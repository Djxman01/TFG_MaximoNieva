def calcular_probabilidad(cantidad_factores: int) -> str:
    if cantidad_factores <= 0:
        return "baja"
    elif cantidad_factores == 1:
        return "media"
    else:
        return "alta"