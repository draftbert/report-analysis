"""Fixtures compartidas: expediente temporal y LLM falso (sin red)."""
from __future__ import annotations

import shutil
from pathlib import Path

import pytest
from pydantic import BaseModel

RAIZ = Path(__file__).resolve().parent.parent
CONFIG = RAIZ / "config" / "estilo.yaml"


class LLMFalso:
    """Sustituto de ClienteLLM: devuelve respuestas preparadas por prefijo de
    acción y registra las llamadas. Sin red, determinista."""

    def __init__(self, respuestas: dict[str, BaseModel] | None = None):
        self.respuestas = respuestas or {}
        self.llamadas: list[tuple[str, str]] = []
        self.proveedor, self.modelo, self.esfuerzo = "falso", "falso", "low"

    dry_run = False

    def descripcion(self):
        return "falso"

    def completar_estructurado(self, accion, system, user, modelo_salida, esfuerzo=None):
        self.llamadas.append((accion, user))
        for prefijo, resp in self.respuestas.items():
            if accion.startswith(prefijo):
                return resp(accion, user) if callable(resp) else resp
        raise AssertionError(f"LLMFalso: sin respuesta preparada para la acción {accion!r}")


@pytest.fixture
def expediente_tmp(tmp_path):
    from audit_agent.expediente import Expediente
    exp = Expediente.crear(tmp_path / "EXP-TEST", "Auditoría de prueba", "EXP-TEST", "Mayo 2026",
                           ["Dirección de Compras"])
    shutil.copy(RAIZ / "ejemplos" / "papel_trabajo_compras.md", exp.ruta / "papeles_trabajo")
    return exp


@pytest.fixture
def contexto(expediente_tmp):
    """Contexto de acciones con LLM falso; los tests añaden respuestas en ctx.llm.respuestas."""
    from audit_agent.acciones import Contexto
    ctx = Contexto(expediente_tmp, config=CONFIG, proveedor="dry-run")
    ctx.llm = LLMFalso()
    return ctx
