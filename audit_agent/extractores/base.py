"""Interfaz común que debe implementar cada extractor de formato (portada de audit-engine)."""

from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path
from typing import ClassVar

from .models import Page


class BaseExtractor(ABC):
    supported_formats: ClassVar[frozenset[str]]

    @abstractmethod
    def extract_pages(self, path: Path) -> list[Page]:
        """Lee `path` y devuelve su contenido como páginas de bloques tipados.
        No genera Markdown: eso lo hace siempre `markdown.render_document`."""
