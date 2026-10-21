"""Pruebas de contraseñas y autenticación (HU-001)."""

from app.seguridad import autenticar, generar_hash, validar_clave, verificar_clave
from tests.conftest import CLAVE_DE_PRUEBA


# ---------- Política de contraseñas ----------


def test_clave_valida_no_tiene_faltantes():
    assert validar_clave("Prueba1234") == []


def test_clave_corta_es_rechazada():
    assert validar_clave("Ab1") != []


def test_clave_sin_mayuscula_es_rechazada():
    assert validar_clave("prueba1234") != []


def test_clave_sin_minuscula_es_rechazada():
    assert validar_clave("PRUEBA1234") != []


def test_clave_sin_numero_es_rechazada():
    assert validar_clave("PruebaPrueba") != []


def test_clave_demasiado_larga_es_rechazada():
    assert validar_clave("Aa1" + "x" * 70) != []


# ---------- Almacenamiento con bcrypt ----------


def test_el_hash_no_contiene_la_clave_en_claro():
    clave_hash = generar_hash(CLAVE_DE_PRUEBA)
    assert CLAVE_DE_PRUEBA not in clave_hash
    assert clave_hash.startswith("$2b$")


def test_la_misma_clave_genera_hashes_distintos():
    # bcrypt agrega una "sal" aleatoria: dos usuarios con la misma contraseña
    # no quedan con el mismo hash.
    assert generar_hash(CLAVE_DE_PRUEBA) != generar_hash(CLAVE_DE_PRUEBA)


def test_verificar_acepta_la_clave_correcta():
    assert verificar_clave(CLAVE_DE_PRUEBA, generar_hash(CLAVE_DE_PRUEBA))


def test_verificar_rechaza_una_clave_incorrecta():
    assert not verificar_clave("Otra12345", generar_hash(CLAVE_DE_PRUEBA))


# ---------- Autenticación ----------


def test_autenticar_con_credenciales_correctas(db, crear_usuario):
    crear_usuario("supervisor@ejemplo.com", "supervisor")
    usuario = autenticar(db, "supervisor@ejemplo.com", CLAVE_DE_PRUEBA)
    assert usuario is not None
    assert usuario.rol == "supervisor"


def test_autenticar_ignora_mayusculas_y_espacios_del_correo(db, crear_usuario):
    crear_usuario("supervisor@ejemplo.com", "supervisor")
    assert autenticar(db, "  Supervisor@Ejemplo.com ", CLAVE_DE_PRUEBA) is not None


def test_autenticar_con_clave_incorrecta(db, crear_usuario):
    crear_usuario("supervisor@ejemplo.com", "supervisor")
    assert autenticar(db, "supervisor@ejemplo.com", "Incorrecta1") is None


def test_autenticar_con_usuario_inexistente(db):
    assert autenticar(db, "nadie@ejemplo.com", CLAVE_DE_PRUEBA) is None
