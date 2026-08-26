"""Extractor de XLSX con openpyxl.

Cada hoja es una `Page` y una sección de Markdown (`Heading` con el nombre
de la hoja), siguiendo el mismo patrón que las diapositivas en PPTX. Dentro
de cada hoja, la primera fila no vacía se trata como cabecera y el resto
como cuerpo de una única `Table` — es la única convención razonable sin
metadatos explícitos de qué fila es cabecera.

`data_only=True`: si una celda tiene fórmula, se lee el último valor
calculado que Excel guardó, no la fórmula en sí (lo que interesa para
auditoría es el dato, no cómo se calculó).

Simplificación deliberada: las celdas combinadas (merged cells) llegan de
openpyxl con el valor solo en la celda superior-izquierda y vacías en el
resto del rango; no se propaga el valor a las demás celdas combinadas.
"""

from __future__ import annotations

from pathlib import Path

import openpyxl

from .base import BaseExtractor
from .models import Block, Heading, Page, Table


class XLSXExtractor(BaseExtractor):
    supported_formats = frozenset({"xlsx"})

    def extract_pages(self, path: Path) -> list[Page]:
        workbook = openpyxl.load_workbook(path, data_only=True, read_only=True)
        try:
            return [
                Page(number=index, blocks=_blocks_for_sheet(sheet))
                for index, sheet in enumerate(workbook.worksheets, start=1)
            ]
        finally:
            workbook.close()


def _blocks_for_sheet(sheet) -> list[Block]:
    blocks: list[Block] = [Heading(text=sheet.title, level=1)]
    table = _table_for_sheet(sheet)
    if table is not None:
        blocks.append(table)
    return blocks


def _table_for_sheet(sheet) -> Table | None:
    rows = [_row_as_strings(row) for row in sheet.iter_rows(values_only=True)]
    rows = [row for row in rows if any(cell for cell in row)]
    if not rows:
        return None
    headers, *body_rows = rows
    return Table(headers=headers, rows=body_rows)


def _row_as_strings(row: tuple) -> list[str]:
    return ["" if cell is None else str(cell) for cell in row]
