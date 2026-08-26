"""Representación interna unificada (portada de audit-engine). Todo extractor
de formato produce `Page`s de estos bloques; nunca genera Markdown directamente.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import ClassVar


class BlockType(str, Enum):
    HEADING = "heading"
    PARAGRAPH = "paragraph"
    TABLE = "table"
    IMAGE = "image"
    LIST = "list"
    CODE = "code"
    QUOTE = "quote"
    HORIZONTAL_RULE = "horizontal_rule"


@dataclass
class Block:
    block_type: ClassVar[BlockType]


@dataclass
class Heading(Block):
    text: str
    level: int = 1
    block_type: ClassVar[BlockType] = BlockType.HEADING


@dataclass
class Paragraph(Block):
    text: str
    block_type: ClassVar[BlockType] = BlockType.PARAGRAPH


@dataclass
class ListBlock(Block):
    items: list[str]
    ordered: bool = False
    block_type: ClassVar[BlockType] = BlockType.LIST


@dataclass
class Table(Block):
    headers: list[str]
    rows: list[list[str]]
    block_type: ClassVar[BlockType] = BlockType.TABLE


@dataclass
class Image(Block):
    alt_text: str = ""
    caption: str = ""
    ocr_text: str = ""
    block_type: ClassVar[BlockType] = BlockType.IMAGE


@dataclass
class Code(Block):
    text: str
    language: str = ""
    block_type: ClassVar[BlockType] = BlockType.CODE


@dataclass
class Quote(Block):
    text: str
    block_type: ClassVar[BlockType] = BlockType.QUOTE


@dataclass
class HorizontalRule(Block):
    block_type: ClassVar[BlockType] = BlockType.HORIZONTAL_RULE


@dataclass
class Page:
    number: int
    blocks: list[Block] = field(default_factory=list)
