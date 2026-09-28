"""Comparación del informe entre dos versiones, apartado a apartado (lo que la web
pinta con «Últimos cambios»). Determinista, sin modelo.

Cada apartado de 02_informe.md (el mismo que se pinta y se exporta como diapositiva)
se empareja con su versión anterior por tipo y título; dentro de cada uno, las líneas
(párrafos, viñetas, metadatos) se comparan como un diff unificado y, en las líneas
modificadas, se marcan las palabras que cambian. La versión anterior es un snapshot
de historial/, así que cubre todo lo que escribe `Expediente.escribir`: chat,
buzón, actas de reunión, edición manual, correcciones del modelo, volcados y deshacer.
"""
from __future__ import annotations

import difflib
import re
import unicodedata

from .formato_md import MARCA_EVALUACION, apartados_informe, parsear_informe

# Motivo con el que se guardó el snapshot (Expediente.escribir) → origen del cambio que vino después.
ORIGENES = {
    "cambio": "Chat del asistente",
    "reunion": "Acta de reunión",
    "aplicar-cambios": "Buzón de instrucciones",
    "web": "Edición manual",
    "corregir": "Corrección de estilo",
    "condensar": "Condensación",
    "redactar-contexto": "Redacción de introducción y resumen",
    "redactar-conclusiones": "Volcado de conclusiones",
    "antes-de-deshacer": "Deshacer",
    "revision": "Revisión de vocabulario",
}

_TOKEN = re.compile(r"\w+|\s+|[^\w\s]")
UMBRAL_PALABRAS = 0.4   # por debajo, la línea se ha reescrito entera: no se marcan palabras sueltas
UMBRAL_PARECIDO = 0.6   # por debajo (en título y en prosa), un apartado en el sitio de otro es otro distinto (eliminado + nuevo)


def origen_cambio(motivo: str) -> str:
    return ORIGENES.get(motivo, motivo.replace("-", " ").capitalize() or "Cambio")


def _norm(s: str) -> str:
    s = unicodedata.normalize("NFKD", s or "").encode("ascii", "ignore").decode().lower()
    return re.sub(r"\s+", " ", s).strip()


def _apartados(md: str) -> list[dict]:
    """Apartados de una versión; la evaluación global se compara dentro del resumen.
    Si no se puede interpretar, el documento entero es un único apartado."""
    try:
        datos = parsear_informe(md)
        apartados = apartados_informe(datos)
    except Exception:  # noqa: BLE001 — un snapshot antiguo o editado a mano no debe romper la comparación
        return [_documento(md)] if md.strip() else []
    if datos.get("evaluacion_global"):
        res = next(a for a in apartados if a["id"] == "resumen")
        res["markdown"] = f"{res['markdown']}\n\n{MARCA_EVALUACION} {datos['evaluacion_global']}".strip()
    return [a for a in apartados if a["markdown"].strip()]


def _documento(md: str) -> dict:
    return {"id": "documento", "tipo": "documento", "titulo": "Documento completo", "markdown": md, "numero": 0, "nivel_riesgo": ""}


def _segmentos(a: str, b: str) -> tuple[list[dict] | None, list[dict] | None]:
    """Palabras que cambian entre una línea eliminada y su sustituta (None si no se parecen)."""
    ta, tb = _TOKEN.findall(a), _TOKEN.findall(b)
    sm = difflib.SequenceMatcher(None, ta, tb, autojunk=False)
    if sm.ratio() < UMBRAL_PALABRAS:
        return None, None
    sa: list[dict] = []
    sb: list[dict] = []

    def poner(lista: list[dict], texto: str, cambio: bool) -> None:
        if not texto:
            return
        if lista and lista[-1]["cambio"] == cambio:
            lista[-1]["texto"] += texto
        else:
            lista.append({"texto": texto, "cambio": cambio})

    for op, i1, i2, j1, j2 in sm.get_opcodes():
        igual = op == "equal"
        poner(sa, "".join(ta[i1:i2]), not igual)
        poner(sb, "".join(tb[j1:j2]), not igual)
    return sa, sb


def _lineas(antes: str, despues: str) -> list[dict]:
    """Diff por líneas no vacías (cada párrafo o viñeta es una línea del Markdown)."""
    a = [l for l in antes.splitlines() if l.strip()]
    b = [l for l in despues.splitlines() if l.strip()]
    filas: list[dict] = []
    for op, i1, i2, j1, j2 in difflib.SequenceMatcher(None, a, b, autojunk=False).get_opcodes():
        if op == "equal":
            filas += [{"tipo": "igual", "texto": l, "segmentos": None} for l in a[i1:i2]]
            continue
        borradas = [{"tipo": "del", "texto": l, "segmentos": None} for l in a[i1:i2]]
        nuevas = [{"tipo": "add", "texto": l, "segmentos": None} for l in b[j1:j2]]
        for d, n in zip(borradas, nuevas):          # primero todas las eliminadas y luego las nuevas (como GitHub)
            d["segmentos"], n["segmentos"] = _segmentos(d["texto"], n["texto"])
        filas += borradas + nuevas
    return filas


# «### N. Título», «- Responsable: …», «*A continuación, se muestran…*»: comunes a casi todas las conclusiones
_METADATO = re.compile(r"^(#{1,6} |- [^:\n]{1,40}:( |$)|\*[^*].*\*$)")
_NUMERACION = re.compile(r"\*\*(recomendación|sugerencia de mejora|propuesta de mejora) \d+\.\d+\.\*\*")


def _prosa(md: str) -> list[str]:
    lineas = (_NUMERACION.sub("", l) for l in md.lower().splitlines() if l.strip() and not _METADATO.match(l.strip()))
    return re.findall(r"\w+", " ".join(lineas))


def _parecidos(x: dict, y: dict) -> bool:
    """¿El apartado `y` es `x` retocado (y no otro distinto en su sitio)?"""
    titulo = difflib.SequenceMatcher(None, _norm(x["titulo"]), _norm(y["titulo"]), autojunk=False).ratio()
    return titulo >= UMBRAL_PARECIDO or difflib.SequenceMatcher(None, _prosa(x["markdown"]), _prosa(y["markdown"]), autojunk=False).ratio() >= UMBRAL_PARECIDO


def _salida(ap: dict, estado: str, lineas: list[dict], prefijo: str = "") -> dict:
    return {"id": prefijo + ap["id"], "tipo": ap["tipo"], "titulo": ap["titulo"], "numero": ap["numero"],
            "nivel_riesgo": ap["nivel_riesgo"], "estado": estado, "lineas": lineas,
            "lineas_nuevas": sum(l["tipo"] == "add" for l in lineas),
            "lineas_borradas": sum(l["tipo"] == "del" for l in lineas)}


def comparar_informes(antes: str, despues: str) -> dict:
    """Apartados de `despues` (más los eliminados, en su posición anterior) con su
    estado (igual | modificado | nuevo | eliminado) y sus líneas comparadas."""
    va, vb = _apartados(antes), _apartados(despues)
    clave = lambda ap: (ap["tipo"], _norm(ap["titulo"]))  # noqa: E731
    salida: list[dict] = []

    def emparejar(x: dict, y: dict) -> None:
        lineas = _lineas(x["markdown"], y["markdown"])
        cambia = any(l["tipo"] != "igual" for l in lineas)
        salida.append(_salida(y, "modificado" if cambia else "igual", lineas))

    ops = difflib.SequenceMatcher(None, [clave(x) for x in va], [clave(y) for y in vb], autojunk=False).get_opcodes()
    for op, i1, i2, j1, j2 in ops:
        viejos, nuevos = va[i1:i2], vb[j1:j2]
        if op == "equal":
            for x, y in zip(viejos, nuevos):
                emparejar(x, y)
            continue
        # título cambiado: se empareja por orden con el siguiente del mismo tipo que se le parezca (título
        # o prosa); una conclusión sustituida por otra distinta queda como eliminada + nueva
        restantes = list(nuevos)
        for x in viejos:
            y = next((n for n in restantes if n["tipo"] == x["tipo"] and _parecidos(x, n)), None)
            if y is None:
                salida.append(_salida(x, "eliminado", _lineas(x["markdown"], ""), prefijo="antes-"))
                continue
            for n in restantes[:restantes.index(y)]:
                salida.append(_salida(n, "nuevo", _lineas("", n["markdown"])))
            restantes = restantes[restantes.index(y) + 1:]
            emparejar(x, y)
        for n in restantes:
            salida.append(_salida(n, "nuevo", _lineas("", n["markdown"])))

    if antes != despues and all(s["estado"] == "igual" for s in salida):
        # el cambio está fuera de los apartados (cabecera, texto fuera de sección): se enseña el documento entero
        salida.append(_salida(_documento(despues), "modificado", _lineas(antes, despues)))
    return {"apartados": salida,
            "lineas_nuevas": sum(s["lineas_nuevas"] for s in salida),
            "lineas_borradas": sum(s["lineas_borradas"] for s in salida)}
