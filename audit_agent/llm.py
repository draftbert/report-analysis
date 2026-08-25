"""
Cliente LLM unificado: un único punto de entrada para todo el paquete.

Proveedores (variable LLM_PROVEEDOR o detección automática):
  - "kaia"      : agente interno (por defecto si hay credenciales KAIA en .env)
  - "anthropic" : API de Claude (si hay ANTHROPIC_API_KEY y no hay KAIA)
  - "dry-run"   : sin proveedor; las acciones que requieren LLM fallan con un
                  mensaje claro, todo lo determinista sigue funcionando.

Toda llamada devuelve un objeto Pydantic validado (salida estructurada) y
queda trazada mediante el callback `trazador(accion, registro)`, que el
expediente usa para guardar prompt + respuesta + tokens (gobernanza:
toda salida del modelo queda ligada a su entrada).
"""
from __future__ import annotations

import json
import os
from datetime import datetime
from typing import Callable, TypeVar

from pydantic import BaseModel, ValidationError

from .kaia_client import KAIAClient, KAIAError

T = TypeVar("T", bound=BaseModel)

MODELO_KAIA_DEFECTO = "gpt-5-mini"
MODELO_ANTHROPIC_DEFECTO = "claude-sonnet-4-6"


class LLMNoDisponible(RuntimeError):
    pass


def _leer_float(nombre: str) -> float | None:
    v = os.environ.get(nombre)
    if v is None or v.strip() == "":
        return None
    try:
        return float(v)
    except ValueError:
        return None


class ClienteLLM:
    def __init__(self, modelo: str | None = None, proveedor: str | None = None,
                 trazador: Callable[[str, dict], None] | None = None,
                 esfuerzo: str | None = None):
        proveedor = (proveedor or os.environ.get("LLM_PROVEEDOR") or "").strip().lower()
        if not proveedor:
            if KAIAClient.disponible():
                proveedor = "kaia"
            elif os.environ.get("ANTHROPIC_API_KEY"):
                proveedor = "anthropic"
            else:
                proveedor = "dry-run"
        self.proveedor = proveedor
        self.trazador = trazador
        self.esfuerzo = esfuerzo or os.environ.get("LLM_REASONING_EFFORT") or "medium"
        self._kaia: KAIAClient | None = None
        self._anthropic = None

        if proveedor == "kaia":
            self.modelo = modelo or os.environ.get("KAIA_AGENT_MODEL_NAME") or MODELO_KAIA_DEFECTO
            self._kaia = KAIAClient(self.modelo,
                                    temperature=_leer_float("KAIA_AGENT_TEMPERATURE"),
                                    reasoning_effort=self.esfuerzo)
        elif proveedor == "anthropic":
            self.modelo = modelo or MODELO_ANTHROPIC_DEFECTO
            try:
                import anthropic
                self._anthropic = anthropic.Anthropic()
            except ImportError as exc:
                raise LLMNoDisponible("Proveedor 'anthropic' requiere `pip install anthropic`.") from exc
        elif proveedor == "dry-run":
            self.modelo = "(ninguno)"
        else:
            raise LLMNoDisponible(f"LLM_PROVEEDOR desconocido: {proveedor!r} (kaia | anthropic | dry-run)")

    @property
    def dry_run(self) -> bool:
        return self.proveedor == "dry-run"

    def descripcion(self) -> str:
        return f"{self.proveedor} · {self.modelo}" + (f" · esfuerzo {self.esfuerzo}" if self.proveedor == "kaia" else "")

    # ------------------------------------------------------------------
    def completar_estructurado(self, accion: str, system: str, user: str,
                               modelo_salida: type[T], esfuerzo: str | None = None) -> T:
        inicio = datetime.now()
        registro = {
            "fecha": inicio.isoformat(timespec="seconds"),
            "accion": accion,
            "proveedor": self.proveedor,
            "modelo": self.modelo,
            "esquema": modelo_salida.__name__,
            "system": system,
            "user": user,
        }
        try:
            if self.dry_run:
                raise LLMNoDisponible(
                    "No hay proveedor LLM configurado. Define las variables KAIA_* (o "
                    "ANTHROPIC_API_KEY) en .env. Las acciones deterministas siguen disponibles.")
            if self._kaia is not None:
                bruto, usage = self._kaia.invocar(system, user, modelo_salida,
                                                  reasoning_effort=esfuerzo)
                registro["usage"] = usage
                try:
                    resultado = modelo_salida.model_validate(bruto)
                except ValidationError as exc:
                    registro["respuesta_bruta"] = bruto
                    raise LLMNoDisponible(f"La respuesta de KAIA no cumple el esquema {modelo_salida.__name__}: {exc}") from exc
            else:
                resultado = self._completar_anthropic(system, user, modelo_salida, registro)
            registro["respuesta"] = resultado.model_dump()
            registro["segundos"] = round((datetime.now() - inicio).total_seconds(), 1)
            return resultado
        except (KAIAError, LLMNoDisponible) as exc:
            registro["error"] = str(exc)
            raise LLMNoDisponible(str(exc)) from exc
        finally:
            if self.trazador:
                self.trazador(accion, registro)

    # ------------------------------------------------------------------
    def _completar_anthropic(self, system: str, user: str, modelo_salida: type[T], registro: dict) -> T:
        esquema = json.dumps(modelo_salida.model_json_schema(), ensure_ascii=False)
        system_json = (system + "\n\nResponde ÚNICAMENTE con un objeto JSON válido conforme a este "
                       f"JSON Schema, sin texto adicional ni marcas de código:\n{esquema}")
        resp = self._anthropic.messages.create(
            model=self.modelo, max_tokens=8000, system=system_json,
            messages=[{"role": "user", "content": user}])
        texto = "".join(b.text for b in resp.content if b.type == "text")
        registro["usage"] = {"prompt_tokens": resp.usage.input_tokens,
                             "completion_tokens": resp.usage.output_tokens}
        limpio = texto.strip().removeprefix("```json").removeprefix("```").removesuffix("```").strip()
        try:
            return modelo_salida.model_validate_json(limpio)
        except ValidationError as exc:
            registro["respuesta_bruta"] = texto
            raise LLMNoDisponible(f"La respuesta del modelo no cumple el esquema: {exc}") from exc
