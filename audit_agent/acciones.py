"""
Acciones del flujo de trabajo sobre un expediente.

Cada acción es una función `accion_x(exp, ...) -> str` que devuelve un
resumen imprimible; la CLI y el menú interactivo solo las envuelven.

Flujo previsto (no es lineal: se vuelve atrás cuando haga falta):

    nuevo ─► entrada/ (papel de trabajo final + contexto + anexos)
          ─► redactar-contexto ─► [auditor valida introducción y resumen ejecutivo]
          ─► extraer ─► [auditor edita/aprueba 01_conclusiones.md] ─► recomendar
          ─► redactar-conclusiones ─► [auditor edita 02_informe.md durante días]
             ├─ revisar / corregir       (vocabulario y estilo)
             ├─ aplicar-cambios          (desde 03_instrucciones.md)
             ├─ diff / deshacer / historial
          ─► ppt ─► archivar

Principio: el modelo propone, la persona decide. Antes de sobreescribir un
fichero editado por una persona, siempre queda snapshot en historial/.
"""
from __future__ import annotations

import difflib
import hashlib
import json
import re
import zipfile
from datetime import datetime
from pathlib import Path

from . import __version__
from .esquemas import (AnalisisReunion, Conclusion, ConclusionExtraida, ContextoInforme, Correcciones, InformeCondensado,
                       ExtraccionConclusiones, PlanCambios, RecomendacionFormateada,
                       RecomendacionPropuesta)
from .expediente import Expediente, ExpedienteError
from .formato_md import (COLETILLA_RIESGO_PROPUESTO, normalizar_nivel, normalizar_tipo,
                         parrafos_con_lineas, parsear_conclusiones, parsear_informe,
                         render_conclusiones, render_informe, textos_informe)
from .lectores import EXTENSIONES as EXT_ENTRADA, Documento, LecturaError, leer as leer_documento
from .llm import ClienteLLM
from .style_checker import StyleChecker, reglas_como_texto, revisar_markdown

RAIZ = Path(__file__).resolve().parent.parent
CONFIG_DEFECTO = RAIZ / "config" / "estilo.yaml"
EJEMPLO_CONCLUSION = RAIZ / "config" / "ejemplo_conclusion.md"


def _ejemplo_conclusion() -> str:
    if not EJEMPLO_CONCLUSION.exists():
        return ""
    lineas = []
    for l in EJEMPLO_CONCLUSION.read_text(encoding="utf-8").splitlines():
        if l.startswith("## "):
            lineas.append(f"Título: {l[3:].strip()}")
        elif not l.startswith(("#", ">")):
            lineas.append(l)
    texto = "\n".join(lineas).strip()
    return ("\n\nEJEMPLO DE REFERENCIA (registro, estructura y nivel de detalle esperados para UNA prueba; sus cifras y "
            "nombres son de OTRA auditoría y no deben reutilizarse):\n" + texto)

MAX_CHARS_ENTRADA = 300_000    # total enviado al modelo (gpt-5-mini admite más, pero el coste crece)
MAX_CHARS_DOCUMENTO = 150_000  # tope por documento: ninguno puede dejar sin sitio a los demás

SYSTEM_BASE = """Eres un auditor interno senior del Departamento de Auditoría Interna y redactas informes de auditoría
para Dirección. Registro calibrado con informes aprobados (docs/ESTILO_INFORMES.md):
- Las actuaciones del equipo auditor se narran en PRIMERA PERSONA DEL PLURAL: «hemos revisado», «hemos
  identificado», «durante nuestra revisión», «validamos», «confirmamos», «destacamos», «consideramos». Los
  hechos y el «deber ser» del control se enuncian en impersonal («se ha identificado», «debe apoyarse en»).
- Formal y sobrio, orientado a proceso y control, nunca a personas. Sin absolutos ni juicios de valor: la
  severidad se expresa con la escala de riesgo (Crítico/Alto/Medio/Bajo).
- Cuantificado: cifras, porcentajes, importes, fechas, periodos, sistemas y muestras del papel de trabajo,
  integrados en la prosa («En concreto, durante 2024, el 1,8 % de…»). NUNCA inventes datos, normas ni causas:
  campo vacío o «no ha sido posible cuantificar» antes que inventar.
- Patrón de una conclusión: (1) el «deber ser» del control; (2) lo identificado («Durante nuestra revisión
  hemos identificado…»), con viñetas «/» si son varias debilidades; (3) datos y evidencia; (4) efecto y riesgo
  («lo que genera…», «pudiendo derivar en…»); (5) materialización y factores mitigantes («Respecto a la
  materialización, …», «Cabe destacar que existen factores mitigantes, como: …»).
- Conectores propios: «Durante nuestra revisión», «En concreto», «Cabe destacar», «Por otro lado», «Asimismo»,
  «No obstante», «Sin embargo», «Por último», «Respecto a».
- Terminología: observación/conclusión, debilidad, deficiencia de control, incidencia, aspecto de mejora,
  riesgo, control mitigante, materialización, plan de acción, recomendación, sugerencia de mejora, área
  responsable, plazo. «Grupo ITX», «la Compañía».
- Recomendaciones en infinitivo, concretas y accionables («Implantar…», «Definir…», «Establecer…»,
  «Revisar…»), una por párrafo, con sub-viñetas «_» si tienen varios puntos.
- Frases claras; se admiten oraciones largas bien puntuadas. Respondes en español, en el formato
  estructurado solicitado.

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


def _cargar_entrada(exp: Expediente, accion: str, carpetas: tuple[str, ...] = ("contexto", "papeles_trabajo"),
                    requerir: str = "papeles_trabajo") -> list[Documento]:
    """Lee las carpetas de documentos indicadas con la capa de lectores y deja
    en trazas/ qué lector se usó y el texto normalizado exacto que se envía al
    modelo (auditoría de la fidelidad de la lectura). `requerir` es la carpeta
    que no puede estar vacía."""
    docs = []
    for carpeta in carpetas:
        docs += exp.leer_documentos(carpeta)
    if requerir and not any(d.carpeta == requerir for d in docs):
        raise ExpedienteError(f"No hay documentos en {exp.ruta / requerir} (formatos: {', '.join(EXT_ENTRADA)}).")
    cupo = _presupuesto(docs)
    exp.trazar(f"{accion}-entrada", {
        "fecha": datetime.now().isoformat(timespec="seconds"), "accion": accion,
        "documentos": [{"carpeta": d.carpeta, "nombre": d.nombre, "lector": d.lector, "avisos": d.avisos,
                        "caracteres": len(d.texto), "caracteres_enviados": cupo[i],
                        "texto_normalizado": d.texto[:cupo[i]]} for i, d in enumerate(docs)]})
    return docs


ETIQUETA_CARPETA = {"contexto": "CONTEXTO DE LA AUDITORÍA", "papeles_trabajo": "PAPEL DE TRABAJO"}


def _presupuesto(docs: list[Documento]) -> dict[int, int]:
    """Caracteres de cada documento que se envían al modelo: reparto justo del
    total (MAX_CHARS_ENTRADA) con tope por documento (MAX_CHARS_DOCUMENTO), dando
    prioridad a los papeles de trabajo sobre el contexto. Así un Excel de datos
    enorme no deja fuera a la prueba del siguiente fichero (caso real)."""
    pt = [i for i, d in enumerate(docs) if d.carpeta == "papeles_trabajo"]
    ctx = [i for i in range(len(docs)) if i not in pt]
    reserva_ctx = min(sum(len(docs[i].texto) for i in ctx), MAX_CHARS_ENTRADA // 4)   # el contexto nunca se queda a cero
    cupo = _repartir(docs, pt, MAX_CHARS_ENTRADA - reserva_ctx)
    cupo.update(_repartir(docs, ctx, MAX_CHARS_ENTRADA - sum(cupo.values())))
    return cupo


def _repartir(docs: list[Documento], indices: list[int], presupuesto: int) -> dict[int, int]:
    """Reparto justo de `presupuesto` entre `indices`: los que caben enteros (o en
    su tope) lo hacen; el resto se reparte a partes iguales."""
    restante, pendientes, cupo = presupuesto, list(indices), {}
    while pendientes:
        cuota = restante // len(pendientes)
        cortos = [i for i in pendientes if min(len(docs[i].texto), MAX_CHARS_DOCUMENTO) <= cuota]
        if not cortos:
            for i in pendientes:
                cupo[i] = max(cuota, 0)
            break
        for i in cortos:
            cupo[i] = min(len(docs[i].texto), MAX_CHARS_DOCUMENTO)
            restante -= cupo[i]
        pendientes = [i for i in pendientes if i not in cupo]
    return cupo


def _texto_entrada(docs: list[Documento]) -> str:
    """Documentos agrupados por carpeta, con cabecera que dice qué es cada uno y
    cada uno recortado a su cupo (`_presupuesto`), marcando el recorte."""
    cupo = _presupuesto(docs)
    partes = []
    for carpeta in ("contexto", "papeles_trabajo", ""):
        grupo = [(i, d) for i, d in enumerate(docs) if (d.carpeta or "") == carpeta]
        if not grupo:
            continue
        if carpeta:
            partes.append(f"########## {ETIQUETA_CARPETA[carpeta]} ##########")
        for i, d in grupo:
            texto = d.texto
            if cupo[i] < len(texto):
                texto = texto[:cupo[i]] + (f"\n[... documento recortado: se envían {cupo[i]:,} de {len(texto):,} "
                                          "caracteres; el resto suele ser hojas de datos ...]").replace(",", ".")
            partes.append(f"===== DOCUMENTO: {d.nombre} (lector: {d.lector}) =====\n{texto.strip()}\n")
    return "\n".join(partes)


def _avisos_entrada(docs: list[Documento]) -> list[str]:
    """Avisos para el auditor: documentos recortados y avisos de lectura (hojas de datos)."""
    cupo = _presupuesto(docs)
    avisos = []
    for i, d in enumerate(docs):
        if cupo[i] < len(d.texto):
            avisos.append(f"⚠ {d.nombre}: enviado recortado ({cupo[i]:,} de {len(d.texto):,} caracteres). Si el fichero "
                          "tiene varias pruebas o la narrativa va al final, sepáralas en ficheros distintos o quita hojas "
                          "de datos.".replace(",", "."))
        for a in d.avisos:
            avisos.append(f"· {d.nombre}: {a}")
    return avisos


_RE_PRUEBA = re.compile(r"(?m)^\s*(\d{1,2}\.\d{1,2})\.?\s+([A-ZÁÉÍÓÚÑ][A-ZÁÉÍÓÚÑ0-9 ,/()\-–—:]{10,})\s*$")


def _pruebas_en(docs: list[Documento]) -> dict[str, str]:
    """Pruebas numeradas («2.11. PROCESO DE …») que aparecen en los papeles de
    trabajo tal como se envían: {código: título}."""
    cupo = _presupuesto(docs)
    pruebas: dict[str, str] = {}
    for i, d in enumerate(docs):
        if d.carpeta == "papeles_trabajo":
            for m in _RE_PRUEBA.finditer(d.texto[:cupo[i]]):
                pruebas.setdefault(m.group(1), m.group(2).strip())
    return pruebas


def _resumen_entrada(docs: list[Documento]) -> str:
    return ", ".join(f"{d.nombre} [{d.carpeta or 'entrada'}, {d.lector}]" for d in docs)


def _documentos_entrada(exp: Expediente, accion: str = "lectura") -> str:
    return _texto_entrada(_cargar_entrada(exp, accion))


def _conc_a_dict(c: Conclusion, ident: str, estado: str = "propuesta", notas: str = "") -> dict:
    d = c.model_dump()
    d["nivel_riesgo"] = normalizar_nivel(d["nivel_riesgo"])
    d["tipo"] = normalizar_tipo(d.get("tipo", "recomendacion"))
    d.update({"id": ident, "estado": estado, "notas": notas})
    soportado = d.pop("riesgo_soportado_por_evidencia", None)
    d.pop("recomendacion_del_pt", None)
    if isinstance(c, ConclusionExtraida):
        # Nivel estimado por el modelo sin evidencia en el PT -> coletilla visible
        d["riesgo_propuesto"] = bool(d["nivel_riesgo"]) and not soportado
    return d


def _campos_conc(c: dict) -> dict:
    return {k: c.get(k, "") for k in Conclusion.model_fields}


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


def _leer_conclusiones(exp: Expediente) -> list[dict]:
    if not exp.existe("conclusiones"):
        raise ExpedienteError("Todavía no hay 01_conclusiones.md. Ejecuta `extraer` primero.")
    return parsear_conclusiones(exp.leer("conclusiones"))


def _normalizar_id(ident: str) -> str:
    ident = ident.strip().upper()
    m = re.match(r"^(?:C|OBS)-?0*(\d+)$", ident) or re.match(r"^0*(\d+)$", ident)
    return f"C-{int(m.group(1)):02d}" if m else ident


def _palabras(texto: str) -> set[str]:
    import unicodedata
    t = unicodedata.normalize("NFD", texto.lower())
    t = "".join(ch for ch in t if unicodedata.category(ch) != "Mn")
    return {w for w in re.findall(r"[a-z0-9€%]{4,}", t)}


def conserva_base(original: str, formateada: str, umbral: float = 0.85) -> bool:
    """Comprobación determinista de que un texto «formateado» conserva la base
    del original: proporción de palabras de contenido del original presentes
    en la versión formateada."""
    base = _palabras(original)
    if not base:
        return True
    return len(base & _palabras(formateada)) / len(base) >= umbral


def _fecha() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M")


# ============================================================ 1. contexto del informe (introducción + resumen)
def accion_redactar_contexto(ctx: Contexto, secciones: list[str] | None = None, forzar: bool = False) -> str:
    """Genera Introducción y Resumen ejecutivo a partir de entrada/ (papel de
    trabajo final, contexto de la auditoría, anexos). Si ya hay conclusiones
    aprobadas, el resumen se apoya en ellas. Conserva el resto del informe."""
    exp = ctx.exp
    actual = parsear_informe(exp.leer("informe")) if exp.existe("informe") else {}
    pedidas = {s.lower()[:5] for s in (secciones or ["introduccion", "resumen"])}
    ya_hay = bool(actual.get("introduccion") or actual.get("resumen_ejecutivo"))
    if ya_hay and not forzar and not secciones:
        raise ExpedienteError("02_informe.md ya tiene introducción/resumen (pueden estar validados por el auditor). "
                              "Usa --forzar para regenerarlos o --secciones introduccion|resumen para rehacer solo una.")
    aprobadas = []
    if exp.existe("conclusiones"):
        aprobadas = [c for c in parsear_conclusiones(exp.leer("conclusiones")) if c["estado"] == "aprobada"]
    docs = _cargar_entrada(exp, "redactar-contexto")
    conclusiones_txt = ("\n\nCONCLUSIONES YA VALIDADAS POR EL AUDITOR (el resumen ejecutivo debe reflejarlas):\n"
                        + json.dumps([{k: c.get(k, "") for k in ("titulo", "tipo", "prueba", "incidencia", "consecuencias",
                                                                  "recomendacion", "nivel_riesgo")} for c in aprobadas],
                                     ensure_ascii=False, indent=2)) if aprobadas else ""
    textos = textos_informe()
    anio = (re.search(r"(20\d{2})", str(exp.proyecto.get("fecha", ""))) or [None, str(datetime.now().year)])[1]
    plan = textos["plan_auditoria"].format(anio=anio)
    user = (f"{_contexto_proyecto(exp)}\n\n"
            "Redacta la INTRODUCCIÓN y el RESUMEN EJECUTIVO del informe de auditoría interna a partir de los "
            "documentos de entrada, con la estructura de los informes aprobados del departamento. Los documentos de "
            "CONTEXTO DE LA AUDITORÍA (design thinking, planificación, motivo, riesgos, alcance previsto, magnitudes) "
            "son la fuente principal de Contexto, Objetivo, Riesgos a cubrir, Alcance y Principales magnitudes; el "
            "PAPEL DE TRABAJO aporta las pruebas realizadas y las conclusiones. Si no hay contexto, usa solo el PT.\n"
            "INTRODUCCIÓN (Markdown): empieza con este párrafo literal: «" + plan + "». Después, bloques con etiqueta "
            "en negrita: **Contexto:** (por qué se hace la auditoría, situación del proceso); **Objetivo de la "
            "auditoría:** (una frase, seguida de «Entre otros, los principales aspectos que se han revisado están "
            "relacionados con:» y una viñeta por aspecto/prueba); **Riesgos a cubrir:** (riesgos que motivan la "
            "revisión); **Alcance de la auditoría:** (sistemas, mercados, procesos y periodo); **Principales "
            "magnitudes:** SOLO si en la fuente hay cifras del proceso (una viñeta «cifra — concepto» por magnitud; "
            "omite el bloque si no las hay). Termina con este párrafo literal: «" + textos["normas"] + "». Omite lo "
            "que no conste (nunca escribas «no consta»).\n"
            "RESUMEN EJECUTIVO (Markdown): (1) párrafo de contexto (qué hace el área, iniciativas en curso); (2) "
            "valoración general del control, con el patrón «A pesar de …, no se han detectado deficiencias de control "
            "significativas. No obstante, se han identificado determinadas mejoras/debilidades que se detallan a "
            "continuación:» o su contrario si las incidencias son relevantes; (3) una viñeta «/ » por conclusión "
            "(una o dos frases: debilidad + efecto), en primera persona del plural cuando narre actuaciones del "
            "equipo, variando el arranque de cada viñeta (no repitas «Durante nuestra revisión hemos identificado» en "
            "todas: empieza por la debilidad, el proceso o el efecto); (4) párrafo final de valoración (madurez por ámbito si procede y "
            "referencia a recomendaciones abiertas si consta). Solo párrafos y viñetas: sin subtítulos ni etiquetas "
            "(«Contexto», «Valoración»…). Sin reproducir campos uno a uno ni copiar recomendaciones completas; sin "
            "inventar cifras.\n"
            "EVALUACIÓN GLOBAL: uno de " + " / ".join(textos["escala_evaluacion_global"]) + ", coherente con el "
            "resumen; vacío si la evidencia no permite sostenerla.\n"
            "EXTENSIÓN: cada bloque de la introducción y cada viñeta del resumen deben caber en su diapositiva: "
            "respeta la extensión orientativa del sistema; concreto y sin redundancias, sin omitir hechos ni cifras.\n\n"
            f"DOCUMENTOS DE ENTRADA:\n{_texto_entrada(docs)}{conclusiones_txt}")
    res = ctx.llm.completar_estructurado("redactar-contexto", ctx.system, user, ContextoInforme)
    datos = {"introduccion": actual.get("introduccion", ""), "resumen_ejecutivo": actual.get("resumen_ejecutivo", ""),
             "evaluacion_global": actual.get("evaluacion_global", ""),
             "conclusiones": actual.get("conclusiones", []), "sugerencias": actual.get("sugerencias", [])}
    if "intro" in pedidas:
        datos["introduccion"] = res.introduccion
    if "resum" in pedidas:
        datos["resumen_ejecutivo"] = res.resumen_ejecutivo
        datos["evaluacion_global"] = res.evaluacion_global
    snap = exp.escribir("informe", render_informe(datos, exp.proyecto), "redactar-contexto")
    hall = revisar_markdown(ctx.checker, exp.leer("informe"))
    errores = sum(h["severidad"] == "error" for h in hall)
    n_ctx = sum(d.carpeta == "contexto" for d in docs)
    msg = [f"Introducción y resumen ejecutivo {'actualizados' if ya_hay else 'redactados'} en {exp.archivo('informe').name}"
           + (f" (con {len(aprobadas)} conclusiones validadas como base del resumen)." if aprobadas else
              f" a partir de {n_ctx} documento(s) de contexto y {len(docs) - n_ctx} papel(es) de trabajo.")]
    if not n_ctx:
        msg.append("Sin documentos en contexto/: la introducción se ha redactado solo con el papel de trabajo. Si tienes "
                   "design thinking o memorando de planificación, déjalo en contexto/ y repite con --forzar.")
    msg.extend(_avisos_entrada(docs))
    if snap:
        msg.append(f"Versión anterior en historial/{snap.name}.")
    msg.append(f"Revisión determinista: {errores} errores, {len(hall) - errores} avisos" + (" ✔" if not hall else "."))
    msg.append("Siguiente: léelos y edítalos hasta que encajen; después `extraer` para pasar a las conclusiones.")
    return "\n".join(msg)


# ============================================================ 2. extraer conclusiones
def accion_extraer(ctx: Contexto, forzar: bool = False) -> str:
    exp = ctx.exp
    if exp.existe("conclusiones") and not forzar:
        raise ExpedienteError("01_conclusiones.md ya existe y puede contener trabajo del auditor. "
                              "Usa --forzar para regenerarlo (se guarda snapshot en historial/).")
    campos = "\n".join(f"- {k}: {v.description}" for k, v in ConclusionExtraida.model_fields.items())
    docs = _cargar_entrada(exp, "extraer")
    user = (f"{_contexto_proyecto(exp)}\n\n"
            "Los documentos de CONTEXTO DE LA AUDITORÍA (si los hay) solo sirven para entender el motivo y el alcance: "
            "NO generan conclusiones. El PAPEL DE TRABAJO contiene el papel de trabajo final de la auditoría: una o varias PRUEBAS "
            "numeradas (p. ej. «2.11. …»), cada una con CONTEXTO, OBJETIVO, PRUEBAS REALIZADAS (apartados a), b)…) y "
            "CONCLUSIONES, donde se indica si la prueba se concluye CON INCIDENCIAS o sin ellas.\n"
            "Recorre TODAS las pruebas de TODOS los documentos: cada fichero de PAPEL DE TRABAJO suele ser una prueba "
            "distinta (su hoja «Memo» lleva el número y el título, p. ej. «6.2. REVISIÓN DEL CÁLCULO…», y las demás hojas "
            "son datos de soporte, a veces recortados). Solo las concluidas CON INCIDENCIAS generan conclusiones; "
            "lista las demás en `pruebas_sin_incidencia`. Ninguna prueba puede quedar sin aparecer en uno u otro sitio.\n"
            "GRANULARIDAD: por defecto, UNA conclusión por prueba, que SINTETIZA su bloque CONCLUSIONES (todas sus "
            "viñetas) en un único apartado. Solo genera varias conclusiones para una prueba si su bloque de "
            "conclusiones recoge incidencias claramente independientes que requieran recomendaciones distintas. "
            "Las debilidades técnicas descritas en el desarrollo de la prueba no son conclusiones por sí mismas: son "
            "los detalles descriptivos que soportan la conclusión.\n"
            "Esquema de cada conclusión:\n"
            f"{campos}\n\n"
            "Reglas:\n"
            "- Cada conclusión se presenta después en una diapositiva con esta lectura: título (frase nominal "
            "específica de la debilidad, p. ej. «Elevado uso de accesos de emergencia con permisos privilegiados»); "
            "cuerpo en prosa (`incidencia`: primero el «deber ser» del control en impersonal y después lo identificado "
            "—«Durante nuestra revisión hemos identificado…»—, con viñetas «/» si son varias debilidades; "
            "`causa_raiz`: por qué, 1 párrafo); una caja «detalles descriptivos de la situación anterior» "
            "(`como_se_ha_llegado`: viñetas con los datos concretos del PT: volúmenes, importes, muestras, periodos, "
            "sistemas, casuísticas); y un párrafo de cierre (`consecuencias`: efecto y riesgo que genera, "
            "materialización —«Respecto a la materialización, …»— y factores mitigantes si constan, y si se ha "
            "podido cuantificar). Redacta cada campo para ese uso; no inventes cifras.\n"
            "- `area`, `responsable`, `plazo`: solo si el PT los indica. `referencia_recomendacion`: código de la "
            "recomendación abierta a la que se remite (p. ej. TMSCIIF-10), si consta.\n"
            "- `recomendacion`: SOLO si el PT la contiene o referencia (p. ej. una recomendación abierta de otra "
            "auditoría); cópiala literal y marca `recomendacion_del_pt`=true. Si una recomendación se referencia a "
            "nivel de prueba, asígnala ÚNICAMENTE a la(s) conclusión(es) cuya incidencia cubre directamente; no la "
            "repitas por defecto en todas. Las demás quedan vacías (el auditor o `recomendar` las completarán).\n"
            "- `tipo`: 'recomendacion' si requiere recomendación y plan de acción; 'sugerencia' si es una mejora "
            "menor sin plan de acción.\n"
            "- `nivel_riesgo`: propón Alto/Medio/Bajo por impacto y probabilidad (el auditor lo validará); "
            "`riesgo_soportado_por_evidencia` true SOLO si el PT menciona explícitamente severidad o riesgo.\n"
            "- Campo vacío antes que inventar hechos. Ordena de mayor a menor riesgo.\n"
            "- EXTENSIÓN: cada conclusión ocupa una diapositiva; respeta la extensión orientativa del sistema "
            "(prosa concreta, sin repetir en `consecuencias` lo ya dicho en `incidencia`, una viñeta por dato)."
            f"{_ejemplo_conclusion()}\n\n"
            f"DOCUMENTOS DE ENTRADA:\n{_texto_entrada(docs)}")
    res = ctx.llm.completar_estructurado("extraer", ctx.system, user, ExtraccionConclusiones)
    conclusiones = [_conc_a_dict(c, f"C-{i:02d}") for i, c in enumerate(res.conclusiones, 1)]
    exp.escribir("conclusiones", render_conclusiones(conclusiones, exp.proyecto, res.notas, res.pruebas_sin_incidencia),
                 "extraer")
    lineas = [f"Se han propuesto {len(conclusiones)} conclusiones en {exp.archivo('conclusiones').name}:"]
    for c in conclusiones:
        r = ctx.checker.revisar_conclusion(_campos_conc(c))
        n_err = sum(h.severidad == "error" for h in r.hallazgos)
        marca = "✔" if not n_err else f"✖ {n_err} hallazgos"
        nivel = (c["nivel_riesgo"] or "N/D") + ("*" if c.get("riesgo_propuesto") else "")
        rec = "rec. del PT" if c["recomendacion"] else "sin recomendación"
        if c.get("referencia_recomendacion"):
            rec += f" (ref. {c['referencia_recomendacion']})"
        lineas.append(f"  {c['id']}  [{c['tipo'][:4]}] [{nivel:6}] {c['titulo'][:60]}  ({c['prueba'][:18]}) {marca} · {rec}")
    if any(c.get("riesgo_propuesto") for c in conclusiones):
        lineas.append("  (*) nivel de riesgo propuesto por el modelo sin evidencia en el PT: valídalo al aprobar "
                      "(la coletilla desaparece con `aprobar`).")
    if res.pruebas_sin_incidencia:
        lineas.append("Pruebas sin incidencias: " + "; ".join(res.pruebas_sin_incidencia))
    if res.notas.strip():
        lineas.append(f"Notas del modelo: {res.notas.strip()}")
    mencionadas = " ".join([c["prueba"] for c in conclusiones] + list(res.pruebas_sin_incidencia))
    sin_cubrir = [f"{cod} {tit[:50]}" for cod, tit in _pruebas_en(docs).items()
                  if not re.search(r"(?<![\d.])" + re.escape(cod) + r"(?![\d])", mencionadas)]
    if sin_cubrir:
        lineas.append("⚠ Pruebas detectadas en los papeles de trabajo que el modelo no ha cubierto (ni conclusión ni "
                      "«sin incidencias»): " + "; ".join(sin_cubrir) + ". Revisa que su fichero no esté recortado y "
                      "repite con --forzar.")
    lineas.append("Entrada leída: " + _resumen_entrada(docs) + " — texto normalizado guardado en trazas/.")
    lineas.extend(_avisos_entrada(docs))
    lineas.append("\nSiguiente: revisa cada bloque, ajusta `Tipo:` si procede y marca `Estado: aprobada` (o `aprobar`); "
                  "después `recomendar` para las que no tengan recomendación.")
    return "\n".join(lineas)


# ============================================================ 3. trabajar conclusiones
def accion_aprobar(exp: Expediente, ids: list[str], estado: str = "aprobada") -> str:
    """Cambia el `Estado:` de las conclusiones indicadas ("todas" admitido)
    con una edición quirúrgica del fichero: no se toca nada más. Al aprobar,
    el auditor valida el nivel de riesgo: la coletilla desaparece."""
    texto = exp.leer("conclusiones")
    if not texto:
        raise ExpedienteError("No hay 01_conclusiones.md.")
    todas = any(i.lower() == "todas" for i in ids)
    objetivo = {_normalizar_id(i) for i in ids if i.lower() != "todas"}
    cambiadas, bloque_actual = [], None
    salida = []
    for linea in texto.splitlines():
        m = re.match(r"^##\s+((?:C|OBS)-\d+)", linea, re.IGNORECASE)
        if m:
            bloque_actual = _normalizar_id(m.group(1))
        elif bloque_actual and re.match(r"^\s*[-*]\s*Estado\s*:", linea, re.IGNORECASE) \
                and (todas or bloque_actual in objetivo):
            linea = f"- Estado: {estado}"
            cambiadas.append(bloque_actual)
        elif (estado == "aprobada" and bloque_actual and (todas or bloque_actual in objetivo)
              and re.match(r"^\s*[-*]\s*Nivel de riesgo\s*:", linea, re.IGNORECASE)
              and COLETILLA_RIESGO_PROPUESTO in linea):
            linea = linea.replace(COLETILLA_RIESGO_PROPUESTO, "").rstrip()
        salida.append(linea)
    exp.escribir("conclusiones", "\n".join(salida) + "\n", f"aprobar-{estado}")
    faltan = sorted(objetivo - set(cambiadas))
    msg = f"Marcadas como «{estado}»: {', '.join(cambiadas) or 'ninguna'}."
    if faltan:
        msg += f" No encontradas: {', '.join(faltan)}."
    if estado == "aprobada" and cambiadas:
        sin_rec = [c["id"] for c in _leer_conclusiones(exp)
                   if c["id"] in cambiadas and c["tipo"] == "recomendacion" and not c["recomendacion"].strip()]
        if sin_rec:
            msg += f"\nSin recomendación todavía: {', '.join(sin_rec)} → escríbela en el fichero o ejecuta `recomendar`."
    return msg


def accion_revisar_conclusiones(ctx: Contexto) -> str:
    exp = ctx.exp
    conclusiones = _leer_conclusiones(exp)
    bloques, total_err = [], 0
    for c in conclusiones:
        if c["estado"] == "descartada":
            continue
        r = ctx.checker.revisar_conclusion(_campos_conc(c))
        hall = r.to_dict()["hallazgos"]
        total_err += sum(h["severidad"] == "error" for h in hall)
        bloques.append(f"### {c['id']} · {c['titulo']} ({c['tipo']}, {c['estado']})\n{_formato_hallazgos(hall, False)}")
    cuerpo = "\n\n".join(bloques)
    exp.anexar_registro("revision", f"\n## Revisión de conclusiones — {_fecha()}\n\n{cuerpo}\n")
    return (f"{cuerpo}\n\nTotal: {total_err} errores en {len(bloques)} conclusiones activas. "
            f"Detalle guardado en revision.md." + ("\nSiguiente: `corregir-conclusiones` para que el modelo corrija "
                                                   "solo lo señalado." if total_err else ""))


def accion_corregir_conclusiones(ctx: Contexto, ids: list[str] | None = None) -> str:
    exp = ctx.exp
    conclusiones = _leer_conclusiones(exp)
    seleccion = {_normalizar_id(i) for i in ids} if ids else None
    corregidas, sin_cambio = [], []
    for c in conclusiones:
        if c["estado"] == "descartada" or (seleccion and c["id"] not in seleccion):
            continue
        r = ctx.checker.revisar_conclusion(_campos_conc(c))
        errores = [h for h in r.to_dict()["hallazgos"] if h["severidad"] == "error"]
        if not errores:
            sin_cambio.append(c["id"])
            continue
        user = ("Corrige esta conclusión de auditoría. Mantén todos los hechos, cifras y tablas; corrige solo el "
                "estilo y completa campos vacíos SOLO si son deducibles del resto (si no, déjalos vacíos). "
                "La recomendación, si existe, se devuelve EXACTAMENTE igual.\n\n"
                f"HALLAZGOS DEL VALIDADOR:\n{json.dumps(errores, ensure_ascii=False, indent=2)}\n\n"
                f"CONCLUSIÓN:\n{json.dumps(_campos_conc(c), ensure_ascii=False, indent=2)}")
        nueva = ctx.llm.completar_estructurado(f"corregir-{c['id']}", ctx.system, user, Conclusion, esfuerzo="low")
        d = _conc_a_dict(nueva, c["id"])
        rec_original = c["recomendacion"]
        c.update(_campos_conc(d))
        c["recomendacion"] = rec_original  # se respeta siempre
        verif = ctx.checker.revisar_conclusion(_campos_conc(c))
        ok = not any(h.severidad == "error" for h in verif.hallazgos)
        corregidas.append(f"{c['id']} ({'✔ verificada' if ok else '⚠ aún con hallazgos: revisar a mano'})")
    if corregidas:
        exp.escribir("conclusiones", render_conclusiones(conclusiones, exp.proyecto), "corregir-conclusiones")
    return (f"Corregidas: {', '.join(corregidas) or 'ninguna'}. Sin errores: {', '.join(sin_cambio) or '—'}."
            + ("\nSe ha regenerado 01_conclusiones.md (snapshot previo en historial/)." if corregidas else ""))


def accion_regenerar(ctx: Contexto, ident: str) -> str:
    exp = ctx.exp
    conclusiones = _leer_conclusiones(exp)
    ident = _normalizar_id(ident)
    c = next((x for x in conclusiones if x["id"] == ident), None)
    if c is None:
        raise ExpedienteError(f"No existe {ident} en 01_conclusiones.md.")
    if not c.get("notas", "").strip():
        raise ExpedienteError(f"{ident} no tiene «Notas del auditor». Escribe ahí qué quieres cambiar.")
    user = (f"{_contexto_proyecto(exp)}\n\n"
            "Rehaz esta conclusión siguiendo las indicaciones del auditor. Conserva lo que no se pida cambiar y "
            "apóyate solo en los papeles de trabajo. Si hay recomendación y no se pide cambiarla, devuélvela igual.\n\n"
            f"INDICACIONES DEL AUDITOR:\n{c['notas']}\n\n"
            f"CONCLUSIÓN ACTUAL:\n{json.dumps(_campos_conc(c), ensure_ascii=False, indent=2)}\n\n"
            "`riesgo_soportado_por_evidencia`: true SOLO si el PT menciona explícitamente la severidad o el "
            "nivel de riesgo.\n\n"
            f"DOCUMENTOS DE ENTRADA:\n{_documentos_entrada(exp, f'regenerar-{ident}')}")
    nueva = ctx.llm.completar_estructurado(f"regenerar-{ident}", ctx.system, user, ConclusionExtraida)
    d = _conc_a_dict(nueva, ident)
    c.update(_campos_conc(d))
    c["tipo"] = d["tipo"]
    c["riesgo_propuesto"] = d.get("riesgo_propuesto", False)
    c["estado"], c["notas"] = "propuesta", ""
    exp.escribir("conclusiones", render_conclusiones(conclusiones, exp.proyecto), f"regenerar-{ident}")
    verif = ctx.checker.revisar_conclusion(_campos_conc(c))
    ok = not any(h.severidad == "error" for h in verif.hallazgos)
    return (f"{ident} regenerada (estado: propuesta; notas aplicadas y vaciadas). "
            f"{'✔ Sin errores de estilo.' if ok else '⚠ Con hallazgos de estilo: ver revisar-conclusiones.'}")


# ============================================================ 4. recomendar
def accion_recomendar(ctx: Contexto, ids: list[str] | None = None, preguntar=None, formatear: bool = False,
                      solo_aprobadas: bool = True) -> str:
    """Para cada conclusión (aprobada):
    - si tiene recomendación (del auditor o del PT): se respeta al 100 %; con
      `formatear`, el modelo solo le da formato y se verifica que conserva la base;
    - si no la tiene: `preguntar(c)` (interactivo) puede devolver el texto del
      auditor; si devuelve vacío/None, el modelo propone recomendación y, solo
      excepcionalmente, una sugerencia de mejora complementaria (nuevo bloque).
    Las de tipo `sugerencia` sin propuesta de mejora reciben una propuesta del
    modelo (sin complementarias)."""
    exp = ctx.exp
    conclusiones = _leer_conclusiones(exp)
    seleccion = {_normalizar_id(i) for i in ids} if ids else None
    lineas, cambiado, nuevas = [], False, []
    for c in conclusiones:
        if c["estado"] == "descartada" or (solo_aprobadas and c["estado"] != "aprobada"):
            continue
        if seleccion and c["id"] not in seleccion:
            continue
        es_sugerencia = c["tipo"] == "sugerencia"
        rec = c["recomendacion"].strip()
        if es_sugerencia and rec:
            continue  # la propuesta de mejora ya está: nada que hacer
        if rec and not formatear:
            lineas.append(f"  {c['id']}: recomendación ya presente, se respeta tal cual.")
            continue
        if rec and formatear:
            user = ("Da formato de informe a esta recomendación aportada por el auditor. Mismos hechos, mismas "
                    "acciones, mismas cifras y referencias: no añadas, no quites, no reinterpretes.\n\n"
                    f"CONCLUSIÓN (contexto):\n{json.dumps({k: c[k] for k in ('titulo', 'incidencia', 'consecuencias')}, ensure_ascii=False, indent=2)}\n\n"
                    f"RECOMENDACIÓN DEL AUDITOR:\n{rec}")
            res = ctx.llm.completar_estructurado(f"formatear-recomendacion-{c['id']}", ctx.system, user,
                                                 RecomendacionFormateada, esfuerzo="low")
            if conserva_base(rec, res.recomendacion):
                c["recomendacion"] = res.recomendacion.strip()
                cambiado = True
                lineas.append(f"  {c['id']}: recomendación formateada (base conservada ✔).")
            else:
                lineas.append(f"  {c['id']}: la versión formateada NO conservaba la base del auditor → se mantiene la original.")
            continue
        texto_auditor = preguntar(c) if preguntar else None
        if texto_auditor is False:
            lineas.append(f"  {c['id']}: sin recomendación (no se ha contestado y no se pide proponer).")
            continue
        if texto_auditor and texto_auditor.strip():
            c["recomendacion"] = texto_auditor.strip()
            cambiado = True
            lineas.append(f"  {c['id']}: recomendación del auditor registrada tal cual.")
            continue
        if es_sugerencia:
            user = ("Propón la PROPUESTA DE MEJORA para esta sugerencia de mejora de auditoría (mejora sin plan de "
                    "acción obligatorio): concreta, breve y proporcionada. Deja vacíos los campos de sugerencia "
                    "complementaria.\n\n"
                    f"SUGERENCIA:\n{json.dumps(_campos_conc(c), ensure_ascii=False, indent=2)}")
        else:
            user = ("Propón la recomendación para esta conclusión de auditoría: concreta, accionable, orientada a "
                    "proceso y proporcionada a la incidencia y sus consecuencias.\n"
                    "Sugerencia de mejora complementaria: SOLO de forma excepcional, si existe una mejora menor "
                    "claramente DISTINTA de la recomendación, que no merezca plan de acción y que la recomendación "
                    "no cubra. En la mayoría de los casos no procede: deja `sugerencia_mejora_titulo` y "
                    "`sugerencia_mejora_texto` vacíos.\n\n"
                    f"CONCLUSIÓN:\n{json.dumps(_campos_conc(c), ensure_ascii=False, indent=2)}")
        res = ctx.llm.completar_estructurado(f"recomendar-{c['id']}", ctx.system, user, RecomendacionPropuesta)
        c["recomendacion"] = res.recomendacion.strip()
        cambiado = True
        lineas.append(f"  {c['id']}: {'propuesta de mejora' if es_sugerencia else 'recomendación'} propuesta por el modelo "
                      "(revísala en el fichero).")
        if not es_sugerencia and res.sugerencia_mejora_titulo.strip() and res.sugerencia_mejora_texto.strip():
            nuevas.append({"titulo": res.sugerencia_mejora_titulo.strip(), "tipo": "sugerencia", "estado": "propuesta",
                           "prueba": c["prueba"], "nivel_riesgo": "", "responsable": "", "fuente": f"derivada de {c['id']}",
                           "incidencia": c["incidencia"], "causa_raiz": c["causa_raiz"], "como_se_ha_llegado": "",
                           "consecuencias": c["consecuencias"], "recomendacion": res.sugerencia_mejora_texto.strip(),
                           "notas": "", "riesgo_propuesto": False})
            lineas.append(f"      + sugerencia de mejora complementaria propuesta: «{nuevas[-1]['titulo']}» (estado: propuesta)")
    for n in nuevas:
        n["id"] = f"C-{len(conclusiones) + 1:02d}"
        conclusiones.append(n)
    if cambiado or nuevas:
        exp.escribir("conclusiones", render_conclusiones(conclusiones, exp.proyecto), "recomendar")
    if not lineas:
        return ("No hay conclusiones aprobadas sobre las que recomendar "
                "(aprueba primero, o usa --todas para incluir las propuestas).")
    return "Recomendaciones:\n" + "\n".join(lineas) + ("\n01_conclusiones.md actualizado (snapshot en historial/)." if cambiado or nuevas else "")


# ============================================================ 5. redactar conclusiones (volcado al informe)
def accion_redactar_conclusiones(ctx: Contexto) -> str:
    """Vuelca las conclusiones y sugerencias aprobadas a 02_informe.md de forma
    determinista (sin modelo): el texto validado por el auditor va tal cual.
    Bloquea las que conserven el riesgo «propuesto» o carezcan de recomendación."""
    exp = ctx.exp
    conclusiones = _leer_conclusiones(exp)
    aprobadas = [c for c in conclusiones if c["estado"] == "aprobada"]
    if not aprobadas:
        raise ExpedienteError("No hay conclusiones con `Estado: aprobada`. Aprueba al menos una "
                              "(edita el fichero o usa `aprobar C-01 ...` / `aprobar todas`).")
    bloqueadas = []
    listas = []
    for c in aprobadas:
        motivos = []
        if c.get("riesgo_propuesto"):
            motivos.append("nivel de riesgo aún «propuesto por el modelo» (valídalo con `aprobar`)")
        if c["tipo"] == "recomendacion" and not c["recomendacion"].strip():
            motivos.append("sin recomendación (`recomendar` o escríbela)")
        if c["tipo"] == "sugerencia" and not c["recomendacion"].strip():
            motivos.append("sin propuesta de mejora")
        (bloqueadas if motivos else listas).append((c, motivos))
    if not listas:
        raise ExpedienteError("Ninguna conclusión aprobada está lista para el informe:\n"
                              + "\n".join(f"  {c['id']}: {'; '.join(m)}" for c, m in bloqueadas))
    actual = parsear_informe(exp.leer("informe")) if exp.existe("informe") else {}
    datos = {"introduccion": actual.get("introduccion", ""), "resumen_ejecutivo": actual.get("resumen_ejecutivo", ""),
             "evaluacion_global": actual.get("evaluacion_global", ""),
             "conclusiones": [c for c, _ in listas if c["tipo"] == "recomendacion"],
             "sugerencias": [c for c, _ in listas if c["tipo"] == "sugerencia"]}
    snap = exp.escribir("informe", render_informe(datos, exp.proyecto), "redactar-conclusiones")
    hall = revisar_markdown(ctx.checker, exp.leer("informe"))
    errores = sum(h["severidad"] == "error" for h in hall)
    msg = [f"Detalle de conclusiones ({len(datos['conclusiones'])}) y sugerencias de mejora ({len(datos['sugerencias'])}) "
           f"volcados a {exp.archivo('informe').name} tal cual fueron aprobados (sin modelo)."]
    if bloqueadas:
        msg.append("⚠ NO incluidas: " + "; ".join(f"{c['id']} ({', '.join(m)})" for c, m in bloqueadas))
    if not datos["introduccion"] or not datos["resumen_ejecutivo"]:
        msg.append("Introducción/resumen pendientes: ejecuta `redactar-contexto`.")
    else:
        msg.append("Si el resumen ejecutivo debe reflejar las conclusiones validadas: `redactar-contexto --secciones resumen`.")
    if snap:
        msg.append(f"Versión anterior en historial/{snap.name}.")
    msg.append(f"Revisión determinista: {errores} errores, {len(hall) - errores} avisos" + (" ✔" if not hall else " — `revisar` / `corregir`."))
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
        return "No hay párrafos que corregir (usa --avisos para incluir también tono, adjetivos y frases largas)."
    parrafos = dict(parrafos_con_lineas(texto))
    lote = []
    for i, (linea, hs) in enumerate(sorted(por_parrafo.items()), 1):
        lote.append({"id": i, "texto": parrafos[linea],
                     "hallazgos": [f"«{h['fragmento']}»: {h['mensaje']} Sugerencia: {h.get('sugerencia', '')}"
                                   for h in hs]})
    user = ("Reescribe cada párrafo corrigiendo exactamente los hallazgos indicados. Conserva el formato "
            "Markdown (etiquetas en negrita, viñetas), todos los hechos y cifras, y el sentido. Los hallazgos de "
            "tono (expresiones negativas o rotundas, adjetivos, absolutos) se EVALÚAN según el contexto: reformula "
            "con la alternativa propuesta solo si es fiel al contenido y precisa el alcance real (casos, muestra, "
            "periodo); si la formulación directa es necesaria por precisión técnica, relevancia regulatoria o "
            "severidad, déjala. Devuelve un párrafo por id.\n\n" + json.dumps(lote, ensure_ascii=False, indent=2))
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
    ULTIMO_RESULTADO.clear()
    ULTIMO_RESULTADO.update({"diff": d, "reescritos": len(aplicados) + len(pendientes), "pendientes": pendientes})
    msg = [d, "", f"Párrafos reescritos: {len(aplicados) + len(pendientes)} de {len(lote)}."]
    if pendientes:
        msg.append(f"⚠ {len(pendientes)} párrafo(s) siguen con errores tras la reescritura: revisar a mano "
                   "(`revisar` para verlos).")
    if snap:
        msg.append(f"Snapshot previo: historial/{snap.name} (`deshacer` lo restaura).")
    return "\n".join(msg)


# ============================================================ 4b. condensar (acortar un poco el informe)
_RE_CIFRAS = re.compile(r"\d[\d.,:/%]*|[A-Z]{2,}[A-Z\d-]*-\d+")


def _cifras(texto: str) -> set[str]:
    """Cifras, porcentajes, fechas y códigos (TMSCIIF-10) que el texto condensado debe
    conservar. Los ordinales de enumeración («1)», «2)») no son datos."""
    salida = set()
    for m in _RE_CIFRAS.finditer(texto or ""):
        c = m.group(0).strip(".,:")
        if c and not (c.isdigit() and len(c) <= 2 and texto[m.end():m.end() + 1] == ")"):
            salida.add(c)
    return salida


def _palabras_n(texto: str) -> int:
    return len(re.findall(r"\w+", texto or ""))


def _acepta_condensado(ctx: Contexto, original: str, nuevo: str, fijas: tuple[str, ...] = ()) -> str | None:
    """None si la versión condensada es válida; si no, el motivo para conservar el original."""
    if not (original or "").strip():
        return None if not (nuevo or "").strip() else "el original estaba vacío"
    if not (nuevo or "").strip():
        return "el modelo devolvió el campo vacío"
    if _palabras_n(nuevo) > _palabras_n(original):
        return "la versión nueva es más larga"
    faltan = _cifras(original) - _cifras(nuevo)
    if faltan:
        return "pierde cifras o referencias: " + ", ".join(sorted(faltan)[:6])
    for f in fijas:
        if f in original and f not in nuevo:
            return "pierde la frase fija «" + f[:40] + "…»"
    if any(h.severidad == "error" for h in ctx.checker.revisar_texto(re.sub(r"\*\*[^*]+?:\*\*\s*", "", nuevo)).hallazgos):
        return "incumple las reglas de estilo"
    return None


def accion_condensar(ctx: Contexto, objetivo: float = 0.85) -> str:
    """Acorta un poco el informe con el modelo (≈ `objetivo` de las palabras actuales) sin
    perder hechos, cifras, referencias ni estructura. La recomendación no se envía ni se
    toca. Cada campo se acepta solo si es más corto, conserva las cifras y cumple las
    reglas; si no, se mantiene el original y se informa. Snapshot previo en historial/."""
    exp = ctx.exp
    texto = exp.leer("informe")
    if not texto:
        raise ExpedienteError("No hay 02_informe.md que condensar.")
    datos = parsear_informe(texto)
    objetivo = min(max(objetivo, 0.5), 0.98)
    campos = ("incidencia", "como_se_ha_llegado", "consecuencias")

    def lote_de(lista):
        return [{"numero": i, "titulo": c.get("titulo", ""), **{k: c.get(k, "") for k in campos}} for i, c in enumerate(lista, 1)]

    lote = {"introduccion": datos["introduccion"], "resumen_ejecutivo": datos["resumen_ejecutivo"],
            "conclusiones": lote_de(datos["conclusiones"]), "sugerencias": lote_de(datos["sugerencias"])}
    antes = _palabras_n(texto)
    user = (f"{_contexto_proyecto(exp)}\n\n"
            f"Condensa el informe de auditoría interna hasta aproximadamente el {int(objetivo * 100)} % de sus palabras "
            "actuales (reducción moderada, no drástica), para que cada apartado quepa mejor en su diapositiva.\n"
            "Reglas:\n"
            "- Conserva TODOS los hechos, cifras, porcentajes, importes, fechas, periodos, sistemas, muestras, nombres "
            "de tablas y referencias (p. ej. TMSCIIF-10). No añadas nada nuevo ni cambies el sentido.\n"
            "- Acorta eliminando redundancias, subordinadas prescindibles, muletillas y repeticiones entre apartados "
            "(lo que ya dice `incidencia` no se repite en `consecuencias`).\n"
            "- Conserva la estructura y el Markdown: en la introducción, las frases fijas literales del principio y "
            "del final y las etiquetas en negrita (**Contexto:**, **Objetivo de la auditoría:**…); en el resumen, sus "
            "párrafos y una viñeta «/ » por conclusión; en los detalles, una viñeta `- ` por dato, sin fusionar ni "
            "eliminar datos.\n"
            "- Mantén el registro (primera persona del plural para el equipo auditor, impersonal para los hechos) y "
            "el patrón deber ser → identificado → datos → riesgo → materialización.\n"
            "- Si un campo ya es breve, devuélvelo sin cambios. Devuelve todos los apartados con su `numero`.\n\n"
            + json.dumps(lote, ensure_ascii=False, indent=2))
    res = ctx.llm.completar_estructurado("condensar", ctx.system, user, InformeCondensado)
    textos = textos_informe()
    fijas_intro = (textos["plan_auditoria"].split("{anio}")[0].strip(), textos["normas"][:60])
    aplicados, rechazados = [], []

    def aplicar(nombre, original, nuevo, fijas=()):
        motivo = _acepta_condensado(ctx, original, nuevo, fijas)
        if motivo is None and (nuevo or "").strip() != (original or "").strip():
            aplicados.append(nombre)
            return nuevo.strip()
        if motivo:
            rechazados.append(f"{nombre} ({motivo})")
        return original

    datos["introduccion"] = aplicar("introducción", datos["introduccion"], res.introduccion, fijas_intro)
    datos["resumen_ejecutivo"] = aplicar("resumen ejecutivo", datos["resumen_ejecutivo"], res.resumen_ejecutivo)
    for clave, etiqueta, devueltos in (("conclusiones", "conclusión", res.conclusiones), ("sugerencias", "sugerencia", res.sugerencias)):
        por_num = {a.numero: a for a in devueltos}
        for i, c in enumerate(datos[clave], 1):
            a = por_num.get(i)
            if a is None:
                rechazados.append(f"{etiqueta} {i} (el modelo no la devolvió)")
                continue
            for k in campos:
                c[k] = aplicar(f"{etiqueta} {i} · {k}", c.get(k, ""), getattr(a, k))
    nuevo = render_informe(datos, exp.proyecto)
    if not aplicados:
        ULTIMO_RESULTADO.clear()
        ULTIMO_RESULTADO.update({"diff": "", "aplicados": [], "rechazados": rechazados, "palabras_antes": antes, "palabras_despues": antes})
        return "No se ha condensado ningún apartado." + ("\n  Conservados: " + "; ".join(rechazados) if rechazados else "")
    snap = exp.escribir("informe", nuevo, "condensar")
    despues = _palabras_n(nuevo)
    d = diff_texto(texto, nuevo, "02_informe.md")
    ULTIMO_RESULTADO.clear()
    ULTIMO_RESULTADO.update({"diff": d, "aplicados": aplicados, "rechazados": rechazados,
                             "palabras_antes": antes, "palabras_despues": despues})
    msg = [d, "", f"Informe condensado: {antes} → {despues} palabras ({100 - round(despues * 100 / max(antes, 1))} % menos); "
           f"{len(aplicados)} apartado(s)/campo(s) acortados."]
    if rechazados:
        msg.append("Conservados sin cambio: " + "; ".join(rechazados))
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
    número: dos conclusiones con el mismo título se distinguen por él.
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


ULTIMO_RESULTADO: dict = {}  # datos estructurados de la última acción (para la API)


def accion_aplicar_cambios(ctx: Contexto, solo_plan: bool = False, instrucciones: str | None = None,
                           origen: str = "03_instrucciones.md") -> str:
    """Aplica instrucciones de cambio sobre 02_informe.md. Por defecto las lee
    de 03_instrucciones.md (y lo vacía al terminar); con `instrucciones` se
    aplican directamente (mensaje de `cambio`/`chat`) sin tocar el buzón."""
    exp = ctx.exp
    directo = instrucciones is not None
    if not directo:
        instrucciones = exp.instrucciones_pendientes()
    if not (instrucciones or "").strip():
        raise ExpedienteError("03_instrucciones.md está vacío: pega debajo de `---` la transcripción o los "
                              "comentarios a aplicar." if not directo else "Mensaje vacío.")
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
            "repite en varias conclusiones (p. ej. `- Responsable: …`), indica la sección exacta.\n"
            "- Para añadir texto usa `insertar_tras` con un fragmento literal del informe.\n"
            "- Si una instrucción requiere información que no está en el informe ni en los comentarios, o "
            "contradice los hechos, NO la apliques: ponla en `pendientes` explicando qué falta.\n"
            "- Respeta las reglas de estilo en todo texto nuevo.\n"
            "FORMATO DEL INFORME (respétalo: cada apartado se exporta tal cual a una diapositiva):\n"
            "- Cada conclusión es `### N. Título` seguido de líneas de metadatos `- Prueba:`, `- Nivel de riesgo:`, "
            "`- Área:`, `- Responsable:`, `- Plazo:`, `- Ref. recomendación:`; después prosa, la línea en cursiva "
            "«A continuación, se muestran los detalles descriptivos…» con viñetas `- `, el párrafo de consecuencias y "
            "las recomendaciones como párrafos `**Recomendación N.k.** texto`.\n"
            "- Para rellenar área/responsable/plazo, sustituye la línea de metadatos vacía existente (texto_original "
            "exacto, p. ej. `- Plazo: `) por la rellena; si hay varias recomendaciones con responsables distintos: "
            "`- Responsable: X (1.1); Y (1.2)`.\n"
            "- Para añadir una sugerencia de mejora, inserta un bloque completo con esta plantilla al final de la "
            "sección `## Sugerencias de mejora` (o sustituyendo `_(ninguna)_`), numerado por su posición (la primera "
            "sugerencia es la 1): `### 1. Título` + `- Prueba: ` + `- Nivel de riesgo: Bajo` + `- Área: …` + párrafo "
            "de descripción + `**Sugerencia de mejora 1.1.** texto`. Nunca la añadas como viñeta suelta ni dejes "
            "letras de plantilla como «N».\n"
            "- Para añadir una conclusión, mismo bloque completo en `## Detalle de conclusiones` con "
            "`**Recomendación N.1.**`. Para dividir una recomendación: dos párrafos `**Recomendación N.1.**` y "
            "`**Recomendación N.2.**`.\n\n"
            f"COMENTARIOS / INSTRUCCIONES:\n{instrucciones}\n\n"
            f"INFORME ACTUAL (02_informe.md):\n{texto}")
    plan = ctx.llm.completar_estructurado("aplicar-cambios", ctx.system, user, PlanCambios)
    nuevo, filas = aplicar_plan(texto, plan)
    ULTIMO_RESULTADO.clear()
    ULTIMO_RESULTADO.update({"plan": [dict(f, texto_original=c.texto_original, texto_nuevo=c.texto_nuevo)
                                      for f, c in zip(filas, plan.cambios)],
                             "pendientes": list(plan.pendientes), "diff": diff_texto(texto, nuevo, "02_informe.md"),
                             "solo_plan": solo_plan})

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
    snap = exp.escribir("informe", nuevo, "aplicar-cambios" if not directo else "cambio")
    registro = [f"\n## Cambios aplicados — {_fecha()} ({origen})\n", "Instrucciones recibidas:\n",
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
    if not directo:
        exp.vaciar_instrucciones()

    n_conf = sum(f["estado"] == "CONFLICTO" for f in filas)
    lineas += ["", diff_texto(texto, nuevo, "02_informe.md"), "",
               (f"⚠ {n_conf} cambio(s) en CONFLICTO con otro anterior: revisar en cambios_aplicados.md.\n" if n_conf else "") +
               f"Aplicados {sum(f['estado'].startswith(('aplicado', 'insertado', 'eliminado')) for f in filas)} "
               f"de {len(filas)} cambios. Registro en cambios_aplicados.md"
               + ("; 03_instrucciones.md vaciado (lo pegado queda en historial/)." if not directo else "."),
               f"Revisión determinista tras los cambios: {errores} errores, {len(hall) - errores} avisos."]
    if snap:
        lineas.append(f"Snapshot previo: historial/{snap.name} (`deshacer` lo restaura).")
    return "\n".join(lineas)


# ============================================================ 5b. reunión (transcripción de Teams)
def accion_reunion(ctx: Contexto, ruta_transcript: str | Path, aplicar: bool = False) -> str:
    """Lee una transcripción de reunión (Teams: .txt/.docx/.vtt…) y separa lo
    que afecta al TEXTO del informe (se deja como instrucciones en
    03_instrucciones.md para que el auditor las revise y aplique) de lo que
    afecta al PPT (informativo: la presentación es beta y se retoca a mano),
    más pendientes y acuerdos. Genera un acta en reuniones/."""
    exp = ctx.exp
    ruta = Path(ruta_transcript)
    if not ruta.exists():
        raise ExpedienteError(f"No existe la transcripción {ruta}.")
    texto_informe = exp.leer("informe")
    if not texto_informe:
        raise ExpedienteError("No hay 02_informe.md: la reunión se contrasta contra el informe.")
    if ruta.suffix.lower() == ".vtt":
        transcript = re.sub(r"^(WEBVTT|\d+|\d\d:\d\d[:.\d]* --> .*)$", "", ruta.read_text(encoding="utf-8", errors="replace"), flags=re.M)
    else:
        try:
            transcript = leer_documento(ruta).texto
        except LecturaError as exc:
            raise ExpedienteError(str(exc)) from exc
    transcript = re.sub(r"\n{3,}", "\n\n", transcript).strip()
    if len(transcript) < 40:
        raise ExpedienteError("La transcripción está vacía o no tiene texto legible.")
    user = ("Analiza la transcripción de una reunión de revisión del informe (Gerente/Directora/área auditada) y "
            "contrástala con el INFORME ACTUAL. Clasifica cada petición:\n"
            "- `cambios_texto`: todo lo que cambia el CONTENIDO del informe (redacción, añadir/quitar/dividir/fusionar "
            "recomendaciones o conclusiones, niveles de riesgo, área/responsable/plazo, viñetas, resumen, "
            "introducción, sugerencias de mejora). Cada `instruccion` debe poder aplicarse sola sobre "
            "02_informe.md: nombra el apartado (p. ej. «Conclusión 1», «Resumen ejecutivo», «Recomendación 1.1») y, "
            "si el interlocutor DICTÓ una redacción para el informe, cítala literal; si habló de forma coloquial "
            "(«…y ya», «larguísima»), formula la instrucción con el sentido, en el registro del informe, sin copiar "
            "la coloquialidad. Área, responsable y plazo van en las líneas de metadatos de la conclusión (si hay "
            "varias recomendaciones con responsables distintos, indícalo así: «Responsable: X (1.1); Y (1.2)»). "
            "Una instrucción por cambio; conserva el orden.\n"
            "- `cambios_ppt`: lo que solo afecta a la presentación (orden de diapositivas, maquetación, gráficos, "
            "plantilla, colores, fuentes, imágenes, animaciones). NO va al informe.\n"
            "- `pendientes`: peticiones que requieren un dato o confirmación que no consta (di qué falta y quién lo aporta).\n"
            "- `acuerdos_sin_cambio`: acuerdos que no modifican el informe (plazos de conformidad, seguimiento, tareas).\n"
            "No inventes peticiones que no estén en la transcripción; si algo es ambiguo, a `pendientes`.\n\n"
            f"TRANSCRIPCIÓN ({ruta.name}):\n{transcript}\n\n"
            f"INFORME ACTUAL (02_informe.md):\n{texto_informe}")
    res = ctx.llm.completar_estructurado("reunion", ctx.system, user, AnalisisReunion)

    marca = datetime.now()
    acta = exp.ruta / "reuniones" / f"{marca:%Y-%m-%d_%H%M}_{ruta.stem[:40]}.md"
    ULTIMO_RESULTADO.clear()
    ULTIMO_RESULTADO.update(res.model_dump())
    ULTIMO_RESULTADO["acta"] = acta.relative_to(exp.ruta).as_posix()
    L = [f"# Acta de cambios — reunión «{ruta.stem}» — {marca:%Y-%m-%d %H:%M}", "", res.resumen.strip(), "",
         f"## Cambios en el texto del informe ({len(res.cambios_texto)})", ""]
    if not res.cambios_texto:
        L.append("(ninguno)")
    for i, c in enumerate(res.cambios_texto, 1):
        L.append(f"{i}. **{c.seccion}** — {c.que_cambiar}" + (f" _(pide: {c.solicitado_por})_" if c.solicitado_por else ""))
        L.append(f"   - Instrucción: {c.instruccion}")
        if c.cita:
            L.append(f"   - Cita: «{c.cita.strip()}»")
    L += ["", f"## Cambios en la presentación (PPT) — informativo, no se aplican ({len(res.cambios_ppt)})", ""]
    if not res.cambios_ppt:
        L.append("(ninguno)")
    for i, c in enumerate(res.cambios_ppt, 1):
        L.append(f"{i}. {c.que_cambiar}" + (f" _(pide: {c.solicitado_por})_" if c.solicitado_por else "")
                 + (f" — «{c.cita.strip()}»" if c.cita else ""))
    L += ["", f"## Pendientes de dato o confirmación ({len(res.pendientes)})", ""] + ([f"- {x}" for x in res.pendientes] or ["(ninguno)"])
    L += ["", f"## Acuerdos que no cambian el informe ({len(res.acuerdos_sin_cambio)})", ""] + ([f"- {x}" for x in res.acuerdos_sin_cambio] or ["(ninguno)"])
    acta.write_text("\n".join(L) + "\n", encoding="utf-8")

    if res.cambios_texto:
        bloque = [f"\nReunión «{ruta.stem}» ({marca:%d/%m/%Y}) — instrucciones detectadas por el sistema; borra o edita las que no procedan:"]
        bloque += [f"- {c.instruccion.strip()}" + (f" [{c.solicitado_por}]" if c.solicitado_por else "") for c in res.cambios_texto]
        exp.anexar_registro("instrucciones", "\n".join(bloque) + "\n")

    out = [f"Acta: {acta.relative_to(exp.ruta)}", "", res.resumen.strip(), "",
           f"El sistema ha detectado {len(res.cambios_texto)} cambio(s) en el TEXTO del informe:"]
    out += [f"  {i}. [{c.seccion}] {c.que_cambiar}" + (f" (pide: {c.solicitado_por})" if c.solicitado_por else "")
            for i, c in enumerate(res.cambios_texto, 1)] or ["  (ninguno)"]
    out.append(f"\nY {len(res.cambios_ppt)} cambio(s) en el PPT (solo informativo; la presentación es beta y se ajusta a mano):")
    out += [f"  {i}. {c.que_cambiar}" + (f" (pide: {c.solicitado_por})" if c.solicitado_por else "") for i, c in enumerate(res.cambios_ppt, 1)] or ["  (ninguno)"]
    if res.pendientes:
        out.append("\nPendientes de dato o confirmación:")
        out += [f"  • {x}" for x in res.pendientes]
    if res.acuerdos_sin_cambio:
        out.append("\nAcuerdos que no cambian el informe:")
        out += [f"  • {x}" for x in res.acuerdos_sin_cambio]
    if res.cambios_texto:
        out.append("\nLas instrucciones de texto se han añadido a 03_instrucciones.md.")
        if aplicar:
            out += ["", "=== aplicar-cambios ===", accion_aplicar_cambios(ctx)]
        else:
            out.append("Revísalas (borra o edita las que no procedan) y ejecuta `aplicar-cambios`, o usa `reunion --aplicar` "
                       "para aplicarlas directamente.")
    return "\n".join(out)


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
    if not datos["conclusiones"] and not datos["sugerencias"]:
        raise ExpedienteError("El informe no tiene conclusiones volcadas (sección `## Detalle de conclusiones` "
                              "con bloques `### N. Título`). Ejecuta `redactar-conclusiones`.")
    ruta = construir_desde_datos(datos, exp.ruta_ppt())
    avisos = "".join(f"\n  Aviso: {a}" for a in getattr(construir_desde_datos, "avisos", []))
    return (f"Presentación generada sobre la plantilla corporativa: {ruta} ({len(datos['conclusiones'])} conclusiones, "
            f"{len(datos['sugerencias'])} sugerencias de mejora).{avisos}")


# ============================================================ 6b. archivar (retención de evidencia)
def _sha256(ruta: Path) -> str:
    h = hashlib.sha256()
    with open(ruta, "rb") as f:
        for bloque in iter(lambda: f.read(1 << 20), b""):
            h.update(bloque)
    return h.hexdigest()


def ficheros_a_archivar(exp: Expediente) -> list[Path]:
    """Ficheros que forman la evidencia del expediente: metadatos, los tres
    Markdown de trabajo, revisión y registro de cambios, trazas/, historial/,
    salidas/ y reuniones/. Nunca los zips de archivos anteriores."""
    ficheros = [exp.archivo(k) for k in ("meta", "conclusiones", "informe", "instrucciones", "revision", "cambios")]
    for d in ("trazas", "historial", "salidas", "reuniones"):
        ficheros += sorted(p for p in (exp.ruta / d).rglob("*") if p.is_file())
    return [f for f in ficheros if f.exists() and f.suffix.lower() != ".zip"]


def accion_archivar(exp: Expediente) -> str:
    fecha = datetime.now()
    destino = exp.ruta / f"{exp.referencia}_archivo_{fecha:%Y%m%d-%H%M%S}.zip"
    ficheros = ficheros_a_archivar(exp)
    manifiesto = {
        "referencia": exp.referencia,
        "nombre": exp.proyecto.get("nombre", ""),
        "fecha_archivo": fecha.isoformat(timespec="seconds"),
        "herramienta": f"revisor-informes {__version__}",
        "algoritmo_hash": "sha256",
        "ficheros": [{"ruta": f.relative_to(exp.ruta).as_posix(), "bytes": f.stat().st_size, "sha256": _sha256(f)}
                     for f in ficheros],
    }
    with zipfile.ZipFile(destino, "w", zipfile.ZIP_DEFLATED) as z:
        for f in ficheros:
            z.write(f, f.relative_to(exp.ruta).as_posix())
        z.writestr("manifest.json", json.dumps(manifiesto, ensure_ascii=False, indent=2))
    n_trazas = sum(1 for f in ficheros if f.parent.name == "trazas")
    n_hist = sum(1 for f in ficheros if f.parent.name == "historial")
    return (f"Archivo de evidencia: {destino}\n  {len(ficheros)} ficheros ({n_trazas} trazas LLM, {n_hist} versiones en "
            f"historial) + manifest.json con sha256 de cada uno.\n"
            "  Adjúntalo al expediente al cerrarlo en Pentana; para verificar la integridad después, recalcula los "
            "sha256 y compáralos con manifest.json.")


def verificar_archivo(ruta_zip: Path) -> list[str]:
    """Recalcula los sha256 del zip contra su manifest.json. Devuelve la lista
    de discrepancias (vacía = íntegro)."""
    problemas = []
    with zipfile.ZipFile(ruta_zip) as z:
        manifiesto = json.loads(z.read("manifest.json"))
        nombres = set(z.namelist())
        for f in manifiesto["ficheros"]:
            if f["ruta"] not in nombres:
                problemas.append(f"falta {f['ruta']}")
                continue
            if hashlib.sha256(z.read(f["ruta"])).hexdigest() != f["sha256"]:
                problemas.append(f"hash distinto: {f['ruta']}")
    return problemas


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
    for clave in ("conclusiones", "informe", "instrucciones"):
        vs = exp.historial(clave)
        if vs:
            lineas.append(f"{exp.archivo(clave).name}: {len(vs)} versiones")
            lineas += [f"    {v.name}" for v in vs[-8:]]
    return "\n".join(lineas) or "historial/ vacío."


# ============================================================ 8. estado
def estado_expediente(exp: Expediente, checker: StyleChecker | None = None) -> dict:
    e: dict = {"referencia": exp.referencia, "nombre": exp.proyecto.get("nombre", ""),
               "contexto": [p.name for p in exp.ficheros("contexto")],
               "papeles": [p.name for p in exp.ficheros("papeles_trabajo")],
               "conclusiones": None, "informe": None, "instrucciones_pendientes": bool(exp.instrucciones_pendientes()),
               "ppt": None, "siguiente": ""}
    if exp.existe("conclusiones"):
        cs = parsear_conclusiones(exp.leer("conclusiones"))
        e["conclusiones"] = {k: sum(c["estado"] == k for c in cs) for k in ("propuesta", "aprobada", "descartada")}
        e["conclusiones"].update({
            "total": len(cs), "sugerencias": sum(c["tipo"] == "sugerencia" for c in cs),
            "con_notas": [c["id"] for c in cs if c.get("notas", "").strip()],
            "sin_recomendacion": [c["id"] for c in cs if c["estado"] == "aprobada" and c["tipo"] == "recomendacion"
                                  and not c["recomendacion"].strip()],
            "riesgo_pendiente": [c["id"] for c in cs if c["estado"] == "aprobada" and c.get("riesgo_propuesto")],
        })
    informe = parsear_informe(exp.leer("informe")) if exp.existe("informe") else None
    if informe is not None:
        texto = exp.leer("informe")
        hall = revisar_markdown(checker, texto) if checker else []
        e["informe"] = {"errores": sum(h["severidad"] == "error" for h in hall),
                        "avisos": sum(h["severidad"] == "aviso" for h in hall),
                        "modificado": datetime.fromtimestamp(exp.archivo("informe").stat().st_mtime),
                        "versiones": len(exp.historial("informe")),
                        "contexto": bool(informe["introduccion"] and informe["resumen_ejecutivo"]),
                        "n_conclusiones": len(informe["conclusiones"]), "n_sugerencias": len(informe["sugerencias"])}
    e["archivos"] = sorted(p.name for p in exp.ruta.glob("*_archivo_*.zip"))
    ppt = exp.ruta_ppt()
    if ppt.exists():
        e["ppt"] = {"ruta": ppt, "desactualizado": exp.existe("informe") and
                    ppt.stat().st_mtime < exp.archivo("informe").stat().st_mtime}

    c, inf = e["conclusiones"], e["informe"]
    if not e["papeles"]:
        e["fase"] = "0 · Sin papeles de trabajo"
        e["siguiente"] = (f"Copia el papel de trabajo final a {exp.ruta / 'papeles_trabajo'}"
                          + ("" if e["contexto"] else f" y, si lo tienes, el design thinking / contexto a {exp.ruta / 'contexto'}"))
    elif inf is None or not inf["contexto"]:
        e["fase"], e["siguiente"] = "1 · Contexto del informe", "`redactar-contexto`: introducción y resumen ejecutivo a partir de entrada/ (luego valídalos)"
    elif c is None:
        e["fase"], e["siguiente"] = "2 · Conclusiones", "`extraer`: conclusiones (incidencias) y sugerencias de mejora de todas las pruebas"
    elif inf["n_conclusiones"] == 0 and inf["n_sugerencias"] == 0:
        e["fase"] = "2 · Conclusiones en revisión"
        if not c["aprobada"]:
            e["siguiente"] = "Lee 01_conclusiones.md, ajusta y marca `Estado: aprobada` (o `aprobar ...`)"
        elif c["riesgo_pendiente"]:
            e["siguiente"] = f"Valida el nivel de riesgo de {', '.join(c['riesgo_pendiente'])} (`aprobar` quita la coletilla)"
        elif c["sin_recomendacion"]:
            e["siguiente"] = f"`recomendar`: {', '.join(c['sin_recomendacion'])} sin recomendación (escríbela o que la proponga el modelo)"
        else:
            e["siguiente"] = "`redactar-conclusiones` para volcar las aprobadas al informe"
    else:
        e["fase"] = "3 · Informe en redacción"
        if e["instrucciones_pendientes"]:
            e["siguiente"] = "`aplicar-cambios`: hay instrucciones pendientes en 03_instrucciones.md"
        elif c["sin_recomendacion"] or c["riesgo_pendiente"]:
            e["siguiente"] = "Hay conclusiones aprobadas pendientes de recomendación/riesgo: `recomendar` y `redactar-conclusiones`"
        elif inf["errores"]:
            e["siguiente"] = f"`corregir`: el informe tiene {inf['errores']} errores de vocabulario/estilo"
        elif e["ppt"] is None or e["ppt"]["desactualizado"]:
            e["siguiente"] = "`ppt` para generar (o regenerar) la presentación del informe"
        else:
            e["fase"] = "4 · Entregable generado"
            ultimo = e["archivos"][-1] if e["archivos"] else None
            archivo_actual = ultimo and (exp.ruta / ultimo).stat().st_mtime >= exp.archivo("informe").stat().st_mtime
            e["siguiente"] = ("Informe emitido y archivado. Seguir editando y regenerar `ppt` + `archivar` si cambia."
                              if archivo_actual else
                              "`archivar`: generar el zip de evidencia (trazas, historial, informe, PPT + manifest sha256) "
                              "para adjuntarlo al expediente al cerrarlo en Pentana")
    return e


def accion_estado(exp: Expediente, checker: StyleChecker | None = None, llm_desc: str = "") -> str:
    e = estado_expediente(exp, checker)
    L = [f"Expediente {e['referencia']} · {e['nombre']}", f"  Carpeta: {exp.ruta}",
         f"  Fase: {e['fase']}"]
    if llm_desc:
        L.append(f"  LLM: {llm_desc}")
    L.append(f"  Contexto: {len(e['contexto'])} documento(s)" + (f" — {', '.join(e['contexto'])}" if e["contexto"] else " (opcional: design thinking, planificación)"))
    L.append(f"  Papeles de trabajo: {len(e['papeles'])} documento(s)" + (f" — {', '.join(e['papeles'])}" if e["papeles"] else ""))
    if e["conclusiones"]:
        c = e["conclusiones"]
        L.append(f"  Conclusiones: {c['total']} ({c['sugerencias']} sugerencias de mejora) — aprobadas {c['aprobada']}, "
                 f"propuestas {c['propuesta']}, descartadas {c['descartada']}"
                 + (f"; sin recomendación: {', '.join(c['sin_recomendacion'])}" if c["sin_recomendacion"] else "")
                 + (f"; riesgo por validar: {', '.join(c['riesgo_pendiente'])}" if c["riesgo_pendiente"] else "")
                 + (f"; con notas para regenerar: {', '.join(c['con_notas'])}" if c["con_notas"] else ""))
    if e["informe"]:
        i = e["informe"]
        L.append(f"  Informe: introducción y resumen {'listos' if i['contexto'] else 'pendientes'}, "
                 f"{i['n_conclusiones']} conclusiones y {i['n_sugerencias']} sugerencias volcadas; modificado "
                 f"{i['modificado']:%Y-%m-%d %H:%M}, {i['versiones']} versiones, {i['errores']} errores / {i['avisos']} avisos de estilo")
    L.append(f"  Instrucciones pendientes: {'sí' if e['instrucciones_pendientes'] else 'no'}")
    if e["ppt"]:
        L.append(f"  PPT: {e['ppt']['ruta'].name}" + (" (anterior a la última edición del informe)" if e["ppt"]["desactualizado"] else ""))
    if e.get("archivos"):
        L.append(f"  Archivos de evidencia: {', '.join(e['archivos'])}")
    L.append(f"  ▶ Siguiente: {e['siguiente']}")
    return "\n".join(L)
