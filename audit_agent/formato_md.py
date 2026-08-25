"""
Formato Markdown de ida y vuelta (render <-> parse) de los ficheros que el
auditor edita. La regla de oro: lo que la herramienta escribe, la
herramienta lo sabe leer después de que una persona lo haya editado.

Convenciones (tolerantes a mayúsculas, tildes y espacios):

    ## OBS-01 · Título                       (01_observaciones.md)
    ### 1. Título                            (02_informe.md)
    - Estado: propuesta | aprobada | descartada
    - Nivel de riesgo: Alto | Medio | Bajo
    - Responsable: ...
    - Fuente: ...
    **Condición:** texto (puede ocupar varios párrafos)
    **Criterio:** ...
    **Causa raíz:** ...
    **Efecto:** ...
    **Recomendación:** ...
    **Notas del auditor:** (solo en 01_observaciones.md; se envían al modelo en `regenerar`)

Las líneas que empiezan por `>` son instrucciones para la persona y se ignoran.
"""
from __future__ import annotations

import re
import unicodedata

ESTADOS = ("propuesta", "aprobada", "descartada")

CAMPOS_TEXTO = [  # (clave, etiqueta visible)
    ("condicion", "Condición"),
    ("criterio", "Criterio"),
    ("causa_raiz", "Causa raíz"),
    ("efecto", "Efecto"),
    ("recomendacion", "Recomendación"),
]
CAMPOS_META = [
    ("nivel_riesgo", "Nivel de riesgo"),
    ("responsable", "Responsable"),
    ("fuente", "Fuente"),
]

_RE_META = re.compile(r"^\s*[-*]\s*([^:]+?)\s*:\s*(.*)$")
_RE_CAMPO = re.compile(r"^\s*\*\*([^*]+?)\s*:?\s*\*\*\s*:?\s*(.*)$")
_RE_OBS_ID = re.compile(r"^OBS-(\d+)\s*[·\-–:.]?\s*(.*)$", re.IGNORECASE)
_RE_NUM = re.compile(r"^(\d+)\s*[.)·\-–:]?\s*(.*)$")


def _norm(s: str) -> str:
    nfkd = unicodedata.normalize("NFD", s.strip().lower())
    return re.sub(r"\s+", " ", "".join(c for c in nfkd if unicodedata.category(c) != "Mn"))


_CLAVES = {_norm(et): cl for cl, et in CAMPOS_TEXTO + CAMPOS_META}
_CLAVES.update({"estado": "estado", "notas del auditor": "notas", "notas": "notas",
                "causa": "causa_raiz", "nivel": "nivel_riesgo", "riesgo": "nivel_riesgo",
                "recomendacion": "recomendacion", "condicion": "condicion"})


def normalizar_nivel(valor: str) -> str:
    v = _norm(valor)
    for n in ("alto", "medio", "bajo"):
        if v.startswith(n):
            return n.capitalize()
    return valor.strip()


# ====================================================================== RENDER
def _bloque_observacion(o: dict, cabecera: str, con_estado: bool, con_notas: bool) -> str:
    lineas = [cabecera, ""]
    if con_estado:
        lineas.append(f"- Estado: {o.get('estado', 'propuesta')}")
    for clave, etiqueta in CAMPOS_META:
        valor = o.get(clave, "")
        if clave == "fuente" and not valor and not con_estado:
            continue
        lineas.append(f"- {etiqueta}: {valor}")
    lineas.append("")
    for clave, etiqueta in CAMPOS_TEXTO:
        lineas.append(f"**{etiqueta}:** {o.get(clave, '').strip()}")
        lineas.append("")
    if con_notas:
        lineas.append(f"**Notas del auditor:** {o.get('notas', '').strip()}")
        lineas.append("")
    return "\n".join(lineas)


CABECERA_OBSERVACIONES = """# Observaciones y recomendaciones — {referencia} · {nombre}

> Cómo trabajar este fichero:
> - Lee cada observación, corrige lo que haga falta directamente en el texto.
> - Cambia `Estado: propuesta` por `aprobada` (irá al informe) o `descartada` (se ignora).
> - Si quieres que el modelo la rehaga, escribe qué cambiar en «Notas del auditor»
>   y ejecuta `regenerar-obs OBS-XX`. Puedes añadir observaciones nuevas a mano
>   copiando la estructura de un bloque.
> - `revisar-obs` comprueba vocabulario prohibido y campos vacíos; `corregir-obs`
>   pide al modelo que corrija solo lo señalado.
> - Cuando tengas las que quieras aprobadas, ejecuta `redactar`.

"""


def render_observaciones(observaciones: list[dict], proyecto: dict, notas_extraccion: str = "") -> str:
    partes = [CABECERA_OBSERVACIONES.format(referencia=proyecto.get("referencia", ""),
                                            nombre=proyecto.get("nombre", ""))]
    if notas_extraccion.strip():
        partes.append("> **Notas del modelo sobre la extracción:** "
                      + notas_extraccion.strip().replace("\n", "\n> ") + "\n")
    for i, o in enumerate(observaciones, 1):
        ident = o.get("id") or f"OBS-{i:02d}"
        partes.append(_bloque_observacion(o, f"## {ident} · {o.get('titulo', '').strip()}",
                                          con_estado=True, con_notas=True))
    return "\n".join(partes).rstrip() + "\n"


CABECERA_INFORME = """# Resumen Ejecutivo — {nombre}

- Referencia: {referencia}
- Fecha: {fecha}
- Distribución: {distribucion}

> Este es el texto de trabajo del informe. Edítalo libremente respetando los
> títulos `##` de sección y la estructura de cada observación (`###` + campos en
> negrita): es lo que permite generar el PPT y aplicar cambios automáticamente.
> Acciones: `revisar` (vocabulario/estilo), `corregir` (reescritura dirigida de
> lo señalado), `aplicar-cambios` (desde 03_instrucciones.md), `diff`,
> `deshacer`, `ppt`.

"""


def render_informe(datos: dict, proyecto: dict) -> str:
    ctx = datos.get("contexto", {}) or {}
    ev = datos.get("evaluacion_global", {}) or {}
    partes = [CABECERA_INFORME.format(
        nombre=proyecto.get("nombre", ""), referencia=proyecto.get("referencia", ""),
        fecha=proyecto.get("fecha", ""), distribucion=", ".join(proyecto.get("distribucion", [])))]
    partes.append(f"## Objetivo\n\n{datos.get('objetivo', '').strip()}\n")
    partes.append(f"## Alcance\n\n{datos.get('alcance', '').strip()}\n")
    mags = "\n".join(f"- {v} — {e}" for v, e in ctx.get("magnitudes", []))
    partes.append(f"## Contexto y principales magnitudes\n\n{mags}\n\n{ctx.get('texto', '').strip()}\n"
                  if mags else f"## Contexto y principales magnitudes\n\n{ctx.get('texto', '').strip()}\n")
    partes.append("## Principales observaciones\n")
    for i, o in enumerate(datos.get("observaciones", []), 1):
        partes.append(_bloque_observacion(o, f"### {i}. {o.get('titulo', '').strip()}",
                                          con_estado=False, con_notas=False))
    partes.append("## Evaluación global\n\n"
                  f"- Gobierno: {ev.get('gobierno', '')}\n"
                  f"- Gestión de riesgos: {ev.get('gestion_riesgos', '')}\n"
                  f"- Entorno de control: {ev.get('entorno_control', '')}\n\n"
                  f"{ev.get('conclusion', '').strip()}\n")
    partes.append(f"## Próximos pasos\n\n{datos.get('proximos_pasos', '').strip()}\n")
    return "\n".join(partes).rstrip() + "\n"


# ====================================================================== PARSE
def _parsear_bloque(lineas: list[str]) -> dict:
    """Parsea las líneas de una observación (sin la cabecera) a dict."""
    o: dict = {"estado": "propuesta", "nivel_riesgo": "", "responsable": "", "fuente": "", "notas": ""}
    for clave, _ in CAMPOS_TEXTO:
        o[clave] = ""
    campo_actual: str | None = None
    buffer: list[str] = []

    def cerrar():
        nonlocal buffer
        if campo_actual:
            o[campo_actual] = (o.get(campo_actual, "") + "\n".join(buffer)).strip()
        buffer = []

    for linea in lineas:
        if linea.lstrip().startswith(">"):
            continue
        m_campo = _RE_CAMPO.match(linea)
        if m_campo and _norm(m_campo.group(1)) in _CLAVES:
            cerrar()
            campo_actual = _CLAVES[_norm(m_campo.group(1))]
            buffer = [m_campo.group(2).strip()] if m_campo.group(2).strip() else []
            continue
        m_meta = _RE_META.match(linea)
        if m_meta and campo_actual is None and _norm(m_meta.group(1)) in _CLAVES:
            clave = _CLAVES[_norm(m_meta.group(1))]
            valor = m_meta.group(2).strip()
            o[clave] = _norm(valor).split()[0] if clave == "estado" and valor else (
                normalizar_nivel(valor) if clave == "nivel_riesgo" else valor)
            continue
        if campo_actual is not None:
            buffer.append(linea.rstrip())
    cerrar()
    if o["estado"] not in ESTADOS:
        o["estado"] = "propuesta"
    return o


def _partir_por_cabeceras(texto: str, nivel: int) -> tuple[list[str], list[tuple[str, list[str]]]]:
    """Devuelve (líneas previas a la primera cabecera, [(título, líneas)])."""
    prefijo = "#" * nivel + " "
    previo: list[str] = []
    bloques: list[tuple[str, list[str]]] = []
    actual: list[str] | None = None
    for linea in texto.splitlines():
        if linea.startswith(prefijo):
            actual = []
            bloques.append((linea[len(prefijo):].strip(), actual))
        elif linea.startswith("#") and actual is not None and _nivel_cabecera(linea) < nivel:
            actual = None  # fin de la sección padre
            previo.append(linea)
        elif actual is None:
            previo.append(linea)
        else:
            actual.append(linea)
    return previo, bloques


def _nivel_cabecera(linea: str) -> int:
    return len(linea) - len(linea.lstrip("#"))


def parsear_observaciones(texto: str) -> list[dict]:
    """01_observaciones.md -> lista de dicts (con id, estado, notas)."""
    _, bloques = _partir_por_cabeceras(texto, 2)
    salida = []
    for i, (titulo, lineas) in enumerate(bloques, 1):
        m = _RE_OBS_ID.match(titulo)
        if m:
            ident, titulo_limpio = f"OBS-{int(m.group(1)):02d}", m.group(2).strip()
        else:
            ident, titulo_limpio = f"OBS-{i:02d}", titulo
        o = _parsear_bloque(lineas)
        o["id"], o["titulo"] = ident, titulo_limpio
        salida.append(o)
    return salida


def parsear_informe(texto: str) -> dict:
    """02_informe.md -> dict compatible con ppt_builder.construir_desde_datos
    (sin `proyecto`, que aporta el expediente)."""
    previo, secciones = _partir_por_cabeceras(texto, 2)
    datos: dict = {"objetivo": "", "alcance": "", "contexto": {"texto": "", "magnitudes": []},
                   "observaciones": [], "evaluacion_global": {}, "proximos_pasos": ""}
    for titulo, lineas in secciones:
        t = _norm(titulo)
        cuerpo = [l for l in lineas if not l.lstrip().startswith(">")]
        if t.startswith("objetivo"):
            datos["objetivo"] = "\n".join(cuerpo).strip()
        elif t.startswith("alcance"):
            datos["alcance"] = "\n".join(cuerpo).strip()
        elif t.startswith("contexto") or "magnitud" in t:
            mags, resto = [], []
            for l in cuerpo:
                m = re.match(r"^\s*[-*]\s*(.+?)\s+[—–-]\s+(.+)$", l)
                if m:
                    mags.append([m.group(1).strip(), m.group(2).strip()])
                else:
                    resto.append(l)
            datos["contexto"] = {"texto": "\n".join(resto).strip(), "magnitudes": mags}
        elif "observacion" in t:
            _, obs_bloques = _partir_por_cabeceras("\n".join(lineas), 3)
            for j, (tit, lin) in enumerate(obs_bloques, 1):
                m = _RE_NUM.match(tit)
                o = _parsear_bloque(lin)
                o["titulo"] = m.group(2).strip() if m else tit
                o["numero"] = j
                datos["observaciones"].append(o)
        elif t.startswith("evaluacion"):
            ev, resto = {}, []
            for l in cuerpo:
                m = _RE_META.match(l)
                if m:
                    k = _norm(m.group(1))
                    if k.startswith("gobierno"):
                        ev["gobierno"] = m.group(2).strip()
                    elif k.startswith("gestion"):
                        ev["gestion_riesgos"] = m.group(2).strip()
                    elif k.startswith("entorno"):
                        ev["entorno_control"] = m.group(2).strip()
                    else:
                        resto.append(l)
                else:
                    resto.append(l)
            ev["conclusion"] = "\n".join(resto).strip()
            datos["evaluacion_global"] = ev
        elif t.startswith("proximos") or t.startswith("siguientes"):
            datos["proximos_pasos"] = "\n".join(cuerpo).strip()
    return datos


def parrafos_con_lineas(texto: str) -> list[tuple[int, str]]:
    """Divide en párrafos (bloques separados por línea en blanco), devolviendo
    (nº de línea inicial 1-based, párrafo). Ignora blockquotes (`>`)."""
    salida = []
    inicio, buffer = None, []
    for i, linea in enumerate(texto.splitlines(), 1):
        if linea.strip() == "":
            if buffer:
                salida.append((inicio, "\n".join(buffer)))
            inicio, buffer = None, []
        elif linea.lstrip().startswith(">"):
            continue
        else:
            if inicio is None:
                inicio = i
            buffer.append(linea)
    if buffer:
        salida.append((inicio, "\n".join(buffer)))
    return salida
