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


def ocr_image(image: Image.Image, *, languages: str = DEFAULT_LANGUAGES) -> str:
    global _AVISADO
    try:
        import pytesseract
        return pytesseract.image_to_string(image, lang=languages).strip()
    except Exception as exc:  # noqa: BLE001
        if not _AVISADO:
            logger.warning("OCR no disponible (%s): las imágenes se leen sin texto.", exc)
            _AVISADO = True
        return ""


def ocr_page(page, *, languages: str = DEFAULT_LANGUAGES, dpi: int = RENDER_DPI) -> str:
    pixmap = page.get_pixmap(dpi=dpi)
    image = Image.frombytes("RGB", (pixmap.width, pixmap.height), pixmap.samples)
    return ocr_image(image, languages=languages)
