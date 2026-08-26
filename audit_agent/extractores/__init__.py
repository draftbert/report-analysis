"""
Extractores de documentos (DOCX, PDF, PPTX, XLSX) -> Markdown.

Módulos aportados por el usuario desde otros proyectos (audit-engine),
integrados aquí con su base común (models, markdown, ocr, base). Cada
extractor produce `Page`s de bloques tipados (encabezados, párrafos, listas,
tablas, imágenes con OCR) en el orden real del documento, y
`markdown.render_document` los vuelca a Markdown de forma idéntica para todos
los formatos. Es la capa que usa `lectores.py` para contexto/ y papeles_trabajo/.

Los ficheros llevan sufijo `_` (docx_.py, pptx_.py…) para no sombrear a los
paquetes python-docx / python-pptx de los que dependen.
"""

from __future__ import annotations

from pathlib import Path

from .base import BaseExtractor
from .docx_ import DOCXExtractor
from .markdown import render_document
from .models import Page
from .pdf_ import PDFExtractor
from .pptx_ import PPTXExtractor
from .xlsx_ import XLSXExtractor

EXTRACTORES: dict[str, type[BaseExtractor]] = {
    ".docx": DOCXExtractor,
    ".pdf": PDFExtractor,
    ".pptx": PPTXExtractor,
    ".xlsx": XLSXExtractor,
}


def extraer_paginas(ruta: str | Path) -> list[Page]:
    ruta = Path(ruta)
    try:
        extractor = EXTRACTORES[ruta.suffix.lower()]
    except KeyError:
        raise ValueError(f"Sin extractor para {ruta.suffix!r}") from None
    return extractor().extract_pages(ruta)


def a_markdown(ruta: str | Path) -> str:
    return render_document(extraer_paginas(ruta))


__all__ = ["EXTRACTORES", "extraer_paginas", "a_markdown", "render_document", "Page"]
