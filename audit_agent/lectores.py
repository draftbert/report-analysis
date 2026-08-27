"""
Lectores de documentos de contexto/ y papeles_trabajo/.

Interfaz común: `leer(ruta) -> Documento` con el texto normalizado a Markdown.
.md/.txt se leen aquí (con normalización del pegado desde Excel); .docx,
.xlsx, .pdf y .pptx pasan por `audit_agent.extractores` (extractores
aportados por el usuario desde audit-engine: orden real del documento,
encabezados, listas, tablas, OCR). Ningún lector inventa secciones.

Añadir un formato nuevo = escribir una función `_leer_xxx(ruta) -> str` y
registrarla en `LECTORES` por extensión. Cuando se conozca el formato real
de la exportación de Pentana, se añade aquí (p. ej. un lector específico que
reconozca sus cabeceras "Tarea / Prueba realizada / Resultados / Comentarios
del área / Evidencias") sin tocar el resto de la herramienta.

Lo que se envía al modelo queda registrado en trazas/ (ver acciones.extraer)
con el nombre del lector usado, para poder auditar la fidelidad de la lectura.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path


class LecturaError(RuntimeError):
    pass


@dataclass
class Documento:
    nombre: str
    lector: str
    texto: str        # Markdown normalizado
    avisos: list[str]
    carpeta: str = ""  # contexto | papeles_trabajo (lo rellena el expediente)


# ------------------------------------------------------------------ utilidades
def _tabla_md(filas: list[list[str]]) -> str:
    filas = [[(c or "").strip().replace("\n", " ").replace("|", "\\|") for c in f] for f in filas]
    filas = [f for f in filas if any(f)]
    if not filas:
        return ""
    ancho = max(len(f) for f in filas)
    filas = [f + [""] * (ancho - len(f)) for f in filas]
    cab, cuerpo = filas[0], filas[1:]
    out = ["| " + " | ".join(cab) + " |", "|" + "---|" * ancho]
    out += ["| " + " | ".join(f) + " |" for f in cuerpo]
    return "\n".join(out)


def _limpiar(texto: str) -> str:
    texto = texto.replace("\r\n", "\n").replace("\r", "\n")
    texto = re.sub(r"[ \t]+\n", "\n", texto)
    texto = re.sub(r"\n{3,}", "\n\n", texto)
    return texto.strip() + "\n"


# ------------------------------------------------------------------ lectores
def _desexcelizar(texto: str) -> str:
    """Normaliza texto pegado desde Excel (caso real de los papeles de trabajo):
    tabulaciones de celdas vacías al final de línea, celdas multilínea entre
    comillas (con `""` como comilla literal) y ráfagas de líneas en blanco."""
    lineas = [l.rstrip("\t ") for l in texto.replace("\r\n", "\n").split("\n")]
    salida: list[str] = []
    en_celda = False
    for l in lineas:
        if not en_celda and l.startswith('"') and not (len(l) > 1 and l.endswith('"') and l.count('"') % 2 == 0):
            en_celda = True
            l = l[1:]
        elif not en_celda and l.startswith('"') and l.endswith('"') and len(l) > 1:
            l = l[1:-1]
        elif en_celda and l.endswith('"') and (len(l) - len(l.rstrip('"'))) % 2 == 1:
            en_celda = False
            l = l[:-1]
        salida.append(l.replace('""', '"'))
    return "\n".join(salida)


def _leer_texto(ruta: Path) -> tuple[str, list[str]]:
    bruto = ruta.read_text(encoding="utf-8", errors="replace")
    avisos = []
    if "\t" in bruto or re.search(r'^"', bruto, re.M):
        bruto = _desexcelizar(bruto)
        avisos.append("Texto pegado desde Excel: se han normalizado tabulaciones y celdas entre comillas.")
    return _limpiar(bruto), avisos


MAX_FILAS_DATOS = 40   # filas de datos por hoja que se envían al modelo (el resto se resume en un aviso)
_RE_SEPARADOR_MD = re.compile(r"^\|\s*(?:-{3,}\s*\|\s*)+$")


def _celdas(linea: str) -> list[str]:
    return [c.strip() for c in linea.strip()[1:-1].split(" | ")]


def _compactar_xlsx(texto: str) -> tuple[str, list[str]]:
    """Cada hoja de Excel llega como una tabla con todas sus columnas, muchas
    vacías. Para el modelo: se quitan las columnas vacías, las filas con una
    sola celda (la narrativa de la hoja «Memo»: contexto, objetivo, pruebas,
    conclusiones) pasan a párrafos y las hojas de datos se recortan a las
    primeras MAX_FILAS_DATOS filas, con aviso de cuántas quedan fuera."""
    avisos: list[str] = []
    salida: list[str] = []
    for sec in re.split(r"(?m)^(?=# )", texto):
        if not sec.strip():
            continue
        lineas = sec.rstrip("\n").split("\n")
        titulo = lineas[0] if lineas[0].startswith("# ") else ""
        cuerpo = lineas[1:] if titulo else lineas
        filas = [_celdas(l) for l in cuerpo if l.startswith("|") and not _RE_SEPARADOR_MD.match(l)]
        sueltas = [l for l in cuerpo if not l.startswith("|") and l.strip()]
        ancho = max((len(f) for f in filas), default=0)
        filas = [f + [""] * (ancho - len(f)) for f in filas]
        usadas = [j for j in range(ancho) if any(f[j] for f in filas)]
        filas = [[f[j] for j in usadas] for f in filas]
        bloque: list[str] = [titulo, ""] if titulo else []
        tabla: list[list[str]] = []
        n_datos, omitidas = 0, 0

        def volcar_tabla():
            if not tabla:
                return
            w = max(len(f) for f in tabla)
            cab, resto = tabla[0], tabla[1:]
            bloque.append("| " + " | ".join(cab + [""] * (w - len(cab))) + " |")
            bloque.append("|" + "---|" * w)
            bloque.extend("| " + " | ".join(f + [""] * (w - len(f))) + " |" for f in resto)
            bloque.append("")
            tabla.clear()

        for f in filas:
            no_vacias = [c for c in f if c]
            if len(no_vacias) <= 1:
                volcar_tabla()
                if no_vacias:
                    bloque.append(no_vacias[0])
                continue
            n_datos += 1
            if n_datos > MAX_FILAS_DATOS:
                omitidas += 1
                continue
            tabla.append(no_vacias)
        volcar_tabla()
        if omitidas:
            bloque.append(f"_(… {omitidas:,} filas de datos más no incluidas)_".replace(",", "."))
            avisos.append(f"Hoja «{titulo[2:].strip() or '?'}»: {n_datos:,} filas de datos; se envían las {MAX_FILAS_DATOS} primeras.".replace(",", "."))
        bloque.extend(sueltas)
        salida.append("\n".join(bloque).rstrip() + "\n")
    return "\n".join(salida), avisos


def _leer_con_extractor(ruta: Path) -> tuple[str, list[str]]:
    """DOCX / XLSX / PDF / PPTX con los extractores de `audit_agent.extractores`
    (orden real del documento, encabezados, listas, tablas, OCR de imágenes y
    de PDF escaneados si Tesseract está instalado)."""
    from .extractores import a_markdown
    from .extractores.ocr import ocr_disponible
    avisos: list[str] = []
    try:
        texto = a_markdown(ruta)
    except Exception as exc:  # noqa: BLE001 — el fallo de una librería de formato se reporta con contexto
        raise LecturaError(f"{ruta.name}: no se ha podido leer ({type(exc).__name__}: {exc}).") from exc
    texto = _limpiar(re.sub(r"!\[[^\]]*\]\(\)", "", texto))  # imágenes sin OCR: fuera
    if ruta.suffix.lower() == ".xlsx":
        texto, avisos_xlsx = _compactar_xlsx(texto)
        texto = _limpiar(texto)
        avisos += avisos_xlsx
    if len(texto.strip()) < 20:
        if ruta.suffix.lower() == ".pdf":
            raise LecturaError(
                f"{ruta.name}: el PDF no tiene capa de texto extraíble" +
                ("" if ocr_disponible() else " y el OCR (Tesseract) no está disponible") +
                ". Exporta desde Pentana a Word/Excel/PDF con texto.")
        avisos.append(f"{ruta.name}: no contiene texto legible.")
    return texto, avisos


LECTORES = {
    ".md": ("texto", _leer_texto),
    ".txt": ("texto", _leer_texto),
    ".docx": ("docx", _leer_con_extractor),
    ".xlsx": ("xlsx", _leer_con_extractor),
    ".pdf": ("pdf", _leer_con_extractor),
    ".pptx": ("pptx", _leer_con_extractor),
}
EXTENSIONES = tuple(LECTORES)


def leer(ruta: str | Path) -> Documento:
    ruta = Path(ruta)
    ext = ruta.suffix.lower()
    if ext not in LECTORES:
        raise LecturaError(f"{ruta.name}: formato no soportado ({ext}). Admitidos: {', '.join(EXTENSIONES)}.")
    nombre_lector, fn = LECTORES[ext]
    texto, avisos = fn(ruta)
    return Documento(nombre=ruta.name, lector=nombre_lector, texto=texto, avisos=avisos)
