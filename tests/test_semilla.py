"""Pruebas de los datos semilla de la demo."""

from sqlalchemy import func, select

from app.models import Activo, CriterioCriticidad, CriticidadActivo, Usuario
from app.semilla import USUARIOS, cargar_datos_semilla
from app.seguridad import autenticar, validar_clave


def contar(db, modelo):
    return db.scalar(select(func.count()).select_from(modelo))


def test_hay_un_usuario_de_cada_perfil(semilla):
    roles = set(semilla.scalars(select(Usuario.rol)))
    assert roles == {"lider", "operador"}


def test_las_claves_de_prueba_cumplen_la_politica(semilla):
    for usuario in USUARIOS:
        assert validar_clave(usuario["clave"]) == []
        assert autenticar(semilla, usuario["email"], usuario["clave"]) is not None


def test_criterios_de_las_dos_dimensiones(semilla):
    dimensiones = set(semilla.scalars(select(CriterioCriticidad.dimension)))
    assert dimensiones == {"probabilidad", "consecuencia"}


def test_criticidades_de_los_activos_de_la_ronda_024(semilla):
    esperadas = {
        "Pozo A-14": "alta",
        "Pozo A-08": "alta",
        "Pozo B-03": "media",
        "Batería 2": "media",
        "Pozo C-07": "baja",
    }
    for codigo, categoria in esperadas.items():
        activo = semilla.scalars(select(Activo).where(Activo.codigo == codigo)).one()
        assert activo.criticidad_vigente().categoria == categoria, codigo


def test_el_pozo_a14_tiene_historial(semilla):
    activo = semilla.scalars(select(Activo).where(Activo.codigo == "Pozo A-14")).one()
    assert [e.categoria for e in activo.evaluaciones] == ["alta", "media"]


def test_hay_activos_sin_evaluar_para_la_demo(semilla):
    sin_evaluar = [a for a in semilla.scalars(select(Activo)) if not a.evaluaciones]
    assert len(sin_evaluar) >= 2


def test_cargar_dos_veces_no_duplica(semilla):
    antes = [contar(semilla, m) for m in (Usuario, CriterioCriticidad, Activo, CriticidadActivo)]
    cargar_datos_semilla(semilla)
    despues = [contar(semilla, m) for m in (Usuario, CriterioCriticidad, Activo, CriticidadActivo)]
    assert antes == despues
