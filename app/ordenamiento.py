"""Regla de ordenamiento de la ronda (HU-007).

Es una regla propia y verificable, no una optimización: no busca el recorrido
más corto posible, sino aplicar siempre el mismo criterio explícito.

1. Se recorren los niveles de criticidad de mayor a menor (alta, media, baja).
2. Dentro de cada nivel se elige el activo más cercano a la posición actual.
   La posición inicial es el origen; después pasa a ser el último activo elegido.
3. Desempate (igual criticidad y distancia): primero el activo SIN telesupervisión.
4. Tiempo de cada paso = distancia / velocidad media + duración de la inspección.
   Un activo entra solo si el tiempo acumulado no supera el tiempo disponible.
5. Si un activo no entra, se lo saltea y se sigue con el siguiente que sí entre
   (decisión de Máximo del 12/10/2026). Los que no entran quedan sin orden.

La criticidad prevalece sobre la distancia: un activo de criticidad alta lejano
va antes que uno de criticidad media cercano. La distancia es en línea recta
sobre coordenadas en metros; no representa la red real de caminos.
"""

import math
from dataclasses import dataclass

NIVELES = ["alta", "media", "baja"]


@dataclass
class Candidato:
    """Lo que la regla necesita saber de cada activo."""

    id: int
    codigo: str
    x: float  # este, en metros
    y: float  # norte, en metros
    criticidad: str  # "alta", "media" o "baja"
    telesupervision: bool


@dataclass
class Paso:
    """Un activo dentro del recorrido propuesto."""

    orden: int
    candidato: Candidato
    distancia_m: float  # desde la posición anterior
    minutos_tramo: float  # viaje + inspección
    minutos_acumulados: float


@dataclass
class Propuesta:
    pasos: list[Paso]
    excluidos: list[Candidato]  # no entraron en el tiempo disponible

    @property
    def minutos_totales(self) -> float:
        return self.pasos[-1].minutos_acumulados if self.pasos else 0.0


def distancia(x1: float, y1: float, x2: float, y2: float) -> float:
    """Distancia en línea recta, en metros (teorema de Pitágoras)."""
    return math.hypot(x2 - x1, y2 - y1)


def minutos_de_tramo(distancia_m: float, velocidad_kmh: float, duracion_min: float) -> float:
    """Tiempo de viaje más tiempo de inspección, en minutos.

    Ojo con las unidades: la distancia está en metros y la velocidad en km/h.
    metros / 1000 = kilómetros; kilómetros / (km/h) = horas; horas * 60 = minutos.
    """
    horas_de_viaje = (distancia_m / 1000) / velocidad_kmh
    return horas_de_viaje * 60 + duracion_min


def proponer_orden(
    candidatos: list[Candidato],
    origen_x: float,
    origen_y: float,
    velocidad_kmh: float,
    duracion_min: float,
    tiempo_disponible_min: float,
) -> Propuesta:
    pasos = []
    elegidos = set()
    x_actual, y_actual = origen_x, origen_y
    acumulado = 0.0

    for nivel in NIVELES:
        pendientes = [c for c in candidatos if c.criticidad == nivel]

        while pendientes:
            # Solo cuentan los activos que todavía entran en el tiempo disponible.
            # Así, si el más cercano no entra, se saltea y se prueba el siguiente.
            que_entran = []
            for candidato in pendientes:
                tramo = minutos_de_tramo(
                    distancia(x_actual, y_actual, candidato.x, candidato.y),
                    velocidad_kmh,
                    duracion_min,
                )
                if acumulado + tramo <= tiempo_disponible_min:
                    que_entran.append(candidato)

            if not que_entran:
                break  # ningún activo de este nivel entra: se pasa al siguiente nivel

            # El más cercano. Si hay empate de distancia, primero el que no tiene
            # telesupervisión (False se ordena antes que True). El código del
            # activo deja el resultado siempre igual si todo lo demás empata.
            elegido = min(
                que_entran,
                key=lambda c: (
                    distancia(x_actual, y_actual, c.x, c.y),
                    c.telesupervision,
                    c.codigo,
                ),
            )
            distancia_m = distancia(x_actual, y_actual, elegido.x, elegido.y)
            tramo = minutos_de_tramo(distancia_m, velocidad_kmh, duracion_min)
            acumulado += tramo
            pasos.append(Paso(len(pasos) + 1, elegido, distancia_m, tramo, acumulado))
            elegidos.add(elegido.id)
            pendientes.remove(elegido)
            x_actual, y_actual = elegido.x, elegido.y

    excluidos = [c for c in candidatos if c.id not in elegidos]
    return Propuesta(pasos, excluidos)


def tiempo_de_recorrido(
    candidatos_en_orden: list[Candidato],
    origen_x: float,
    origen_y: float,
    velocidad_kmh: float,
    duracion_min: float,
) -> float:
    """Minutos totales de un recorrido en el orden dado (sirve para el ajuste, HU-008)."""
    total = 0.0
    x_actual, y_actual = origen_x, origen_y
    for candidato in candidatos_en_orden:
        total += minutos_de_tramo(
            distancia(x_actual, y_actual, candidato.x, candidato.y), velocidad_kmh, duracion_min
        )
        x_actual, y_actual = candidato.x, candidato.y
    return total
