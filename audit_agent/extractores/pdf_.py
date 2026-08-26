"""Extractor de PDF con PyMuPDF.

Si una página no tiene texto extraíble (PDF escaneado), se rasteriza entera
y se pasa por OCR (`ocr.py`).

Si tiene texto, se trabaja a nivel de LÍNEA (`page.get_text("dict")`), no de
banda de texto corrido: cada línea trae su tamaño de fuente y negrita, que es
lo que hace falta para distinguir un encabezado real de un párrafo (ver
`_classify_and_group_lines`). Tablas (`page.find_tables()`) e imágenes
incrustadas (`page.get_image_info()`) se detectan aparte y se intercalan con
los encabezados/párrafos en orden de lectura (de arriba abajo).

Simplificación deliberada: el orden de lectura se calcula solo por la
coordenada Y (de arriba abajo); un PDF a dos columnas puede intercalar mal
el contenido de una columna con la otra, y una tabla angosta en una columna
con texto normal en la de al lado puede recortar de más. Suficiente para
los documentos de oficina a una columna del PoC, no para maquetación
compleja.
"""

from __future__ import annotations

import logging
import re
from collections import defaultdict
from dataclasses import dataclass
from io import BytesIO
from pathlib import Path

import pymupdf as fitz
from PIL import Image as PILImage

from .base import BaseExtractor
from .models import Block, Heading, Image, Page, Paragraph, Table
from .ocr import ocr_image, ocr_page

logger = logging.getLogger(__name__)

# Por debajo de esto se considera que la página no tiene texto extraíble
# de verdad (ruido de metadatos, marcas de agua sueltas, etc.) y hace falta OCR.
MIN_CHARS_PER_PAGE = 20

# Imágenes con algún lado menor a esto (en puntos, ~1/72") en la página son
# casi siempre viñetas, logos de cabecera/pie o iconos decorativos: pasarlas
# por OCR no aporta contenido citable y solo mete ruido en el grafo.
MIN_IMAGE_SIDE_PT = 40

# Validación de tabla detectada (invariante 9 de CLAUDE.md: ningún fallo
# silencioso). `find_tables()` puede detectar una estructura de cuadrícula
# real (líneas, bordes) sin que `.extract()` devuelva texto útil -- plantilla
# en blanco, celdas vacías, o una detección que no logra asociar el texto de
# la página a las celdas. Sin esta validación, esa zona de la página
# desaparece sin más: no es un Paragraph, no es un Table con contenido, no es
# nada -- la unidad ni siquiera cuenta como no procesada. Umbral absoluto
# (caracteres útiles, sin espacios) calibrado contra tablas reales del
# corpus: la más pequeña con contenido genuino ronda 47 caracteres sobre un
# área de ~24.000pt² (densidad ~2,0); 20 caracteres deja margen por debajo
# sin admitir una tabla realmente vacía.
MIN_TABLE_USEFUL_CHARS = 20
# Caracteres útiles por pt² de área ocupada. Calibrado contra la tabla real
# más dispersa del corpus (Anexo III, Lefties): 47 caracteres / 23.733pt² ~=
# 0,00198. El umbral queda claramente por debajo (un orden de magnitud) para
# no penalizar tablas legítimas pero compactas -- solo atrapa tablas grandes
# con casi nada de texto dentro.
MIN_TABLE_CHAR_DENSITY = 0.0003

# --- Detección de encabezados: umbrales, ver docstring de _classify_and_group_lines ---

# Señal A (tipografía), relativa a la mediana del documento, nunca en puntos
# absolutos (varía por documento/plantilla).
_HEADING_SIZE_RATIO = 1.15
_HEADING_BOLD_SIZE_RATIO = 1.02
_HEADING_MAX_CHARS = 120
_MAX_HEADING_LEVELS = 4

# Banda superior/inferior de página donde se buscan cabeceras/pies repetidos.
_HEADER_FOOTER_BAND_RATIO = 0.08
# Un bloque en esa banda que se repite (texto idéntico) en más de este
# porcentaje de páginas de texto, y en al menos 2 páginas distintas (para no
# disparar en falso en documentos de 1 página), se descarta como cabecera/pie.
_HEADER_FOOTER_REPEAT_RATIO = 0.6

_NUM_PATTERN = re.compile(r"^\s*(\d+(?:\.\d+){0,3})([.)]?)\s+(\S)")
_KEYWORD_PATTERN = re.compile(
    r"^\s*(ANEXO|AP[ÉE]NDICE|CAP[ÍI]TULO|SECCI[ÓO]N|T[ÍI]TULO|ART[ÍI]CULO|PARTE|TABLA|FIGURA)\b",
    re.IGNORECASE,
)
_SENTENCE_END = re.compile(r"[.:;!?…][\"'\)\]]*\Z")
# Línea de índice/sumario: puntos o guiones de relleno (4+) seguidos de un
# número de página al final -- "5 Support..........................6".
_INDEX_LINE_PATTERN = re.compile(r"[.\-·]{4,}\s*\d+\s*$")


@dataclass
class _Line:
    text: str
    y0: float
    y1: float
    size: float
    bold: bool
    x0: float = 0.0
    x1: float = 0.0
    # True si esta línea empieza una columna distinta de la línea anterior en
    # el orden de lectura final (ver `_order_lines_by_column`) -- fuerza a
    # `_classify_and_group_lines` a cortar párrafo antes de ella, para que dos
    # columnas a la misma altura nunca se fusionen en un párrafo corrido.
    column_break: bool = False


class PDFExtractor(BaseExtractor):
    supported_formats = frozenset({"pdf"})

    def extract_pages(self, path: Path) -> list[Page]:
        with fitz.open(path) as document:
            # Primera pasada: recoge datos crudos de todas las páginas. La
            # detección de cabecera/pie y la mediana de tamaño de fuente son
            # señales DE TODO EL DOCUMENTO (invariante: nunca umbrales
            # absolutos ni por página), así que hace falta ver todas las
            # páginas antes de poder clasificar la primera.
            #
            # `table.extract()` se llama AQUÍ, en la misma iteración que
            # `find_tables()` -- nunca diferido a una segunda pasada. `Table`
            # es un proxy perezoso de PyMuPDF: su `.extract()` depende de
            # estado interno del documento en el momento de la llamada: si se
            # difiere hasta después de recorrer TODO el documento (como hacía
            # antes esta función), devuelve el contenido de otra página --
            # bug real encontrado sobre un informe de auditoría con tablas en
            # varias páginas, confirmado por experimento (extracción
            # inmediata vs. diferida sobre el mismo fichero). Ver SPEC.md.
            page_infos = []
            for page_number, pdf_page in enumerate(document, start=1):
                text = pdf_page.get_text().strip()
                if len(text) < MIN_CHARS_PER_PAGE:
                    page_infos.append((page_number, pdf_page, None, None))
                    continue
                raw_tables = sorted(pdf_page.find_tables().tables, key=lambda t: (t.bbox[1], t.bbox[0]))
                table_items: list[tuple[float, Table]] = []
                valid_rects: list[fitz.Rect] = []
                for raw_table in raw_tables:
                    rect = fitz.Rect(raw_table.bbox)
                    block = _table_block(raw_table)
                    if _is_table_content_valid(block, rect):
                        table_items.append((rect.y0, block))
                        valid_rects.append(rect)
                    else:
                        logger.warning("tabla detectada sin contenido en p.%d, fallback aplicado", page_number)
                lines = _lines_for_page(pdf_page, valid_rects)
                page_infos.append((page_number, pdf_page, table_items, lines))

            text_pages = [info for info in page_infos if info[2] is not None]
            header_footer_texts = _detect_header_footer(text_pages)
            median_size = _weighted_median_size(text_pages, header_footer_texts)
            level_by_size = _heading_level_by_size(text_pages, header_footer_texts, median_size)

            pages = []
            for page_number, pdf_page, table_items, lines in page_infos:
                if table_items is None:
                    ocr_text = ocr_page(pdf_page)
                    blocks: list[Block] = [Image(caption=f"Página {page_number} (OCR)", ocr_text=ocr_text)]
                else:
                    blocks = _blocks_for_text_page(
                        pdf_page, table_items, lines, header_footer_texts, median_size, level_by_size
                    )
                pages.append(Page(number=page_number, blocks=blocks))
        return pages


# --- Líneas: extracción y estilo ---------------------------------------------


def _lines_for_page(pdf_page: fitz.Page, table_rects: list[fitz.Rect]) -> list[_Line]:
    """Líneas de texto de la página, EXCLUYENDO las que caen dentro de una
    tabla detectada (su contenido ya lo devuelve `find_tables()` con
    estructura de filas; incluirlas aquí las duplicaría como Heading/Paragraph
    corrido y contaminaría la mediana de tamaño de fuente con texto de celda).
    """
    raw = pdf_page.get_text("dict")
    lines: list[_Line] = []
    for block in raw.get("blocks", []):
        for line in block.get("lines", []):
            spans = line.get("spans", [])
            text = "".join(span.get("text", "") for span in spans).strip()
            if not text:
                continue
            bbox = line.get("bbox", (0, 0, 0, 0))
            line_rect = fitz.Rect(bbox)
            if any(line_rect.intersects(rect) for rect in table_rects):
                continue
            size, bold = _line_style(spans)
            lines.append(_Line(text=text, y0=bbox[1], y1=bbox[3], x0=bbox[0], x1=bbox[2], size=size, bold=bold))
    return _order_lines_by_column(lines)


# Umbrales de `_order_lines_by_column` -- ver su docstring para la razón de
# cada uno (condiciones 1-3, acumulativas).
_MARKER_MAX_CHARS = 15
_MIN_COLUMN_GAP = 8.0
_COLUMN_RECURRENCE_TOLERANCE = 8.0
_MIN_COLUMN_RECURRENCE = 3
_BULLET_CHARS = {"•", "-", "*", "▪", "◦", "‣", "·", "●", "○"}

# Condición 3 (recurrencia), filtro de contenido: un fragmento sin carga
# semántica (conector suelto, o demasiado corto para ser el inicio real de
# una columna) no debe poder formar por sí solo un grupo de recurrencia,
# aunque su x0 coincida por casualidad con el de otros conectores sueltos
# varias veces en la página -- ver SPEC.md § extractor, umbral relativo vs
# absoluto, para el caso real medido que motivó esto ("y"/"de"/"aire" sueltos
# en distintas frases, x0 casi idéntico por azar, nunca una columna real).
_MIN_CONTENT_CHARS = 4
_STOPWORDS_ES = frozenset(
    {
        # preposiciones
        "a", "ante", "bajo", "cabe", "con", "contra", "de", "desde", "durante", "en", "entre",
        "excepto", "hacia", "hasta", "mediante", "para", "por", "salvo", "según", "sin", "so",
        "sobre", "tras", "vía",
        # conjunciones
        "aunque", "como", "e", "mas", "ni", "o", "pero", "porque", "pues", "que", "si", "sino", "u", "y",
    }
)
_NON_WORD_CHARS_RE = re.compile(r"[^\w]", re.UNICODE)


def _is_contentless_fragment(text: str) -> bool:
    """Condición 3, filtro de contenido: menos de 4 caracteres (sin contar
    puntuación) o preposición/conjunción suelta -- ninguna de las dos aporta
    la carga semántica que distingue el inicio real de una columna."""
    stripped = _NON_WORD_CHARS_RE.sub("", text).casefold()
    return len(stripped) < _MIN_CONTENT_CHARS or stripped in _STOPWORDS_ES


def _order_lines_by_column(lines: list[_Line]) -> list[_Line]:
    """Orden de lectura: y0 (de arriba abajo) por defecto. Un salto de
    columna real (`column_break`) exige TRES condiciones acumulativas -- solo
    con las tres se distingue una tabla/layout a columnas genuino de un
    accidente de cómo PyMuPDF particiona una línea con puntos de relleno o
    numeración (ver SPEC.md § extractor para el caso real que motivó esto):

    1. El fragmento IZQUIERDO del salto no es un marcador (numeración corta
       tipo "1."/"3.1." o una viñeta suelta, < 15 caracteres) -- "1." es un
       marcador, "DDP (Delivered Duty Paid...)" es contenido de columna. Un
       número SIN separador ("3100", código de cuenta) no cuenta como
       marcador -- por eso se exige que `_matches_numbering` capture un
       separador real (el "." de "1.", no el hueco vacío de "3100").
    2. Hueco horizontal >= 8pt entre el fragmento izquierdo y el derecho.
       Absoluto, no relativo a ninguna mediana de página -- medido contra un
       informe real con líneas partidas palabra por palabra (SPEC.md §
       extractor): el hueco entre palabras normales (2,6-13,7pt) y el hueco
       real entre columnas (10,9-16,8pt) se solapan casi por completo ahí, así
       que ninguna variante de "N veces la mediana" los separa -- quien
       discrimina de verdad es la condición 3, no el tamaño del hueco.
    3. RECURRENCIA: el x0 del fragmento derecho se repite (±8pt) al menos 3
       veces en la página, y esas repeticiones tienen que tener contenido
       real -- se descartan del recuento los fragmentos de menos de 4
       caracteres o que sean preposiciones/conjunciones sueltas
       (`_is_contentless_fragment`), para que conectores sueltos que
       coinciden de x0 por azar ("y", "de", "aire" en frases distintas) no
       formen un grupo de recurrencia falso. Una columna real se repite en
       varias filas CON CONTENIDO; un fragmento suelto no. Es la condición
       que de verdad distingue estructura de accidente -- las otras dos por
       sí solas no bastan (un índice con poco punteado podría colar la
       condición 2, y un código de tabla con separador podría colar la 1).

    Sin ninguna línea que cumpla las tres, el resultado es idéntico al
    `lines.sort(key=lambda l: l.y0)` de siempre -- ninguna las cumple en un
    documento a una columna.

    Implementación en dos pasadas: (1) agrupa en "bandas" -- líneas
    mutuamente solapadas en Y por unión transitiva -- y dentro de cada banda
    agrupa por columna (clustering 1D sobre x0); recoge como candidatos los
    saltos que pasan las condiciones 1 y 2. (2) sobre TODA la página, se
    queda solo con los candidatos cuyo x0 recurre (condición 3) y vuelve a
    fusionar en una sola columna los que no -- así una banda con una tabla de
    verdad (repetida en la página) se separa, y una banda suelta (una
    entrada de índice, un accidente de una sola fila) no.

    Una banda con al menos un salto confirmado es una FILA de tabla: su
    última columna también fuerza `column_break` en la línea que abre la
    banda siguiente. Sin esto, la fila N y la fila N+1 pueden acabar en el
    mismo párrafo si la última columna de N no termina en punto (`_merge_fragments`
    no las separaría por sí solo) -- detectado con el test de la tabla de dos
    columnas sin puntuación final, no algo hipotético.
    """
    lines = sorted(lines, key=lambda line: line.y0)
    bands = _group_into_bands(lines)
    band_columns = [_cluster_by_column(band) if len(band) > 1 else [band] for band in bands]

    candidate_x0s = [
        columns[k + 1][0].x0
        for columns in band_columns
        for k in range(len(columns) - 1)
        if _is_real_column_split(columns[k], columns[k + 1])
        and not _is_contentless_fragment(columns[k + 1][0].text)
    ]
    recurring = _recurring_x0_ranges(candidate_x0s)

    ordered: list[_Line] = []
    force_break_on_next_band = False
    for columns in band_columns:
        band_lines, was_table_row = _apply_confirmed_splits(columns, recurring)
        if force_break_on_next_band and band_lines:
            band_lines[0].column_break = True
        ordered.extend(band_lines)
        force_break_on_next_band = was_table_row
    return ordered


def _group_into_bands(lines: list[_Line]) -> list[list[_Line]]:
    """Líneas (ya en orden de y0) agrupadas en bandas: unión transitiva de
    solapes en Y. Una banda de tamaño 1 es el caso normal -- una línea de
    párrafo no comparte altura con ninguna otra."""
    bands: list[list[_Line]] = []
    band: list[_Line] = []
    band_y1: float | None = None
    for line in lines:
        if band and band_y1 is not None and line.y0 < band_y1:
            band.append(line)
            band_y1 = max(band_y1, line.y1)
        else:
            if band:
                bands.append(band)
            band = [line]
            band_y1 = line.y1
    if band:
        bands.append(band)
    return bands


def _cluster_by_column(band: list[_Line]) -> list[list[_Line]]:
    """Clustering 1D sobre x0: dos líneas caen en la misma columna si sus
    rangos X se solapan (transitivamente, siguiendo la extensión acumulada de
    la columna en curso); un hueco horizontal claro abre columna nueva. Esto
    es solo agrupación geométrica -- qué columnas son REALES (condiciones
    1-3) se decide después, en `_order_lines_by_column`."""
    by_x = sorted(band, key=lambda line: line.x0)
    columns: list[list[_Line]] = [[by_x[0]]]
    extent = by_x[0].x1
    for line in by_x[1:]:
        if line.x0 < extent:
            columns[-1].append(line)
            extent = max(extent, line.x1)
        else:
            columns.append([line])
            extent = line.x1
    return columns


def _is_real_column_split(left: list[_Line], right: list[_Line]) -> bool:
    """Condiciones 1 y 2 (la 3, recurrencia, se aplica aparte sobre toda la
    página -- ver `_order_lines_by_column`)."""
    left_text = " ".join(line.text for line in left)
    if _is_bare_marker(left_text):
        return False
    gap = min(line.x0 for line in right) - max(line.x1 for line in left)
    return gap >= _MIN_COLUMN_GAP


def _is_bare_marker(text: str) -> bool:
    """Condición 1: el fragmento es SOLO un marcador (numeración corta con
    separador real, o una viñeta), no contenido de columna. `_matches_numbering`
    exige contenido tras el número en el mismo string ("1. Alcance"), pero
    PyMuPDF suele partir justo ahí ("1." y "Alcance" como líneas distintas) --
    se le añade un sufijo neutro para poder probar solo la forma del número.
    Un número SIN separador ("3100") no cuenta: `numbering[1]` (el separador
    capturado) tiene que ser no vacío, para no confundir un código de tabla
    con una numeración de lista/epígrafe.
    """
    stripped = text.strip()
    if len(stripped) >= _MARKER_MAX_CHARS:
        return False
    if stripped in _BULLET_CHARS:
        return True
    numbering = _matches_numbering(f"{stripped} x")
    return numbering is not None and numbering[1] != ""


def _recurring_x0_ranges(candidate_x0s: list[float]) -> list[tuple[float, float]]:
    """Condición 3: agrupa los x0 candidatos con tolerancia ±8pt (1D,
    consecutivo tras ordenar) y se queda con los grupos de >= 3 apariciones
    -- una columna real se repite en varias filas de la página, un
    fragmento suelto no."""
    clusters: list[list[float]] = []
    for x0 in sorted(candidate_x0s):
        if clusters and x0 - clusters[-1][-1] <= _COLUMN_RECURRENCE_TOLERANCE:
            clusters[-1].append(x0)
        else:
            clusters.append([x0])
    return [(cluster[0], cluster[-1]) for cluster in clusters if len(cluster) >= _MIN_COLUMN_RECURRENCE]


def _x0_is_recurring(x0: float, recurring: list[tuple[float, float]]) -> bool:
    return any(lo - _COLUMN_RECURRENCE_TOLERANCE <= x0 <= hi + _COLUMN_RECURRENCE_TOLERANCE for lo, hi in recurring)


def _apply_confirmed_splits(
    columns: list[list[_Line]], recurring: list[tuple[float, float]]
) -> tuple[list[_Line], bool]:
    """Reconstruye una banda: los saltos candidatos cuyo x0 NO recurre en la
    página (condición 3) se deshacen -- sus columnas se fusionan de vuelta en
    una sola, como si nunca se hubieran separado. Devuelve también si quedó
    al menos un salto confirmado (banda = fila de tabla real), para que
    `_order_lines_by_column` fuerce el corte con la banda siguiente."""
    merged: list[list[_Line]] = [columns[0]]
    for k in range(1, len(columns)):
        left, right = columns[k - 1], columns[k]
        confirmed = _is_real_column_split(left, right) and _x0_is_recurring(right[0].x0, recurring)
        if confirmed:
            merged.append(right)
        else:
            merged[-1] = merged[-1] + right

    ordered: list[_Line] = []
    for i, column in enumerate(merged):
        column_sorted = sorted(column, key=lambda line: line.y0)
        if i > 0:
            column_sorted[0].column_break = True
        ordered.extend(column_sorted)
    return ordered, len(merged) > 1


def _line_style(spans: list[dict]) -> tuple[float, bool]:
    """Tamaño ponderado por caracteres y negrita mayoritaria de una línea
    (una línea puede mezclar spans de distinto estilo; se resuelve por peso
    de caracteres, no por el primer span nada más).
    """
    total_chars = 0
    weighted_size = 0.0
    bold_chars = 0
    for span in spans:
        text = span.get("text", "")
        n = len(text)
        if n == 0:
            continue
        total_chars += n
        weighted_size += span.get("size", 0.0) * n
        font = (span.get("font") or "").lower()
        is_bold = bool(span.get("flags", 0) & (1 << 4)) or "bold" in font
        if is_bold:
            bold_chars += n
    if total_chars == 0:
        return 0.0, False
    return weighted_size / total_chars, (bold_chars / total_chars) >= 0.5


# --- Señales de documento completo: cabecera/pie, mediana, clusters de tamaño ---


def _detect_header_footer(text_pages: list[tuple]) -> set[str]:
    """Texto que se repite, idéntico, en la banda superior/inferior (8% de la
    altura de página) de más del 60% de las páginas de texto, y en al menos 2
    páginas distintas -- ese último requisito evita que un documento de 1 sola
    página marque su propio título como "repetido" (1/1 páginas > 60%).
    """
    total_pages = len(text_pages)
    if total_pages == 0:
        return set()

    band_pages: dict[str, set[int]] = defaultdict(set)
    for page_number, pdf_page, _table_items, lines in text_pages:
        page_rect = pdf_page.rect
        top_cut = page_rect.y0 + page_rect.height * _HEADER_FOOTER_BAND_RATIO
        bottom_cut = page_rect.y1 - page_rect.height * _HEADER_FOOTER_BAND_RATIO
        for line in lines:
            if line.y0 <= top_cut or line.y1 >= bottom_cut:
                band_pages[line.text].add(page_number)

    return {
        text
        for text, pages in band_pages.items()
        if len(pages) >= 2 and len(pages) / total_pages > _HEADER_FOOTER_REPEAT_RATIO
    }


def _body_lines(text_pages: list[tuple], header_footer_texts: set[str]):
    for _page_number, pdf_page, _table_items, lines in text_pages:
        isolated = _isolated_lines(lines)
        for line in lines:
            if _is_discarded(line, header_footer_texts, pdf_page.rect, id(line) in isolated):
                continue
            yield line


def _numbered_body_lines(text_pages: list[tuple], header_footer_texts: set[str]):
    """Igual que `_body_lines`, pero además lleva el separador de numeración
    de la línea anterior DENTRO DE LA MISMA PÁGINA (se reinicia por página,
    igual que `_classify_and_group_lines`, para que el clustering tipográfico
    global (pass 2) y la clasificación por página (pass 3) traten cada línea
    de forma consistente).
    """
    for _page_number, pdf_page, _table_items, lines in text_pages:
        isolated = _isolated_lines(lines)
        previous_separator: str | None = None
        for line in lines:
            if _is_discarded(line, header_footer_texts, pdf_page.rect, id(line) in isolated):
                continue
            yield line, previous_separator
            numbering = _matches_numbering(line.text.strip())
            previous_separator = numbering[1] if numbering else None


def _weighted_median_size(text_pages: list[tuple], header_footer_texts: set[str]) -> float:
    """Mediana del tamaño de fuente del cuerpo, ponderada por caracteres.
    Mediana y no media a propósito (SPEC.md): resiste a que los propios
    encabezados -- pocos, más grandes -- tiren de la referencia hacia arriba.
    """
    samples = [(line.size, len(line.text)) for line in _body_lines(text_pages, header_footer_texts)]
    if not samples:
        return 0.0
    samples.sort(key=lambda s: s[0])
    total_weight = sum(weight for _, weight in samples)
    if total_weight == 0:
        return samples[len(samples) // 2][0]
    half = total_weight / 2
    cumulative = 0.0
    for size, weight in samples:
        cumulative += weight
        if cumulative >= half:
            return size
    return samples[-1][0]


def _heading_level_by_size(
    text_pages: list[tuple], header_footer_texts: set[str], median_size: float
) -> dict[float, int]:
    """Clusters de tamaño (redondeo a 0.5pt) entre los candidatos tipográficos
    de TODO el documento -- no por página, para que el nivel de un tamaño dado
    sea el mismo en la página 3 y en la 30. Máximo 4 niveles: el 5º tamaño en
    tamaño descendente y los que le siguen no entran en el mapa, y por tanto
    se tratan como Paragraph (no se fuerzan al nivel 4).
    """
    if median_size <= 0:
        return {}
    candidate_sizes: set[float] = set()
    for line, previous_separator in _numbered_body_lines(text_pages, header_footer_texts):
        if _numbering_level(line.text, previous_separator) is not None:
            continue  # la numeración manda directamente; no entra en el cluster tipográfico
        if _is_typography_candidate(line, median_size):
            candidate_sizes.add(round(line.size * 2) / 2)
    ordered = sorted(candidate_sizes, reverse=True)[:_MAX_HEADING_LEVELS]
    return {size: level for level, size in enumerate(ordered, start=1)}


# --- Clasificación de una línea: descartes, numeración, tipografía -----------


def _isolated_lines(lines: list[_Line]) -> set[int]:
    """`id()` de las líneas que están SOLAS en su banda -- ninguna otra línea
    de la página comparte su rango Y (mismo agrupamiento que
    `_order_lines_by_column`, aquí solo para distinguir un fragmento suelto
    de uno que forma parte de una fila con más contenido)."""
    bands = _group_into_bands(sorted(lines, key=lambda line: line.y0))
    return {id(band[0]) for band in bands if len(band) == 1}


def _is_discarded(line: _Line, header_footer_texts: set[str], page_rect: fitz.Rect, isolated: bool) -> bool:
    text = line.text
    if text in header_footer_texts:
        return True
    stripped = text.strip()
    if stripped.isdigit() and isolated:
        # Número de página suelto: SOLO si cae en la banda de cabecera/pie Y
        # es el único fragmento de su línea -- sin las dos condiciones, esto
        # descarta cualquier cifra real embebida en una frase en cuanto
        # PyMuPDF trocea el texto palabra por palabra (SPEC.md § extractor:
        # "cifras perdidas"), que es precisamente lo que NO se quiere.
        top_cut = page_rect.y0 + page_rect.height * _HEADER_FOOTER_BAND_RATIO
        bottom_cut = page_rect.y1 - page_rect.height * _HEADER_FOOTER_BAND_RATIO
        if line.y0 <= top_cut or line.y1 >= bottom_cut:
            return True
    if 0 < len(stripped) < 4 and stripped == stripped.upper() and any(c.isalpha() for c in stripped):
        return True
    if _INDEX_LINE_PATTERN.search(text):  # línea de índice/sumario, no contenido
        return True
    return False


def _matches_numbering(stripped: str) -> tuple[int, str, str] | None:
    """Solo el patrón crudo (profundidad, separador, primer carácter tras el
    número) -- sin filtros de cordura, esos van en `_numbering_level`. Separado
    porque el separador hace falta también para detectar listas consecutivas
    ("1) ...", "2) ...") aunque la línea en curso no llegue a ser Heading.
    """
    match = _NUM_PATTERN.match(stripped)
    if not match:
        return None
    number, separator, first_char = match.group(1), match.group(2), match.group(3)
    depth = min(number.count(".") + 1, _MAX_HEADING_LEVELS)
    return depth, separator, first_char


def _numbering_level(text: str, previous_separator: str | None = None) -> int | None:
    stripped = text.strip()
    if not stripped or len(stripped) >= _HEADING_MAX_CHARS or stripped[-1] in ".;,":
        return None
    numbering = _matches_numbering(stripped)
    if numbering:
        depth, separator, first_char = numbering
        if first_char.islower():
            return None  # "1) integrate and..." -- ítem de lista, no encabezado
        if separator == ")" and previous_separator == ")":
            return None  # "1) ..." seguido de "2) ..." -- lista, no jerarquía
        return depth
    if _KEYWORD_PATTERN.match(stripped):
        return 1
    return None


def _is_typography_candidate(line: _Line, median_size: float) -> bool:
    stripped = line.text.strip()
    if not stripped or len(stripped) >= _HEADING_MAX_CHARS or stripped.endswith("."):
        return False
    if _is_mostly_numeric(stripped):
        return False
    if median_size <= 0:
        return False
    if line.size >= median_size * _HEADING_SIZE_RATIO:
        return True
    return line.size >= median_size * _HEADING_BOLD_SIZE_RATIO and line.bold


_NUMERIC_HEADING_CHARS = set("0123456789%€$.,-+()")
_NUMERIC_HEADING_RATIO = 0.5


def _is_mostly_numeric(text: str) -> bool:
    """Una etiqueta numérica de gráfico ("411 M (V22)", "32,8%") puede
    disparar el umbral tipográfico con facilidad -- las cifras grandes de un
    dashboard suelen ir en el tamaño de fuente más grande de la página. Solo
    aplica a la señal de tipografía (aquí): la numeración de un epígrafe real
    ("1.1 Antecedentes...") pasa por `_numbering_level`, un mecanismo
    deliberadamente distinto que exige la estructura completa de un número de
    sección, no solo dígitos.
    """
    chars = [c for c in text if not c.isspace()]
    if not chars:
        return False
    numeric = sum(1 for c in chars if c in _NUMERIC_HEADING_CHARS)
    return numeric / len(chars) > _NUMERIC_HEADING_RATIO


def _heading_level(
    line: _Line, median_size: float, level_by_size: dict[float, int], previous_separator: str | None
) -> int | None:
    # Veto antes de mirar cualquiera de las dos vías: una cifra grande de
    # gráfico ("411 M (V22)") puede colar por AMBAS -- por tipografía (ver
    # `_is_typography_candidate`) y, menos obvio, por numeración: `_NUM_PATTERN`
    # solo exige "dígitos + separador opcional + espacio + un carácter", así
    # que "411 M (V22)" casa como (profundidad=1, separador="", primer
    # carácter="M") sin que la cifra sea en absoluto un número de epígrafe.
    # Caso real: informe Lefties, `section_path` con '411 M (V22)' como
    # heading (ver SPEC.md).
    if _is_mostly_numeric(line.text):
        return None
    level = _numbering_level(line.text, previous_separator)
    if level is not None:
        return level
    if _is_typography_candidate(line, median_size):
        return level_by_size.get(round(line.size * 2) / 2)
    return None


# --- Construcción de bloques --------------------------------------------------


def _blocks_for_text_page(
    pdf_page: fitz.Page,
    table_items: list[tuple[float, Table]],
    lines: list[_Line],
    header_footer_texts: set[str],
    median_size: float,
    level_by_size: dict[float, int],
) -> list[Block]:
    """`table_items` ya viene materializado (`_table_block` + validación
    aplicados en la primera pasada de `extract_pages`, ver su docstring):
    aquí solo se intercala por posición Y, nunca se vuelve a llamar
    `table.extract()`.
    """
    items: list[tuple[float, int, Block]] = []

    for y0, table_block in table_items:
        items.append((y0, 0, table_block))

    for y0, block in _classify_and_group_lines(lines, header_footer_texts, median_size, level_by_size, pdf_page.rect):
        items.append((y0, 1, block))

    for info in pdf_page.get_image_info(xrefs=True):
        x0, y0, x1, y1 = info["bbox"]
        if (x1 - x0) < MIN_IMAGE_SIDE_PT or (y1 - y0) < MIN_IMAGE_SIDE_PT:
            continue
        image_block = _image_block(pdf_page, info["xref"])
        if image_block is not None:
            items.append((y0, 2, image_block))

    items.sort(key=lambda item: (item[0], item[1]))
    return _merge_consecutive_headings([block for _, _, block in items])


def _merge_consecutive_headings(blocks: list[Block]) -> list[Block]:
    """Dos o más Heading consecutivos del MISMO nivel, sin ningún bloque de
    contenido entre medias (ni Paragraph, ni Table, ni Image), son
    continuación del mismo título partido en varias líneas -- no dos
    secciones distintas. Se fusionan concatenando el texto con un espacio.
    Opera sobre la secuencia final ya ordenada por posición Y, así una tabla
    o un párrafo que se interponga entre dos headings del mismo nivel sí
    bloquea la fusión (no es solo "consecutivos entre líneas de texto").
    """
    merged: list[Block] = []
    for block in blocks:
        if (
            isinstance(block, Heading)
            and merged
            and isinstance(merged[-1], Heading)
            and merged[-1].level == block.level
        ):
            merged[-1] = Heading(text=f"{merged[-1].text} {block.text}", level=block.level)
        else:
            merged.append(block)
    return merged


def _classify_and_group_lines(
    lines: list[_Line],
    header_footer_texts: set[str],
    median_size: float,
    level_by_size: dict[float, int],
    page_rect: fitz.Rect,
) -> list[tuple[float, Block]]:
    """Recorre las líneas de la página en orden de lectura: una línea que
    clasifica como encabezado (numeración o tipografía, ver `_heading_level`)
    corta el párrafo en curso y se emite como `Heading` propio; el resto se
    acumula y se agrupa en párrafos con `_merge_fragments` (un fragmento sin
    final de frase se pega al siguiente -- mismo criterio ya usado para
    reconstruir párrafos sin depender de que PyMuPDF marque línea en blanco
    entre ellos). `line.column_break` (ver `_order_lines_by_column`) también
    corta el párrafo en curso, sin emitir un `Heading`: dos columnas a la
    misma altura nunca deben fusionarse en un párrafo corrido.
    """
    items: list[tuple[float, Block]] = []
    buffer: list[str] = []
    buffer_y0: float | None = None
    previous_separator: str | None = None
    isolated = _isolated_lines(lines)

    def flush() -> None:
        if not buffer:
            return
        for paragraph_text in _merge_fragments(list(buffer)):
            items.append((buffer_y0, Paragraph(paragraph_text)))
        buffer.clear()

    for line in lines:
        if _is_discarded(line, header_footer_texts, page_rect, id(line) in isolated):
            continue

        level = _heading_level(line, median_size, level_by_size, previous_separator)

        numbering = _matches_numbering(line.text.strip())
        previous_separator = numbering[1] if numbering else None

        if level is not None:
            flush()
            items.append((line.y0, Heading(text=line.text, level=level)))
            continue

        if line.column_break:
            flush()

        if not buffer:
            buffer_y0 = line.y0
        buffer.append(line.text)

    flush()
    return items


def _merge_fragments(texts: list[str]) -> list[str]:
    merged: list[str] = []
    buffer = ""
    for text in texts:
        buffer = f"{buffer} {text}".strip() if buffer else text
        last_line = buffer.splitlines()[-1].strip() if buffer else ""
        if _SENTENCE_END.search(last_line):
            merged.append(buffer)
            buffer = ""
    if buffer:
        merged.append(buffer)
    return merged


def _table_block(table) -> Table:
    rows = [[(cell or "").strip() for cell in row] for row in table.extract()]
    headers = rows[0] if rows else []
    body_rows = rows[1:]
    return Table(headers=headers, rows=body_rows)


def _table_useful_chars(table: Table) -> int:
    return sum(len(cell) for row in ([table.headers] + table.rows) for cell in row if cell)


def _is_table_content_valid(table: Table, rect: fitz.Rect) -> bool:
    """Una tabla detectada (`find_tables`) cuyo contenido extraído
    (`.extract()`) es casi vacío es una detección fallida, no una tabla en
    blanco legítima -- ver `MIN_TABLE_USEFUL_CHARS`/`MIN_TABLE_CHAR_DENSITY`.
    Dos condiciones independientes: muy poco texto en términos absolutos, o
    muy poco texto en relación al área que ocupa (una tabla grande casi vacía
    puede superar el umbral absoluto sin ser contenido real).
    """
    chars = _table_useful_chars(table)
    if chars < MIN_TABLE_USEFUL_CHARS:
        return False
    area = rect.width * rect.height
    if area <= 0:
        return True
    return (chars / area) >= MIN_TABLE_CHAR_DENSITY


def _image_block(pdf_page: fitz.Page, xref: int) -> Image | None:
    try:
        raw = pdf_page.parent.extract_image(xref)
    except Exception:
        return None
    with PILImage.open(BytesIO(raw["image"])) as pil_image:
        ocr_text = ocr_image(pil_image.convert("RGB"))
    return Image(caption="Imagen incrustada", ocr_text=ocr_text)
