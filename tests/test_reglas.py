"""Edición del criterio de estilo desde la web: round-trip con comentarios, snapshot, validación,
restauración y propuesta por chat (modelo mockeado)."""
from __future__ import annotations

import shutil
import time
from pathlib import Path

import pytest
import yaml
from fastapi.testclient import TestClient

from audit_agent import api as api_mod
from audit_agent import reglas
from audit_agent.esquemas import PropuestaReglas, ReglasEstilo
from audit_agent.expediente import ExpedienteError
from tests.conftest import LLMFalso

RAIZ = Path(__file__).resolve().parent.parent


@pytest.fixture
def estilo_tmp(tmp_path, monkeypatch):
    ruta = tmp_path / "estilo.yaml"
    shutil.copy(RAIZ / "config" / "estilo.yaml", ruta)
    monkeypatch.setattr(reglas, "RUTA_ESTILO", ruta)
    monkeypatch.setattr(reglas, "DIR_HISTORIAL", tmp_path / "historial")
    return ruta


def test_round_trip_sin_cambios_no_toca_el_yaml(estilo_tmp):
    texto = reglas.leer_texto()
    assert reglas.texto_desde_reglas(reglas.leer()) == texto


def test_guardar_conserva_comentarios_y_hace_snapshot(estilo_tmp):
    r = reglas.leer()
    r["reglas"]["longitud_maxima_frase"] = 40
    r["palabras_prohibidas"].append({"termino": "catastrófico", "sugerencia": "de impacto alto", "motivo": "Alarmista."})
    guardadas = reglas.guardar(r, motivo="prueba")
    texto = reglas.leer_texto()
    assert "# Este fichero es EL punto de mantenimiento" in texto          # cabecera
    assert "#Ojo revisar para auditorias de fraude" in texto               # comentario en línea de una lista modificada
    assert "longitud_maxima_frase: 40" in texto
    assert guardadas["reglas"]["longitud_maxima_frase"] == 40
    assert any(p["termino"] == "catastrófico" for p in yaml.safe_load(texto)["palabras_prohibidas"])
    versiones = reglas.historial()
    assert len(versiones) == 1 and versiones[0]["motivo"] == "prueba"
    # el snapshot es el YAML anterior
    assert "longitud_maxima_frase: 55" in (reglas.DIR_HISTORIAL / versiones[0]["nombre"]).read_text(encoding="utf-8")


def test_guardar_sin_cambios_no_crea_snapshot(estilo_tmp):
    reglas.guardar(reglas.leer())
    assert reglas.historial() == []


def test_validacion_rechaza_yaml_roto_y_estructura_mala(estilo_tmp):
    with pytest.raises(ExpedienteError):
        reglas.guardar_texto("palabras_prohibidas: [\n")
    with pytest.raises(ExpedienteError):
        reglas.guardar_texto("- solo una lista\n")
    with pytest.raises(ExpedienteError):
        reglas.guardar_texto("palabras_prohibidas:\n  - sugerencia: sin termino\n")
    assert reglas.historial() == []   # nada se escribió


def test_restaurar_version(estilo_tmp):
    original = reglas.leer_texto()
    r = reglas.leer(); r["primera_persona"].append("me parece")
    reglas.guardar(r, motivo="cambio")
    time.sleep(1.05)   # nombres de snapshot con resolución de segundo
    nombre = reglas.historial()[0]["nombre"]
    reglas.restaurar(nombre)
    assert reglas.leer_texto() == original
    assert reglas.historial()[0]["motivo"] == "restaurar"
    with pytest.raises(ExpedienteError):
        reglas.restaurar("../../etc/passwd")


def test_chat_propone_sin_escribir(estilo_tmp):
    base = ReglasEstilo.model_validate(reglas.leer())
    propuesta = base.model_copy(deep=True)
    propuesta.reglas.longitud_maxima_frase = 45
    falso = LLMFalso({"reglas-chat": PropuestaReglas(respuesta="Bajada la longitud máxima a 45.", cambios=["reglas.longitud_maxima_frase: 55 → 45"], reglas=propuesta)})
    antes = reglas.leer_texto()
    r = reglas.chat("Baja la longitud máxima de frase a 45 palabras", llm=falso)
    assert r["reglas"]["reglas"]["longitud_maxima_frase"] == 45
    assert r["cambios"] and not r["sin_cambios"]
    assert "-  longitud_maxima_frase: 55" in r["diff"] and "+  longitud_maxima_frase: 45" in r["diff"]
    assert reglas.leer_texto() == antes                       # el modelo propone, no escribe
    assert "PETICIÓN DEL AUDITOR" in falso.llamadas[0][1]
    with pytest.raises(ExpedienteError):
        reglas.chat("   ", llm=falso)


def test_api_reglas(estilo_tmp, monkeypatch):
    propuesta = ReglasEstilo.model_validate(reglas.leer())
    propuesta.palabras_prohibidas.append({"termino": "desastre", "sugerencia": "incidencia", "motivo": "Alarmista."})
    falso = LLMFalso({"reglas-chat": PropuestaReglas(respuesta="Añadida «desastre».", cambios=["palabras_prohibidas: + desastre"], reglas=propuesta)})
    monkeypatch.setattr(reglas, "cliente_llm", lambda: falso)
    c = TestClient(api_mod.app)

    est = c.get("/api/reglas").json()
    assert est["reglas"]["reglas"]["longitud_maxima_frase"] == 55 and "palabras_prohibidas" in est["yaml"] and est["historial"] == []

    # chat → job → propuesta (nada escrito)
    job = c.post("/api/reglas/chat", json={"mensaje": "Prohíbe la palabra desastre"}).json()
    for _ in range(100):
        j = c.get(f"/api/jobs/{job['job_id']}").json()
        if j["estado"] != "en_curso":
            break
        time.sleep(0.05)
    assert j["estado"] == "ok" and j["resultado"]["cambios"] == ["palabras_prohibidas: + desastre"]
    assert "desastre" not in reglas.leer_texto()

    # el auditor guarda la propuesta
    est = c.put("/api/reglas", json={"reglas": j["resultado"]["reglas"], "motivo": "chat"}).json()
    assert any(p["termino"] == "desastre" for p in est["reglas"]["palabras_prohibidas"])
    assert "desastre" in reglas.leer_texto() and est["historial"][0]["motivo"] == "chat"

    # YAML completo inválido → 400 con mensaje
    r = c.put("/api/reglas", json={"yaml": "primera_persona: [yo\n"})
    assert r.status_code == 400 and "error" in r.json()
    assert c.put("/api/reglas", json={}).status_code == 400
    assert c.post("/api/reglas/chat", json={"mensaje": " "}).status_code == 400
    assert c.post("/api/reglas/restaurar", json={"nombre": "no-existe.yaml"}).status_code == 400
