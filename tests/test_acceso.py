"""Sesión de la interfaz web: contraseña, token firmado y caducidad. Sin HTTP: el
módulo es lo que nginx consulta vía la API; la puerta la pone nginx (auth_request)."""
from __future__ import annotations

import time

import pytest

from audit_agent import acceso


@pytest.fixture
def configurado(monkeypatch):
    monkeypatch.setenv("REVISOR_UI_PASSWORD", "secreta-123")
    monkeypatch.setenv("REVISOR_UI_SESSION_SECRET", "a" * 64)


def test_password_correcta_incorrecta_y_vacia(configurado):
    assert acceso.password_correcta("secreta-123")
    assert not acceso.password_correcta("otra")
    assert not acceso.password_correcta("")
    assert not acceso.password_correcta(None)


def test_sin_configuracion_nada_valida(monkeypatch):
    monkeypatch.delenv("REVISOR_UI_PASSWORD", raising=False)
    monkeypatch.delenv("REVISOR_UI_SESSION_SECRET", raising=False)
    assert not acceso.password_correcta("")          # ni vacía contra vacía
    assert not acceso.password_correcta("cualquiera")
    assert not acceso.validar_token("123.abc")
    monkeypatch.setenv("REVISOR_UI_PASSWORD", "p")   # solo una de las dos tampoco
    assert not acceso.password_correcta("p") and not acceso.validar_token(acceso.crear_token())


def test_token_valido_caducado_y_alterado(configurado):
    token = acceso.crear_token()
    assert acceso.validar_token(token)
    exp, firma = token.split(".")
    assert not acceso.validar_token(f"{int(exp) + 999}.{firma}")     # exp alterado: la firma no cuadra
    assert not acceso.validar_token(f"{int(time.time()) - 10}.{acceso._firmar('a' * 64, int(time.time()) - 10)}")  # caducado
    for raro in (None, "", "abc", "1.2.3", "no-digitos.firma", firma):
        assert not acceso.validar_token(raro)


def test_rotar_el_secreto_invalida_sesiones(configurado, monkeypatch):
    token = acceso.crear_token()
    assert acceso.validar_token(token)
    monkeypatch.setenv("REVISOR_UI_SESSION_SECRET", "b" * 64)
    assert not acceso.validar_token(token)
