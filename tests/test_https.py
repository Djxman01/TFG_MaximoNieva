"""Pruebas de HTTPS: cookie Secure, configuración de Caddy y redirección.

Las últimas pruebas hablan con los servicios reales de Docker y solo se corren
con la variable PRUEBAS_DOCKER=1 (con `docker compose up -d` hecho antes):

    PRUEBAS_DOCKER=1 pytest tests/test_https.py
"""

import os
import socket
from pathlib import Path

import httpx2 as httpx
import pytest
import yaml

from app.semilla import USUARIOS

RAIZ = Path(__file__).parent.parent
COMPOSE = yaml.safe_load((RAIZ / "docker-compose.yml").read_text(encoding="utf-8"))
CADDYFILE = (RAIZ / "Caddyfile").read_text(encoding="utf-8")


# ---------- Sin Docker ----------


def test_la_cookie_de_sesion_es_secure(cliente, semilla):
    respuesta = cliente.post(
        "/login",
        data={"email": USUARIOS[0]["email"], "clave": USUARIOS[0]["clave"]},
        follow_redirects=False,
    )
    cookie = respuesta.headers["set-cookie"].lower()
    assert "secure" in cookie
    assert "httponly" in cookie
    assert "samesite=lax" in cookie


def test_la_aplicacion_no_publica_su_puerto():
    assert "ports" not in COMPOSE["services"]["app"]


def test_solo_caddy_publica_los_puertos_80_y_443():
    puertos = COMPOSE["services"]["caddy"]["ports"]
    assert set(puertos) == {"80:80", "443:443"}
    assert "ports" not in COMPOSE["services"]["db"]


def test_caddy_usa_certificado_local_y_envia_a_la_aplicacion():
    assert "tls internal" in CADDYFILE
    assert "reverse_proxy app:8000" in CADDYFILE


# ---------- Con Docker en marcha ----------

con_docker = pytest.mark.skipif(
    os.environ.get("PRUEBAS_DOCKER") != "1",
    reason="Necesita los servicios de Docker en marcha (PRUEBAS_DOCKER=1).",
)


@con_docker
def test_http_redirige_a_https():
    respuesta = httpx.get("http://localhost/login", follow_redirects=False, timeout=10)
    assert respuesta.status_code in (301, 302, 307, 308)
    assert respuesta.headers["location"].startswith("https://localhost/")


@con_docker
def test_https_responde_con_el_certificado_local():
    # verify=False: la autoridad local de Caddy no está instalada en esta máquina.
    respuesta = httpx.get("https://localhost/login", verify=False, timeout=10)
    assert respuesta.status_code == 200
    assert "Ingreso al sistema" in respuesta.text


@con_docker
def test_el_puerto_de_la_aplicacion_no_esta_abierto():
    with socket.socket() as conexion:
        conexion.settimeout(2)
        assert conexion.connect_ex(("127.0.0.1", 8000)) != 0
