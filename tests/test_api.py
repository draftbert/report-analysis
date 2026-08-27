"""API REST (FastAPI) sobre expedientes temporales, con el LLM mockeado."""
from __future__ import annotations

import io
import time
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from audit_agent import api as api_mod
from audit_agent.esquemas import ConclusionExtraida, ContextoInforme, ExtraccionConclusiones
from tests.conftest import LLMFalso

RAIZ = Path(__file__).resolve().parent.parent


@pytest.fixture
def cliente(tmp_path, monkeypatch):
    monkeypatch.setattr(api_mod, "DIR_EXPEDIENTES", tmp_path)
    falso = LLMFalso({
        "redactar-contexto": ContextoInforme(introduccion="Intro.", resumen_ejecutivo="Res.", evaluacion_global="Mejorable"),
        "extraer": ExtraccionConclusiones(conclusiones=[ConclusionExtraida(
            titulo="Mantenimiento manual", prueba="2.11 b)", incidencia="Inc.", causa_raiz="C", como_se_ha_llegado="- d1",
            consecuencias="K", recomendacion="", nivel_riesgo="Medio", riesgo_soportado_por_evidencia=False)]),
    })
    monkeypatch.setattr(api_mod, "_ctx", lambda exp: _ctx_falso(exp, falso))
    return TestClient(api_mod.app), falso


def _ctx_falso(exp, falso):
    from audit_agent.acciones import Contexto
    ctx = Contexto(exp, proveedor="dry-run")
    ctx.llm = falso
    return ctx


def _esperar(c: TestClient, job_id: str):
    for _ in range(100):
        j = c.get(f"/api/jobs/{job_id}").json()
        if j["estado"] != "en_curso":
            return j
        time.sleep(0.05)
    raise AssertionError("job no termina")


def test_flujo_completo_por_api(cliente):
    c, falso = cliente
    r = c.post("/api/expedientes", json={"referencia": "T-1", "nombre": "Prueba", "fecha": "Junio 2026", "distribucion": ["D"]})
    assert r.status_code == 201 and r.json()["fase"].startswith("0")
    assert [e["referencia"] for e in c.get("/api/expedientes").json()] == ["T-1"]
    # documentos
    pt = (RAIZ / "ejemplos" / "papel_trabajo_compras.md").read_bytes()
    r = c.post("/api/expedientes/T-1/documentos/papeles_trabajo", files=[("ficheros", ("pt.md", io.BytesIO(pt), "text/markdown"))])
    assert r.status_code == 200 and r.json()["papeles_trabajo"][0]["nombre"] == "pt.md"
    assert c.post("/api/expedientes/T-1/documentos/otra", files=[("ficheros", ("x.md", b"x"))]).status_code == 400
    assert c.get("/api/expedientes/T-1").json()["fase"].startswith("1")
    # contexto (job)
    j = _esperar(c, c.post("/api/expedientes/T-1/acciones/redactar-contexto", json={}).json()["job_id"])
    assert j["estado"] == "ok" and "Introducción" in j["mensaje"]
    inf = c.get("/api/expedientes/T-1/informe").json()
    assert inf["apartados"][0]["markdown"] == "Intro." and inf["evaluacion_global"] == "Mejorable"
    # editar el resumen desde el front
    inf = c.put("/api/expedientes/T-1/informe", json={"resumen_ejecutivo": "Res. editado", "evaluacion_global": "Razonable"}).json()
    assert inf["apartados"][1]["markdown"] == "Res. editado" and inf["evaluacion_global"] == "Razonable"
    # extraer (job) + conclusiones
    j = _esperar(c, c.post("/api/expedientes/T-1/acciones/extraer", json={}).json()["job_id"])
    assert j["estado"] == "ok"
    cs = c.get("/api/expedientes/T-1/conclusiones").json()["conclusiones"]
    assert cs[0]["id"] == "C-01" and cs[0]["riesgo_propuesto"] is True
    # editar una conclusión (el auditor rellena la recomendación) y aprobar
    r = c.put("/api/expedientes/T-1/conclusiones/C-01", json={"recomendacion": "Implantar un sistema.", "area": "Transporte"}).json()
    assert r["recomendacion"] == "Implantar un sistema." and r["area"] == "Transporte"
    assert "C-01" in c.post("/api/expedientes/T-1/acciones/aprobar", json={"ids": ["todas"], "estado": "aprobada"}).json()["mensaje"]
    assert c.get("/api/expedientes/T-1/conclusiones").json()["conclusiones"][0]["riesgo_propuesto"] is False
    # recomendar: nada que hacer (ya tiene) → job ok sin llamadas al modelo
    j = _esperar(c, c.post("/api/expedientes/T-1/acciones/recomendar", json={"respuestas": {}, "auto": False}).json()["job_id"])
    assert j["estado"] == "ok" and "se respeta tal cual" in j["mensaje"]
    # volcar al informe + revisar + historial + diff
    assert "Detalle de conclusiones (1)" in c.post("/api/expedientes/T-1/acciones/redactar-conclusiones").json()["mensaje"]
    inf = c.get("/api/expedientes/T-1/informe").json()
    assert [a["tipo"] for a in inf["apartados"]] == ["introduccion", "resumen", "conclusion"] and inf["apartados"][2]["nivel_riesgo"] == "Medio"
    rev = c.post("/api/expedientes/T-1/acciones/revisar").json()
    assert "hallazgos" in rev and "errores" in rev
    assert c.get("/api/expedientes/T-1/historial").json()[0]["fichero"] == "informe"
    assert "diff" in c.get("/api/expedientes/T-1/diff?fichero=informe").json()
    # instrucciones
    assert c.put("/api/expedientes/T-1/instrucciones", json={"texto": "Cambiar X."}).json()["texto"] == "Cambiar X."
    assert c.get("/api/expedientes/T-1").json()["instrucciones_pendientes"] is True
    # ppt + archivar + descarga + trazas
    ppt = c.post("/api/expedientes/T-1/acciones/ppt").json()
    assert ppt["nombre"].endswith(".pptx") and c.get(ppt["url"]).status_code == 200
    z = c.post("/api/expedientes/T-1/acciones/archivar").json()
    assert z["nombre"].endswith(".zip") and c.get(z["url"]).status_code == 200
    trazas = c.get("/api/expedientes/T-1/trazas").json()
    assert any(t["accion"].endswith("entrada") for t in trazas)
    assert c.get("/api/expedientes/NO-EXISTE").status_code == 404


def test_errores_y_jobs(cliente):
    c, _ = cliente
    c.post("/api/expedientes", json={"referencia": "T-2", "nombre": "P"})
    assert c.post("/api/expedientes", json={"referencia": "T-2", "nombre": "P"}).status_code == 409
    assert c.post("/api/expedientes", json={"referencia": "../x", "nombre": "P"}).status_code == 400
    assert c.get("/api/jobs/nope").status_code == 404
    # aprobar sin conclusiones → 400 con {error}
    r = c.post("/api/expedientes/T-2/acciones/aprobar", json={"ids": ["todas"]})
    assert r.status_code == 400 and "error" in r.json()
    # cambio sin mensaje
    assert c.post("/api/expedientes/T-2/acciones/cambio", json={"mensaje": " "}).status_code == 400
