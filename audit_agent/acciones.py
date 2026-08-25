"""
Acciones del flujo de trabajo sobre un expediente.

Cada acción es una función `accion_x(exp, ...) -> str` que devuelve un
resumen imprimible; la CLI y el menú interactivo solo las envuelven.

Flujo previsto (no es lineal: se vuelve atrás cuando haga falta):

    nuevo ─► entrada/ ─► extraer ─► [auditor edita/aprueba 01_observaciones.md]
          ─► redactar ─► [auditor edita 02_informe.md durante días]
             ├─ revisar / corregir       (vocabulario y estilo)
             ├─ aplicar-cambios          (desde 03_instrucciones.md)
             ├─ diff / deshacer / historial
          ─► ppt

Principio: el modelo propone, la persona decide. Antes de sobreescribir un
fichero editado por una persona, siempre queda snapshot en historial/.
"""
from __future__ import annotations

import difflib
import json
import re
from datetime import datetime
from pathlib import Path

from .esquemas import (BorradorInforme, Correcciones, ExtraccionObservaciones,
                       Observacion, ObservacionExtraida, PlanCambios)
from .expediente import Expediente, ExpedienteError
from .formato_md import (COLETILLA_RIESGO_PROPUESTO, normalizar_nivel, parrafos_con_lineas,
                         parsear_informe, parsear_observaciones,
                         render_informe, render_observaciones)
from .llm import ClienteLLM
from .style_checker import StyleChecker, reglas_como_texto, revisar_markdown

RAIZ = Path(__file__).resolve().parent.parent
CONFIG_DEFECTO = RAIZ / "config" / "estilo.yaml"

MAX_CHARS_ENTRADA = 250_000  # protección: gpt-5-mini admite mucho más, pero el coste crece

SYSTEM_BASE = """Eres un auditor interno senior y revisor de informes de auditoría interna.
Trabajas SIEMPRE con estas reglas:
- Redacción impersonal ("se ha observado", "se recomienda"), orientada a proceso, nunca a personas.
- Objetiva y soportada por evidencia: nada de absolutos ni juicios de valor. La severidad se expresa
  solo mediante el nivel de riesgo (Alto/Medio/Bajo).
- Frases cortas. Terminología: "observación", "debilidad", "recomendación".
- NUNCA inventas datos, cifras, fechas, normas ni causas. Si algo no está en la fuente, lo dejas vacío
  o lo señalas como pendiente. Conservas todos los datos objetivos existentes.
- Respondes en español, en el formato estructurado solicitado.

{reglas_estilo}"""


class Contexto:
    """Dependencias compartidas por las acciones (checker + LLM con trazas)."""

    def __init__(self, exp: Expediente, config: str | Path = CONFIG_DEFECTO,
                 modelo: str | None = None, proveedor: str | None = None,
                 esfuerzo: str | None = None):
        self.exp = exp
        self.checker = StyleChecker(config)
        self.llm = ClienteLLM(modelo=modelo, proveedor=proveedor, trazador=exp.trazar,
                              esfuerzo=esfuerzo)
        self.system = SYSTEM_BASE.format(reglas_estilo=reglas_como_texto(self.checker))


# ============================================================ utilidades
def _contexto_proyecto(exp: Expediente) -> str:
    p = exp.proyecto
    notas = exp.meta.get("notas", "")
    lineas = [f"Trabajo: {p.get('nombre', '')} (ref. {p.get('referencia', '')}, {p.get('fecha', '')})",
              f"Distribución: {', '.join(p.get('distribucion', []))}"]
    if notas and not str(notas).startswith("Contexto adicional para el modelo"):
        lineas.append(f"Notas del auditor sobre el trabajo: {notas}")
    return "\n".join(lineas)


def _documentos_entrada(exp: Expediente) -> str:
    docs = exp.leer_entrada()
    if not docs:
        raise ExpedienteError(f"No hay papeles de trabajo en {exp.ruta / 'entrada'} (.md/.txt/.docx).")
    partes, total = [], 0
    for nombre, texto in docs:
        if total + len(texto) > MAX_CHARS_ENTRADA:
            texto = texto[: max(0, MAX_CHARS_ENTRADA - total)] + "\n[... documento truncado ...]"
        total += len(texto)
        partes.append(f"===== DOCUMENTO: {nombre} =====\n{texto.strip()}\n")
    return "\n".join(partes)


def _obs_a_dict(o: Observacion, ident: str, estado: str = "propuesta", notas: str = "") -> dict:
    d = o.model_dump()
    d["nivel_riesgo"] = normalizar_nivel(d["nivel_riesgo"])
    d.update({"id": ident, "estado": estado, "notas": notas})
    soportado = d.pop("riesgo_soportado_por_evidencia", None)
    if isinstance(o, ObservacionExtraida):
        # Nivel estimado por el modelo sin evidencia en el PT -> coletilla visible
        d["riesgo_propuesto"] = bool(d["nivel_riesgo"]) and not soportado
    return d


def _campos_obs(o: dict) -> dict:
    return {k: o.get(k, "") for k in Observacion.model_fields}


def diff_texto(antes: str, despues: str, nombre: str = "", contexto: int = 2) -> str:
    lineas = difflib.unified_diff(antes.splitlines(), despues.splitlines(),
                                  fromfile=f"{nombre} (antes)", tofile=f"{nombre} (después)",
                                  lineterm="", n=contexto)
    return "\n".join(lineas)


def _formato_hallazgos(hallazgos: list[dict], con_linea: bool = True) -> str:
    if not hallazgos:
        return "  ✔ Sin hallazgos."
    out = []
    for h in hallazgos:
        icono = "✖" if h["severidad"] == "error" else "⚠"
        pos = f"L{h['linea']:>4} " if con_linea and "linea" in h else ""
        out.append(f"  {icono} {pos}«{h['fragmento']}» — {h['mensaje']}")
        if h.get("sugerencia"):
            out.append(f"         → {h['sugerencia']}")
    return "\n".join(out)


def _leer_observaciones(exp: Expediente) -> list[dict]:
    if not exp.existe("observaciones"):
        raise ExpedienteError("Todavía no hay 01_observaciones.md. Ejecuta `extraer` primero.")
    return parsear_observaciones(exp.leer("observaciones"))


def _fecha() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M")


# ============================================================ 1. extraer
def accion_extraer(ctx: Contexto, forzar: bool = False) -> str:
    exp = ctx.exp
    if exp.existe("observaciones") and not forzar:
        raise ExpedienteError("01_observaciones.md ya existe y puede contener trabajo del auditor. "
                              "Usa --forzar para regenerarlo (se guarda snapshot en historial/).")
    campos = "\n".join(f"- {k}: {v.description}" for k, v in ObservacionExtraida.model_fields.items())
    user = (f"{_contexto_proyecto(exp)}\n\n"
            "Extrae TODAS las observaciones (debilidades de control) soportadas por los papeles de trabajo, "
            "cada una con su recomendación, en el esquema:\n"
            f"{campos}\n\n"
            "Reglas: una observación por debilidad real (no fragmentes ni fusiones); campo vacío antes que "
            "inventar hechos; en `nivel_riesgo` PROPÓN siempre Alto/Medio/Bajo según impacto y probabilidad "
            "(es una propuesta que el auditor validará); en `fuente` cita el documento y apartado. "
            "`riesgo_soportado_por_evidencia`: true SOLO si el papel de trabajo menciona explícitamente la "
            "severidad, criticidad o nivel de riesgo de esa debilidad; si el PT no habla de riesgo, false. "
            "Ordena de mayor a menor riesgo.\n\n"
            f"PAPELES DE TRABAJO:\n{_documentos_entrada(exp)}")
    res = ctx.llm.completar_estructurado("extraer", ctx.system, user, ExtraccionObservaciones)
    observaciones = [_obs_a_dict(o, f"OBS-{i:02d}") for i, o in enumerate(res.observaciones, 1)]
    exp.escribir("observaciones", render_observaciones(observaciones, exp.proyecto, res.notas), "extraer")

    lineas = [f"Se han propuesto {len(observaciones)} observaciones en {exp.archivo('observaciones').name}:"]
    for o in observaciones:
        r = ctx.checker.revisar_observacion(_campos_obs(o))
        marca = "✔" if r.limpio else f"✖ {sum(h.severidad == 'error' for h in r.hallazgos)} hallazgos"
        nivel = (o["nivel_riesgo"] or "N/D") + ("*" if o.get("riesgo_propuesto") else "")
        lineas.append(f"  {o['id']}  [{nivel:6}] {o['titulo'][:70]}  {marca}")
    if any(o.get("riesgo_propuesto") for o in observaciones):
        lineas.append("  (*) nivel de riesgo propuesto por el modelo sin evidencia en el PT: valídalo al aprobar "
                      "(la coletilla desaparece con `aprobar`).")
    if res.notas.strip():
        lineas.append(f"\nNotas del modelo: {res.notas.strip()}")
    lineas.append("\nSiguiente: abre el fichero, corrige lo que haga falta y marca `Estado: aprobada` "
                  "en las que vayan al informe (o usa `aprobar`).")
    return "\n".join(lineas)


# ============================================================ 2. trabajar observaciones
def accion_aprobar(exp: Expediente, ids: list[str], estado: str = "aprobada") -> str:
    """Cambia el `Estado:` de las observaciones indicadas ("todas" admitido)
    con una edición quirúrgica del fichero: no se toca nada más."""
    texto = exp.leer("observaciones")
    if not texto:
        raise ExpedienteError("No hay 01_observaciones.md.")
    objetivo = {i.upper() for i in ids}
    todas = "TODAS" in objetivo
    cambiadas, bloque_actual = [], None
    salida = []
    for linea in texto.splitlines():
        m = re.match(r"^##\s+(OBS-\d+)", linea, re.IGNORECASE)
        if m:
            bloque_actual = m.group(1).upper()
        elif bloque_actual and re.match(r"^\s*[-*]\s*Estado\s*:", linea, re.IGNORECASE) \
                and (todas or bloque_actual in objetivo):
            linea = f"- Estado: {estado}"
            cambiadas.append(bloque_actual)
        elif (estado == "aprobada" and bloque_actual and (todas or bloque_actual in objetivo)
              and re.match(r"^\s*[-*]\s*Nivel de riesgo\s*:", linea, re.IGNORECASE)
              and COLETILLA_RIESGO_PROPUESTO in linea):
            # El auditor valida el nivel al aprobar: la coletilla desaparece
            linea = linea.replace(COLETILLA_RIESGO_PROPUESTO, "").rstrip()
        salida.append(linea)
    exp.escribir("observaciones", "\n".join(salida) + "\n", f"aprobar-{estado}")
    faltan = sorted(objetivo - set(cambiadas) - {"TODAS"})
    msg = f"Marcadas como «{estado}»: {', '.join(cambiadas) or 'ninguna'}."
    if faltan:
        msg += f" No encontradas: {', '.join(faltan)}."
    return msg


def accion_revisar_obs(ctx: Contexto) -> str:
    exp = ctx.exp
    observaciones = _leer_observaciones(exp)
    bloques, total_err = [], 0
    for o in observaciones:
        if o["estado"] == "descartada":
            continue
        r = ctx.checker.revisar_observacion(_campos_obs(o))
        hall = r.to_dict()["hallazgos"]
        total_err += sum(h["severidad"] == "error" for h in hall)
        bloques.append(f"### {o['id']} · {o['titulo']} ({o['estado']})\n{_formato_hallazgos(hall, False)}")
    cuerpo = "\n\n".join(bloques)
    exp.anexar_registro("revision", f"\n## Revisión de observaciones — {_fecha()}\n\n{cuerpo}\n")
    return (f"{cuerpo}\n\nTotal: {total_err} errores en {len(bloques)} observaciones activas. "
            f"Detalle guardado en revision.md." + ("\nSiguiente: `corregir-obs` para que el modelo corrija "
                                                   "solo lo señalado." if total_err else ""))


def accion_corregir_obs(ctx: Contexto, ids: list[str] | None = None) -> str:
    exp = ctx.exp
    observaciones = _leer_observaciones(exp)
    seleccion = {i.upper() for i in ids} if ids else None
    corregidas, sin_cambio = [], []
    for o in observaciones:
        if o["estado"] == "descartada" or (seleccion and o["id"] not in seleccion):
            continue
        r = ctx.checker.revisar_observacion(_campos_obs(o))
        if r.limpio:
            sin_cambio.append(o["id"])
            continue
        user = ("Corrige esta observación de auditoría. Mantén todos los hechos y cifras; corrige solo el "
                "estilo y completa campos vacíos SOLO si son deducibles del resto (si no, déjalos vacíos).\n\n"
                f"HALLAZGOS DEL VALIDADOR:\n{json.dumps(r.to_dict()['hallazgos'], ensure_ascii=False, indent=2)}\n\n"
                f"OBSERVACIÓN:\n{json.dumps(_campos_obs(o), ensure_ascii=False, indent=2)}")
        nueva = ctx.llm.completar_estructurado(f"corregir-obs-{o['id']}", ctx.system, user, Observacion,
                                               esfuerzo="low")
        verif = ctx.checker.revisar_observacion(nueva.model_dump())
        o.update(_campos_obs(_obs_a_dict(nueva, o["id"])))
        corregidas.append(f"{o['id']} ({'✔ verificada' if verif.limpio else '⚠ aún con hallazgos: revisar a mano'})")
    if corregidas:
        exp.escribir("observaciones", render_observaciones(observaciones, exp.proyecto), "corregir-obs")
    return (f"Corregidas: {', '.join(corregidas) or 'ninguna'}. Sin hallazgos: {', '.join(sin_cambio) or '—'}."
            + ("\nSe ha regenerado 01_observaciones.md (snapshot previo en historial/)." if corregidas else ""))


def accion_regenerar_obs(ctx: Contexto, ident: str) -> str:
    exp = ctx.exp
    observaciones = _leer_observaciones(exp)
    ident = ident.upper()
    if not ident.startswith("OBS-"):
        ident = f"OBS-{int(ident):02d}"
    o = next((x for x in observaciones if x["id"] == ident), None)
    if o is None:
        raise ExpedienteError(f"No existe {ident} en 01_observaciones.md.")
    if not o.get("notas", "").strip():
        raise ExpedienteError(f"{ident} no tiene «Notas del auditor». Escribe ahí qué quieres cambiar.")
    user = (f"{_contexto_proyecto(exp)}\n\n"
            "Rehaz esta observación siguiendo las indicaciones del auditor. Conserva lo que no se pida "
            "cambiar y apóyate solo en los papeles de trabajo.\n\n"
            f"INDICACIONES DEL AUDITOR:\n{o['notas']}\n\n"
            f"OBSERVACIÓN ACTUAL:\n{json.dumps(_campos_obs(o), ensure_ascii=False, indent=2)}\n\n"
            "`riesgo_soportado_por_evidencia`: true SOLO si el PT menciona explícitamente la severidad o el "
            "nivel de riesgo.\n\n"
            f"PAPELES DE TRABAJO:\n{_documentos_entrada(exp)}")
    nueva = ctx.llm.completar_estructurado(f"regenerar-{ident}", ctx.system, user, ObservacionExtraida)
    d = _obs_a_dict(nueva, ident)
    o.update(_campos_obs(d))
    o["riesgo_propuesto"] = d.get("riesgo_propuesto", False)
    o["estado"], o["notas"] = "propuesta", ""
    exp.escribir("observaciones", render_observaciones(observaciones, exp.proyecto), f"regenerar-{ident}")
    verif = ctx.checker.revisar_observacion(_campos_obs(o))
    return (f"{ident} regenerada (estado: propuesta; notas aplicadas y vaciadas). "
            f"{'✔ Sin hallazgos de estilo.' if verif.limpio else '⚠ Con hallazgos de estilo: ver revisar-obs.'}")


# ============================================================ 3. redactar informe
SECCIONES_INFORME = ("objetivo", "alcance", "contexto", "observaciones", "evaluacion", "proximos")


def accion_redactar(ctx: Contexto, forzar: bool = False, secciones: list[str] | None = None) -> str:
    exp = ctx.exp
    observaciones = _leer_observaciones(exp)
    aprobadas = [o for o in observaciones if o["estado"] == "aprobada"]
    if not aprobadas:
        raise ExpedienteError("No hay observaciones con `Estado: aprobada`. Aprueba al menos una "
                              "(edita el fichero o usa `aprobar OBS-01 ...` / `aprobar todas`).")
    # Una observación aprobada a mano cuyo nivel de riesgo sigue marcado como
    # «propuesto por el modelo» no ha sido validada: no entra en el informe.
    bloqueadas = [o for o in aprobadas if o.get("riesgo_propuesto")]
    aprobadas = [o for o in aprobadas if not o.get("riesgo_propuesto")]
    if bloqueadas and not aprobadas:
        raise ExpedienteError(
            "Todas las observaciones aprobadas tienen el nivel de riesgo «propuesto por el modelo, sin "
            "evidencia en PT»: valida el nivel (edita la línea o usa `aprobar OBS-XX`, que quita la coletilla). "
            f"Pendientes: {', '.join(o['id'] for o in bloqueadas)}.")
    existe = exp.existe("informe")
    if existe and not forzar and not secciones:
        raise ExpedienteError("02_informe.md ya existe y puede contener trabajo de varios días. Usa "
                              "--forzar para reescribirlo entero o --secciones para rehacer solo algunas "
                              "(objetivo, alcance, contexto, observaciones, evaluacion, proximos).")
    obs_json = json.dumps([_campos_obs(o) for o in aprobadas], ensure_ascii=False, indent=2)
    informe_actual = ""
    if existe and secciones:
        informe_actual = ("\n\nINFORME ACTUAL (rehaz SOLO las secciones indicadas; el resto devuélvelo "
                          "tal cual está):\n" + exp.leer("informe") + f"\n\nSECCIONES A REHACER: {', '.join(secciones)}")
    user = (f"{_contexto_proyecto(exp)}\n\n"
            "Redacta el texto del Resumen Ejecutivo del informe de auditoría interna a partir de las "
            "observaciones APROBADAS por el auditor y de los papeles de trabajo.\n"
            "- Objetivo y alcance: derívalos de los papeles de trabajo (pruebas realizadas, muestra, periodo).\n"
            "- Contexto: párrafo breve con las magnitudes del proceso que aparezcan en la fuente.\n"
            "- Observaciones: las aprobadas, en el mismo orden; puedes pulir la redacción pero no cambiar hechos, "
            "cifras, nivel de riesgo ni responsable, ni añadir o quitar observaciones.\n"
            "- Evaluación global: valoración de gobierno / gestión de riesgos / entorno de control en formato "
            "'Razonable|Mejorable|Deficiente — Impacto Alto|Medio|Bajo' y conclusión coherente con las observaciones.\n"
            "- Próximos pasos: plan de acción y seguimiento, sin inventar fechas que no consten.\n\n"
            f"OBSERVACIONES APROBADAS:\n{obs_json}\n\n"
            f"PAPELES DE TRABAJO:\n{_documentos_entrada(exp)}{informe_actual}")
    borrador = ctx.llm.completar_estructurado("redactar", ctx.system, user, BorradorInforme)
    datos = {
        "objetivo": borrador.objetivo, "alcance": borrador.alcance,
        "contexto": {"texto": borrador.contexto, "magnitudes": [[m.valor, m.etiqueta] for m in borrador.magnitudes]},
        "observaciones": [_obs_a_dict(o, f"OBS-{i:02d}") for i, o in enumerate(borrador.observaciones, 1)],
        "evaluacion_global": borrador.evaluacion_global.model_dump(),
        "proximos_pasos": borrador.proximos_pasos,
    }
    if existe and secciones:
        actual = parsear_informe(exp.leer("informe"))
        pedidas = {s.lower()[:4] for s in secciones}
        for clave, prefijo in (("objetivo", "obje"), ("alcance", "alca"), ("contexto", "cont"),
                               ("observaciones", "obse"), ("evaluacion_global", "eval"), ("proximos_pasos", "prox")):
            if prefijo not in pedidas:
                datos[clave] = actual[clave]
    nuevo = render_informe(datos, exp.proyecto)
    snap = exp.escribir("informe", nuevo, "redactar")
    hall = revisar_markdown(ctx.checker, nuevo)
    errores = sum(h["severidad"] == "error" for h in hall)
    msg = [f"Informe {'actualizado' if existe else 'redactado'} en {exp.archivo('informe').name} "
           f"con {len(datos['observaciones'])} observaciones."]
    if bloqueadas:
        msg.append("⚠ NO incluidas por tener el nivel de riesgo aún «propuesto por el modelo, sin evidencia en PT» "
                   "(valídalo con `aprobar OBS-XX` y vuelve a `redactar --secciones observaciones`): "
                   + ", ".join(f"{o['id']} ({o['nivel_riesgo']})" for o in bloqueadas))
    if snap:
        msg.append(f"Versión anterior guardada en historial/{snap.name}.")
    msg.append(f"Revisión determinista: {errores} errores, {len(hall) - errores} avisos"
               + (" — ejecuta `revisar` para el detalle y `corregir` para arreglarlos." if hall else " ✔"))
    msg.append("Siguiente: edita el informe con calma; cuando quieras, `revisar`, `aplicar-cambios` o `ppt`.")
    return "\n".join(msg)


# ============================================================ 4. revisar / corregir informe
def _hallazgos_informe(ctx: Contexto) -> tuple[str, list[dict]]:
    texto = ctx.exp.leer("informe")
    if not texto:
        raise ExpedienteError("No hay 02_informe.md. Ejecuta `redactar` primero.")
    return texto, revisar_markdown(ctx.checker, texto)


def accion_revisar(ctx: Contexto) -> str:
    texto, hall = _hallazgos_informe(ctx)
    errores = sum(h["severidad"] == "error" for h in hall)
    detalle = _formato_hallazgos(hall)
    ctx.exp.anexar_registro("revision", f"\n## Revisión del informe — {_fecha()}\n\n{detalle}\n")
    resumen = f"\n{errores} errores y {len(hall) - errores} avisos en 02_informe.md (detalle en revision.md)."
    if errores:
        resumen += "\nSiguiente: `corregir` reescribe solo los párrafos con errores y vuelve a validarlos."
    return detalle + resumen


def accion_corregir(ctx: Contexto, incluir_avisos: bool = False) -> str:
    exp = ctx.exp
    texto, hall = _hallazgos_informe(ctx)
    severidades = {"error", "aviso"} if incluir_avisos else {"error"}
    por_parrafo: dict[int, list[dict]] = {}
    for h in hall:
        if h["severidad"] in severidades:
            por_parrafo.setdefault(h["parrafo_linea"], []).append(h)
    if not por_parrafo:
        return "No hay párrafos que corregir (usa --avisos para incluir también las frases largas)."
    parrafos = dict(parrafos_con_lineas(texto))
    lote = []
    for i, (linea, hs) in enumerate(sorted(por_parrafo.items()), 1):
        lote.append({"id": i, "texto": parrafos[linea],
                     "hallazgos": [f"«{h['fragmento']}»: {h['mensaje']} Sugerencia: {h.get('sugerencia', '')}"
                                   for h in hs]})
    user = ("Reescribe cada párrafo corrigiendo exactamente los hallazgos indicados. Conserva el formato "
            "Markdown (etiquetas en negrita, viñetas), todos los hechos y cifras, y el sentido. Devuelve un "
            "párrafo por id.\n\n" + json.dumps(lote, ensure_ascii=False, indent=2))
    res = ctx.llm.completar_estructurado("corregir", ctx.system, user, Correcciones, esfuerzo="low")
    originales = {p["id"]: p["texto"] for p in lote}
    nuevo, aplicados, pendientes = texto, [], []
    for p in res.parrafos:
        orig = originales.get(p.id)
        if orig is None or orig not in nuevo:
            continue
        verif = ctx.checker.revisar_texto(re.sub(r"\*\*[^*]+?:\*\*\s*", "", p.texto))
        ok = not any(h.severidad == "error" for h in verif.hallazgos)
        nuevo = nuevo.replace(orig, p.texto.strip(), 1)
        (aplicados if ok else pendientes).append(p.id)
    snap = exp.escribir("informe", nuevo, "corregir")
    d = diff_texto(texto, nuevo, "02_informe.md")
    msg = [d, "", f"Párrafos reescritos: {len(aplicados) + len(pendientes)} de {len(lote)}."]
    if pendientes:
        msg.append(f"⚠ {len(pendientes)} párrafo(s) siguen con errores tras la reescritura: revisar a mano "
                   "(`revisar` para verlos).")
    if snap:
        msg.append(f"Snapshot previo: historial/{snap.name} (`deshacer` lo restaura).")
    return "\n".join(msg)


# ============================================================ 5. aplicar cambios (instrucciones)
def _num_cabecera(t: str) -> str | None:
    m = re.match(r"^(?:obs-)?0*(\d+)\b", t)
    return m.group(1) if m else None


def _rango_seccion(texto: str, seccion: str) -> tuple[int, int] | None:
    """Rango [inicio, fin) del bloque de la cabecera Markdown que mejor casa
    con `seccion` (p. ej. "### 3. Aprobador coincide…" o "Evaluación global").
    Si `seccion` lleva número (3., OBS-03) solo casan cabeceras con ese mismo
    número: dos observaciones con el mismo título se distinguen por él.
    None si no hay cabecera parecida (ratio < 0.6)."""
    objetivo = _norm_simple(re.sub(r"^#+\s*", "", seccion.strip()))
    objetivo_sin = re.sub(r"^(obs-\d+|\d+)\s*[.)·\-–:]?\s*", "", objetivo)
    if not objetivo:
        return None
    n_obj = _num_cabecera(objetivo)
    cabeceras = [(m.start(), len(m.group(1)), m.group(2)) for m in re.finditer(r"^(#+)\s+(.+)$", texto, re.M)]
    mejor, mejor_ratio = None, 0.0
    for i, (pos, nivel, titulo) in enumerate(cabeceras):
        t = _norm_simple(titulo)
        t_sin = re.sub(r"^(obs-\d+|\d+)\s*[.)·\-–:]?\s*", "", t)
        n_tit = _num_cabecera(t)
        if n_obj and n_tit and n_obj != n_tit:
            continue
        ratio = max(difflib.SequenceMatcher(None, t, objetivo).ratio(),
                    difflib.SequenceMatcher(None, t_sin, objetivo_sin).ratio())
        if objetivo_sin and (objetivo_sin in t_sin or t_sin in objetivo_sin):
            ratio = max(ratio, 0.9)
        if t == objetivo:
            ratio = 1.0
        if ratio > mejor_ratio:
            mejor, mejor_ratio = i, ratio
    if mejor is None or mejor_ratio < 0.6:
        return None
    pos, nivel, _ = cabeceras[mejor]
    fin = len(texto)
    for p2, n2, _ in cabeceras[mejor + 1:]:
        if n2 <= nivel:
            fin = p2
            break
    return pos, fin


def _norm_simple(s: str) -> str:
    import unicodedata
    nfkd = unicodedata.normalize("NFD", s.lower())
    return re.sub(r"\s+", " ", "".join(c for c in nfkd if unicodedata.category(c) != "Mn")).strip()


def _norm_aprox(s: str) -> str:
    """Normalización para la coincidencia aproximada: tildes, mayúsculas,
    espacios y comillas/guiones tipográficos. Nada más: un texto distinto
    (otra cifra, otra palabra) nunca se aproxima."""
    t = _norm_simple(s)
    return re.sub(r"[\"'«»“”‘’`]", "", t).replace("–", "-").replace("—", "-").strip(" .")


def _localizar(texto: str, fragmento: str, seccion: str = "") -> tuple[str | None, int, str]:
    """Localiza `fragmento` en `texto` y devuelve (fragmento_real, posición, motivo).
    `fragmento_real` es None si no se puede aplicar, con `motivo` explicando por qué:
    - sección indicada inexistente -> no se aplica (no se busca en todo el documento);
    - fragmento inexistente -> no se aplica (sin aproximaciones salvo diferencias
      de tildes/mayúsculas/espacios/comillas: igualdad tras normalizar);
    - fragmento repetido dentro del ámbito de búsqueda -> ambiguo, no se aplica."""
    frag = fragmento.strip()
    if not frag:
        return None, -1, "fragmento vacío"
    if seccion.strip():
        rango = _rango_seccion(texto, seccion)
        if rango is None:
            return None, -1, f"sección «{seccion.strip()}» no encontrada en el informe"
        ini, fin = rango
        ambito_desc = f"la sección «{seccion.strip()}»"
    else:
        ini, fin = 0, len(texto)
        ambito_desc = "el informe (no se indicó sección)"
    ambito = texto[ini:fin]

    for patron in (re.escape(frag), r"\s+".join(re.escape(t) for t in frag.split())):
        hits = list(re.finditer(patron, ambito))
        if len(hits) == 1:
            return hits[0].group(0), ini + hits[0].start(), "exacto"
        if len(hits) > 1:
            return None, -1, f"ambiguo: el texto aparece {len(hits)} veces en {ambito_desc}"

    # Aproximación solo por diferencias de tildes/mayúsculas/espacios/comillas
    candidatos: dict[tuple[str, int], None] = {}
    for m in re.finditer(r"[^\n]+", ambito):
        linea = m.group(0)
        candidatos[(linea.strip(), m.start() + (len(linea) - len(linea.lstrip())))] = None
        off = 0
        for frase in re.split(r"(?<=[.!?])\s+", linea):
            if frase.strip():
                pos_f = linea.find(frase, off)
                candidatos[(frase.strip(), m.start() + pos_f)] = None
                off = pos_f + len(frase)
    objetivo = _norm_aprox(frag)
    coincidencias = [(c, pos) for c, pos in candidatos if c and _norm_aprox(c) == objetivo]
    if len(coincidencias) == 1:
        c, pos = coincidencias[0]
        return c, ini + pos, "aproximado"
    if len(coincidencias) > 1:
        return None, -1, f"ambiguo: el texto (aproximado) aparece {len(coincidencias)} veces en {ambito_desc}"
    return None, -1, f"texto original no encontrado en {ambito_desc}"


def _sustituir_en(texto: str, real: str, pos: int, nuevo: str) -> str:
    return texto[:pos] + nuevo + texto[pos + len(real):]


def aplicar_plan(texto: str, plan: PlanCambios) -> tuple[str, list[dict]]:
    """Aplica los cambios EN ORDEN. Cada cambio se localiza en el texto ya
    modificado por los anteriores. Si dos cambios apuntan al mismo fragmento
    original (instrucciones contradictorias del transcript), el primero se
    aplica y el segundo se marca CONFLICTO con referencia al primero: nunca
    se pisa en silencio; la persona decide cuál prevalece."""
    resultado = []
    aplicados: list[tuple[int, str]] = []  # (nº de cambio, fragmento original normalizado)
    for i, c in enumerate(plan.cambios, 1):
        fila = {"seccion": c.seccion, "motivo": c.motivo, "estado": "", "detalle": ""}
        orig = _norm_simple(c.texto_original)
        if orig:
            previo = next((n for n, o in aplicados if o == orig or (len(orig) > 20 and (orig in o or o in orig))), None)
            real, pos, motivo = _localizar(texto, c.texto_original, c.seccion)
            if real is None and previo is not None:
                fila.update(estado="CONFLICTO", detalle=f"el fragmento ya fue modificado por el cambio {previo}; "
                                                        "revisar cuál de las dos instrucciones prevalece")
            elif real is None:
                fila.update(estado="NO APLICADO", detalle=motivo)
            else:
                texto = _sustituir_en(texto, real, pos, c.texto_nuevo.strip())
                fila["estado"] = "eliminado" if not c.texto_nuevo.strip() else (
                    "aplicado" if motivo == "exacto" else "aplicado (coincidencia aproximada)")
                aplicados.append((i, orig))
        elif c.insertar_tras.strip() and c.texto_nuevo.strip():
            real, pos, motivo = _localizar(texto, c.insertar_tras, c.seccion)
            if real is None:
                fila.update(estado="NO APLICADO", detalle=f"punto de inserción: {motivo}")
            else:
                texto = _sustituir_en(texto, real, pos, real + "\n\n" + c.texto_nuevo.strip())
                fila["estado"] = "insertado"
        else:
            fila.update(estado="NO APLICADO", detalle="cambio sin texto original ni punto de inserción")
        resultado.append(fila)
    return texto, resultado


def accion_aplicar_cambios(ctx: Contexto, solo_plan: bool = False) -> str:
    exp = ctx.exp
    instrucciones = exp.instrucciones_pendientes()
    if not instrucciones:
        raise ExpedienteError("03_instrucciones.md está vacío: pega debajo de `---` la transcripción o los "
                              "comentarios a aplicar.")
    texto = exp.leer("informe")
    if not texto:
        raise ExpedienteError("No hay 02_informe.md sobre el que aplicar cambios.")
    user = ("Un revisor (Gerente/Directora/reunión con el área) ha hecho comentarios sobre el informe. "
            "Conviértelos en cambios concretos sobre el texto actual.\n"
            "Reglas:\n"
            "- Cambios mínimos: sustituye solo el fragmento necesario; no reescribas lo que no se pide.\n"
            "- `seccion` es la cabecera literal (`## …` o `### N. …`) bajo la que está el fragmento.\n"
            "- `texto_original` debe ser una copia LITERAL y contigua del informe actual (misma puntuación, "
            "mismas etiquetas Markdown), de una frase a un párrafo. Nunca lo resumas. Si la misma línea se "
            "repite en varias observaciones (p. ej. `- Responsable: …`), indica la sección exacta.\n"
            "- Para añadir texto usa `insertar_tras` con un fragmento literal del informe.\n"
            "- Si una instrucción requiere información que no está en el informe ni en los comentarios, o "
            "contradice los hechos, NO la apliques: ponla en `pendientes` explicando qué falta.\n"
            "- Respeta las reglas de estilo en todo texto nuevo.\n\n"
            f"COMENTARIOS / INSTRUCCIONES:\n{instrucciones}\n\n"
            f"INFORME ACTUAL (02_informe.md):\n{texto}")
    plan = ctx.llm.completar_estructurado("aplicar-cambios", ctx.system, user, PlanCambios)
    nuevo, filas = aplicar_plan(texto, plan)

    lineas = [f"Plan de cambios ({len(plan.cambios)}):"]
    for i, (c, f) in enumerate(zip(plan.cambios, filas), 1):
        lineas.append(f"  {i}. [{f['estado'] or 'previsto'}] {c.seccion} — {c.motivo}")
        if f["detalle"]:
            lineas.append(f"       {f['detalle']}")
    if plan.pendientes:
        lineas.append("Pendientes (no aplicables automáticamente):")
        lineas += [f"  • {p}" for p in plan.pendientes]
    if solo_plan:
        lineas.append("\n(--solo-plan: no se ha modificado el informe ni vaciado 03_instrucciones.md)")
        return "\n".join(lineas)

    hall = revisar_markdown(ctx.checker, nuevo)
    errores = sum(h["severidad"] == "error" for h in hall)
    snap = exp.escribir("informe", nuevo, "aplicar-cambios")
    registro = [f"\n## Cambios aplicados — {_fecha()}\n", "Instrucciones recibidas:\n",
                "> " + instrucciones.replace("\n", "\n> "), ""]
    for i, (c, f) in enumerate(zip(plan.cambios, filas), 1):
        registro.append(f"{i}. **[{f['estado']}]** {c.seccion} — {c.motivo}" + (f" ({f['detalle']})" if f["detalle"] else ""))
        if c.texto_original.strip():
            registro.append(f"   - Antes: {c.texto_original.strip()}")
        registro.append(f"   - Después: {c.texto_nuevo.strip() or '(eliminado)'}")
    if plan.pendientes:
        registro.append("\nPendientes:")
        registro += [f"- {p}" for p in plan.pendientes]
    exp.anexar_registro("cambios", "\n".join(registro) + "\n")
    exp.vaciar_instrucciones()

    n_conf = sum(f["estado"] == "CONFLICTO" for f in filas)
    lineas += ["", diff_texto(texto, nuevo, "02_informe.md"), "",
               (f"⚠ {n_conf} cambio(s) en CONFLICTO con otro anterior: revisar en cambios_aplicados.md.\n" if n_conf else "") +
               f"Aplicados {sum(f['estado'].startswith(('aplicado', 'insertado', 'eliminado')) for f in filas)} "
               f"de {len(filas)} cambios. Registro en cambios_aplicados.md; 03_instrucciones.md vaciado "
               f"(lo pegado queda en historial/).",
               f"Revisión determinista tras los cambios: {errores} errores, {len(hall) - errores} avisos."]
    if snap:
        lineas.append(f"Snapshot previo: historial/{snap.name} (`deshacer` lo restaura).")
    return "\n".join(lineas)


# ============================================================ 6. entregables
def accion_ppt(exp: Expediente) -> str:
    from .ppt_builder import construir_desde_datos
    texto = exp.leer("informe")
    if not texto:
        raise ExpedienteError("No hay 02_informe.md. Ejecuta `redactar` primero.")
    datos = parsear_informe(texto)
    datos["proyecto"] = {"nombre": exp.proyecto.get("nombre", ""), "referencia": exp.referencia,
                         "fecha": exp.proyecto.get("fecha", ""),
                         "distribucion": exp.proyecto.get("distribucion", [])}
    if not datos["observaciones"]:
        raise ExpedienteError("No se ha reconocido ninguna observación en 02_informe.md "
                              "(sección `## Principales observaciones` con bloques `### N. Título`).")
    ruta = construir_desde_datos(datos, exp.ruta_ppt())
    return f"Resumen Ejecutivo generado: {ruta} ({len(datos['observaciones'])} observaciones)."


# ============================================================ 7. historial
def accion_deshacer(exp: Expediente, clave: str = "informe") -> str:
    origen = exp.restaurar(clave)
    return f"{exp.archivo(clave).name} restaurado desde historial/{origen.name} (la versión que había se guardó también en historial/)."


def accion_diff(exp: Expediente, clave: str = "informe") -> str:
    versiones = exp.historial(clave)
    if not versiones:
        return f"No hay versiones anteriores de {exp.archivo(clave).name}."
    antes = versiones[-1].read_text(encoding="utf-8")
    d = diff_texto(antes, exp.leer(clave), exp.archivo(clave).name)
    return (f"Diferencias respecto a historial/{versiones[-1].name}:\n\n{d}" if d
            else f"Sin diferencias respecto a historial/{versiones[-1].name}.")


def accion_historial(exp: Expediente) -> str:
    lineas = []
    for clave in ("observaciones", "informe", "instrucciones"):
        vs = exp.historial(clave)
        if vs:
            lineas.append(f"{exp.archivo(clave).name}: {len(vs)} versiones")
            lineas += [f"    {v.name}" for v in vs[-8:]]
    return "\n".join(lineas) or "historial/ vacío."


# ============================================================ 8. estado
def estado_expediente(exp: Expediente, checker: StyleChecker | None = None) -> dict:
    e: dict = {"referencia": exp.referencia, "nombre": exp.proyecto.get("nombre", ""),
               "entrada": [p.name for p in exp.ficheros_entrada()],
               "observaciones": None, "informe": None, "instrucciones_pendientes": bool(exp.instrucciones_pendientes()),
               "ppt": None, "siguiente": ""}
    if exp.existe("observaciones"):
        obs = parsear_observaciones(exp.leer("observaciones"))
        e["observaciones"] = {k: sum(o["estado"] == k for o in obs) for k in ("propuesta", "aprobada", "descartada")}
        e["observaciones"]["total"] = len(obs)
        e["observaciones"]["con_notas"] = [o["id"] for o in obs if o.get("notas", "").strip()]
    if exp.existe("informe"):
        texto = exp.leer("informe")
        hall = revisar_markdown(checker, texto) if checker else []
        e["informe"] = {"errores": sum(h["severidad"] == "error" for h in hall),
                        "avisos": sum(h["severidad"] == "aviso" for h in hall),
                        "modificado": datetime.fromtimestamp(exp.archivo("informe").stat().st_mtime),
                        "versiones": len(exp.historial("informe"))}
    ppt = exp.ruta_ppt()
    if ppt.exists():
        e["ppt"] = {"ruta": ppt, "desactualizado": exp.existe("informe") and
                    ppt.stat().st_mtime < exp.archivo("informe").stat().st_mtime}

    if not e["entrada"]:
        e["fase"], e["siguiente"] = "0 · Sin entrada", f"Copia los papeles de trabajo de Pentana a {exp.ruta / 'entrada'}"
    elif e["observaciones"] is None:
        e["fase"], e["siguiente"] = "1 · Entrada lista", "`extraer` para que el modelo proponga observaciones y recomendaciones"
    elif e["informe"] is None:
        e["fase"] = "2 · Observaciones en revisión"
        e["siguiente"] = ("`redactar` para escribir el informe con las aprobadas"
                          if e["observaciones"]["aprobada"] else
                          "Lee 01_observaciones.md, edita y marca `Estado: aprobada` (o `aprobar ...`)")
    else:
        e["fase"] = "3 · Informe en redacción"
        if e["instrucciones_pendientes"]:
            e["siguiente"] = "`aplicar-cambios`: hay instrucciones pendientes en 03_instrucciones.md"
        elif e["informe"]["errores"]:
            e["siguiente"] = f"`corregir`: el informe tiene {e['informe']['errores']} errores de vocabulario/estilo"
        elif e["ppt"] is None or e["ppt"]["desactualizado"]:
            e["siguiente"] = "`ppt` para generar (o regenerar) el Resumen Ejecutivo"
        else:
            e["fase"], e["siguiente"] = "4 · Entregable generado", "Seguir editando el informe y regenerar `ppt`, o cerrar."
    return e


def accion_estado(exp: Expediente, checker: StyleChecker | None = None, llm_desc: str = "") -> str:
    e = estado_expediente(exp, checker)
    L = [f"Expediente {e['referencia']} · {e['nombre']}", f"  Carpeta: {exp.ruta}",
         f"  Fase: {e['fase']}"]
    if llm_desc:
        L.append(f"  LLM: {llm_desc}")
    L.append(f"  Entrada: {len(e['entrada'])} documento(s)" + (f" — {', '.join(e['entrada'])}" if e["entrada"] else ""))
    if e["observaciones"]:
        o = e["observaciones"]
        L.append(f"  Observaciones: {o['total']} (aprobadas {o['aprobada']}, propuestas {o['propuesta']}, "
                 f"descartadas {o['descartada']})" + (f"; con notas para regenerar: {', '.join(o['con_notas'])}" if o["con_notas"] else ""))
    if e["informe"]:
        i = e["informe"]
        L.append(f"  Informe: modificado {i['modificado']:%Y-%m-%d %H:%M}, {i['versiones']} versiones en historial, "
                 f"{i['errores']} errores / {i['avisos']} avisos de estilo")
    L.append(f"  Instrucciones pendientes: {'sí' if e['instrucciones_pendientes'] else 'no'}")
    if e["ppt"]:
        L.append(f"  PPT: {e['ppt']['ruta'].name}" + (" (anterior a la última edición del informe)" if e["ppt"]["desactualizado"] else ""))
    L.append(f"  ▶ Siguiente: {e['siguiente']}")
    return "\n".join(L)
