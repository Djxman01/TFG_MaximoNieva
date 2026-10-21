"""Cobertura de la ronda (HU-012) — objetivo específico 4.

- Operativa = activos inspeccionados / activos de la ronda.
- Ponderada = suma de pesos de los inspeccionados / suma de pesos de todos.
- Peso según la criticidad vigente AL PLANIFICAR: alta = 3, media = 2, baja = 1.
- Los pendientes y los no accesibles quedan en el total; los no accesibles se
  informan aparte. Los pesos son ponderadores del indicador, no valores de riesgo.
"""

from dataclasses import dataclass

from app.models import PESOS


@dataclass
class ActivoParaCobertura:
    """Lo que el cálculo necesita saber de cada activo de la ronda."""

    criticidad: str  # la congelada al planificar
    estado_atencion: str  # "pendiente", "inspeccionado" o "no_accesible"


@dataclass
class Cobertura:
    total: int
    inspeccionados: int
    no_accesibles: int
    pendientes: int
    peso_total: int
    peso_inspeccionado: int
    por_criticidad: dict  # {"alta": {"total": n, "inspeccionados": m}, ...}

    @property
    def operativa(self) -> float:
        return self.inspeccionados / self.total if self.total else 0.0

    @property
    def ponderada(self) -> float:
        return self.peso_inspeccionado / self.peso_total if self.peso_total else 0.0


def calcular_cobertura(activos: list[ActivoParaCobertura]) -> Cobertura:
    por_criticidad = {nivel: {"total": 0, "inspeccionados": 0} for nivel in PESOS}
    inspeccionados = no_accesibles = pendientes = 0
    peso_total = peso_inspeccionado = 0

    for activo in activos:
        peso = PESOS[activo.criticidad]
        peso_total += peso
        por_criticidad[activo.criticidad]["total"] += 1
        if activo.estado_atencion == "inspeccionado":
            inspeccionados += 1
            peso_inspeccionado += peso
            por_criticidad[activo.criticidad]["inspeccionados"] += 1
        elif activo.estado_atencion == "no_accesible":
            no_accesibles += 1
        else:
            pendientes += 1

    return Cobertura(
        total=len(activos),
        inspeccionados=inspeccionados,
        no_accesibles=no_accesibles,
        pendientes=pendientes,
        peso_total=peso_total,
        peso_inspeccionado=peso_inspeccionado,
        por_criticidad=por_criticidad,
    )
