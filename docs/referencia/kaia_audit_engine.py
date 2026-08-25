"""Proveedor KAIA: agente multi-proveedor de Inditex
(`iop-kaia-auditoriainterna.cloud.inditex.com`), autenticación OAuth2
client-credentials contra Azure AD (v1, con `resource` -- NO es el flujo
`scope`/v2) y salida estructurada vía `output_format_schema`.

`output_format_schema` (`name`/`strict`/`parameters`) es el formato de
*tool calling* de OpenAI, no el `response_format` de tipo `json_schema`
estándar -- probado contra la API real (no está documentado en el ejemplo
de Swagger, que solo mostraba Q&A de texto libre): la respuesta trae el
payload ya parseado en `structured_output` (dict, no string), así que no
hace falta `json.loads` sobre `text` como en `ollama.py`.

El JSON Schema que viaja en `parameters` se construye con el mismo
compilador "strict" que usa el SDK de `openai` para `response_format=`
(`to_strict_json_schema`, el mismo que usa `azure_openai.py` por debajo de
`chat.completions.parse`) y NO a mano: KAIA reenvía la petición al
despliegue real (aquí, OpenAI) y exige el mismo `additionalProperties:
false` + todos los campos listados en `required` en CADA nivel anidado que
ya exige Structured Outputs de OpenAI/Azure -- replicar esa transformación
a mano habría sido reinventar lo que el propio SDK ya hace y ya está
probado en producción vía `azure_openai.py`.
"""

from __future__ import annotations

import json
import os
import threading
import time

import requests
from openai.lib._pydantic import to_strict_json_schema
from pydantic import ValidationError

from audit_engine.sweep.prompts.builder import PACKS, build_system_prompt, build_user_prompt
from audit_engine.sweep.providers.base import BaseProvider, LLMExtractionPayload, RecoverableProviderError
from audit_engine.sweep.schemas import ExtractionRequest, ExtractionResult, Rejection

DEFAULT_TIMEOUT = 120.0
DEFAULT_INVOKE_PATH = "/api/v2/agent/invoke"

# Margen antes de `expires_on` para forzar la renovación del token: evita que
# una llamada en vuelo reciba un 401 justo en el filo de la expiración.
_TOKEN_REFRESH_MARGIN_S = 60

# Uno por extraction_intent, calculados una vez -- no por request (mismo
# patrón que azure_openai.py/ollama.py; SPEC.md § Intenciones de carga).
_SYSTEM_PROMPTS = {intent: build_system_prompt(intent) for intent in PACKS}
_RESPONSE_SCHEMA = to_strict_json_schema(LLMExtractionPayload)  # ver docstring del módulo
_OUTPUT_FORMAT_SCHEMA = {
    "name": "llm_extraction_payload",
    "strict": True,
    "parameters": _RESPONSE_SCHEMA,
}


class KAIAProvider(BaseProvider):
    def __init__(
        self,
        model_name: str,
        *,
        tenant_id: str | None = None,
        client_id: str | None = None,
        client_secret: str | None = None,
        resource: str | None = None,
        base_url: str | None = None,
        invoke_path: str | None = None,
        temperature: float | None = None,
        reasoning_effort: str | None = None,
        timeout: float = DEFAULT_TIMEOUT,
    ) -> None:
        """Credenciales: si no se pasan, se leen de `KAIA_TENANT_ID` /
        `KAIA_CLIENT_ID` / `KAIA_CLIENT_SECRET` / `KAIA_RESOURCE` /
        `KAIA_AGENT_BASE_URL` / `KAIA_AGENT_INVOKE_PATH` (`.env`, cargado por
        `cli.py` con `python-dotenv`) -- mismo patrón que
        `AzureOpenAIProvider`. `resource` es el Application ID del registro
        de aplicación de la API KAIA en Azure AD, no derivable del código.

        `temperature`: igual que `AzureOpenAIProvider` -- `None` por
        defecto, no se manda el parámetro salvo que se pida explícitamente.
        Esta clase tampoco sabe qué familia de modelo hay detrás de
        `model_name` (mismo principio que `AzureOpenAIProvider`): la
        decisión de no mandarlo para un modelo reasoning (`gpt-5*`/`o1*`/
        `o3*`, que rechazan cualquier valor salvo su default) es de quien
        construye el proveedor, no de aquí.

        `reasoning_effort`: `None` por defecto, no se manda salvo que se
        pida ("minimal"/"low"/"medium"/"high") -- viaja dentro de
        `llm_config` junto a `model_name`/`temperature`, sin más lógica: KAIA
        reenvía ese dict tal cual al despliegue real (ver docstring del
        módulo). **Verificado en vivo** (`model_name="gpt-5-mini"`,
        `reasoning_effort="medium"`, SPEC.md § Proveedores): la llamada
        pasa y `usage.output_token_details.reasoning` viene > 0 -- el
        backend lo honra de verdad, no lo ignora en silencio.
        """
        tenant_id = tenant_id or os.environ.get("KAIA_TENANT_ID")
        client_id = client_id or os.environ.get("KAIA_CLIENT_ID")
        client_secret = client_secret or os.environ.get("KAIA_CLIENT_SECRET")
        resource = resource or os.environ.get("KAIA_RESOURCE")
        base_url = base_url or os.environ.get("KAIA_AGENT_BASE_URL")
        invoke_path = invoke_path or os.environ.get("KAIA_AGENT_INVOKE_PATH") or DEFAULT_INVOKE_PATH
        if not all([tenant_id, client_id, client_secret, resource, base_url]):
            raise ValueError(
                "Faltan credenciales de KAIA: define KAIA_TENANT_ID, KAIA_CLIENT_ID, "
                "KAIA_CLIENT_SECRET, KAIA_RESOURCE y KAIA_AGENT_BASE_URL (en .env o como "
                "variables de entorno)."
            )
        self._tenant_id = tenant_id
        self._client_id = client_id
        self._client_secret = client_secret
        self._resource = resource
        self._token_url = f"https://login.microsoftonline.com/{tenant_id}/oauth2/token"
        self._invoke_url = base_url.rstrip("/") + invoke_path
        self.model_name = model_name
        self.temperature = temperature
        self.reasoning_effort = reasoning_effort
        self.timeout = timeout

        # Un token compartido por todos los hilos de extract() del mismo
        # proveedor (uno por `run()`, ver AzureOpenAIProvider): se renueva
        # solo al caducar, no en cada request.
        self._token_lock = threading.Lock()
        self._token: str | None = None
        self._token_expires_at: float = 0.0

        # Mismo patrón que AzureOpenAIProvider._usage_by_unit /
        # OllamaProvider._pre_rejections_by_unit: cada hilo solo toca su
        # propia clave (text_unit_id), el lock solo protege la mutación del
        # dict en sí.
        self._usage_lock = threading.Lock()
        self._usage_by_unit: dict[str, dict] = {}
        self._pre_rejections_lock = threading.Lock()
        self._pre_rejections_by_unit: dict[str, list[Rejection]] = {}

    def pop_usage(self, text_unit_id: str) -> dict | None:
        """Ver AzureOpenAIProvider.pop_usage: tokens de la última llamada a
        `extract()` para esta unidad, consumidos una vez."""
        with self._usage_lock:
            return self._usage_by_unit.pop(text_unit_id, None)

    def pop_pre_rejections(self, text_unit_id: str) -> list[Rejection]:
        """Ver OllamaProvider.pop_pre_rejections: relaciones descartadas en
        el parseo de rescate para la última llamada a esta unidad."""
        with self._pre_rejections_lock:
            return self._pre_rejections_by_unit.pop(text_unit_id, [])

    def _get_token(self) -> str:
        with self._token_lock:
            if self._token is not None and time.time() < self._token_expires_at - _TOKEN_REFRESH_MARGIN_S:
                return self._token
            body = {
                "grant_type": "client_credentials",
                "client_id": self._client_id,
                "client_secret": self._client_secret,
                "resource": self._resource,
            }
            try:
                response = requests.post(self._token_url, data=body, timeout=self.timeout)
                response.raise_for_status()
            except requests.Timeout as exc:
                raise RecoverableProviderError("timeout obteniendo token de Azure AD para KAIA") from exc
            except requests.ConnectionError as exc:
                raise RecoverableProviderError(f"no se pudo conectar a Azure AD: {exc}") from exc
            except requests.HTTPError as exc:
                raise RecoverableProviderError(f"Azure AD devolvió un error HTTP obteniendo el token: {exc}") from exc
            data = response.json()
            self._token = data["access_token"]
            self._token_expires_at = float(data["expires_on"])
            return self._token

    def extract(self, request: ExtractionRequest) -> ExtractionResult:
        token = self._get_token()
        system_prompt = _SYSTEM_PROMPTS.get(request.extraction_intent, _SYSTEM_PROMPTS["NORMATIVO"])
        llm_config: dict = {"model_name": self.model_name}
        if self.temperature is not None:
            llm_config["temperature"] = self.temperature
        if self.reasoning_effort is not None:
            llm_config["reasoning_effort"] = self.reasoning_effort
        request_body = {
            "messages": [
                {"type": "system", "content_blocks": [{"type": "text", "text": system_prompt}]},
                {"type": "human", "content_blocks": [{"type": "text", "text": build_user_prompt(request)}]},
            ],
            "llm_config": llm_config,
            "output_format_schema": _OUTPUT_FORMAT_SCHEMA,
            # Sin esto, la respuesta no trae `usage` -- probado en vivo
            # (CLAUDE.md § Convenciones: coste en tokens acumulado por comando).
            "return_metadata": True,
        }
        try:
            response = requests.post(
                self._invoke_url,
                json=request_body,
                headers={"Authorization": f"Bearer {token}"},
                timeout=self.timeout,
            )
            response.raise_for_status()
        except requests.Timeout as exc:
            raise RecoverableProviderError(f"timeout llamando a KAIA ({self.model_name})") from exc
        except requests.ConnectionError as exc:
            raise RecoverableProviderError(f"no se pudo conectar a KAIA: {exc}") from exc
        except requests.HTTPError as exc:
            raise RecoverableProviderError(f"KAIA devolvió un error HTTP {response.status_code}: {response.text}") from exc

        try:
            response_body = response.json()
        except json.JSONDecodeError as exc:
            raise RecoverableProviderError(f"la respuesta HTTP de KAIA no es JSON: {exc}") from exc

        raw_payload = response_body.get("structured_output")
        if raw_payload is None:
            raise RecoverableProviderError("KAIA no devolvió 'structured_output' en la respuesta")

        try:
            payload, pre_rejections = self._parse_payload_with_rescue(raw_payload)
        except ValidationError as exc:
            raise RecoverableProviderError(f"el JSON de KAIA no es conforme al schema esperado: {exc}") from exc

        if pre_rejections:
            with self._pre_rejections_lock:
                self._pre_rejections_by_unit[request.text_unit_id] = pre_rejections

        usage = response_body.get("usage")
        if usage is not None:
            details = usage.get("output_token_details") or {}
            with self._usage_lock:
                self._usage_by_unit[request.text_unit_id] = {
                    "prompt_tokens": usage.get("input_tokens"),
                    "completion_tokens": usage.get("output_tokens"),
                    "reasoning_tokens": details.get("reasoning", 0),
                    "total_tokens": usage.get("total_tokens"),
                }

        return self._to_extraction_result(payload, request.text_unit_id)
