"""
API REST para el front (contrato en docs/SUPERPROMPT_FRONT.md § 5).

Envuelve las acciones de `acciones.py` sin lógica propia: las acciones que
usan el modelo se ejecutan como trabajos en segundo plano (`/api/jobs/{id}`),
en serie por expediente (un lock por expediente evita escrituras
concurrentes sobre los mismos ficheros); el resto responde en síncrono.
Sirve el front compilado (frontend/dist) en `/` con fallback SPA.

    ./revisor web [--puerto 8000]
"""
from __future__ import annotations

import json
import re
import shutil
import threading
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from . import acciones
from .acciones import CONFIG_DEFECTO, Contexto, estado_expediente
from .expediente import ARCHIVOS, Expediente, ExpedienteError
from .formato_md import (COLETILLA_RIESGO_PROPUESTO, _apartado_conclusion, parsear_conclusiones,
                         parsear_informe, render_conclusiones, render_informe)
from .lectores import EXTENSIONES, LecturaError
from .llm import LLMNoDisponible
from .style_checker import StyleChecker, revisar_markdown

RAIZ = Path(__file__).resolve().parent.parent
DIR_EXPEDIENTES = RAIZ / "expedientes"
DIST = RAIZ / "frontend" / "dist"

app = FastAPI(title="Revisor de informes de auditoría interna", version="0.3")

# ---------------------------------------------------------------- utilidades
_LOCKS: dict[str, threading.Lock] = {}
_JOBS: dict[str, dict] = {}
_JOBS_LOCK = threading.Lock()


def _lock(ref: str) -> threading.Lock:
    with _JOBS_LOCK:
        return _LOCKS.setdefault(ref, threading.Lock())


def _exp(ref: str) -> Expediente:
    if not re.fullmatch(r"[A-Za-z0-9._-]+", ref):
        raise HTTPException(400, {"error": "Referencia no válida."})
    try:
        return Expediente(DIR_EXPEDIENTES / ref)
    except ExpedienteError:
        raise HTTPException(404, {"error": f"No existe el expediente {ref}."}) from None


def _ctx(exp: Expediente) -> Contexto:
    try:
        return Contexto(exp, config=CONFIG_DEFECTO)
    except LLMNoDisponible as exc:
        raise HTTPException(503, {"error": str(exc)}) from exc


def _checker() -> StyleChecker:
    return StyleChecker(CONFIG_DEFECTO)


def _job(ref: str, accion: str, fn) -> dict:
    """Lanza `fn()` en un hilo, en serie por expediente. Devuelve {job_id}."""
    job_id = uuid.uuid4().hex[:12]
    _JOBS[job_id] = {"estado": "en_curso", "accion": accion, "mensaje": "", "resultado": None,
                     "expediente": ref, "inicio": datetime.now().isoformat(timespec="seconds")}

    def correr():
        with _lock(ref):
            try:
                acciones.ULTIMO_RESULTADO.clear()
                mensaje = fn()
                _JOBS[job_id].update(estado="ok", mensaje=mensaje or "",
                                     resultado=json.loads(json.dumps(acciones.ULTIMO_RESULTADO, default=str)) or None)
            except (ExpedienteError, LLMNoDisponible, LecturaError, ValueError) as exc:
                _JOBS[job_id].update(estado="error", mensaje=str(exc))
            except Exception as exc:  # noqa: BLE001 — el job no debe dejar al front colgado
                _JOBS[job_id].update(estado="error", mensaje=f"{type(exc).__name__}: {exc}")

    threading.Thread(target=correr, daemon=True).start()
    return {"job_id": job_id}


def _sincrono(fn):
    try:
        return fn()
    except (ExpedienteError, LecturaError, ValueError) as exc:
        raise HTTPException(400, {"error": str(exc)}) from exc
    except LLMNoDisponible as exc:
        raise HTTPException(503, {"error": str(exc)}) from exc


def _estado_json(exp: Expediente) -> dict:
    e = estado_expediente(exp, _checker())
    try:
        from .llm import ClienteLLM
        llm = ClienteLLM().descripcion()
    except Exception as exc:  # noqa: BLE001
        llm = f"no disponible ({exc})"
    p = exp.proyecto
    return {
        "referencia": exp.referencia, "nombre": p.get("nombre", ""), "fecha": p.get("fecha", ""),
        "distribucion": p.get("distribucion", []), "fase": e["fase"], "siguiente": e["siguiente"],
        "contexto": e["contexto"], "papeles": e["papeles"], "conclusiones": e["conclusiones"],
        "informe": ({**e["informe"], "modificado": e["informe"]["modificado"].isoformat(timespec="seconds")}
                    if e["informe"] else None),
        "instrucciones_pendientes": e["instrucciones_pendientes"],
        "ppt": ({"nombre": e["ppt"]["ruta"].name, "desactualizado": bool(e["ppt"]["desactualizado"])} if e["ppt"] else None),
        "archivos": e["archivos"], "llm": llm,
        "modificado": datetime.fromtimestamp(max(f.stat().st_mtime for f in exp.ruta.glob("*") if f.is_file())).isoformat(timespec="seconds"),
    }


@app.exception_handler(HTTPException)
async def _http_error(_request, exc: HTTPException):
    detalle = exc.detail if isinstance(exc.detail, dict) else {"error": str(exc.detail)}
    return JSONResponse(status_code=exc.status_code, content=detalle)


# ---------------------------------------------------------------- expedientes
class NuevoExpediente(BaseModel):
    referencia: str
    nombre: str
    fecha: str = ""
    distribucion: list[str] = []


@app.get("/api/expedientes")
def listar_expedientes():
    salida = []
    for meta in sorted(DIR_EXPEDIENTES.glob("*/expediente.yaml")):
        try:
            salida.append(_estado_json(Expediente(meta.parent)))
        except Exception:  # noqa: BLE001 — un expediente corrupto no tumba la lista
            continue
    return sorted(salida, key=lambda x: x["modificado"], reverse=True)


@app.post("/api/expedientes", status_code=201)
def crear_expediente(datos: NuevoExpediente):
    if not re.fullmatch(r"[A-Za-z0-9._-]+", datos.referencia):
        raise HTTPException(400, {"error": "La referencia solo admite letras, números, punto, guion y guion bajo."})
    try:
        exp = Expediente.crear(DIR_EXPEDIENTES / datos.referencia, datos.nombre, datos.referencia, datos.fecha, datos.distribucion)
    except ExpedienteError as exc:
        raise HTTPException(409, {"error": str(exc)}) from exc
    return _estado_json(exp)


@app.get("/api/expedientes/{ref}")
def estado(ref: str):
    return _estado_json(_exp(ref))


class Confirmacion(BaseModel):
    confirmacion: str = ""


@app.delete("/api/expedientes/{ref}")
def eliminar_expediente(ref: str, c: Confirmacion):
    """Borra el expediente entero (documentos, informe, historial, trazas,
    salidas). Exige escribir la referencia exacta como confirmación."""
    exp = _exp(ref)
    if c.confirmacion.strip() != exp.referencia:
        raise HTTPException(400, {"error": f"Para eliminar el expediente escribe exactamente su referencia: {exp.referencia}"})
    with _lock(ref):
        shutil.rmtree(exp.ruta)
    return {"mensaje": f"Expediente {exp.referencia} eliminado."}


@app.get("/api/jobs/{job_id}")
def job(job_id: str):
    j = _JOBS.get(job_id)
    if not j:
        raise HTTPException(404, {"error": "Trabajo desconocido."})
    return {k: j[k] for k in ("estado", "accion", "mensaje", "resultado")}


# ---------------------------------------------------------------- documentos
def _docs(exp: Expediente) -> dict:
    from .lectores import LECTORES
    return {carpeta: [{"nombre": p.name, "bytes": p.stat().st_size, "lector": LECTORES[p.suffix.lower()][0]}
                      for p in exp.ficheros(carpeta)] for carpeta in ("contexto", "papeles_trabajo")}


@app.get("/api/expedientes/{ref}/documentos")
def documentos(ref: str):
    return _docs(_exp(ref))


@app.post("/api/expedientes/{ref}/documentos/{carpeta}")
async def subir_documentos(ref: str, carpeta: str, ficheros: list[UploadFile] = File(...)):
    exp = _exp(ref)
    if carpeta not in ("contexto", "papeles_trabajo"):
        raise HTTPException(400, {"error": "Carpeta no válida (contexto | papeles_trabajo)."})
    for f in ficheros:
        nombre = Path(f.filename or "documento").name
        if Path(nombre).suffix.lower() not in EXTENSIONES:
            raise HTTPException(400, {"error": f"{nombre}: formato no admitido ({', '.join(EXTENSIONES)})."})
        with open(exp.ruta / carpeta / nombre, "wb") as destino:
            shutil.copyfileobj(f.file, destino)
    return _docs(exp)


@app.delete("/api/expedientes/{ref}/documentos/{carpeta}/{nombre}")
def borrar_documento(ref: str, carpeta: str, nombre: str):
    exp = _exp(ref)
    ruta = exp.ruta / carpeta / Path(nombre).name
    if carpeta not in ("contexto", "papeles_trabajo") or not ruta.exists():
        raise HTTPException(404, {"error": "Documento no encontrado."})
    ruta.unlink()
    return _docs(exp)


# ---------------------------------------------------------------- acciones con modelo (jobs)
class Opciones(BaseModel):
    forzar: bool = False
    secciones: list[str] | None = None
    ids: list[str] | None = None
    id: str | None = None
    notas: str | None = None
    respuestas: dict[str, str] = {}
    auto: bool = False
    formatear: bool = False
    avisos: bool = False
    mensaje: str | None = None
    solo_plan: bool = False
    estado: str = "aprobada"
    fichero: str = "informe"
    objetivo: float = 0.85


@app.post("/api/expedientes/{ref}/acciones/redactar-contexto")
def redactar_contexto(ref: str, o: Opciones):
    exp = _exp(ref); ctx = _ctx(exp)
    return _job(ref, "redactar-contexto", lambda: acciones.accion_redactar_contexto(ctx, secciones=o.secciones or None, forzar=o.forzar))


@app.post("/api/expedientes/{ref}/acciones/extraer")
def extraer(ref: str, o: Opciones):
    exp = _exp(ref); ctx = _ctx(exp)
    return _job(ref, "extraer", lambda: acciones.accion_extraer(ctx, forzar=o.forzar))


@app.post("/api/expedientes/{ref}/acciones/corregir-conclusiones")
def corregir_conclusiones(ref: str, o: Opciones):
    exp = _exp(ref); ctx = _ctx(exp)
    return _job(ref, "corregir-conclusiones", lambda: acciones.accion_corregir_conclusiones(ctx, ids=o.ids or None))


@app.post("/api/expedientes/{ref}/acciones/regenerar")
def regenerar(ref: str, o: Opciones):
    exp = _exp(ref); ctx = _ctx(exp)
    if not o.id:
        raise HTTPException(400, {"error": "Falta el id de la conclusión."})
    if o.notas:
        _actualizar_conclusion(exp, o.id, {"notas": o.notas})
    return _job(ref, f"regenerar-{o.id}", lambda: acciones.accion_regenerar(ctx, o.id))


@app.post("/api/expedientes/{ref}/acciones/recomendar")
def recomendar(ref: str, o: Opciones):
    exp = _exp(ref); ctx = _ctx(exp)
    respuestas = {acciones._normalizar_id(k): v for k, v in o.respuestas.items()}

    def preguntar(c):
        if c["id"] in respuestas and respuestas[c["id"]].strip():
            return respuestas[c["id"]]
        return None if o.auto else False

    return _job(ref, "recomendar", lambda: acciones.accion_recomendar(ctx, ids=o.ids or None, preguntar=preguntar, formatear=o.formatear))


@app.post("/api/expedientes/{ref}/acciones/corregir")
def corregir(ref: str, o: Opciones):
    exp = _exp(ref); ctx = _ctx(exp)
    return _job(ref, "corregir", lambda: acciones.accion_corregir(ctx, incluir_avisos=o.avisos))


@app.post("/api/expedientes/{ref}/acciones/condensar")
def condensar(ref: str, o: Opciones):
    exp = _exp(ref); ctx = _ctx(exp)
    return _job(ref, "condensar", lambda: acciones.accion_condensar(ctx, objetivo=o.objetivo))


@app.post("/api/expedientes/{ref}/acciones/cambio")
def cambio(ref: str, o: Opciones):
    exp = _exp(ref); ctx = _ctx(exp)
    if not (o.mensaje or "").strip():
        raise HTTPException(400, {"error": "Mensaje vacío."})
    return _job(ref, "cambio", lambda: acciones.accion_aplicar_cambios(ctx, solo_plan=o.solo_plan, instrucciones=o.mensaje, origen="chat"))


@app.post("/api/expedientes/{ref}/acciones/aplicar-cambios")
def aplicar_cambios(ref: str, o: Opciones):
    exp = _exp(ref); ctx = _ctx(exp)
    return _job(ref, "aplicar-cambios", lambda: acciones.accion_aplicar_cambios(ctx, solo_plan=o.solo_plan))


@app.post("/api/expedientes/{ref}/acciones/reunion")
async def reunion(ref: str, transcripcion: UploadFile = File(...), aplicar: bool = Form(False)):
    exp = _exp(ref); ctx = _ctx(exp)
    nombre = Path(transcripcion.filename or "transcripcion.txt").name
    destino = exp.ruta / "reuniones" / f"{datetime.now():%Y-%m-%d_%H%M}_{nombre}"
    with open(destino, "wb") as f:
        shutil.copyfileobj(transcripcion.file, f)
    return _job(ref, "reunion", lambda: acciones.accion_reunion(ctx, destino, aplicar=aplicar))


# ---------------------------------------------------------------- acciones síncronas
@app.post("/api/expedientes/{ref}/acciones/aprobar")
def aprobar(ref: str, o: Opciones):
    exp = _exp(ref)
    return {"mensaje": _sincrono(lambda: acciones.accion_aprobar(exp, o.ids or ["todas"], estado=o.estado))}


@app.post("/api/expedientes/{ref}/acciones/revisar-conclusiones")
def revisar_conclusiones(ref: str):
    exp = _exp(ref)
    checker = _checker()
    hallazgos = []
    for c in _sincrono(lambda: acciones._leer_conclusiones(exp)):
        if c["estado"] == "descartada":
            continue
        for h in checker.revisar_conclusion(acciones._campos_conc(c)).to_dict()["hallazgos"]:
            hallazgos.append({"id": c["id"], **h})
    return {"hallazgos": hallazgos}


@app.post("/api/expedientes/{ref}/acciones/redactar-conclusiones")
def redactar_conclusiones(ref: str):
    exp = _exp(ref); ctx = _ctx(exp)
    return {"mensaje": _sincrono(lambda: acciones.accion_redactar_conclusiones(ctx))}


@app.post("/api/expedientes/{ref}/acciones/revisar")
def revisar(ref: str):
    exp = _exp(ref)
    texto = exp.leer("informe")
    if not texto:
        raise HTTPException(400, {"error": "No hay 02_informe.md."})
    hall = revisar_markdown(_checker(), texto)
    exp.anexar_registro("revision", f"\n## Revisión del informe — {datetime.now():%Y-%m-%d %H:%M} (web)\n\n"
                        + acciones._formato_hallazgos(hall) + "\n")
    return {"hallazgos": hall, "errores": sum(h["severidad"] == "error" for h in hall),
            "avisos": sum(h["severidad"] == "aviso" for h in hall)}


@app.post("/api/expedientes/{ref}/acciones/deshacer")
def deshacer(ref: str, o: Opciones):
    exp = _exp(ref)
    return {"mensaje": _sincrono(lambda: acciones.accion_deshacer(exp, o.fichero))}


@app.get("/api/expedientes/{ref}/diff")
def diff(ref: str, fichero: str = "informe"):
    exp = _exp(ref)
    versiones = exp.historial(fichero)
    if not versiones:
        return {"diff": "", "contra": None}
    antes = versiones[-1].read_text(encoding="utf-8")
    return {"diff": acciones.diff_texto(antes, exp.leer(fichero), ARCHIVOS[fichero]), "contra": versiones[-1].name}


@app.post("/api/expedientes/{ref}/acciones/ppt")
def ppt(ref: str):
    exp = _exp(ref)
    _sincrono(lambda: acciones.accion_ppt(exp))
    return {"nombre": exp.ruta_ppt().name, "url": f"/api/expedientes/{ref}/salidas/{exp.ruta_ppt().name}"}


@app.post("/api/expedientes/{ref}/acciones/archivar")
def archivar(ref: str):
    exp = _exp(ref)
    _sincrono(lambda: acciones.accion_archivar(exp))
    zips = sorted(exp.ruta.glob("*_archivo_*.zip"))
    return {"nombre": zips[-1].name, "url": f"/api/expedientes/{ref}/salidas/{zips[-1].name}"}


@app.get("/api/expedientes/{ref}/salidas/{nombre}")
def descargar(ref: str, nombre: str):
    exp = _exp(ref)
    nombre = Path(nombre).name
    for ruta in (exp.ruta / "salidas" / nombre, exp.ruta / nombre):
        if ruta.exists() and ruta.is_file():
            return FileResponse(ruta, filename=nombre)
    raise HTTPException(404, {"error": "Fichero no encontrado."})


# ---------------------------------------------------------------- conclusiones e informe
class Texto(BaseModel):
    markdown: str | None = None
    texto: str | None = None


def _actualizar_conclusion(exp: Expediente, ident: str, campos: dict) -> dict:
    conclusiones = acciones._leer_conclusiones(exp)
    ident = acciones._normalizar_id(ident)
    c = next((x for x in conclusiones if x["id"] == ident), None)
    if c is None:
        raise HTTPException(404, {"error": f"No existe {ident}."})
    permitidos = {"titulo", "tipo", "estado", "prueba", "nivel_riesgo", "riesgo_propuesto", "area", "responsable", "plazo",
                  "referencia_recomendacion", "fuente", "incidencia", "causa_raiz", "como_se_ha_llegado", "consecuencias",
                  "recomendacion", "notas"}
    for k, v in campos.items():
        if k in permitidos and v is not None:
            c[k] = v
    if c.get("estado") == "aprobada":
        c["riesgo_propuesto"] = False  # el auditor valida el nivel al aprobar
    exp.escribir("conclusiones", render_conclusiones(conclusiones, exp.proyecto), f"web-{ident}")
    return c


@app.get("/api/expedientes/{ref}/conclusiones")
def conclusiones(ref: str):
    exp = _exp(ref)
    md = exp.leer("conclusiones")
    return {"markdown": md, "conclusiones": parsear_conclusiones(md) if md else []}


@app.put("/api/expedientes/{ref}/conclusiones")
def guardar_conclusiones(ref: str, t: Texto):
    exp = _exp(ref)
    if t.markdown is None:
        raise HTTPException(400, {"error": "Falta markdown."})
    exp.escribir("conclusiones", t.markdown, "web")
    return {"conclusiones": parsear_conclusiones(t.markdown)}


@app.put("/api/expedientes/{ref}/conclusiones/{ident}")
def guardar_conclusion(ref: str, ident: str, campos: dict[str, Any]):
    return _sincrono(lambda: _actualizar_conclusion(_exp(ref), ident, campos))


@app.get("/api/expedientes/{ref}/informe")
def informe(ref: str):
    exp = _exp(ref)
    md = exp.leer("informe")
    datos = parsear_informe(md) if md else {"introduccion": "", "resumen_ejecutivo": "", "evaluacion_global": "", "conclusiones": [], "sugerencias": []}
    apartados = [
        {"id": "introduccion", "tipo": "introduccion", "titulo": "Introducción", "markdown": datos["introduccion"], "numero": 0, "nivel_riesgo": ""},
        {"id": "resumen", "tipo": "resumen", "titulo": "Resumen ejecutivo", "markdown": datos["resumen_ejecutivo"], "numero": 0, "nivel_riesgo": ""},
    ]
    for i, c in enumerate(datos["conclusiones"], 1):
        apartados.append({"id": f"c{i}", "tipo": "conclusion", "titulo": c["titulo"], "numero": i, "nivel_riesgo": c["nivel_riesgo"],
                          "markdown": _apartado_conclusion(c, i, es_sugerencia=False)})
    for i, s in enumerate(datos["sugerencias"], 1):
        apartados.append({"id": f"s{i}", "tipo": "sugerencia", "titulo": s["titulo"], "numero": i, "nivel_riesgo": s["nivel_riesgo"] or "Bajo",
                          "markdown": _apartado_conclusion(s, i, es_sugerencia=True)})
    return {"markdown": md, "apartados": apartados, "evaluacion_global": datos["evaluacion_global"],
            "conclusiones": datos["conclusiones"], "sugerencias": datos["sugerencias"]}


class InformeEdicion(BaseModel):
    markdown: str | None = None
    introduccion: str | None = None
    resumen_ejecutivo: str | None = None
    evaluacion_global: str | None = None


@app.put("/api/expedientes/{ref}/informe")
def guardar_informe(ref: str, t: InformeEdicion):
    exp = _exp(ref)
    if t.markdown is not None:
        exp.escribir("informe", t.markdown, "web")
    else:
        datos = parsear_informe(exp.leer("informe")) if exp.existe("informe") else {"introduccion": "", "resumen_ejecutivo": "", "evaluacion_global": "", "conclusiones": [], "sugerencias": []}
        for k in ("introduccion", "resumen_ejecutivo", "evaluacion_global"):
            v = getattr(t, k)
            if v is not None:
                datos[k] = v
        exp.escribir("informe", render_informe(datos, exp.proyecto), "web")
    return informe(ref)


@app.get("/api/expedientes/{ref}/instrucciones")
def instrucciones(ref: str):
    return {"texto": _exp(ref).instrucciones_pendientes()}


@app.put("/api/expedientes/{ref}/instrucciones")
def guardar_instrucciones(ref: str, t: Texto):
    exp = _exp(ref)
    from .expediente import PLANTILLA_INSTRUCCIONES
    exp.escribir("instrucciones", PLANTILLA_INSTRUCCIONES.format(referencia=exp.referencia) + (t.texto or "").strip() + "\n", "web")
    return {"texto": exp.instrucciones_pendientes()}


@app.get("/api/expedientes/{ref}/historial")
def historial(ref: str):
    exp = _exp(ref)
    salida = []
    for clave in ("informe", "conclusiones", "instrucciones"):
        for v in exp.historial(clave):
            m = re.match(r"^(\d{4}-\d{2}-\d{2}T\d{2}-\d{2}-\d{2})_[^_]+_(.*)\.md$", v.name)
            fecha = m.group(1).replace("T", " ").replace("-", ":", 0) if m else ""
            salida.append({"fichero": clave, "nombre": v.name, "fecha": fecha[:10] + " " + fecha[11:].replace("-", ":") if m else "",
                           "motivo": m.group(2) if m else ""})
    return sorted(salida, key=lambda x: x["nombre"], reverse=True)


@app.get("/api/expedientes/{ref}/cambios")
def cambios(ref: str):
    return {"markdown": _exp(ref).leer("cambios")}


@app.get("/api/expedientes/{ref}/reuniones")
def reuniones(ref: str):
    exp = _exp(ref)
    return [{"nombre": p.name, "fecha": p.name[:16].replace("_", " "), "markdown": p.read_text(encoding="utf-8")}
            for p in sorted((exp.ruta / "reuniones").glob("*.md"), reverse=True)]


@app.get("/api/expedientes/{ref}/trazas")
def trazas(ref: str):
    exp = _exp(ref)
    salida = []
    for p in sorted((exp.ruta / "trazas").glob("*.json"), reverse=True):
        try:
            d = json.loads(p.read_text(encoding="utf-8"))
        except ValueError:
            continue
        usage = d.get("usage") or {}
        salida.append({"nombre": p.name, "fecha": d.get("fecha", ""), "accion": p.stem.split("_", 1)[-1],
                       "modelo": d.get("modelo", ""), "error": d.get("error"),
                       "tokens": {"prompt": usage.get("prompt_tokens"), "completion": usage.get("completion_tokens")}})
    return salida


@app.get("/api/expedientes/{ref}/trazas/{nombre}")
def traza(ref: str, nombre: str):
    exp = _exp(ref)
    ruta = exp.ruta / "trazas" / Path(nombre).name
    if not ruta.exists():
        raise HTTPException(404, {"error": "Traza no encontrada."})
    return json.loads(ruta.read_text(encoding="utf-8"))


@app.get("/api/config/estilo")
def config_estilo():
    return {"yaml": (RAIZ / "config" / "estilo.yaml").read_text(encoding="utf-8"),
            "coletilla_riesgo": COLETILLA_RIESGO_PROPUESTO}


# ---------------------------------------------------------------- front estático (SPA)
if DIST.exists():
    app.mount("/assets", StaticFiles(directory=DIST / "assets"), name="assets")

    @app.get("/{ruta:path}", include_in_schema=False)
    def spa(ruta: str):
        candidato = DIST / ruta
        if ruta and candidato.is_file():
            return FileResponse(candidato)
        return FileResponse(DIST / "index.html")
