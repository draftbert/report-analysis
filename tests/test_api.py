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
    assert inf["apartados"][0]["markdown"] == "Intro." and inf["evaluacion_global"] == ""   # la califica el auditor, no el modelo
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


def test_eliminar_expediente_exige_la_referencia(cliente):
    c, _ = cliente
    c.post("/api/expedientes", json={"referencia": "T-3", "nombre": "P"})
    r = c.request("DELETE", "/api/expedientes/T-3", json={"confirmacion": "T-33"})
    assert r.status_code == 400 and "T-3" in r.json()["error"]
    assert c.get("/api/expedientes/T-3").status_code == 200
    r = c.request("DELETE", "/api/expedientes/T-3", json={"confirmacion": "T-3"})
    assert r.status_code == 200 and "eliminado" in r.json()["mensaje"]
    assert c.get("/api/expedientes/T-3").status_code == 404
    assert c.request("DELETE", "/api/expedientes/T-3", json={"confirmacion": "T-3"}).status_code == 404


def test_aprobar_una_a_una_por_api(cliente):
    c, _ = cliente
    c.post("/api/expedientes", json={"referencia": "T-4", "nombre": "P"})
    pt = (RAIZ / "ejemplos" / "papel_trabajo_compras.md").read_bytes()
    c.post("/api/expedientes/T-4/documentos/papeles_trabajo", files=[("ficheros", ("pt.md", io.BytesIO(pt), "text/markdown"))])
    _esperar(c, c.post("/api/expedientes/T-4/acciones/extraer", json={}).json()["job_id"])
    assert "C-01" in c.post("/api/expedientes/T-4/acciones/aprobar", json={"ids": ["C-01"], "estado": "aprobada"}).json()["mensaje"]
    cs = c.get("/api/expedientes/T-4/conclusiones").json()["conclusiones"]
    assert cs[0]["estado"] == "aprobada" and cs[0]["riesgo_propuesto"] is False
    assert c.post("/api/expedientes/T-4/acciones/aprobar", json={"ids": ["C-01"], "estado": "descartada"}).status_code == 200
    assert c.get("/api/expedientes/T-4/conclusiones").json()["conclusiones"][0]["estado"] == "descartada"
    assert c.post("/api/expedientes/T-4/acciones/aprobar", json={"ids": ["C-01"], "estado": "propuesta"}).status_code == 200
    assert c.get("/api/expedientes/T-4/conclusiones").json()["conclusiones"][0]["estado"] == "propuesta"


def test_comparacion_del_informe_con_el_ultimo_cambio(cliente):
    c, falso = cliente
    c.post("/api/expedientes", json={"referencia": "T-8", "nombre": "N", "fecha": "Mayo 2026", "distribucion": []})
    assert c.get("/api/expedientes/T-8/informe/comparacion").json() == {
        "contra": None, "versiones": [], "apartados": [], "lineas_nuevas": 0, "lineas_borradas": 0}
    c.put("/api/expedientes/T-8/informe", json={"introduccion": "Intro con 12 casos.", "resumen_ejecutivo": "Res."})
    c.put("/api/expedientes/T-8/informe", json={"introduccion": "Intro con 15 casos."})           # edición manual
    c.put("/api/expedientes/T-8/informe", json={"introduccion": "Intro con 15 casos."})           # guardar sin cambios
    r = c.get("/api/expedientes/T-8/informe/comparacion").json()
    assert r["contra"]["origen"] == "Edición manual" and r["contra"]["motivo"] == "web"
    intro = next(a for a in r["apartados"] if a["id"] == "introduccion")                          # salta el guardado sin cambios
    assert intro["estado"] == "modificado" and [s["texto"] for l in intro["lineas"] if l["tipo"] == "add" for s in l["segmentos"] if s["cambio"]] == ["15"]
    # cambio aplicado desde un acta de reunión (web): queda identificado como tal
    from audit_agent.esquemas import Cambio, PlanCambios
    falso.respuestas["aplicar-cambios"] = PlanCambios(cambios=[Cambio(
        seccion="## Introducción", motivo="acta", texto_original="15 casos", texto_nuevo="16 casos", insertar_tras="")], pendientes=[])
    j = _esperar(c, c.post("/api/expedientes/T-8/acciones/aplicar-cambios", json={"texto": "Son 16 casos."}).json()["job_id"])
    assert j["estado"] == "ok"
    r = c.get("/api/expedientes/T-8/informe/comparacion").json()
    assert r["contra"]["origen"] == "Acta de reunión" and r["versiones"][0]["origen"] == "Acta de reunión"
    assert c.get("/api/expedientes/T-8/historial").json()[0]["motivo"] == "reunion"
    # contra una versión anterior concreta: cambios acumulados desde entonces
    primera = r["versiones"][-1]["nombre"]
    r = c.get(f"/api/expedientes/T-8/informe/comparacion?contra={primera}").json()
    assert r["contra"]["nombre"] == primera and r["lineas_nuevas"] >= 1
    assert c.get("/api/expedientes/T-8/informe/comparacion?contra=no-existe.md").status_code == 404


def test_cambios_desde_el_ultimo_powerpoint(cliente):
    c, _ = cliente
    c.post("/api/expedientes", json={"referencia": "T-5", "nombre": "N", "fecha": "Mayo 2026", "distribucion": []})
    assert c.get("/api/expedientes/T-5/informe/comparacion?desde=ppt").status_code == 404   # aún no hay PowerPoint
    exp_dir = api_mod.DIR_EXPEDIENTES / "T-5"
    (exp_dir / "02_informe.md").write_text(
        "# Informe\n\n## Introducción\n\nIntro con 12 casos.\n\n## Resumen ejecutivo\n\nRes.\n\n"
        "## Detalle de conclusiones\n\n### 1. T\n\n- Nivel de riesgo: Medio\n\nCuerpo.\n\n"
        "**Recomendación 1.1.** Implantar.\n\n## Sugerencias de mejora\n\n_(ninguna)_\n", encoding="utf-8")
    c.put("/api/expedientes/T-5/informe", json={"introduccion": "Intro con 10 casos."})     # cambio anterior al PPT
    assert c.post("/api/expedientes/T-5/acciones/ppt").status_code == 200
    r = c.get("/api/expedientes/T-5/informe/comparacion?desde=ppt").json()
    assert r["ppt"] and r["contra"] is None and r["apartados"] == []                         # nada cambió desde el PPT
    c.put("/api/expedientes/T-5/informe", json={"introduccion": "Intro con 15 casos."})
    c.put("/api/expedientes/T-5/informe", json={"resumen_ejecutivo": "Res. ampliado."})
    r = c.get("/api/expedientes/T-5/informe/comparacion?desde=ppt").json()
    cambiados = {a["id"] for a in r["apartados"] if a["estado"] != "igual"}
    assert cambiados == {"introduccion", "resumen"}                                         # los dos cambios posteriores, no el anterior
    intro = next(a for a in r["apartados"] if a["id"] == "introduccion")
    assert [s["texto"] for l in intro["lineas"] if l["tipo"] == "del" for s in l["segmentos"] if s["cambio"]] == ["10"]
    assert c.get("/api/expedientes/T-5").json()["ppt"]["desactualizado"] is True


def test_aplicar_desde_un_acta_marca_los_enviados(cliente):
    import json
    from audit_agent.esquemas import Cambio, PlanCambios
    c, falso = cliente
    c.post("/api/expedientes", json={"referencia": "T-7", "nombre": "N", "fecha": "Mayo 2026", "distribucion": []})
    c.put("/api/expedientes/T-7/informe", json={"introduccion": "Intro con 12 casos.", "resumen_ejecutivo": "Res."})
    reuniones = api_mod.DIR_EXPEDIENTES / "T-7" / "reuniones"
    (reuniones / "2026-09-28_1000_reunion.md").write_text("# Acta", encoding="utf-8")
    (reuniones / "2026-09-28_1000_reunion.json").write_text(json.dumps({"resumen": "r", "cambios_texto": [
        {"seccion": "Introducción", "que_cambiar": "a", "instruccion": "Son 16 casos.", "solicitado_por": "", "cita": ""},
        {"seccion": "Resumen", "que_cambiar": "b", "instruccion": "Otro.", "solicitado_por": "", "cita": ""}],
        "cambios_ppt": [], "pendientes": [], "acuerdos_sin_cambio": []}), encoding="utf-8")
    falso.respuestas["aplicar-cambios"] = PlanCambios(cambios=[Cambio(
        seccion="## Introducción", motivo="acta", texto_original="12 casos", texto_nuevo="16 casos", insertar_tras="")], pendientes=[])
    j = _esperar(c, c.post("/api/expedientes/T-7/acciones/aplicar-cambios",
                           json={"texto": "- Son 16 casos.", "acta": "2026-09-28_1000_reunion.md", "indices": [0]}).json()["job_id"])
    assert j["estado"] == "ok"
    datos = c.get("/api/expedientes/T-7/reuniones").json()[0]["actas"][0]["datos"]
    assert list(datos["aplicados"]) == ["0"] and datos["aplicados"]["0"]["resumen"] == "Aplicados 1 de 1 cambios en el informe"
    r = c.put("/api/expedientes/T-7/reuniones/2026-09-28_1000_reunion.md/aplicados", json={"indices": [0], "aplicado": False})
    assert r.status_code == 200 and r.json()["aplicados"] == {}
    assert c.put("/api/expedientes/T-7/reuniones/2026-09-28_1000_reunion.md/aplicados", json={"indices": [9]}).status_code == 400


def test_revision_de_vocabulario_propone_y_aplica_por_parrafo(cliente):
    from audit_agent.esquemas import Correcciones, ParrafoCorregido
    c, falso = cliente
    c.post("/api/expedientes", json={"referencia": "T-6", "nombre": "N", "fecha": "Mayo 2026", "distribucion": []})
    c.put("/api/expedientes/T-6/informe", json={"introduccion": "Se detectó un fallo en la conciliación mensual.", "resumen_ejecutivo": "Res."})
    rev = c.post("/api/expedientes/T-6/acciones/revisar").json()
    h = next(x for x in rev["hallazgos"] if x["fragmento"].lower() == "fallo")
    assert h["apartado"] == "introduccion" and h["parrafo"] == "Se detectó un fallo en la conciliación mensual."
    # el modelo propone; el informe no se toca
    falso.respuestas["proponer-correcciones"] = lambda accion, user: Correcciones(parrafos=[
        ParrafoCorregido(id=1, texto="Se detectó una debilidad en la conciliación mensual.")])
    antes = c.get("/api/expedientes/T-6/informe").json()["markdown"]
    j = _esperar(c, c.post("/api/expedientes/T-6/acciones/proponer-correcciones", json={}).json()["job_id"])
    assert j["estado"] == "ok" and c.get("/api/expedientes/T-6/informe").json()["markdown"] == antes
    prop = j["resultado"]["propuestas"][0]
    assert prop["apartado"] == "introduccion" and prop["errores_restantes"] == []
    assert [s["texto"] for l in prop["lineas"] if l["tipo"] == "add" for s in l["segmentos"] if s["cambio"]] == ["una", "debilidad"]
    # el auditor aplica la propuesta
    r = c.post("/api/expedientes/T-6/acciones/aplicar-correccion", json={"original": prop["original"], "propuesta": prop["propuesta"]})
    assert r.status_code == 200
    assert "una debilidad" in c.get("/api/expedientes/T-6/informe").json()["apartados"][0]["markdown"]
    assert c.get("/api/expedientes/T-6/informe/comparacion").json()["contra"]["origen"] == "Revisión de vocabulario"
    # otra vez la misma: el párrafo ya no está como se revisó
    r = c.post("/api/expedientes/T-6/acciones/aplicar-correccion", json={"original": prop["original"], "propuesta": prop["propuesta"]})
    assert r.status_code == 400 and "vuelve a revisar" in r.json()["error"]


def test_reunion_api_con_audio_y_hablantes(cliente, monkeypatch):
    from audit_agent import acciones
    from tests.test_reunion import ANALISIS
    c, falso = cliente
    c.post("/api/expedientes", json={"referencia": "T-A", "nombre": "N", "fecha": "Mayo 2026", "distribucion": []})
    (api_mod.DIR_EXPEDIENTES / "T-A" / "02_informe.md").write_text("# I\n\n## Introducción\n\nTexto suficiente para contrastar la reunión.\n", encoding="utf-8")
    visto = {}

    def falso_transcribir(ruta, hablantes=None):
        visto["hablantes"] = hablantes
        return {"model": "gpt-4o-transcribe-diarize", "duration": 5.0,
                "segments": [{"speaker": "Marta", "text": "Cambiamos el riesgo a Alto y revisamos la redacción entera."}]}

    from audit_agent import transcripcion
    monkeypatch.setattr(transcripcion, "transcribir_audio", falso_transcribir)
    falso.respuestas["reunion"] = ANALISIS
    j = _esperar(c, c.post("/api/expedientes/T-A/acciones/reunion",
                           files={"transcripcion": ("revision.mp3", b"\x00" * 32, "audio/mpeg"),
                                  "muestras": ("marta.wav", b"\x00" * 16, "audio/wav")},
                           data={"aplicar": "false", "hablantes": ["Marta"]}).json()["job_id"])
    assert j["estado"] == "ok", j["mensaje"]
    assert "progreso" in j and "progreso_pct" in j and "progreso_partes" in j   # el front enseña las fases del job
    assert j["resultado"]["transcripcion"].startswith("reuniones/") and j["resultado"]["cambios_texto"]
    reuniones = api_mod.DIR_EXPEDIENTES / "T-A" / "reuniones"
    assert not list(reuniones.glob("*.mp3"))                       # el audio subido se borra al terminar
    assert list(reuniones.glob("*_transcripcion.txt"))             # la transcripción sí se conserva
    assert visto["hablantes"][0][0] == "Marta" and visto["hablantes"][0][1] is not None
    assert not list(__import__("glob").glob("/tmp/muestras_voz_*"))  # las muestras de voz no se conservan


def test_listado_agrupado_y_borrado_de_reuniones(cliente):
    import json as json_mod
    c, _ = cliente
    c.post("/api/expedientes", json={"referencia": "T-R", "nombre": "N", "fecha": "Mayo 2026", "distribucion": []})
    reuniones = api_mod.DIR_EXPEDIENTES / "T-R" / "reuniones"
    # acta + transcripción del mismo origen (con estructura .json) y una reunión suelta de otro día
    (reuniones / "2026-09-04_1001_revision_tarifarios.md").write_text("# Acta", encoding="utf-8")
    (reuniones / "2026-09-04_1001_revision_tarifarios.json").write_text(json_mod.dumps({
        "resumen": "R.", "cambios_texto": [], "cambios_ppt": [], "pendientes": ["p1"], "acuerdos_sin_cambio": []}), encoding="utf-8")
    (reuniones / "2026-09-04_0952_revision_tarifarios_transcripcion.txt").write_text("Marta: hola", encoding="utf-8")
    (reuniones / "2026-09-02_0900_kickoff_transcripcion.txt").write_text("Javier: hola", encoding="utf-8")
    listado = c.get("/api/expedientes/T-R/reuniones").json()
    assert [i["origen"] for i in listado] == ["revision_tarifarios", "kickoff"]
    item = listado[0]
    assert [a["nombre"] for a in item["actas"]] == ["2026-09-04_1001_revision_tarifarios.md"]
    assert item["actas"][0]["datos"]["pendientes"] == ["p1"]           # la estructura viaja con el acta
    assert [t["nombre"] for t in item["transcripciones"]] == ["2026-09-04_0952_revision_tarifarios_transcripcion.txt"]
    assert listado[1]["actas"] == [] and len(listado[1]["transcripciones"]) == 1
    # borrar la transcripción devuelve el listado agrupado actualizado; el acta sigue en su ítem
    tras = c.delete("/api/expedientes/T-R/reuniones/2026-09-04_0952_revision_tarifarios_transcripcion.txt").json()
    assert [a["nombre"] for a in tras[0]["actas"]] == ["2026-09-04_1001_revision_tarifarios.md"] and tras[0]["transcripciones"] == []
    assert not (reuniones / "2026-09-04_0952_revision_tarifarios_transcripcion.txt").exists()
    # borrar el acta se lleva también su .json hermano
    tras = c.delete("/api/expedientes/T-R/reuniones/2026-09-04_1001_revision_tarifarios.md").json()
    assert [i["origen"] for i in tras] == ["kickoff"]
    assert not (reuniones / "2026-09-04_1001_revision_tarifarios.json").exists()
    # nombres con rutas relativas no salen de reuniones/ y un nombre inexistente da 404
    assert c.delete("/api/expedientes/T-R/reuniones/..%2Fexpediente.yaml").status_code in (404, 405)
    assert (api_mod.DIR_EXPEDIENTES / "T-R" / "expediente.yaml").exists()
    assert c.delete("/api/expedientes/T-R/reuniones/no_existe.txt").status_code == 404


def test_flujo_web_de_identificacion_de_hablantes(cliente, monkeypatch, tmp_path):
    import shutil as sh
    import subprocess
    from audit_agent import transcripcion
    if not sh.which("ffmpeg"):
        import pytest
        pytest.skip("sin ffmpeg")
    c, _ = cliente
    c.post("/api/expedientes", json={"referencia": "T-V", "nombre": "N", "fecha": "Mayo 2026", "distribucion": []})
    wav = tmp_path / "reunion.wav"
    subprocess.run(["ffmpeg", "-y", "-f", "lavfi", "-i", "sine=frequency=440:duration=30", "-ac", "1", "-ar", "16000",
                    str(wav)], capture_output=True, check=True)
    respuesta = {"model": "m", "provider": "openai", "duration": 30.0, "text": "", "segments": [
        {"id": "0", "speaker": "A", "start": 0.0, "end": 12.0, "text": "Subid el riesgo a alto."},
        {"id": "1", "speaker": "B", "start": 12.5, "end": 26.0, "text": "De acuerdo con el cambio."}]}
    monkeypatch.setattr(transcripcion, "transcribir_audio", lambda *a, **k: respuesta)
    j = _esperar(c, c.post("/api/expedientes/T-V/acciones/transcribir",
                           files={"fichero": ("reunion.wav", wav.read_bytes(), "audio/wav")}).json()["job_id"])
    assert j["estado"] == "ok", j["mensaje"]
    t = c.get("/api/expedientes/T-V/transcripcion").json()
    assert t["hay_transcripcion"] and not t["etiquetada"] and [h["id"] for h in t["hablantes"]] == ["SPEAKER_01", "SPEAKER_02"]
    assert "Subid el riesgo a alto." in t["markdown"]              # la web muestra la transcripción entera
    assert c.get(f"/api/expedientes/T-V/audio/hablantes/{t['hablantes'][0]['clip']}").status_code == 200
    # el borrador del etiquetado se guarda en el expediente y sobrevive a un refresco del navegador
    b = c.put("/api/expedientes/T-V/transcripcion/borrador", json={
        "asignaciones": {"SPEAKER_01": {"nombre": "Marta", "accion": ""}}, "guardar_voces": ["SPEAKER_01"]}).json()
    assert not b["etiquetada"]                                     # guardar el borrador no etiqueta nada
    t = c.get("/api/expedientes/T-V/transcripcion").json()
    h1, h2 = (next(h for h in t["hablantes"] if h["id"] == i) for i in ("SPEAKER_01", "SPEAKER_02"))
    assert h1["nombre"] == "Marta" and h1["guardar"] and h2["nombre"] == "" and not h2["guardar"]
    # etiquetar es un job: sin 02_informe.md no hay acta y cae al volcado en bruto al buzón
    j = _esperar(c, c.post("/api/expedientes/T-V/acciones/etiquetar", json={
        "asignaciones": {"SPEAKER_01": {"nombre": "Marta", "accion": ""}, "SPEAKER_02": {"nombre": "Javier", "accion": ""}},
        "guardar_voces": ["Marta"]}).json()["job_id"])
    assert j["estado"] == "ok", j["mensaje"]
    r = j["resultado"]
    assert "Sin acta" in j["mensaje"] and r["etiquetada"]
    assert [v["nombre"] for v in r["voces"]] == ["Marta"]
    txts = list((api_mod.DIR_EXPEDIENTES / "T-V" / "reuniones").glob("*_transcripcion.txt"))
    assert len(txts) == 1 and "Marta: Subid el riesgo a alto." in txts[0].read_text(encoding="utf-8")
    instrucciones = (api_mod.DIR_EXPEDIENTES / "T-V" / "03_instrucciones.md").read_text(encoding="utf-8")
    assert "Marta" not in instrucciones                                # el buzón del auditor no se toca
    assert c.delete("/api/expedientes/T-V/voces/Marta").json()["voces"] == []


def test_reunion_repetida_avisa_y_borrar_desbloquea(cliente):
    from audit_agent.esquemas import AnalisisReunion
    c, falso = cliente
    falso.respuestas["reunion"] = AnalisisReunion(resumen="Se revisó el borrador con el área.")
    c.post("/api/expedientes", json={"referencia": "T-H", "nombre": "N", "fecha": "Mayo 2026", "distribucion": []})
    (api_mod.DIR_EXPEDIENTES / "T-H" / "02_informe.md").write_text("# Informe\n\nTexto actual del informe.", encoding="utf-8")
    contenido = b"Marta: subid el riesgo a alto, por favor, y acortad tambien el resumen ejecutivo."
    subir = lambda: _esperar(c, c.post("/api/expedientes/T-H/acciones/reunion",
                                       files={"transcripcion": ("notas.txt", contenido, "text/plain")}).json()["job_id"])
    assert subir()["estado"] == "ok"
    j = subir()                                                        # mismo contenido otra vez
    assert j["estado"] == "error" and "Reunión repetida" in j["mensaje"] and "elimina esa reunión" in j["mensaje"]
    listado = c.get("/api/expedientes/T-H/reuniones").json()
    assert len(listado) == 1 and len(listado[0]["transcripciones"]) == 1   # el intento repetido no deja copia huérfana
    # borrar el acta olvida la huella y desbloquea la re-subida
    c.delete(f"/api/expedientes/T-H/reuniones/{listado[0]['actas'][0]['nombre']}")
    assert subir()["estado"] == "ok"


def test_detener_job(cliente):
    import threading
    c, _ = cliente
    api_mod._JOBS["j-test"] = {"estado": "en_curso", "accion": "transcribir", "mensaje": "", "resultado": None,
                               "_cancelar": threading.Event(), "expediente": "X"}
    r = c.post("/api/jobs/j-test/detener").json()
    assert api_mod._JOBS["j-test"]["_cancelar"].is_set() and "Deteniendo" in r["mensaje"]
    api_mod._JOBS["j-test"]["estado"] = "error"
    assert "ya había terminado" in c.post("/api/jobs/j-test/detener").json()["mensaje"]
    assert c.post("/api/jobs/nope/detener").status_code == 404
    assert "_cancelar" not in c.get("/api/jobs/j-test").json()          # el evento no viaja al front
