"""OCR para páginas e imágenes sin texto extraíble (portada de audit-engine):
Tesseract vía `pytesseract` sobre la imagen rasterizada con PyMuPDF.

Requisito de sistema (no es pip): `tesseract-ocr` y `tesseract-ocr-spa`.
Aquí el OCR es OPCIONAL: si falta pytesseract o el binario, se devuelve
cadena vacía y se registra un aviso, para que la lectura de un .docx/.pptx
con imágenes no falle por una dependencia de sistema. Un PDF escaneado sin
OCR disponible acaba en `LecturaError` en lectores.py (sin texto).
"""

from __future__ import annotations

import logging
import warnings

from PIL import Image

logger = logging.getLogger(__name__)
# Logos y viñetas en paleta con transparencia: aviso de PIL sin consecuencia
warnings.filterwarnings("ignore", message="Palette images with Transparency", category=UserWarning)

DEFAULT_LANGUAGES = "spa+eng"
RENDER_DPI = 300
_AVISADO = False


def ocr_disponible() -> bool:
    try:
        import pytesseract
        pytesseract.get_tesseract_version()
        return True
    except Exception:  # noqa: BLE001 — cualquier fallo = no disponible
        return False


import re

_RE_PALABRA = re.compile(r"[A-Za-zÁÉÍÓÚÜÑáéíóúüñ]{4,}")


def limpiar_ocr(texto: str) -> str:
    """Filtra el ruido típico del OCR de diagramas, logos e iconos («Al al Ho >
    > ® th»): se conservan solo las líneas con contenido legible (mayoría de
    letras/espacios y al menos dos palabras de 4+ letras) y el bloque entero
    se descarta si queda demasiado corto para aportar algo al modelo."""
    lineas = []
    for l in texto.splitlines():
        l = l.strip()
        if not l:
            continue
        letras = sum(ch.isalpha() or ch.isspace() for ch in l)
        palabras = _RE_PALABRA.findall(l)
        # Etiquetas de diagrama en mayúsculas sueltas ("CROSSDOCKING HUB LE STORE") no son prosa
        minimo = 5 if not any(ch.islower() for ch in l) else 2
        if letras / max(len(l), 1) >= 0.6 and len(palabras) >= minimo:
            lineas.append(l)
    limpio = "\n".join(lineas)
    return limpio if len(limpio) >= 20 else ""


def ocr_image(image: Image.Image, *, languages: str = DEFAULT_LANGUAGES) -> str:
    global _AVISADO
    try:
        import pytesseract
        return limpiar_ocr(pytesseract.image_to_string(image, lang=languages))
    except Exception as exc:  # noqa: BLE001
        if not _AVISADO:
            logger.warning("OCR no disponible (%s): las imágenes se leen sin texto.", exc)
            _AVISADO = True
        return ""


def ocr_page(page, *, languages: str = DEFAULT_LANGUAGES, dpi: int = RENDER_DPI) -> str:
    pixmap = page.get_pixmap(dpi=dpi)
    image = Image.frombytes("RGB", (pixmap.width, pixmap.height), pixmap.samples)
    return ocr_image(image, languages=languages)
