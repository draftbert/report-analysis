"""
Formato Markdown de ida y vuelta (render <-> parse) de los ficheros que el
auditor edita. La regla de oro: lo que la herramienta escribe, la
herramienta lo sabe leer después de que una persona lo haya editado.

Convenciones (tolerantes a mayúsculas, tildes y espacios):

    ## C-01 · Título                          (01_conclusiones.md)
    ### 1. Título                             (02_informe.md, detalle y sugerencias)
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
    for n in ("alto", "medio", "bajo"):
        if v.startswith(n):
            return n.capitalize()
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

> Texto de trabajo del informe. Edítalo libremente respetando los títulos `##` de
> sección y la estructura de cada conclusión (`###` + campos en negrita): es lo que
> permite generar el PPT y aplicar cambios automáticamente.
> Acciones: `redactar-contexto` (introducción y resumen), `redactar-conclusiones`
> (vuelca las aprobadas), `revisar`/`corregir` (vocabulario), `aplicar-cambios`
> (desde 03_instrucciones.md), `diff`, `deshacer`, `ppt`, `archivar`.

"""
SECCIONES_INFORME = ("Introducción", "Resumen ejecutivo", "Detalle de conclusiones", "Sugerencias de mejora")
PENDIENTE = "_(pendiente)_"


def render_informe(datos: dict, proyecto: dict) -> str:
    partes = [CABECERA_INFORME.format(
        nombre=proyecto.get("nombre", ""), referencia=proyecto.get("referencia", ""),
        fecha=proyecto.get("fecha", ""), distribucion=", ".join(proyecto.get("distribucion", [])))]
    partes.append(f"## Introducción\n\n{(datos.get('introduccion') or PENDIENTE).strip()}\n")
    partes.append(f"## Resumen ejecutivo\n\n{(datos.get('resumen_ejecutivo') or PENDIENTE).strip()}\n")
    partes.append("## Detalle de conclusiones\n")
    conclusiones = datos.get("conclusiones", [])
    if not conclusiones:
        partes.append(PENDIENTE + "\n")
    for i, c in enumerate(conclusiones, 1):
        partes.append(_bloque({**c, "tipo": "conclusion"}, f"### {i}. {(c.get('titulo', '') or '').strip()}",
                              con_estado=False, con_notas=False))
    partes.append("## Sugerencias de mejora\n")
    sugerencias = datos.get("sugerencias", [])
    if not sugerencias:
        partes.append("_(ninguna)_\n" if conclusiones else PENDIENTE + "\n")
    for i, s in enumerate(sugerencias, 1):
        partes.append(_bloque({**s, "tipo": "sugerencia"}, f"### {i}. {(s.get('titulo', '') or '').strip()}",
                              con_estado=False, con_notas=False))
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


def _parsear_lista(lineas: list[str], tipo: str) -> list[dict]:
    _, bloques = _partir_por_cabeceras("\n".join(lineas), 3)
    salida = []
    for j, (tit, lin) in enumerate(bloques, 1):
        m = _RE_NUM.match(tit)
        c = _parsear_bloque(lin)
        c["titulo"] = m.group(2).strip() if m else tit
        c["numero"], c["tipo"] = j, tipo
        salida.append(c)
    return salida


def parsear_informe(texto: str) -> dict:
    """02_informe.md -> dict (introduccion, resumen_ejecutivo, conclusiones, sugerencias).
    Las secciones marcadas como pendientes devuelven cadena vacía / lista vacía."""
    _, secciones = _partir_por_cabeceras(texto, 2)
    datos: dict = {"introduccion": "", "resumen_ejecutivo": "", "conclusiones": [], "sugerencias": []}
    for titulo, lineas in secciones:
        t = _norm(titulo)
        cuerpo = [l for l in lineas if not l.lstrip().startswith(">")]
        texto_cuerpo = "\n".join(cuerpo).strip()
        if texto_cuerpo in (PENDIENTE, "_(ninguna)_"):
            texto_cuerpo = ""
        if t.startswith("introduccion"):
            datos["introduccion"] = texto_cuerpo
        elif t.startswith("resumen"):
            datos["resumen_ejecutivo"] = texto_cuerpo
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
