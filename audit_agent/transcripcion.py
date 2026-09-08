"""
Transcripción de reuniones con identificación de hablantes (KAIA /api/v2/transcribe/upload).

Hallazgos de la exploración contra la API real (2026-09-04) que fijan el diseño:
- Autenticación: mismo bearer OAuth2 que `/agent/invoke`; sin token → 401.
- `segments` = {id, start, end, speaker, text}; tiempos float en segundos POR LLAMADA
  (al trocear hay que sumar el offset de cada parte).
- Sin hablantes conocidos, `speaker` son letras «A», «B», … por orden de aparición.
  Con `known_speaker_names`, esos salen nombrados y LOS GENÉRICOS SE RENUMERAN desde
  «A»: lo genérico se define como «etiqueta que no está entre los nombres enviados»,
  nunca por su forma.
- El endpoint acepta mp4 con pista de vídeo, pero SIEMPRE se extrae el audio con
  ffmpeg antes de subir (menos bytes de un fichero confidencial). Nunca se usa la
  variante por URL pública.
- Límites: el gateway corta a ~240 s de proceso → partes de KAIA_TRANSCRIBE_MAX_S
  (300 s; ~90 s de proceso) y, si una parte da 504 reproducible (tramo denso), se
  transcribe en dos mitades; el modelo admite 1.400 s/llamada; una parte de <1 s da
  400 «file might be corrupted» (la última parte absorbe la cola). 422 solo por
  validación de la petición; fichero no-audio → 400 «Unsupported file format».

Las MUESTRAS DE VOZ son material temporal de CADA expediente: viven en
{expediente}/entrada/audio/voces/, no existen bibliotecas globales, no se comparten
entre expedientes y `archivar` las destruye (dejando constancia en el manifiesto).
"""
from __future__ import annotations

import json
import math
import os
import re
import shutil
import subprocess
import tempfile
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path

import yaml

from .expediente import Expediente, ExpedienteError
from .kaia_client import EXTENSIONES_AUDIO, EXTENSIONES_VIDEO, transcribir_audio  # noqa: F401  (mockeable en tests)

EXTENSIONES_AV = tuple(dict.fromkeys(EXTENSIONES_AUDIO + EXTENSIONES_VIDEO))
UMBRAL_HABLANTE_S = 10.0     # habla total mínima para considerar relevante a un hablante
MAX_VOCES_ENVIADAS = 4       # límite de known_speakers de la API
CLIP_MAX_S = 9.9             # las referencias de known_speakers admiten 2-10 s: apurar sin pasarse


# ============================================================ ffmpeg
def duracion_audio(ruta: Path) -> float | None:
    """Duración en segundos vía ffprobe; None si no se puede medir."""
    if not shutil.which("ffprobe"):
        return None
    try:
        p = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(ruta)],
                           capture_output=True, text=True, timeout=120)
        return float(p.stdout.strip()) if p.returncode == 0 and p.stdout.strip() else None
    except (ValueError, subprocess.SubprocessError):
        return None


def _ffmpeg(argumentos: list[str], salida: Path, contexto: str) -> Path:
    proc = subprocess.run(["ffmpeg", "-y", *argumentos, str(salida)], capture_output=True, text=True, timeout=1800)
    if proc.returncode != 0 or not salida.exists() or salida.stat().st_size == 0:
        detalle = (proc.stderr or "").strip().splitlines()[-1:] or ["ffmpeg falló"]
        raise ExpedienteError(f"{contexto}: {detalle[0][:200]}")
    return salida


def normalizar_audio(origen: Path, destino: Path) -> Path:
    """Audio o vídeo -> mp3 mono 16 kHz 48 kbps (~20 MB/hora): lo que se sube a KAIA
    y de donde se cortan los clips (los timestamps de la API cuadran con él).
    Si origen y destino son el mismo fichero (retranscribir la copia normalizada del
    expediente), no se toca: ffmpeg escribiría sobre su propia fuente y la corrompería."""
    if origen.resolve() == destino.resolve():
        return destino
    if not shutil.which("ffmpeg"):
        raise ExpedienteError("Hace falta ffmpeg para preparar el audio (extraer pista de vídeo / normalizar).")
    destino.parent.mkdir(parents=True, exist_ok=True)
    return _ffmpeg(["-i", str(origen), "-vn", "-ac", "1", "-ar", "16000", "-b:a", "48k"],
                   destino, f"No se ha podido preparar el audio de {origen.name}")


def preparar_audio(ruta: Path, destino_dir: Path) -> list[tuple[Path, float]]:
    """Lista [(fichero, offset_s)] listo para /transcribe: de un vídeo se extrae la
    pista y, si dura más que KAIA_TRANSCRIBE_MAX_S (+margen), se trocea; la última
    parte absorbe la cola para no generar partes de centésimas (dan 400)."""
    maximo = int(os.environ.get("KAIA_TRANSCRIBE_MAX_S") or 300)
    margen = min(5, maximo)
    es_video = ruta.suffix.lower() in EXTENSIONES_VIDEO
    duracion = duracion_audio(ruta)
    trocear = duracion is not None and duracion > maximo + margen
    if not es_video and not trocear:
        return [(ruta, 0.0)]
    if not shutil.which("ffmpeg"):
        if es_video and ruta.suffix.lower() in EXTENSIONES_AUDIO and not trocear:
            return [(ruta, 0.0)]      # .mp4/.webm cortos: el servicio acepta el contenedor
        raise ExpedienteError(f"{ruta.name}: hace falta ffmpeg para " +
                              (f"trocear un audio de más de {maximo} s." if trocear else f"transcribir vídeo {ruta.suffix}."))
    partes = max(1, math.ceil((duracion or 1) / maximo)) if trocear else 1
    if partes > 1 and (duracion - (partes - 1) * maximo) < margen:
        partes -= 1
    salidas = []
    for i in range(partes):
        salida = destino_dir / f"{ruta.stem[:40]}_audio_{i + 1:02d}.mp3"
        corte = ["-ss", str(i * maximo)] + ([] if i == partes - 1 else ["-t", str(maximo)])
        _ffmpeg([*corte, "-i", str(ruta), "-vn", "-ac", "1", "-ar", "16000", "-b:a", "48k"],
                salida, f"No se ha podido extraer el audio de {ruta.name}")
        salidas.append((salida, float(i * maximo)))
    return salidas


def en_mitades(parte: Path, destino_dir: Path, hablantes) -> tuple[dict, float]:
    """Último recurso para una parte con 504 reproducible (tramo denso que excede los
    ~240 s del gateway): dos mitades transcritas por separado y combinadas.
    Devuelve (respuesta_combinada, offset_de_la_segunda_mitad)."""
    dur = duracion_audio(parte)
    if not shutil.which("ffmpeg") or not dur or dur < 60:
        raise ExpedienteError("no se puede partir en mitades (sin ffmpeg o parte demasiado corta)")
    mitades = []
    for k, (ini, fin) in enumerate(((0, dur / 2), (dur / 2, None)), 1):
        salida = destino_dir / f"{parte.stem}_{'ab'[k - 1]}.mp3"
        corte = ["-ss", str(ini)] + ([] if fin is None else ["-t", str(fin - ini)])
        _ffmpeg([*corte, "-i", str(parte), "-vn", "-ac", "1", "-ar", "16000", "-b:a", "48k"],
                salida, "ffmpeg no pudo partir la parte")
        mitades.append(salida)
    r1, r2 = (transcribir_audio(m, hablantes) for m in mitades)
    desplazados = [dict(s, start=(s.get("start") or 0) + dur / 2, end=(s.get("end") or 0) + dur / 2)
                   for s in (r2.get("segments") or [])]
    return ({"model": r1.get("model") or r2.get("model"), "provider": r1.get("provider"),
             "duration": (r1.get("duration") or 0) + (r2.get("duration") or 0),
             "segments": (r1.get("segments") or []) + desplazados,
             "text": ((r1.get("text") or "") + "\n" + (r2.get("text") or "")).strip()}, dur / 2)


def _referencias_de_parte(respuesta: dict, fichero_parte: Path, destino_dir: Path,
                          conocidos: set[str], maximo: int, numero_inicial: int = 1) -> list[tuple[str, str]]:
    """Con audio troceado, las letras de hablante NO son estables entre llamadas (el «A»
    de una parte puede ser otra persona en la siguiente). De la primera parte se corta
    una muestra de cada voz genérica detectada (≥2 s de tramo limpio) y se devuelven
    como known_speakers sintéticos «HABLANTE_N» para el resto de partes; los segments
    de esta respuesta se renombran a esos mismos nombres."""
    segs = [{"speaker": (s.get("speaker") or "").strip(), "start": s.get("start") or 0,
             "end": s.get("end") or 0, "text": (s.get("text") or "").strip()}
            for s in respuesta.get("segments") or []]
    genericos = _por_hablante([s for s in segs if s["speaker"] and s["speaker"] not in conocidos])
    refs: list[tuple[str, str]] = []
    renombres: dict[str, str] = {}
    for etiqueta, g in sorted(genericos.items(), key=lambda kv: -kv[1]["segundos"]):
        if len(refs) >= maximo:
            break
        ini, dur = _segmento_para_clip(g["segmentos"], segs)
        if dur < 2.0:
            continue                       # sin 2 s limpios no hay referencia fiable
        nombre = f"HABLANTE_{numero_inicial + len(refs)}"
        clip = destino_dir / f"ref_{nombre}.wav"
        _ffmpeg(["-ss", str(ini), "-t", str(dur), "-i", str(fichero_parte), "-ac", "1", "-ar", "16000"],
                clip, f"No se ha podido cortar la referencia de {etiqueta}")
        refs.append((nombre, str(clip)))
        renombres[etiqueta] = nombre
    for s in respuesta.get("segments") or []:
        quien = (s.get("speaker") or "").strip()
        if quien in renombres:
            s["speaker"] = renombres[quien]
    return refs


def _aislar_letras_sueltas(respuestas: list, conocidos: set[str], desde: int) -> None:
    """Etiquetas genéricas que quedaron sin referencia en partes posteriores: se les
    añade el número de parte («A·p3») porque no son comparables entre llamadas."""
    for i, r in enumerate(respuestas):
        if i < desde or not r:
            continue
        for s in r.get("segments") or []:
            quien = (s.get("speaker") or "").strip()
            if quien and quien not in conocidos:
                s["speaker"] = f"{quien}·p{i + 1}"


def transcribir_en_partes(ruta: Path, hablantes, destino_dir: Path, informar=None):
    """Transcribe un audio/vídeo por partes (2 en paralelo, un reintento por parte y
    mitades como último recurso). Con varias partes, la primera se transcribe sola y
    sus voces se pasan como referencias al resto para que la identidad de cada
    hablante sea estable en toda la reunión. Devuelve (respuestas, offsets, errores):
    - respuestas[i]: dict de la API o None si la parte falló del todo;
    - offsets[i]: segundos que hay que sumar a los tiempos de esa parte;
    - errores: {índice: motivo}. Lanza ExpedienteError solo si fallan TODAS."""
    informar = informar or (lambda texto, pct=None, partes=None: None)
    pares = preparar_audio(ruta, destino_dir)
    partes = [p for p, _ in pares]
    offsets = [o for _, o in pares]
    estados = ["pendiente"] * len(partes)
    errores: dict[int, str] = {}

    def _publicar():
        hechas = sum(e == "hecha" for e in estados)
        informar(f"Transcritas {hechas} de {len(partes)} partes…" if len(partes) > 1 else "Transcribiendo el audio…",
                 15 + round(65 * hechas / len(partes)), partes=list(estados))

    def _una(i: int, refs):
        estados[i] = "en_curso"
        _publicar()
        ultimo = ""
        for intento in (1, 2):
            try:
                r = transcribir_audio(partes[i], refs)
                estados[i] = "hecha"
                _publicar()
                return r
            except Exception as exc:  # noqa: BLE001 — el motivo se conserva por parte
                ultimo = str(exc)
                if intento == 1:
                    time.sleep(5)
        try:
            r, _ = en_mitades(partes[i], destino_dir, refs)
            estados[i] = "hecha"
            _publicar()
            return r
        except Exception as exc:  # noqa: BLE001
            errores[i] = f"{ultimo} | en mitades: {exc}"
            estados[i] = "error"
            _publicar()
            return None

    respuestas: list = [None] * len(partes)
    _publicar()
    conocidos = {n for n, _ in hablantes}
    refs = list(hablantes)
    arranque = 0
    if len(partes) > 1:
        # Las letras de hablante no son estables entre llamadas. Mientras queden plazas
        # de referencia (máx. 4), las partes van EN SECUENCIA y cada voz nueva con ≥2 s
        # de tramo limpio se enrola como «HABLANTE_N» para las partes siguientes (una
        # persona que entra a mitad de reunión también se identifica); con las plazas
        # cubiertas, el resto va en paralelo.
        informar("Transcribiendo por partes e identificando las voces según aparecen…", 12)
        while arranque < len(partes) and len(refs) < MAX_VOCES_ENVIADAS:
            respuestas[arranque] = _una(arranque, list(refs))
            if respuestas[arranque] is not None:
                try:
                    pseudos = sum(1 for n in conocidos if n.startswith("HABLANTE_"))
                    nuevas = _referencias_de_parte(respuestas[arranque], partes[arranque], destino_dir,
                                                   conocidos, MAX_VOCES_ENVIADAS - len(refs), numero_inicial=pseudos + 1)
                except ExpedienteError:
                    nuevas = []
                refs = refs + nuevas
                conocidos |= {n for n, _ in nuevas}
            arranque += 1
    if arranque < len(partes):
        with ThreadPoolExecutor(max_workers=min(2, len(partes) - arranque)) as pool:
            futuros = {pool.submit(_una, i, refs): i for i in range(arranque, len(partes))}
            for futuro in as_completed(futuros):
                respuestas[futuros[futuro]] = futuro.result()
    if len(partes) > 1:      # con una sola llamada las letras ya son consistentes
        _aislar_letras_sueltas(respuestas, conocidos, desde=0)
    if len(errores) == len(partes):
        raise ExpedienteError(f"No se ha podido transcribir {ruta.name}: {errores[min(errores)][:300]}")
    return respuestas, offsets, errores


def segmentos_globales(respuestas: list, offsets: list[float]) -> list[dict]:
    """Une los segments de todas las partes con tiempos globales del audio completo."""
    salida = []
    for r, offset in zip(respuestas, offsets):
        for s in (r or {}).get("segments") or []:
            texto = (s.get("text") or "").strip()
            if texto:
                salida.append({"start": round((s.get("start") or 0) + offset, 2),
                               "end": round((s.get("end") or 0) + offset, 2),
                               "speaker": (s.get("speaker") or "").strip(), "text": texto})
    return sorted(salida, key=lambda s: s["start"])


# ============================================================ voces del expediente
def dir_audio(exp: Expediente) -> Path:
    return exp.ruta / "entrada" / "audio"


def cargar_voces(exp: Expediente) -> dict:
    """voces.yaml del expediente: {nombre: {fichero, origen, fecha, segundos}}.
    Solo se leen las voces del PROPIO expediente, nunca de otro."""
    ruta = dir_audio(exp) / "voces" / "voces.yaml"
    if not ruta.exists():
        return {}
    return yaml.safe_load(ruta.read_text(encoding="utf-8")) or {}


def guardar_voz(exp: Expediente, nombre: str, clip: Path, origen: str, segundos: float) -> Path:
    voces_dir = dir_audio(exp) / "voces"
    voces_dir.mkdir(parents=True, exist_ok=True)
    destino = voces_dir / (re.sub(r"[^\w\- ]", "", nombre).strip().replace(" ", "_") + ".wav")
    shutil.copy(clip, destino)
    voces = cargar_voces(exp)
    previo = voces.get(nombre, {})
    voces[nombre] = {"fichero": destino.name, "origen": origen,
                     "fecha": datetime.now().isoformat(timespec="seconds"),
                     "segundos": round((previo.get("segundos") or 0) + segundos, 1)}
    (voces_dir / "voces.yaml").write_text(yaml.safe_dump(voces, allow_unicode=True, sort_keys=True), encoding="utf-8")
    return destino


def voces_para_enviar(exp: Expediente) -> list[tuple[str, str]]:
    """Hasta 4 voces del expediente como known_speakers, priorizadas por segundos
    de habla acumulados en ESTE expediente."""
    voces_dir = dir_audio(exp) / "voces"
    candidatas = []
    for nombre, datos in cargar_voces(exp).items():
        ruta = voces_dir / (datos.get("fichero") or "")
        if ruta.exists():
            candidatas.append((datos.get("segundos") or 0, nombre, str(ruta)))
    candidatas.sort(reverse=True)
    return [(nombre, ruta) for _, nombre, ruta in candidatas[:MAX_VOCES_ENVIADAS]]


# ============================================================ transcribir
def _mmss(segundos: float) -> str:
    return f"{int(segundos // 60):02d}:{int(segundos % 60):02d}"


def _por_hablante(segmentos: list[dict]) -> dict[str, dict]:
    """Agrupa por etiqueta de hablante (orden de aparición): segundos totales y segmentos."""
    salida: dict[str, dict] = {}
    for s in segmentos:
        h = salida.setdefault(s["speaker"], {"segundos": 0.0, "segmentos": []})
        h["segundos"] += max(0.0, s["end"] - s["start"])
        h["segmentos"].append(s)
    return salida


def _segmento_para_clip(segmentos_hablante: list[dict], todos: list[dict]) -> tuple[float, float]:
    """(inicio, duración) del clip: el tramo más largo en que la persona habla
    ININTERRUMPIDAMENTE (segmentos suyos consecutivos, sin otro hablante en medio),
    recortado a CLIP_MAX_S (~10 s). Se prefieren tramos sin solape con otros; si el
    tramo es más corto, se usa entero."""
    quien = segmentos_hablante[0]["speaker"]
    orden = sorted(todos, key=lambda s: s["start"])
    tramos: list[tuple[float, float]] = []
    ini = fin = None
    for s in orden:
        if s["speaker"] == quien:
            if ini is None:
                ini, fin = s["start"], s["end"]
            else:
                fin = s["end"]
        elif ini is not None:
            tramos.append((ini, fin))
            ini = None
    if ini is not None:
        tramos.append((ini, fin))

    def solapa(tramo):
        return any(o["speaker"] != quien and o["start"] < tramo[1] and o["end"] > tramo[0] for o in orden)

    limpios = [t for t in tramos if not solapa(t)] or tramos
    ini, fin = max(limpios, key=lambda t: t[1] - t[0])
    return ini, min(CLIP_MAX_S, max(1.0, fin - ini))


def accion_transcribir(exp: Expediente, ruta_fichero: str | Path, umbral_s: float = UMBRAL_HABLANTE_S,
                       forzar: bool = False, informar=None) -> str:
    """Transcribe un audio/vídeo de reunión con diarización. Deja en entrada/audio/:
    la copia normalizada del audio, transcripcion_cruda.md (timestamps y hablante),
    hablantes.md (tabla a rellenar) y hablantes/SPEAKER_XX.wav (clips para nombrar).
    Si el expediente tiene voces guardadas, se envían como known_speakers y esos
    hablantes llegan ya nombrados. NO toca 03_instrucciones.md (eso lo hace
    `etiquetar-transcript`)."""
    ruta = Path(ruta_fichero)
    if not ruta.exists():
        raise ExpedienteError(f"No existe {ruta}.")
    if ruta.suffix.lower() not in EXTENSIONES_AV:
        raise ExpedienteError(f"{ruta.name}: no es audio/vídeo admitido ({', '.join(EXTENSIONES_AV)}).")
    base = dir_audio(exp)
    cruda = base / "transcripcion_cruda.md"
    if cruda.exists() and "> Etiquetada" not in cruda.read_text(encoding="utf-8")[:200] and not forzar:
        raise ExpedienteError("Hay una transcripcion_cruda.md sin etiquetar. Ejecuta `etiquetar-transcript` "
                              "(o repite con --forzar para descartarla).")
    base.mkdir(parents=True, exist_ok=True)
    shutil.rmtree(base / "hablantes", ignore_errors=True)   # clips y meta de la transcripción anterior
    (base / "hablantes").mkdir(exist_ok=True)

    inicio = datetime.now()
    conocidos = voces_para_enviar(exp)
    normalizado = base / (re.sub(r"[^\w\-. ]", "", ruta.stem)[:60].strip().replace(" ", "_") + ".mp3")
    normalizar_audio(ruta, normalizado)

    temporal = Path(tempfile.mkdtemp(prefix="transcribir_"))
    try:
        respuestas, offsets, errores = transcribir_en_partes(normalizado, conocidos, temporal, informar)
    finally:
        shutil.rmtree(temporal, ignore_errors=True)
    segmentos = segmentos_globales(respuestas, offsets)
    if not segmentos:
        raise ExpedienteError(f"La transcripción de {ruta.name} ha vuelto vacía (¿audio sin habla?).")

    nombres_conocidos = {n for n, _ in conocidos}
    grupos = _por_hablante(segmentos)
    relevantes = {h: g for h, g in grupos.items() if g["segundos"] >= umbral_s or h in nombres_conocidos}
    menores = [h for h in grupos if h not in relevantes]
    # etiquetas genéricas (las que no son nombres enviados) -> SPEAKER_NN por orden de aparición
    ids: dict[str, str] = {}
    for h in relevantes:
        ids[h] = h if h in nombres_conocidos else f"SPEAKER_{sum(1 for v in ids.values() if v.startswith('SPEAKER_')) + 1:02d}"

    meta = {"origen": ruta.name, "fecha": inicio.isoformat(timespec="seconds"), "umbral_s": umbral_s,
            "duracion_s": round(sum((r or {}).get("duration") or 0 for r in respuestas), 1),
            "normalizado": normalizado.name, "menores_descartados": len(menores), "hablantes": {}}
    filas = []
    for etiqueta, g in relevantes.items():
        ident = ids[etiqueta]
        info = {"etiqueta_api": etiqueta, "segundos": round(g["segundos"], 1), "clip": "",
                "conocido": etiqueta in nombres_conocidos,
                "muestra": " ".join(s["text"] for s in g["segmentos"][:2])[:160]}
        if not info["conocido"]:
            ini, dur = _segmento_para_clip(g["segmentos"], segmentos)
            clip = base / "hablantes" / f"{ident}.wav"
            _ffmpeg(["-ss", str(ini), "-t", str(dur), "-i", str(normalizado), "-ac", "1", "-ar", "16000"],
                    clip, f"No se ha podido cortar el clip de {ident}")
            info["clip"] = clip.name
            filas.append(f"| {ident} | {clip.name} | {info['muestra']} |  |  |")
        meta["hablantes"][ident] = info
    (base / "hablantes" / "meta.json").write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")

    if filas:
        (base / "hablantes.md").write_text(
            "# Hablantes de la reunión — " + ruta.name + "\n\n"
            "> Escucha cada clip (entrada/audio/hablantes/) y rellena **Nombre**. En **Acción**: vacío = usar;\n"
            "> `fusionar con SPEAKER_XX` si es la misma persona que otro; `ignorar` para descartarlo.\n"
            "> Después: `./revisor etiquetar-transcript`.\n\n"
            "| ID | Clip | Muestra de lo dicho | Nombre | Acción |\n|---|---|---|---|---|\n"
            + "\n".join(filas) + "\n", encoding="utf-8")
    elif (base / "hablantes.md").exists():
        (base / "hablantes.md").unlink()

    L = [f"# Transcripción cruda — {ruta.name}", "",
         f"- Fecha: {inicio:%Y-%m-%d %H:%M}", f"- Duración: {_mmss(meta['duracion_s'])}",
         f"- Hablantes relevantes: {len(relevantes)} (+{len(menores)} menores descartados, umbral {umbral_s:g} s)",
         f"- Voces del expediente enviadas: {', '.join(sorted(nombres_conocidos)) or '(ninguna)'}", ""]
    for s in segmentos:
        quien = ids.get(s["speaker"], s["speaker"])
        L.append(f"- [{_mmss(s['start'])}–{_mmss(s['end'])}] {quien}: {s['text']}")
    cruda.write_text("\n".join(L) + "\n", encoding="utf-8")

    exp.trazar("transcribir", {"fecha": inicio.isoformat(timespec="seconds"), "accion": "transcribir",
                               "fichero": ruta.name, "modelo": next((r.get("model") for r in respuestas if r), None),
                               "duracion_audio_s": meta["duracion_s"], "partes": len(respuestas),
                               "partes_fallidas": sorted(i + 1 for i in errores),
                               "segundos": round((datetime.now() - inicio).total_seconds(), 1),
                               "known_speakers": sorted(nombres_conocidos),
                               "hablantes": {i: {"segundos": d["segundos"]} for i, d in meta["hablantes"].items()},
                               "respuesta": {"segments": segmentos}})   # JSON crudo; el audio NO se copia a trazas

    sin_nombrar = [i for i, d in meta["hablantes"].items() if not d["conocido"]]
    out = [f"Transcripción: {cruda.relative_to(exp.ruta)} ({len(segmentos)} segmentos, {_mmss(meta['duracion_s'])})",
           f"Hablantes relevantes: {len(relevantes)} (+{len(menores)} menores descartados)."]
    if errores:
        out.append(f"⚠ {len(errores)} parte(s) no se pudieron transcribir: revisa huecos en la cruda.")
    if nombres_conocidos:
        out.append("Ya nombrados por las voces del expediente: " + ", ".join(sorted(nombres_conocidos)) + ".")
    if sin_nombrar:
        out.append(f"Por nombrar: {', '.join(sin_nombrar)} → escucha los clips de entrada/audio/hablantes/, "
                   "rellena entrada/audio/hablantes.md y ejecuta `etiquetar-transcript`.")
    else:
        out.append("Todos los hablantes llegaron nombrados: ejecuta `etiquetar-transcript` para volcar a 03_instrucciones.md.")
    return "\n".join(out)


# ============================================================ etiquetar-transcript
_RE_FILA = re.compile(r"^\|\s*(SPEAKER_\d\d)\s*\|[^|]*\|[^|]*\|([^|]*)\|([^|]*)\|\s*$")
_RE_SEG = re.compile(r"^- \[(\d+):(\d\d)–(\d+):(\d\d)\] ([^:]+): (.*)$")


def _resolver(ident: str, mapa: dict[str, tuple[str, str]], profundidad: int = 0) -> str | None:
    """Nombre final de un SPEAKER: sigue fusiones (con límite) y devuelve None si se ignora."""
    if profundidad > 10:
        raise ExpedienteError(f"Fusiones circulares en hablantes.md alrededor de {ident}.")
    nombre, accion = mapa.get(ident, ("", ""))
    if accion.lower().startswith("ignorar"):
        return None
    m = re.search(r"(SPEAKER_\d\d)", accion)
    if accion.lower().startswith("fusionar") and m:
        return _resolver(m.group(1), mapa, profundidad + 1)
    if nombre:
        return nombre
    raise ExpedienteError(f"{ident} no tiene Nombre ni Acción en entrada/audio/hablantes.md: "
                          "pon un nombre, «fusionar con SPEAKER_XX» o «ignorar».")


def aplicar_asignaciones(exp: Expediente, asignaciones: dict) -> None:
    """Escribe en hablantes.md las asignaciones {SPEAKER_XX: {nombre, accion}} que llegan
    de la interfaz web (misma fuente de verdad que el flujo manual)."""
    ruta = dir_audio(exp) / "hablantes.md"
    if not ruta.exists():
        return
    lineas = []
    for linea in ruta.read_text(encoding="utf-8").splitlines():
        m = _RE_FILA.match(linea)
        if m and m.group(1) in asignaciones:
            a = asignaciones[m.group(1)] or {}
            partes = linea.split("|")
            partes[4] = f" {(a.get('nombre') or '').strip()} "
            partes[5] = f" {(a.get('accion') or '').strip()} "
            linea = "|".join(partes)
        lineas.append(linea)
    ruta.write_text("\n".join(lineas) + "\n", encoding="utf-8")


def estado_transcripcion(exp: Expediente) -> dict:
    """Para la web: hablantes de la transcripción actual (con clip y muestra), si está
    etiquetada, y las voces guardadas del expediente."""
    base = dir_audio(exp)
    meta_ruta = base / "hablantes" / "meta.json"
    cruda = base / "transcripcion_cruda.md"
    salida = {"hay_transcripcion": cruda.exists(), "etiquetada": False, "origen": "", "fecha": "",
              "duracion_s": 0, "hablantes": [], "voces": []}
    if cruda.exists():
        salida["etiquetada"] = cruda.read_text(encoding="utf-8")[:40].startswith("> Etiquetada")
    if meta_ruta.exists():
        meta = json.loads(meta_ruta.read_text(encoding="utf-8"))
        salida.update(origen=meta.get("origen", ""), fecha=meta.get("fecha", ""), duracion_s=meta.get("duracion_s", 0))
        salida["hablantes"] = [{"id": ident, "clip": d.get("clip", ""), "muestra": d.get("muestra", ""),
                                "segundos": d.get("segundos", 0), "conocido": bool(d.get("conocido"))}
                               for ident, d in meta.get("hablantes", {}).items()]
    salida["voces"] = [{"nombre": n, "segundos": d.get("segundos", 0), "origen": d.get("origen", ""), "fecha": d.get("fecha", "")}
                       for n, d in sorted(cargar_voces(exp).items(), key=lambda kv: -(kv[1].get("segundos") or 0))]
    return salida


def accion_etiquetar(exp: Expediente, preguntar_guardar=None) -> str:
    """Aplica EN LOCAL los nombres/fusiones/ignorados de hablantes.md sobre la
    transcripción cruda (sin segunda llamada a la API), agrupa intervenciones
    consecutivas y vuelca a 03_instrucciones.md para el `aplicar-cambios` de siempre.
    `preguntar_guardar(nombre, clip)` -> bool decide, hablante a hablante, si su clip
    se guarda en las voces del expediente para las siguientes reuniones."""
    base = dir_audio(exp)
    cruda = base / "transcripcion_cruda.md"
    if not cruda.exists():
        raise ExpedienteError("No hay entrada/audio/transcripcion_cruda.md: ejecuta antes `transcribir <fichero>`.")
    texto_cruda = cruda.read_text(encoding="utf-8")
    if texto_cruda.startswith("> Etiquetada"):
        raise ExpedienteError("Esta transcripción ya se etiquetó (la cabecera lo indica). Transcribe otra reunión.")
    meta = json.loads((base / "hablantes" / "meta.json").read_text(encoding="utf-8")) \
        if (base / "hablantes" / "meta.json").exists() else {"hablantes": {}, "origen": "?"}

    mapa: dict[str, tuple[str, str]] = {}
    if (base / "hablantes.md").exists():
        for linea in (base / "hablantes.md").read_text(encoding="utf-8").splitlines():
            m = _RE_FILA.match(linea)
            if m:
                mapa[m.group(1)] = (m.group(2).strip(), m.group(3).strip())
    nombres: dict[str, str | None] = {}
    for ident, datos in meta["hablantes"].items():
        nombres[ident] = ident if datos.get("conocido") else _resolver(ident, mapa)

    segmentos = []
    for linea in texto_cruda.splitlines():
        m = _RE_SEG.match(linea)
        if not m:
            continue
        quien = m.group(5).strip()
        if quien.startswith("SPEAKER_"):
            nombre = nombres.get(quien)        # nombrado, fusionado o None si «ignorar»
        elif quien in meta["hablantes"]:
            nombre = quien                     # conocido por las voces del expediente
        else:
            nombre = None                      # hablante menor descartado por el umbral
        if nombre is not None:
            segmentos.append((nombre, m.group(6).strip()))
    if not segmentos:
        raise ExpedienteError("La transcripción quedó vacía tras aplicar los ignorados: revisa hablantes.md.")

    # agrupar intervenciones consecutivas del mismo hablante
    intervenciones: list[tuple[str, str]] = []
    for nombre, frase in segmentos:
        if intervenciones and intervenciones[-1][0] == nombre:
            intervenciones[-1] = (nombre, intervenciones[-1][1] + " " + frase)
        else:
            intervenciones.append((nombre, frase))

    marca = datetime.now()
    bloque = [f"\nReunión transcrita «{meta.get('origen', '?')}» ({marca:%d/%m/%Y %H:%M}) — transcripción etiquetada; "
              "borra lo que no aplique antes de `aplicar-cambios`:"]
    bloque += [f"- {nombre}: {frase}" for nombre, frase in intervenciones]
    exp.anexar_registro("instrucciones", "\n".join(bloque) + "\n")
    cruda.write_text(f"> Etiquetada el {marca:%Y-%m-%d %H:%M} → 03_instrucciones.md\n\n" + texto_cruda, encoding="utf-8")

    guardadas = []
    if preguntar_guardar is not None:
        ofrecidos = set(cargar_voces(exp))     # una pregunta por PERSONA (las fusiones comparten nombre)
        for ident, datos in meta["hablantes"].items():
            nombre = nombres.get(ident)
            clip = base / "hablantes" / (datos.get("clip") or "")
            if datos.get("conocido") or not nombre or not clip.exists() or nombre in ofrecidos:
                continue
            ofrecidos.add(nombre)
            if preguntar_guardar(nombre, clip):
                guardar_voz(exp, nombre, clip, meta.get("origen", "?"), datos.get("segundos") or 0)
                guardadas.append(nombre)

    hablantes_finales = sorted({n for n, _ in intervenciones})
    out = [f"{len(intervenciones)} intervenciones de {len(hablantes_finales)} hablante(s) "
           f"({', '.join(hablantes_finales)}) volcadas a 03_instrucciones.md.",
           "Revisa el buzón (borra lo que no aplique) y ejecuta `aplicar-cambios`."]
    if guardadas:
        out.append("Voces guardadas para las próximas reuniones de ESTE expediente: " + ", ".join(guardadas) +
                   " (se borran al archivar).")
    return "\n".join(out)


# ============================================================ voces (listar/borrar)
def accion_voces(exp: Expediente, borrar: list[str] | None = None) -> str:
    voces_dir = dir_audio(exp) / "voces"
    voces = cargar_voces(exp)
    if borrar:
        for nombre in borrar:
            if nombre not in voces:
                raise ExpedienteError(f"No hay una voz guardada con el nombre «{nombre}».")
            fichero = voces_dir / (voces[nombre].get("fichero") or "")
            fichero.unlink(missing_ok=True)
            del voces[nombre]
        if voces:
            (voces_dir / "voces.yaml").write_text(yaml.safe_dump(voces, allow_unicode=True, sort_keys=True), encoding="utf-8")
        else:
            (voces_dir / "voces.yaml").unlink(missing_ok=True)
        return f"Voz(es) eliminada(s): {', '.join(borrar)}. Quedan {len(voces)}."
    if not voces:
        return ("No hay voces guardadas en este expediente. Se ofrecen al terminar `etiquetar-transcript` "
                "y solo sirven para las reuniones de ESTA auditoría (se borran al archivar).")
    L = [f"Voces del expediente {exp.referencia} (máx. {MAX_VOCES_ENVIADAS} se envían como known_speakers, "
         "priorizadas por habla acumulada; se borran al archivar):"]
    for nombre, d in sorted(voces.items(), key=lambda kv: -(kv[1].get("segundos") or 0)):
        L.append(f"  {nombre:<20} {d.get('segundos', 0):>6.1f} s de habla · origen {d.get('origen', '?')} · {d.get('fecha', '')[:16]}")
    L.append("Borrar: ./revisor voces --borrar \"Nombre\"")
    return "\n".join(L)


# ============================================================ ciclo de vida (archivar)
def audio_a_borrar_al_archivar(exp: Expediente) -> list[Path]:
    """Material de voz/audio que NUNCA va al zip de evidencia y se destruye al
    archivar: voces/, hablantes/ (clips) y los audios de entrada/audio/.
    hablantes.md y transcripcion_cruda.md SÍ son evidencia y no están aquí."""
    base = dir_audio(exp)
    if not base.exists():
        return []
    ficheros = [p for p in (base / "voces").rglob("*") if p.is_file()] if (base / "voces").exists() else []
    ficheros += [p for p in (base / "hablantes").rglob("*") if p.is_file()] if (base / "hablantes").exists() else []
    ficheros += [p for p in base.iterdir() if p.is_file() and p.suffix.lower() in EXTENSIONES_AV]
    return sorted(set(ficheros))


def borrar_audio_del_expediente(exp: Expediente) -> None:
    base = dir_audio(exp)
    for d in ("voces", "hablantes"):
        shutil.rmtree(base / d, ignore_errors=True)
    for p in list(base.iterdir()) if base.exists() else []:
        if p.is_file() and p.suffix.lower() in EXTENSIONES_AV:
            p.unlink(missing_ok=True)
