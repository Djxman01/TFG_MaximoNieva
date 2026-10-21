"""Conversión de coordenadas con pyproj.

El sistema guarda las posiciones en metros, en Gauss-Krüger sobre POSGAR 2007,
faja 2 (EPSG:5344). Los mapas web (Leaflet) trabajan en latitud y longitud
(WGS84, EPSG:4326). Este módulo convierte entre los dos.

Convención de ejes del prototipo: x = ESTE, y = NORTE.
La definición oficial de EPSG:5344 llama "X" al norte y "Y" al este (al revés).
Para no confundirlos se usa always_xy=True: así pyproj siempre recibe y devuelve
primero el este (o la longitud) y después el norte (o la latitud).
"""

from pyproj import Transformer

EPSG_GAUSS_KRUGER = 5344  # POSGAR 2007 / Argentina 2
EPSG_LAT_LON = 4326  # WGS84

_a_lat_lon = Transformer.from_crs(EPSG_GAUSS_KRUGER, EPSG_LAT_LON, always_xy=True)
_desde_lat_lon = Transformer.from_crs(EPSG_LAT_LON, EPSG_GAUSS_KRUGER, always_xy=True)


def a_lat_lon(x_este: float, y_norte: float) -> tuple[float, float]:
    """Convierte metros (este, norte) a (latitud, longitud) para el mapa."""
    longitud, latitud = _a_lat_lon.transform(float(x_este), float(y_norte))
    return latitud, longitud


def desde_lat_lon(latitud: float, longitud: float) -> tuple[float, float]:
    """Convierte una posición de GPS a metros (este, norte)."""
    x_este, y_norte = _desde_lat_lon.transform(longitud, latitud)
    return x_este, y_norte
