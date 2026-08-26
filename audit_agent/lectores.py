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
