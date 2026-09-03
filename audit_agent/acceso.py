"""Sesión de la interfaz web (patrón de audit-engine): pantalla de login propia +
cookie de sesión firmada, sin basic auth del navegador.

Token sin estado `exp.firma`: `exp` es el epoch de caducidad (12 h) y `firma` el
HMAC-SHA256 del secreto sobre `str(exp)`, en hex. nginx pregunta a la API por cada
petición (`auth_request` → `GET /api/acceso/verificar`) y la API solo valida.

Config por entorno (en `.env.secrets`, nunca en git ni en logs):
  REVISOR_UI_PASSWORD        contraseña de acceso a la interfaz
  REVISOR_UI_SESSION_SECRET  secreto de firma (generar con `openssl rand -hex 32`)

Si falta cualquiera de las dos, NADA valida (ni contraseña vacía contra contraseña
vacía): un entorno a medio configurar queda cerrado, no abierto. Rotar el secreto
invalida todas las sesiones a la vez: es la vía de revocación.
"""
from __future__ import annotations

import hashlib
import hmac
import os
import time

DURACION_SESION_S = 12 * 3600


def _config() -> tuple[str, str]:
    return (os.environ.get("REVISOR_UI_PASSWORD") or "", os.environ.get("REVISOR_UI_SESSION_SECRET") or "")


def _firmar(secreto: str, exp: int) -> str:
    return hmac.new(secreto.encode(), str(exp).encode(), hashlib.sha256).hexdigest()


def password_correcta(candidata: str) -> bool:
    """False SIEMPRE si falta configuración; comparación en tiempo constante."""
    password, secreto = _config()
    if not password or not secreto:
        return False
    return hmac.compare_digest(password.encode(), (candidata or "").encode())


def crear_token() -> str:
    _, secreto = _config()
    exp = int(time.time()) + DURACION_SESION_S
    return f"{exp}.{_firmar(secreto, exp)}"


def validar_token(token: str | None) -> bool:
    """Rechaza formato raro, token caducado o firma que no cuadra (y todo si falta config)."""
    password, secreto = _config()
    if not password or not secreto or not token or token.count(".") != 1:
        return False
    exp_txt, firma = token.split(".", 1)
    if not exp_txt.isdigit():
        return False
    exp = int(exp_txt)
    if exp < time.time():
        return False
    return hmac.compare_digest(_firmar(secreto, exp), firma)
