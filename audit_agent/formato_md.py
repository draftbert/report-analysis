"""
Formato Markdown de ida y vuelta (render <-> parse) de los ficheros que el
auditor edita. La regla de oro: lo que la herramienta escribe, la
herramienta lo sabe leer después de que una persona lo haya editado.

Convenciones (tolerantes a mayúsculas, tildes y espacios):

    ## C-01 · Título                          (01_conclusiones.md: campos etiquetados, se validan aquí)
    ### 1. Título                             (02_informe.md: apartado WYSIWYG = diapositiva; ver render_informe)
    - Tipo: conclusion | sugerencia
    - Estado: propuesta | aprobada | descartada
    - Prueba: 2.11 a) …                       (referencia del papel de trabajo)
    - Nivel de riesgo: Alto | Medio | Bajo [ (propuesto por el modelo, sin evidencia en PT) ]
    - Área: ...            - Responsable: ...            - Plazo: ...
    - Ref. recomendación: TMSCIIF-10   (recomendación abierta de otra auditoría a la que se remite)
    - Fuente: ...
    **Incidencia detectada:** texto (puede ocupar varios párrafos, tablas, listas)
    **Causa raíz:** ...
    **Cómo se ha llegado:** ...
    **Consecuencias:** ...
    **Recomendación:** ...                    (en sugerencias: **Propuesta de mejora:**)
    **Notas del auditor:** (solo en 01_conclusiones.md; se envían al modelo en `regenerar`)

Las líneas que empiezan por `>` son instrucciones para la persona y se ignoran.
"""
from __future__ import annotations

import re
import unicodedata
from pathlib import Path

import yaml

_TEXTOS_POR_DEFECTO = {
    "plan_auditoria": "La auditoría ha sido realizada en cumplimiento del Plan de Auditoría del año {anio}, aprobado por la Comisión de Auditoría y Cumplimiento.",
    "normas": "El trabajo ha sido llevado a cabo de acuerdo con las Normas Internacionales para la Práctica Profesional de Auditoría Interna, según certificado emitido por el Instituto de Auditores Internos.",
    "proximos_pasos": "Los destinatarios del presente informe deberán remitir su conformidad sobre el mismo al Departamento de Auditoría Interna. En el Anexo se recogerán los planes de acción a implantar para solventar las incidencias identificadas acorde al plazo acordado de implantación.",
    "intro_sugerencias": "A continuación, se muestran las debilidades identificadas para las que, dado su impacto limitado, no se exigirá la elaboración de un plan de acción específico, si bien se exponen para su consideración con el objetivo de mejorar el nivel de control.",
    "detalles_descriptivos": "A continuación, se muestran los detalles descriptivos de la situación anterior:",
    "escala_evaluacion_global": ["Deficiente", "Insuficiente", "Mejorable", "Razonable", "Adecuado"],
}


def textos_informe() -> dict:
    """Textos fijos del informe (config/textos_informe.yaml, con valores por defecto)."""
    ruta = Path(__file__).resolve().parent.parent / "config" / "textos_informe.yaml"
    textos = dict(_TEXTOS_POR_DEFECTO)
    if ruta.exists():
        textos.update(yaml.safe_load(ruta.read_text(encoding="utf-8")) or {})
    return textos


TEXTOS = textos_informe()

ESTADOS = ("propuesta", "aprobada", "descartada")
TIPOS = ("conclusion", "sugerencia")

# Coletilla que marca un nivel de riesgo estimado por el modelo sin evidencia
# en el papel de trabajo (PT). La quita `aprobar` cuando el auditor valida.
COLETILLA_RIESGO_PROPUESTO = "(propuesto por el modelo, sin evidencia en PT)"

CAMPOS_TEXTO = [  # (clave, etiqueta visible)
    ("incidencia", "Incidencia detectada"),
    ("causa_raiz", "Causa raíz"),
    ("como_se_ha_llegado", "Cómo se ha llegado"),
    ("consecuencias", "Consecuencias"),
    ("recomendacion", "Recomendación"),
]
ETIQUETA_PROPUESTA = "Propuesta de mejora"   # etiqueta de `recomendacion` cuando tipo=sugerencia
CAMPOS_META = [
    ("prueba", "Prueba"),
    ("nivel_riesgo", "Nivel de riesgo"),
    ("area", "Área"),
    ("responsable", "Responsable"),
    ("plazo", "Plazo"),
    ("referencia_recomendacion", "Ref. recomendación"),
    ("fuente", "Fuente"),
]

_RE_META = re.compile(r"^\s*[-*]\s*([^:]+?)\s*:\s*(.*)$")
_RE_CAMPO = re.compile(r"^\s*\*\*([^*]+?)\s*:?\s*\*\*\s*:?\s*(.*)$")
_RE_ID = re.compile(r"^(?:C|OBS)-(\d+)\s*[·\-–:.]?\s*(.*)$", re.IGNORECASE)
_RE_NUM = re.compile(r"^(\d+)\s*[.)·\-–:]?\s*(.*)$")


def _norm(s: str) -> str:
    nfkd = unicodedata.normalize("NFD", s.strip().lower())
    return re.sub(r"\s+", " ", "".join(c for c in nfkd if unicodedata.category(c) != "Mn"))


_CLAVES = {_norm(et): cl for cl, et in CAMPOS_TEXTO + CAMPOS_META}
_CLAVES.update({
    "estado": "estado", "tipo": "tipo", "notas del auditor": "notas", "notas": "notas",
    _norm(ETIQUETA_PROPUESTA): "recomendacion", "propuesta": "recomendacion",
    "incidencia": "incidencia", "causa": "causa_raiz", "como se ha llegado a ella": "como_se_ha_llegado",
    "como": "como_se_ha_llegado", "detalles descriptivos": "como_se_ha_llegado", "consecuencia": "consecuencias",
    "nivel": "nivel_riesgo", "riesgo": "nivel_riesgo", "ref recomendacion": "referencia_recomendacion",
    "referencia recomendacion": "referencia_recomendacion", "referencia": "referencia_recomendacion",
    "ref.": "referencia_recomendacion",
})


def separar_coletilla(valor: str) -> tuple[str, bool]:
    """'Medio (propuesto por el modelo, sin evidencia en PT)' -> ('Medio', True)."""
    v = valor.strip()
    if COLETILLA_RIESGO_PROPUESTO in v:
        return v.replace(COLETILLA_RIESGO_PROPUESTO, "").strip(), True
    return v, False


def normalizar_nivel(valor: str) -> str:
    valor, _ = separar_coletilla(valor)
    v = _norm(valor)
    for n, etiqueta in (("critico", "Crítico"), ("alto", "Alto"), ("medio", "Medio"), ("bajo", "Bajo")):
        if v.startswith(n):
            return etiqueta
    return valor.strip()


def normalizar_tipo(valor: str) -> str:
    v = _norm(valor)
    return "sugerencia" if v.startswith("sug") or v.startswith("mejora") else "conclusion"


# ====================================================================== RENDER
def _bloque(c: dict, cabecera: str, con_estado: bool, con_notas: bool) -> str:
    tipo = normalizar_tipo(c.get("tipo", "conclusion"))
    lineas = [cabecera, ""]
    if con_estado:
        lineas.append(f"- Tipo: {tipo}")
        lineas.append(f"- Estado: {c.get('estado', 'propuesta')}")
    for clave, etiqueta in CAMPOS_META:
        valor = c.get(clave, "") or ""
        if clave == "fuente" and not con_estado:
            continue  # en el informe no se muestra la fuente interna
        if clave == "nivel_riesgo" and c.get("riesgo_propuesto") and valor:
            valor = f"{valor} {COLETILLA_RIESGO_PROPUESTO}"
        if clave in ("area", "responsable", "plazo", "nivel_riesgo", "referencia_recomendacion") \
                and tipo == "sugerencia" and not valor and not con_estado:
            continue
        lineas.append(f"- {etiqueta}: {valor}")
    lineas.append("")
    for clave, etiqueta in CAMPOS_TEXTO:
        if clave == "recomendacion" and tipo == "sugerencia":
            etiqueta = ETIQUETA_PROPUESTA
        valor = (c.get(clave, "") or "").strip()
        # Listas, tablas o varios párrafos: en línea aparte para que rendericen bien
        sep = "\n" if valor.startswith(("- ", "* ", "|", "1)", "1.")) or "\n" in valor else " "
        lineas.append(f"**{etiqueta}:**{sep}{valor}" if valor else f"**{etiqueta}:** ")
        lineas.append("")
    if con_notas:
        lineas.append(f"**Notas del auditor:** {(c.get('notas', '') or '').strip()}")
        lineas.append("")
    return "\n".join(lineas)


CABECERA_CONCLUSIONES = """# Detalle de conclusiones y sugerencias de mejora — {referencia} · {nombre}

> Cómo trabajar este fichero:
> - Cada bloque es una incidencia detectada en los papeles de trabajo: qué se ha
>   detectado, por qué (causa raíz), cómo se ha llegado (datos y tablas) y consecuencias.
> - `Tipo: conclusion` lleva recomendación y plan de acción; `Tipo: sugerencia` es una
>   mejora sin plan de acción (irá a «Sugerencias de mejora»). Cámbialo si procede.
> - Corrige el texto directamente y cambia `Estado: propuesta` por `aprobada` o `descartada`.
> - Recomendación: si la tienes, escríbela en «Recomendación:» y se respetará tal cual
>   (`recomendar` solo le da formato). Si la dejas vacía, `recomendar` la propone. Varias
>   recomendaciones: un párrafo cada una (en el PPT se numeran N.1, N.2…).
> - Área / Responsable / Plazo / Ref. recomendación: rellénalos si no vienen del papel de trabajo.
> - Si quieres que el modelo rehaga un bloque, escribe qué cambiar en «Notas del auditor»
>   y ejecuta `regenerar C-XX`. `revisar-conclusiones` comprueba vocabulario y campos.
> - Cuando estén aprobadas y con recomendación, ejecuta `redactar-conclusiones`.

"""


def render_conclusiones(conclusiones: list[dict], proyecto: dict, notas_extraccion: str = "",
                        pruebas_sin_incidencia: list[str] | None = None) -> str:
    partes = [CABECERA_CONCLUSIONES.format(referencia=proyecto.get("referencia", ""),
                                           nombre=proyecto.get("nombre", ""))]
    if pruebas_sin_incidencia:
        partes.append("> **Pruebas concluidas sin incidencias** (no generan conclusión): "
                      + "; ".join(pruebas_sin_incidencia) + "\n")
    if notas_extraccion.strip():
        partes.append("> **Notas del modelo sobre la extracción:** "
                      + notas_extraccion.strip().replace("\n", "\n> ") + "\n")
    for i, c in enumerate(conclusiones, 1):
        ident = c.get("id") or f"C-{i:02d}"
        partes.append(_bloque(c, f"## {ident} · {(c.get('titulo', '') or '').strip()}", con_estado=True, con_notas=True))
    return "\n".join(partes).rstrip() + "\n"


CABECERA_INFORME = """# Informe de auditoría interna — {nombre}

- Referencia: {referencia}
- Fecha: {fecha}
- Distribución: {distribucion}

> Texto de trabajo del informe: lo que se lee aquí es lo que exporta `ppt`, apartado a
> apartado (cada `##` y cada `###` es una diapositiva). Edítalo libremente respetando los
> títulos y, en las conclusiones, la línea «A continuación, se muestran los detalles…»,
> las viñetas de datos y los párrafos `**Recomendación N.1.**`.
> Acciones: `redactar-contexto` (introducción y resumen), `redactar-conclusiones`
> (vuelca las aprobadas), `revisar`/`corregir` (vocabulario), `aplicar-cambios`
> (desde 03_instrucciones.md), `diff`, `deshacer`, `ppt` (exporta el informe entero),
> `archivar`.

"""
SECCIONES_INFORME = ("Introducción", "Resumen ejecutivo", "Detalle de conclusiones", "Sugerencias de mejora")
PENDIENTE = "_(pendiente)_"
MARCADOR_DETALLES = f"*{TEXTOS['detalles_descriptivos']}*"
MARCA_EVALUACION = "**Evaluación global:**"
MARCA_PROXIMOS = "**Próximos pasos:**"
META_INFORME = [("prueba", "Prueba"), ("nivel_riesgo", "Nivel de riesgo"), ("area", "Área"),
                ("responsable", "Responsable"), ("plazo", "Plazo"), ("referencia_recomendacion", "Ref. recomendación")]


def partir_recomendaciones(texto: str) -> list[str]:
    """Una recomendación por párrafo (o por viñeta); sin prefijos de lista."""
    partes = re.split(r"\n\s*\n|\n(?=\s*[-*•]\s)", (texto or "").strip())
    return [re.sub(r"^\s*(?:[-*•]|\d+[.)])\s*", "", x).strip() for x in partes if x.strip()]


def _apartado_conclusion(c: dict, num: int, es_sugerencia: bool) -> str:
    """Apartado del informe tal como se leerá en la diapositiva."""
    L = [f"### {num}. {(c.get('titulo', '') or '').strip()}", ""]
    for clave, etiqueta in META_INFORME:
        valor = (c.get(clave, "") or "").strip()
        if clave == "nivel_riesgo" and c.get("riesgo_propuesto") and valor:
            valor = f"{valor} {COLETILLA_RIESGO_PROPUESTO}"
        if es_sugerencia and not valor and clave != "prueba":
            continue
        L.append(f"- {etiqueta}: {valor}")
    L.append("")
    cuerpo = [t.strip() for t in ((c.get("incidencia") or ""), (c.get("causa_raiz") or "")) if t and t.strip()]
    L += [p + "\n" for p in cuerpo]
    detalles = (c.get("como_se_ha_llegado") or "").strip()
    if detalles:
        items = [re.sub(r"^\s*[-*•/]\s*", "", l).strip() for l in detalles.splitlines() if l.strip()]
        L.append(MARCADOR_DETALLES)
        L += [f"- {it}" for it in items]
        L.append("")
    if (c.get("consecuencias") or "").strip():
        L.append(c["consecuencias"].strip() + "\n")
    etiqueta = "Propuesta de mejora" if es_sugerencia else "Recomendación"
    for k, rec in enumerate(partir_recomendaciones(c.get("recomendacion", "")), 1):
        L.append(f"**{etiqueta} {num}.{k}.** {rec}\n")
    return "\n".join(L)


def render_informe(datos: dict, proyecto: dict) -> str:
    partes = [CABECERA_INFORME.format(
        nombre=proyecto.get("nombre", ""), referencia=proyecto.get("referencia", ""),
        fecha=proyecto.get("fecha", ""), distribucion=", ".join(proyecto.get("distribucion", [])))]
    partes.append(f"## Introducción\n\n{(datos.get('introduccion') or PENDIENTE).strip()}\n")
    resumen = (datos.get("resumen_ejecutivo") or PENDIENTE).strip()
    if datos.get("evaluacion_global"):
        resumen += f"\n\n{MARCA_EVALUACION} {datos['evaluacion_global'].strip()}"
    if datos.get("resumen_ejecutivo"):
        resumen += f"\n\n{MARCA_PROXIMOS} {TEXTOS['proximos_pasos']}"
    partes.append(f"## Resumen ejecutivo\n\n{resumen}\n")
    partes.append("## Detalle de conclusiones\n")
    conclusiones = datos.get("conclusiones", [])
    if not conclusiones:
        partes.append(PENDIENTE + "\n")
    for i, c in enumerate(conclusiones, 1):
        partes.append(_apartado_conclusion(c, i, es_sugerencia=False))
    partes.append("## Sugerencias de mejora\n")
    sugerencias = datos.get("sugerencias", [])
    if sugerencias:
        partes.append(f"_{TEXTOS['intro_sugerencias']}_\n")
    else:
        partes.append("_(ninguna)_\n" if conclusiones else PENDIENTE + "\n")
    for i, s in enumerate(sugerencias, 1):
        partes.append(_apartado_conclusion(s, i, es_sugerencia=True))
    return "\n".join(partes).rstrip() + "\n"


# ====================================================================== PARSE
def _parsear_bloque(lineas: list[str]) -> dict:
    """Parsea las líneas de una conclusión (sin la cabecera) a dict."""
    c: dict = {"tipo": "conclusion", "estado": "propuesta", "prueba": "", "nivel_riesgo": "", "area": "",
               "responsable": "", "plazo": "", "referencia_recomendacion": "", "fuente": "", "notas": "",
               "riesgo_propuesto": False}
    for clave, _ in CAMPOS_TEXTO:
        c[clave] = ""
    campo_actual: str | None = None
    buffer: list[str] = []

    def cerrar():
        nonlocal buffer
        if campo_actual:
            c[campo_actual] = (c.get(campo_actual, "") + "\n".join(buffer)).strip()
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
            if clave == "estado" and valor:
                c[clave] = _norm(valor).split()[0]
            elif clave == "tipo":
                c[clave] = normalizar_tipo(valor)
            elif clave == "nivel_riesgo":
                c[clave] = normalizar_nivel(valor)
                c["riesgo_propuesto"] = separar_coletilla(valor)[1]
            else:
                c[clave] = valor
            continue
        if campo_actual is not None:
            buffer.append(linea.rstrip())
    cerrar()
    if c["estado"] not in ESTADOS:
        c["estado"] = "propuesta"
    return c


def _nivel_cabecera(linea: str) -> int:
    return len(linea) - len(linea.lstrip("#"))


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


def parsear_conclusiones(texto: str) -> list[dict]:
    """01_conclusiones.md -> lista de dicts (con id, tipo, estado, notas)."""
    _, bloques = _partir_por_cabeceras(texto, 2)
    salida = []
    for i, (titulo, lineas) in enumerate(bloques, 1):
        m = _RE_ID.match(titulo)
        if m:
            ident, titulo_limpio = f"C-{int(m.group(1)):02d}", m.group(2).strip()
        else:
            ident, titulo_limpio = f"C-{i:02d}", titulo
        c = _parsear_bloque(lineas)
        c["id"], c["titulo"] = ident, titulo_limpio
        salida.append(c)
    return salida


_RE_REC = re.compile(r"^\*\*(?:Recomendaci[oó]n|Propuesta de mejora)\s*\d+\.\d+\.?\*\*\s*(.*)$", re.IGNORECASE)


def _parsear_apartado(lineas: list[str]) -> dict:
    """Apartado WYSIWYG del informe -> dict con los mismos campos que una
    conclusión (la prosa del cuerpo va a `incidencia`; `causa_raiz` queda
    vacía porque en el informe ya no se distinguen)."""
    c: dict = {"tipo": "conclusion", "estado": "aprobada", "prueba": "", "nivel_riesgo": "", "area": "",
               "responsable": "", "plazo": "", "referencia_recomendacion": "", "fuente": "", "notas": "",
               "riesgo_propuesto": False, "incidencia": "", "causa_raiz": "", "como_se_ha_llegado": "",
               "consecuencias": "", "recomendacion": ""}
    cuerpo: list[str] = []          # párrafos antes de los detalles
    detalles: list[str] = []
    despues: list[str] = []         # párrafos tras los detalles (consecuencias)
    recs: list[str] = []
    fase = "meta"
    parrafo: list[str] = []

    def cerrar():
        nonlocal parrafo
        if parrafo:
            texto = "\n".join(parrafo).strip()
            if recs and fase == "rec":
                recs[-1] = (recs[-1] + "\n" + texto).strip()
            elif fase in ("meta", "cuerpo"):
                cuerpo.append(texto)
            else:
                despues.append(texto)
        parrafo = []

    for linea in lineas:
        if linea.lstrip().startswith(">"):
            continue
        if not linea.strip():
            cerrar()  # tras una recomendación, los párrafos siguientes la continúan
            continue
        m_rec = _RE_REC.match(linea.strip())
        if m_rec:
            cerrar()
            recs.append(m_rec.group(1).strip())
            fase = "rec"
            continue
        if linea.strip() == MARCADOR_DETALLES.strip() or linea.strip().lower().startswith("*a continuación, se muestran los detalles"):
            cerrar()
            fase = "detalles"
            continue
        if fase == "detalles" and re.match(r"^\s*[-*•/]\s+", linea):
            detalles.append(re.sub(r"^\s*[-*•/]\s+", "", linea).strip())
            continue
        if fase == "detalles":
            fase = "despues"
        m_meta = _RE_META.match(linea)
        if fase == "meta" and m_meta and _norm(m_meta.group(1)) in _CLAVES:
            clave = _CLAVES[_norm(m_meta.group(1))]
            valor = m_meta.group(2).strip()
            if clave == "nivel_riesgo":
                c[clave] = normalizar_nivel(valor)
                c["riesgo_propuesto"] = separar_coletilla(valor)[1]
            elif clave in c:
                c[clave] = valor
            continue
        if fase == "meta":
            fase = "cuerpo"
        parrafo.append(linea.rstrip())
    cerrar()
    c["incidencia"] = "\n\n".join(cuerpo)
    c["como_se_ha_llegado"] = "\n".join(f"- {d}" for d in detalles)
    c["consecuencias"] = "\n\n".join(despues)
    c["recomendacion"] = "\n\n".join(recs)
    return c


def _parsear_lista(lineas: list[str], tipo: str) -> list[dict]:
    _, bloques = _partir_por_cabeceras("\n".join(lineas), 3)
    salida = []
    for j, (tit, lin) in enumerate(bloques, 1):
        m = _RE_NUM.match(tit)
        c = _parsear_apartado(lin)
        c["titulo"] = m.group(2).strip() if m else tit
        c["numero"], c["tipo"] = j, tipo
        salida.append(c)
    return salida


def parsear_informe(texto: str) -> dict:
    """02_informe.md -> dict (introduccion, resumen_ejecutivo, conclusiones, sugerencias).
    Las secciones marcadas como pendientes devuelven cadena vacía / lista vacía."""
    _, secciones = _partir_por_cabeceras(texto, 2)
    datos: dict = {"introduccion": "", "resumen_ejecutivo": "", "evaluacion_global": "", "conclusiones": [], "sugerencias": []}
    for titulo, lineas in secciones:
        t = _norm(titulo)
        cuerpo = [l for l in lineas if not l.lstrip().startswith(">")]
        texto_cuerpo = "\n".join(cuerpo).strip()
        if texto_cuerpo in (PENDIENTE, "_(ninguna)_"):
            texto_cuerpo = ""
        if t.startswith("introduccion"):
            datos["introduccion"] = texto_cuerpo
        elif t.startswith("resumen"):
            lineas_res = []
            for l in texto_cuerpo.splitlines():
                if l.strip().startswith(MARCA_EVALUACION):
                    datos["evaluacion_global"] = l.strip()[len(MARCA_EVALUACION):].strip()
                elif l.strip().startswith(MARCA_PROXIMOS):
                    continue  # texto fijo: lo añade el render
                else:
                    lineas_res.append(l)
            datos["resumen_ejecutivo"] = "\n".join(lineas_res).strip()
        elif "conclusion" in t:
            datos["conclusiones"] = _parsear_lista(lineas, "conclusion")
        elif "sugerencia" in t or "mejora" in t:
            datos["sugerencias"] = _parsear_lista(lineas, "sugerencia")
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
