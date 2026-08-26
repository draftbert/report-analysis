"""Generación de Markdown a partir de la representación interna (portada de
audit-engine). Siempre desde `Page`/`Block`, nunca desde el fichero original."""

from __future__ import annotations

from .models import Block, Code, Heading, HorizontalRule, Image, ListBlock, Page, Paragraph, Quote, Table


def render_document(pages: list[Page]) -> str:
    return "\n\n".join(render_block(block) for page in pages for block in page.blocks)


def render_block(block: Block) -> str:
    if isinstance(block, Heading):
        return f"{'#' * block.level} {block.text}"
    if isinstance(block, Paragraph):
        return block.text
    if isinstance(block, ListBlock):
        return "\n".join(f"{f'{i + 1}.' if block.ordered else '-'} {item}" for i, item in enumerate(block.items))
    if isinstance(block, Table):
        header = "| " + " | ".join(block.headers) + " |"
        separator = "| " + " | ".join("---" for _ in block.headers) + " |"
        rows = ["| " + " | ".join(row) + " |" for row in block.rows]
        return "\n".join([header, separator, *rows])
    if isinstance(block, Code):
        return f"```{block.language}\n{block.text}\n```"
    if isinstance(block, Quote):
        return "\n".join(f"> {line}" for line in block.text.splitlines())
    if isinstance(block, HorizontalRule):
        return "---"
    if isinstance(block, Image):
        if block.ocr_text:
            return block.ocr_text  # el texto OCR ES el contenido legible de la imagen
        return f"![{block.caption or block.alt_text or 'imagen'}]()"
    raise TypeError(f"Tipo de bloque sin renderer Markdown: {type(block).__name__}")
