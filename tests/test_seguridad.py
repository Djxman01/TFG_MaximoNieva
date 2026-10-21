"""Pruebas de contraseñas y autenticación (HU-001).

La política de contraseñas sigue NIST SP 800-63B-4, sección 3.1.1.2.
"""

import unicodedata

from app.seguridad import autenticar, generar_hash, validar_clave, verificar_clave
from tests.conftest import CLAVE_DE_PRUEBA


# ---------- Política de contraseñas (NIST) ----------


def test_frase_de_15_caracteres_es_valida():
    assert validar_clave("una frase larga") == []  # 15 caracteres exactos


def test_clave_de_14_caracteres_es_rechazada():
    assert validar_clave("una frase larg") != []


def test_no_se_exigen_mayusculas_numeros_ni_simbolos():
    # Solo minúsculas y espacios: NIST prohíbe imponer reglas de composición.
    assert validar_clave("el perro come pan") == []


def test_se_aceptan_espacios_y_caracteres_acentuados():
    assert validar_clave("mañana salgo a las seis") == []


def test_clave_de_64_caracteres_es_valida():
    assert validar_clave("a" * 30 + " " + "b" * 33) == []


def test_clave_de_65_caracteres_es_rechazada():
    assert validar_clave("a" * 30 + " " + "b" * 34) != []


def test_clave_que_supera_72_bytes_es_rechazada_con_mensaje_claro():
    # 40 letras "ñ" son 40 caracteres pero 80 bytes en UTF-8: bcrypt la recortaría.
    faltantes = validar_clave("ñ" * 40)
    assert len(faltantes) == 1
    assert "demasiado larga" in faltantes[0]


def test_clave_de_la_lista_de_bloqueo_es_rechazada():
    assert validar_clave("passwordpassword") != []


def test_la_lista_de_bloqueo_no_distingue_mayusculas():
    assert validar_clave("RondasRondasRondas") != []


def test_palabras_del_sistema_estan_bloqueadas():
    assert validar_clave("sistema de rondas") != []


# ---------- Almacenamiento con bcrypt ----------


def test_el_hash_no_contiene_la_clave_en_claro():
    clave_hash = generar_hash(CLAVE_DE_PRUEBA)
    assert CLAVE_DE_PRUEBA not in clave_hash
    # $2b$ = bcrypt; 12 = factor de costo.
    assert clave_hash.startswith("$2b$12$")


def test_la_misma_clave_genera_hashes_distintos():
    # bcrypt agrega una "sal" aleatoria: dos usuarios con la misma contraseña
    # no quedan con el mismo hash.
    assert generar_hash(CLAVE_DE_PRUEBA) != generar_hash(CLAVE_DE_PRUEBA)


def test_verificar_acepta_la_clave_correcta():
    assert verificar_clave(CLAVE_DE_PRUEBA, generar_hash(CLAVE_DE_PRUEBA))


def test_verificar_rechaza_una_clave_incorrecta():
    assert not verificar_clave("otra frase distinta", generar_hash(CLAVE_DE_PRUEBA))


def test_verificar_no_recorta_claves_largas():
    # Dos claves que comparten los primeros 72 bytes no pueden darse por iguales.
    base = "x" * 72
    assert not verificar_clave(base + "diferente", generar_hash(base))


def test_la_clave_se_normaliza_antes_de_comparar():
    # "é" escrita como un solo carácter (NFC) o como "e" + tilde (NFD).
    compuesta = unicodedata.normalize("NFC", "contraseña con café")
    descompuesta = unicodedata.normalize("NFD", "contraseña con café")
    assert compuesta != descompuesta
    assert verificar_clave(descompuesta, generar_hash(compuesta))


# ---------- Autenticación ----------


def test_autenticar_con_credenciales_correctas(db, crear_usuario):
    crear_usuario("lider@ejemplo.com", "lider")
    usuario = autenticar(db, "lider@ejemplo.com", CLAVE_DE_PRUEBA)
    assert usuario is not None
    assert usuario.rol == "lider"


def test_autenticar_ignora_mayusculas_y_espacios_del_correo(db, crear_usuario):
    crear_usuario("lider@ejemplo.com", "lider")
    assert autenticar(db, "  Lider@Ejemplo.com ", CLAVE_DE_PRUEBA) is not None


def test_autenticar_con_clave_incorrecta(db, crear_usuario):
    crear_usuario("lider@ejemplo.com", "lider")
    assert autenticar(db, "lider@ejemplo.com", "otra frase distinta") is None


def test_autenticar_con_usuario_inexistente(db):
    assert autenticar(db, "nadie@ejemplo.com", CLAVE_DE_PRUEBA) is None
