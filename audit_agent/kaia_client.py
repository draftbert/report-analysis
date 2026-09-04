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


# --------------------------------------------------------------- transcripción de audio
DEFAULT_TRANSCRIBE_PATH = "/api/v2/transcribe/upload"
MODELO_TRANSCRIBE = "gpt-4o-transcribe-diarize"   # con separación de hablantes
MAX_HABLANTES = 4
EXTENSIONES_AUDIO = (".mp3", ".wav", ".m4a", ".webm", ".ogg", ".oga", ".flac", ".mp4", ".mpga")
_MIME_AUDIO = {".mp3": "audio/mpeg", ".mpga": "audio/mpeg", ".wav": "audio/wav", ".m4a": "audio/mp4",
               ".mp4": "audio/mp4", ".webm": "audio/webm", ".ogg": "audio/ogg", ".oga": "audio/ogg", ".flac": "audio/flac"}


def dialogo_de(respuesta: dict) -> str:
    """Respuesta de /transcribe -> diálogo «Hablante: texto», agrupando segmentos
    consecutivos del mismo hablante. Sin segmentos, el texto plano."""
    lineas: list[str] = []
    ultimo = None
    for s in respuesta.get("segments") or []:
        hablante = (s.get("speaker") or "").strip()
        texto = (s.get("text") or "").strip()
        if not texto:
            continue
        if lineas and hablante and hablante == ultimo:
            lineas[-1] += " " + texto
        else:
            lineas.append((f"{hablante}: " if hablante else "") + texto)
            ultimo = hablante
    return "\n".join(lineas) if lineas else (respuesta.get("text") or "").strip()


def transcribir_audio(ruta_audio, hablantes=None) -> dict:
    """Transcribe un audio con KAIA (función de módulo para poder sustituirla en tests).
    `hablantes`: [(nombre, ruta_muestra | None)], máximo 4."""
    modelo = os.environ.get("KAIA_TRANSCRIBE_MODEL") or MODELO_TRANSCRIBE
    return KAIAClient(modelo).transcribir(ruta_audio, hablantes)


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
        self._transcribe_url = base_url.rstrip("/") + (env("KAIA_TRANSCRIBE_PATH") or DEFAULT_TRANSCRIBE_PATH)
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
    def transcribir(self, ruta_audio, hablantes=None, timeout: float = 900.0) -> dict:
        """POST /api/v2/transcribe/upload. Con muestra de voz (2-10 s) para TODOS los
        hablantes se envían `known_speaker_names`/`known_speaker_references` y el
        transcript sale con sus nombres; si falta alguna muestra, diarización genérica
        (los nombres se usan igualmente como contexto en el análisis posterior)."""
        from pathlib import Path
        ruta = Path(ruta_audio)
        hablantes = [(n, m) for n, m in (hablantes or []) if (n or "").strip()]
        if len(hablantes) > MAX_HABLANTES:
            raise KAIAError(f"Máximo {MAX_HABLANTES} hablantes conocidos (llegaron {len(hablantes)}).")
        datos = [("model", os.environ.get("KAIA_TRANSCRIBE_MODEL") or MODELO_TRANSCRIBE)]
        abiertos = [open(ruta, "rb")]
        ficheros = [("file", (ruta.name, abiertos[0], _MIME_AUDIO.get(ruta.suffix.lower(), "application/octet-stream")))]
        if hablantes and all(m for _, m in hablantes):
            for nombre, muestra in hablantes:
                datos.append(("known_speaker_names", nombre.strip()))
                m = Path(muestra)
                abiertos.append(open(m, "rb"))
                ficheros.append(("known_speaker_references", (m.name, abiertos[-1], _MIME_AUDIO.get(m.suffix.lower(), "application/octet-stream"))))
        try:
            r = requests.post(self._transcribe_url, headers={"Authorization": f"Bearer {self._get_token()}"},
                              data=datos, files=ficheros, timeout=(30, timeout))
        except requests.RequestException as exc:
            raise KAIAError(f"Error de red transcribiendo con KAIA: {exc}") from exc
        finally:
            for f in abiertos:
                f.close()
        if r.status_code != 200:
            raise KAIAError(f"KAIA /transcribe devolvió {r.status_code}: {r.text[:300]}")
        return r.json()

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
