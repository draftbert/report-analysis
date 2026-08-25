"""
Calibración de config/estilo.yaml contra informes YA APROBADOS.

Las palabras prohibidas del YAML inicial son plausibles pero inventadas; el
criterio real del departamento está en los informes que Dirección ha
aprobado. Este módulo:

  (a) Determinista: pasa el validador actual a los informes aprobados. Todo
      lo que dispare ahí es un FALSO POSITIVO (el término sí se usa en
      textos aprobados): señal de que la regla sobra o necesita excepción.
      Se listan con recuento y contexto.
  (b) LLM (salida estructurada): propone altas/bajas/modificaciones de reglas.
      Si en el corpus hay parejas borrador/aprobado (mismo nombre con sufijo
      `_borrador` / `-borrador`), compara qué cambió la revisión; si no,
      detecta patrones consistentes en los aprobados.

La salida es un informe Markdown (calibracion_estilo.md). NUNCA modifica
estilo.yaml: el equipo revisa el informe y edita el YAML a mano.
"""
from __future__ import annotations

import re
from collections import defaultdict
from datetime import datetime
from pathlib import Path

from .esquemas import PropuestasEstilo
from .lectores import EXTENSIONES, LecturaError, leer
from .llm import ClienteLLM, LLMNoDisponible
from .style_checker import StyleChecker, reglas_como_texto, revisar_markdown

MAX_CHARS_CORPUS = 200_000
CONTEXTO = 70

SYSTEM_CALIBRACION = """Eres el responsable de metodología de un departamento de auditoría interna.
Tu tarea es calibrar el criterio de estilo de los informes (lista de términos prohibidos, expresiones
en primera persona, reglas cuantitativas) contra informes YA APROBADOS por Dirección, que son la
referencia real del estilo del departamento.
Reglas:
- Solo propones reglas soportadas por evidencia literal del corpus; cada propuesta cita fragmentos.
- Una regla vigente que aparece en informes aprobados es un falso positivo: propón baja o excepción.
- Si hay parejas borrador/aprobado, lo que la revisión cambió sistemáticamente es la mejor señal de
  regla nueva (alta): término del borrador -> término del aprobado.
- No propongas reglas de gusto personal ni genéricas; sé concreto y conservador.
- Responde en español, en el formato estructurado solicitado."""


def _es_borrador(nombre: str) -> bool:
    return bool(re.search(r"[_\-. ]borrador", nombre.lower()))


def _es_salida_calibracion(ruta: Path) -> bool:
    """Informes generados por este comando (calibracion_estilo*.md) o sus trazas."""
    return ruta.stem.lower().startswith("calibracion_estilo") or "_trazas" in ruta.parent.name


def _clave_pareja(stem: str) -> str:
    return re.sub(r"[_\-. ]?(borrador|aprobad[oa]|final|v\d+)$", "", stem.lower(), flags=re.IGNORECASE).strip("_- .")


def cargar_corpus(carpeta: Path) -> tuple[list[tuple[str, str]], list[tuple[str, str]], list[str]]:
    """Devuelve (aprobados, borradores, avisos) como listas de (nombre, texto)."""
    aprobados, borradores, avisos = [], [], []
    for ruta in sorted(p for p in carpeta.rglob("*") if p.is_file() and p.suffix.lower() in EXTENSIONES):
        if _es_salida_calibracion(ruta):
            continue  # el informe de una pasada anterior no es corpus (cita los términos prohibidos)
        try:
            doc = leer(ruta)
        except LecturaError as exc:
            avisos.append(str(exc))
            continue
        (borradores if _es_borrador(ruta.stem) else aprobados).append((ruta.name, doc.texto))
    return aprobados, borradores, avisos


def falsos_positivos(checker: StyleChecker, aprobados: list[tuple[str, str]]) -> dict[str, dict]:
    """{termino_normalizado: {"tipo", "mensaje", "sugerencia", "n", "ficheros": set, "ejemplos": [..]}}"""
    fp: dict[str, dict] = defaultdict(lambda: {"n": 0, "ficheros": set(), "ejemplos": []})
    for nombre, texto in aprobados:
        for h in revisar_markdown(checker, texto):
            if h["severidad"] != "error":
                continue  # las frases largas no son "términos": se informan aparte
            clave = h["fragmento"].lower()
            reg = fp[clave]
            reg.update(tipo=h["tipo"], mensaje=h["mensaje"], sugerencia=h.get("sugerencia", ""))
            reg["n"] += 1
            reg["ficheros"].add(nombre)
            if len(reg["ejemplos"]) < 3:
                reg["ejemplos"].append((nombre, _contexto(texto, h)))
    return dict(fp)


def _contexto(texto: str, h: dict) -> str:
    lineas = texto.splitlines()
    linea = lineas[h["linea"] - 1] if 0 < h["linea"] <= len(lineas) else ""
    pos = linea.lower().find(h["fragmento"].lower())
    if pos < 0:
        return linea[:2 * CONTEXTO]
    ini, fin = max(0, pos - CONTEXTO), min(len(linea), pos + len(h["fragmento"]) + CONTEXTO)
    return ("…" if ini else "") + linea[ini:fin] + ("…" if fin < len(linea) else "")


def frases_largas(checker: StyleChecker, aprobados: list[tuple[str, str]]) -> tuple[int, int]:
    """(nº de avisos de frase larga en aprobados, nº total de frases)."""
    avisos = total = 0
    for _, texto in aprobados:
        total += len([f for f in re.split(r"(?<=[.!?])\s+", texto) if f.strip()])
        avisos += sum(h["tipo"] == "frase_larga" for h in revisar_markdown(checker, texto))
    return avisos, total


def _recortar(docs: list[tuple[str, str]], presupuesto: int) -> str:
    partes, total = [], 0
    for nombre, texto in docs:
        if total >= presupuesto:
            partes.append(f"[... {nombre} omitido por tamaño ...]")
            continue
        t = texto[: presupuesto - total]
        total += len(t)
        partes.append(f"===== {nombre} =====\n{t}")
    return "\n\n".join(partes)


def calibrar(carpeta: Path, checker: StyleChecker, llm: ClienteLLM | None, salida: Path) -> str:
    aprobados, borradores, avisos = cargar_corpus(carpeta)
    if not aprobados and not borradores:
        raise LecturaError(f"No hay documentos legibles en {carpeta} ({', '.join(EXTENSIONES)}).")
    fp = falsos_positivos(checker, aprobados)
    n_largas, n_frases = frases_largas(checker, aprobados)
    por_clave = {_clave_pareja(Path(n).stem): (n, t) for n, t in aprobados}
    parejas = [((nb, tb), por_clave[_clave_pareja(Path(nb).stem)]) for nb, tb in borradores
               if _clave_pareja(Path(nb).stem) in por_clave]
    sin_pareja = [(n, t) for n, t in borradores if _clave_pareja(Path(n).stem) not in por_clave]

    # ---------------- (b) propuestas del modelo
    propuestas: PropuestasEstilo | None = None
    error_llm = ""
    if llm is not None and not llm.dry_run:
        resumen_fp = "\n".join(
            f"- «{k}» ({v['n']} veces en {len(v['ficheros'])} fichero(s)); regla actual: {v['mensaje']}"
            for k, v in sorted(fp.items(), key=lambda kv: -kv[1]["n"])) or "(ninguno)"
        bloques = [f"CRITERIO ACTUAL (config/estilo.yaml):\n{reglas_como_texto(checker)}",
                   f"FALSOS POSITIVOS DETECTADOS (términos prohibidos que SÍ aparecen en aprobados):\n{resumen_fp}"]
        if parejas:
            bloques.append("PAREJAS BORRADOR -> APROBADO (lo que cambió la revisión es la mejor señal de regla):\n"
                           + "\n\n".join(f"----- BORRADOR {nb} -----\n{tb[:20000]}\n----- APROBADO {na} -----\n{ta[:20000]}"
                                         for (nb, tb), (na, ta) in parejas))
        if sin_pareja:
            bloques.append("BORRADORES SIN VERSIÓN APROBADA (solo orientativos):\n" + _recortar(sin_pareja, 30000))
        bloques.append("INFORMES APROBADOS (referencia del estilo real):\n" + _recortar(aprobados, MAX_CHARS_CORPUS))
        user = ("Propón altas, bajas y modificaciones del criterio de estilo con evidencia literal. Para cada falso "
                "positivo decide si la regla sobra (baja) o necesita matiz (modificacion). Añade `patrones_observados` "
                "con rasgos consistentes de los aprobados.\n\n" + "\n\n".join(bloques))
        try:
            propuestas = llm.completar_estructurado("calibrar-estilo", SYSTEM_CALIBRACION, user, PropuestasEstilo)
        except LLMNoDisponible as exc:
            error_llm = str(exc)
    elif llm is None or llm.dry_run:
        error_llm = "sin proveedor LLM: solo se incluye el análisis determinista (a)."

    # ---------------- informe Markdown
    L = [f"# Calibración del criterio de estilo — {datetime.now():%Y-%m-%d %H:%M}", "",
         f"Corpus: `{carpeta}` — {len(aprobados)} aprobado(s), {len(borradores)} borrador(es), "
         f"{len(parejas)} pareja(s) borrador/aprobado.",
         "", "> Este informe NO modifica `config/estilo.yaml`. Revisa cada propuesta y edita el YAML a mano.", ""]
    if avisos:
        L += ["Avisos de lectura:"] + [f"- {a}" for a in avisos] + [""]
    L += ["## (a) Falsos positivos: reglas que disparan en informes aprobados", ""]
    if not fp:
        L.append("Ninguna regla vigente dispara en los informes aprobados. ✔")
    else:
        L += ["| Término | Regla | Veces | Ficheros | Acción sugerida |", "|---|---|---:|---:|---|"]
        for k, v in sorted(fp.items(), key=lambda kv: -kv[1]["n"]):
            accion = "baja o excepción" if len(v["ficheros"]) > 1 or v["n"] >= 3 else "revisar (poca evidencia)"
            L.append(f"| «{k}» | {v['tipo']} — {v['mensaje']} | {v['n']} | {len(v['ficheros'])} | {accion} |")
        L.append("")
        for k, v in sorted(fp.items(), key=lambda kv: -kv[1]["n"]):
            L.append(f"**«{k}»** — contexto en aprobados:")
            L += [f"- [{n}] {c}" for n, c in v["ejemplos"]]
            L.append("")
    lim = checker.cfg.get("reglas", {}).get("longitud_maxima_frase")
    L += [f"Frases por encima del límite de {lim} palabras en aprobados: {n_largas} de {n_frases} "
          f"({(100 * n_largas / n_frases):.1f}%)." if n_frases else "", ""]
    if n_frases and n_largas / n_frases > 0.1:
        L.append("> Más del 10% de las frases aprobadas superan el límite: considerar subir `longitud_maxima_frase`.")
        L.append("")

    L += ["## (b) Propuestas de nuevas reglas y ajustes (modelo)", ""]
    if propuestas is None:
        L.append(f"No disponible: {error_llm}")
    else:
        for tipo, titulo in (("alta", "Altas propuestas"), ("baja", "Bajas propuestas"), ("modificacion", "Modificaciones propuestas")):
            items = [p for p in propuestas.propuestas if p.tipo.lower().startswith(tipo[:4])]
            L += [f"### {titulo} ({len(items)})", ""]
            if not items:
                L += ["(ninguna)", ""]
            for p in items:
                L.append(f"- **«{p.termino}»** [{p.seccion}] — confianza {p.confianza}")
                if p.sugerencia:
                    L.append(f"  - Sugerencia: {p.sugerencia}")
                L.append(f"  - Motivo: {p.motivo}")
                L += [f"  - Evidencia: {e}" for e in p.evidencia]
            L.append("")
        if propuestas.patrones_observados.strip():
            L += ["### Patrones de estilo observados en los aprobados", "", propuestas.patrones_observados.strip(), ""]
        L += ["### Cómo trasladarlo al YAML", "",
              "```yaml", "palabras_prohibidas:", "  - termino: \"<término>\"", "    sugerencia: \"<alternativa>\"",
              "    motivo: \"<motivo>\"", "```", "Bajas: eliminar la entrada. Modificaciones: ajustar `sugerencia`/`motivo`.", ""]
    salida.parent.mkdir(parents=True, exist_ok=True)
    salida.write_text("\n".join(L).rstrip() + "\n", encoding="utf-8")
    resumen = (f"Informe de calibración: {salida}\n  Falsos positivos: {len(fp)} término(s); "
               f"propuestas del modelo: {len(propuestas.propuestas) if propuestas else 'n/d'}"
               + (f" ({error_llm})" if error_llm else "") + "\n  estilo.yaml NO se ha modificado.")
    return resumen
