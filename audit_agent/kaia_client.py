"""
Transporte KAIA: agente multi-proveedor interno
(`iop-kaia-auditoriainterna.cloud.inditex.com`), con autenticación OAuth2
client-credentials contra Azure AD v1 (`resource`, no `scope`) y salida
estructurada vía `output_format_schema`.

Adaptado del proveedor de `audit-engine` (ver docs/referencia/kaia_audit_engine.py),
que es lo único probado contra la API real:

- `output_format_schema` usa el formato de *tool calling* de OpenAI
  (`name`/`strict`/`parameters`), no `response_format`. La respuesta trae el
  payload ya parseado en `structured_output` (dict).
- El schema se compila con `to_strict_json_schema` (mismo compilador que el
  SDK de OpenAI): `additionalProperties: false` y todos los campos en
  `required` en cada nivel anidado.
- `return_metadata: True` es necesario para recibir `usage`.
- Los modelos reasoning (`gpt-5*`, `o1*`, `o3*`) rechazan `temperature`:
  no se envía para ellos aunque esté en `.env`.
"""
from __future__ import annotations

import os
import threading
import time

import requests
from openai.lib._pydantic import to_strict_json_schema
from pydantic import BaseModel

DEFAULT_TIMEOUT = 180.0
DEFAULT_INVOKE_PATH = "/api/v2/agent/invoke"
_TOKEN_REFRESH_MARGIN_S = 60
_PREFIJOS_REASONING = ("gpt-5", "o1", "o3", "o4")


class KAIAError(RuntimeError):
    pass


def es_modelo_reasoning(nombre: str) -> bool:
    return nombre.lower().startswith(_PREFIJOS_REASONING)


def schema_para(modelo: type[BaseModel]) -> dict:
    return {
        "name": modelo.__name__.lower(),
        "strict": True,
        "parameters": to_strict_json_schema(modelo),
    }


class KAIAClient:
    def __init__(
        self,
        model_name: str,
        *,
        temperature: float | None = None,
        reasoning_effort: str | None = None,
        timeout: float = DEFAULT_TIMEOUT,
    ) -> None:
        env = os.environ.get
        tenant_id = env("KAIA_TENANT_ID")
        client_id = env("KAIA_CLIENT_ID")
        client_secret = env("KAIA_CLIENT_SECRET")
        resource = env("KAIA_RESOURCE")
        base_url = env("KAIA_AGENT_BASE_URL")
        invoke_path = env("KAIA_AGENT_INVOKE_PATH") or DEFAULT_INVOKE_PATH
        if not all([tenant_id, client_id, client_secret, resource, base_url]):
            raise KAIAError(
                "Faltan credenciales de KAIA: define KAIA_TENANT_ID, KAIA_CLIENT_ID, "
                "KAIA_CLIENT_SECRET, KAIA_RESOURCE y KAIA_AGENT_BASE_URL en .env."
            )
        self._client_id = client_id
        self._client_secret = client_secret
        self._resource = resource
        self._token_url = f"https://login.microsoftonline.com/{tenant_id}/oauth2/token"
        self._invoke_url = base_url.rstrip("/") + invoke_path
        self.model_name = model_name
        self.temperature = None if es_modelo_reasoning(model_name) else temperature
        self.reasoning_effort = reasoning_effort if es_modelo_reasoning(model_name) else None
        self.timeout = timeout
        self._token_lock = threading.Lock()
        self._token: str | None = None
        self._token_expires_at = 0.0

    @staticmethod
    def disponible() -> bool:
        return all(os.environ.get(k) for k in (
            "KAIA_TENANT_ID", "KAIA_CLIENT_ID", "KAIA_CLIENT_SECRET", "KAIA_RESOURCE", "KAIA_AGENT_BASE_URL"))

    # ------------------------------------------------------------------
    def _get_token(self) -> str:
        with self._token_lock:
            if self._token and time.time() < self._token_expires_at - _TOKEN_REFRESH_MARGIN_S:
                return self._token
            body = {
                "grant_type": "client_credentials",
                "client_id": self._client_id,
                "client_secret": self._client_secret,
                "resource": self._resource,
            }
            try:
                r = requests.post(self._token_url, data=body, timeout=self.timeout)
                r.raise_for_status()
            except requests.RequestException as exc:
                raise KAIAError(f"No se pudo obtener el token de Azure AD para KAIA: {exc}") from exc
            data = r.json()
            self._token = data["access_token"]
            self._token_expires_at = float(data["expires_on"])
            return self._token

    # ------------------------------------------------------------------
    def invocar(self, system: str, user: str, modelo_salida: type[BaseModel],
                reasoning_effort: str | None = None) -> tuple[dict, dict | None]:
        """Devuelve (structured_output, usage). `reasoning_effort` puntual
        prevalece sobre el del constructor (solo modelos reasoning)."""
        llm_config: dict = {"model_name": self.model_name}
        if self.temperature is not None:
            llm_config["temperature"] = self.temperature
        esfuerzo = reasoning_effort if es_modelo_reasoning(self.model_name) else None
        esfuerzo = esfuerzo or self.reasoning_effort
        if esfuerzo:
            llm_config["reasoning_effort"] = esfuerzo
        body = {
            "messages": [
                {"type": "system", "content_blocks": [{"type": "text", "text": system}]},
                {"type": "human", "content_blocks": [{"type": "text", "text": user}]},
            ],
            "llm_config": llm_config,
            "output_format_schema": schema_para(modelo_salida),
            "return_metadata": True,
        }
        try:
            r = requests.post(self._invoke_url, json=body,
                              headers={"Authorization": f"Bearer {self._get_token()}"},
                              timeout=self.timeout)
            r.raise_for_status()
        except requests.HTTPError as exc:
            raise KAIAError(f"KAIA devolvió HTTP {r.status_code}: {r.text[:800]}") from exc
        except requests.RequestException as exc:
            raise KAIAError(f"Error de red llamando a KAIA: {exc}") from exc
        try:
            data = r.json()
        except ValueError as exc:
            raise KAIAError("La respuesta de KAIA no es JSON.") from exc
        salida = data.get("structured_output")
        if salida is None:
            raise KAIAError(f"KAIA no devolvió 'structured_output'. Claves recibidas: {list(data)[:10]}")
        usage = data.get("usage")
        if usage:
            det = usage.get("output_token_details") or {}
            usage = {
                "prompt_tokens": usage.get("input_tokens"),
                "completion_tokens": usage.get("output_tokens"),
                "reasoning_tokens": det.get("reasoning", 0),
                "total_tokens": usage.get("total_tokens"),
            }
        return salida, usage
