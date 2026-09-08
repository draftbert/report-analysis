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
import tempfile
import threading
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any

from fastapi import Cookie, FastAPI, File, Form, HTTPException, Response, UploadFile
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from . import __version__, acciones
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
        raise HTTPException(404, {"error": f"No existe el informe {ref}."}) from None


def _ctx(exp: Expediente) -> Contexto:
    try:
        return Contexto(exp, config=CONFIG_DEFECTO)
    except LLMNoDisponible as exc:
        raise HTTPException(503, {"error": str(exc)}) from exc


def _checker() -> StyleChecker:
    return StyleChecker(CONFIG_DEFECTO)


def _job(ref: str, accion: str, fn, ctx=None) -> dict:
    """Lanza `fn()` en un hilo, en serie por expediente. Devuelve {job_id}. Si se pasa
    `ctx`, su `informar(texto, pct)` va actualizando `progreso`/`progreso_pct` del job."""
    job_id = uuid.uuid4().hex[:12]
    _JOBS[job_id] = {"estado": "en_curso", "accion": accion, "mensaje": "", "resultado": None,
                     "progreso": "", "progreso_pct": None,
                     "expediente": ref, "inicio": datetime.now().isoformat(timespec="seconds")}
    if ctx is not None:
        ctx.informar = lambda texto, pct=None, partes=None: _JOBS[job_id].update(
            progreso=texto, progreso_pct=pct, progreso_partes=partes)

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


class Credenciales(BaseModel):
    password: str = ""


@app.post("/api/acceso/login")
def login(credenciales: Credenciales, response: Response):
    """Inicio de sesión de la interfaz (ver audit_agent/acceso.py). nginx lo expone sin sesión."""
    from . import acceso
    if not acceso.password_correcta(credenciales.password):
        raise HTTPException(401, {"error": "Contraseña incorrecta."})
    response.status_code = 204
    response.set_cookie("sesion", acceso.crear_token(), max_age=acceso.DURACION_SESION_S,
                        httponly=True, samesite="lax", path="/")
    return response


@app.get("/api/acceso/verificar")
def verificar(sesion: str | None = Cookie(default=None)):
    """Lo consulta nginx (auth_request) en cada petición: 204 con cookie válida, 401 si no."""
    from . import acceso
    if not acceso.validar_token(sesion):
        raise HTTPException(401, {"error": "Sesión no válida o caducada."})
    return Response(status_code=204)


@app.post("/api/acceso/logout")
def logout(response: Response):
    response.status_code = 204
    response.delete_cookie("sesion", path="/")
    return response


@app.get("/api/salud")
def salud():
    """Comprobación de vida para Docker/monitorización: versión y nº de expedientes."""
    return {"estado": "ok", "version": __version__,
            "expedientes": len(list(DIR_EXPEDIENTES.glob("*/expediente.yaml"))) if DIR_EXPEDIENTES.exists() else 0}


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
        raise HTTPException(400, {"error": f"Para eliminar el informe escribe exactamente su referencia: {exp.referencia}"})
    with _lock(ref):
        shutil.rmtree(exp.ruta)
    return {"mensaje": f"Informe {exp.referencia} eliminado."}


@app.get("/api/jobs/{job_id}")
def job(job_id: str):
    j = _JOBS.get(job_id)
    if not j:
        raise HTTPException(404, {"error": "Trabajo desconocido."})
    return {k: j.get(k) for k in ("estado", "accion", "mensaje", "resultado", "progreso", "progreso_pct", "progreso_partes")}


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
async def reunion(ref: str, transcripcion: UploadFile = File(...), aplicar: bool = Form(False),
                  repetir: bool = Form(False),
                  hablantes: list[str] = Form(default=[]), muestras: list[UploadFile] = File(default=[])):
    """Transcripción (.txt/.docx/.vtt) o audio (.mp3/.wav/.m4a/.webm…). Con audio,
    `hablantes` (máx. 4) y sus `muestras` de voz (opcionales, emparejadas por orden;
    solo se usan para la diarización si TODOS los hablantes traen muestra)."""
    exp = _exp(ref); ctx = _ctx(exp)
    nombre = Path(transcripcion.filename or "transcripcion.txt").name
    destino = exp.ruta / "reuniones" / f"{datetime.now():%Y-%m-%d_%H%M}_{nombre}"
    with open(destino, "wb") as f:
        shutil.copyfileobj(transcripcion.file, f)
    nombres = [h.strip() for h in hablantes if h.strip()]
    if len(nombres) > 4:
        raise HTTPException(400, {"error": "Máximo 4 hablantes conocidos."})
    tmp = None
    pares: list[tuple[str, str | None]] = [(n, None) for n in nombres]
    if nombres and muestras:
        tmp = Path(tempfile.mkdtemp(prefix="muestras_voz_"))
        pares = []
        for i, n in enumerate(nombres):
            ruta_m = None
            if i < len(muestras) and (muestras[i].filename or "").strip():
                ruta_m = tmp / f"{i}_{Path(muestras[i].filename).name}"
                with open(ruta_m, "wb") as f:
                    shutil.copyfileobj(muestras[i].file, f)
            pares.append((n, str(ruta_m) if ruta_m else None))

    def tarea():
        try:
            return acciones.accion_reunion(ctx, destino, aplicar=aplicar, hablantes=pares or None, repetir=repetir)
        except ExpedienteError:
            if destino.suffix.lower() not in acciones.EXTENSIONES_REUNION_AV:
                usados = {a for d in acciones._huellas(exp).values() for a in (d.get("artefactos") or [])}
                if destino.name not in usados:           # p. ej. transcripción repetida: no dejar copia huérfana
                    destino.unlink(missing_ok=True)      # (pero sin tocar la de una reunión ya registrada)
            raise
        finally:
            if tmp is not None:
                shutil.rmtree(tmp, ignore_errors=True)   # las muestras de voz no se conservan
            if destino.suffix.lower() in acciones.EXTENSIONES_REUNION_AV:
                destino.unlink(missing_ok=True)          # el audio/vídeo subido no se conserva (pesa cientos de MB);
                                                         # quedan la transcripción y el acta en reuniones/

    return _job(ref, "reunion", tarea, ctx=ctx)


@app.post("/api/expedientes/{ref}/acciones/transcribir")
async def transcribir(ref: str, fichero: UploadFile = File(...), umbral: float = Form(10.0), forzar: bool = Form(False),
                      repetir: bool = Form(False)):
    """Flujo con identificación de hablantes: transcribe con diarización y deja clips +
    hablantes por nombrar (GET /transcripcion). NO genera acta ni toca instrucciones."""
    from . import transcripcion as tr
    exp = _exp(ref); ctx = _ctx(exp)
    nombre = Path(fichero.filename or "reunion").name
    if Path(nombre).suffix.lower() not in tr.EXTENSIONES_AV:
        raise HTTPException(400, {"error": f"{nombre}: no es audio/vídeo admitido."})
    tmp = Path(tempfile.mkdtemp(prefix="transcribir_web_")) / nombre
    with open(tmp, "wb") as f:
        shutil.copyfileobj(fichero.file, f)

    def tarea():
        try:
            mensaje = tr.accion_transcribir(exp, tmp, umbral_s=umbral, forzar=forzar, informar=ctx.informar, repetir=repetir)
            acciones.ULTIMO_RESULTADO.update(tr.estado_transcripcion(exp))
            return mensaje
        finally:
            shutil.rmtree(tmp.parent, ignore_errors=True)   # el fichero subido no se conserva (queda el normalizado)

    return _job(ref, "transcribir", tarea, ctx=ctx)


@app.get("/api/expedientes/{ref}/transcripcion")
def transcripcion_estado(ref: str):
    from . import transcripcion as tr
    return tr.estado_transcripcion(_exp(ref))


class Etiquetado(BaseModel):
    asignaciones: dict[str, dict] = {}
    guardar_voces: list[str] = []


@app.put("/api/expedientes/{ref}/transcripcion/borrador")
def transcripcion_borrador(ref: str, o: Etiquetado):
    """Guarda el borrador del etiquetado (nombres/acciones en hablantes.md y las casillas
    de «guardar voz» en meta.json) sin aplicarlo: la web lo autoguarda para que un
    refresco del navegador no pierda el trabajo a medias. Aquí `guardar_voces` son IDs."""
    from . import transcripcion as tr
    exp = _exp(ref)
    tr.aplicar_asignaciones(exp, o.asignaciones, guardar_voces=o.guardar_voces)
    return tr.estado_transcripcion(exp)


@app.post("/api/expedientes/{ref}/acciones/etiquetar")
def etiquetar(ref: str, o: Etiquetado):
    """Aplica nombres/fusiones/ignorados en local, guarda la transcripción etiquetada en
    reuniones/ y la analiza como una reunión (acta + instrucciones). Job: el análisis usa
    el modelo; el `resultado` lleva el acta (si la hubo) y el estado de la transcripción."""
    from . import transcripcion as tr
    exp = _exp(ref); ctx = _ctx(exp)
    tr.aplicar_asignaciones(exp, o.asignaciones)
    deseadas = set(o.guardar_voces)

    def tarea():
        mensaje = tr.accion_etiquetar(exp, preguntar_guardar=lambda nombre, clip: nombre in deseadas, ctx=ctx)
        acciones.ULTIMO_RESULTADO.update(tr.estado_transcripcion(exp))
        return mensaje

    return _job(ref, "etiquetar", tarea, ctx=ctx)


@app.get("/api/expedientes/{ref}/audio/hablantes/{fichero}")
def clip_hablante(ref: str, fichero: str):
    from . import transcripcion as tr
    exp = _exp(ref)
    ruta = tr.dir_audio(exp) / "hablantes" / Path(fichero).name
    if not ruta.is_file() or ruta.suffix.lower() != ".wav":
        raise HTTPException(404, {"error": "No existe ese clip."})
    return FileResponse(ruta, media_type="audio/wav")


@app.delete("/api/expedientes/{ref}/voces/{nombre}")
def borrar_voz(ref: str, nombre: str):
    from . import transcripcion as tr
    exp = _exp(ref)
    tr.accion_voces(exp, borrar=[nombre])
    return tr.estado_transcripcion(exp)


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


def _clave_reunion(nombre: str) -> str:
    """Clave de agrupación de un fichero de reuniones/: sin prefijos de fecha ni sufijo
    _transcripcion, en minúsculas. Acta y transcripción del mismo origen comparten raíz."""
    s = Path(nombre).stem
    while re.match(r"^\d{4}-\d{2}-\d{2}_\d{4}_", s):
        s = s[16:]
    s = re.sub(r"_transcripcion$", "", s, flags=re.I)
    return s.lower() or Path(nombre).stem.lower()


def _listar_reuniones(exp: Expediente) -> list[dict]:
    """Reuniones agrupadas por origen, más recientes primero: cada ítem junta el acta
    (con su estructura .json si existe: la web la pinta como tarjetas) y sus
    transcripciones. Ficheros de origen distinto = ítems distintos."""
    items: list[dict] = []
    for p in sorted((exp.ruta / "reuniones").glob("*"), reverse=True):
        ext = p.suffix.lower()
        if ext == ".md":
            tipo, contenido = "acta", p.read_text(encoding="utf-8")
        elif ext in (".txt", ".vtt"):
            tipo, contenido = "transcripcion", p.read_text(encoding="utf-8", errors="replace")
        elif ext == ".docx":
            tipo, contenido = "transcripcion", "_(documento Word)_"
        else:
            continue
        clave = _clave_reunion(p.name)
        item = next((i for i in items if i["_clave"].startswith(clave) or clave.startswith(i["_clave"])), None)
        if item is None:
            item = {"_clave": clave, "origen": clave, "fecha": p.name[:16].replace("_", " "), "actas": [], "transcripciones": []}
            items.append(item)
        item["_clave"] = min(item["_clave"], clave, key=len)
        item["origen"] = item["_clave"]
        if tipo == "acta":
            datos = None
            if p.with_suffix(".json").exists():
                try:
                    datos = json.loads(p.with_suffix(".json").read_text(encoding="utf-8"))
                except (OSError, ValueError):
                    datos = None
            item["actas"].append({"nombre": p.name, "fecha": p.name[:16].replace("_", " "), "markdown": contenido, "datos": datos})
        else:
            item["transcripciones"].append({"nombre": p.name, "fecha": p.name[:16].replace("_", " "), "markdown": contenido})
    for i in items:
        i.pop("_clave")
    return items


@app.get("/api/expedientes/{ref}/reuniones")
def reuniones(ref: str):
    return _listar_reuniones(_exp(ref))


@app.delete("/api/expedientes/{ref}/reuniones/{nombre}")
def borrar_reunion(ref: str, nombre: str):
    """Borra una transcripción o un acta de reuniones/ y devuelve el listado actualizado."""
    exp = _exp(ref)
    ruta = exp.ruta / "reuniones" / Path(nombre).name   # Path(...).name: sin rutas relativas
    if not ruta.is_file():
        raise HTTPException(404, {"error": f"No existe {Path(nombre).name} en reuniones/."})
    ruta.unlink()
    if ruta.suffix.lower() == ".md":
        ruta.with_suffix(".json").unlink(missing_ok=True)   # la estructura del acta va con su .md
    acciones.olvidar_huellas_de(exp, ruta.name)             # y su huella deja de bloquear una re-subida
    return _listar_reuniones(exp)


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
