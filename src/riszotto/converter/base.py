"""Converter protocol, result type, and shared type aliases."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Annotated, Literal, Protocol

StyleOption = Literal["inline", "image"]
BackendName = Literal["markitdown", "docling"]
BackendOption = Annotated[StyleOption | None, "Only available with docling backend"]
EquationMode = Literal["image", "latex"]


@dataclass
class ConversionResult:
    """Internal result object -- dataclass, not serialized to disk."""

    markdown: str
    figures: dict[str, Path] = field(default_factory=dict)


class Converter(Protocol):
    """Protocol for PDF-to-markdown converters."""

    def convert(
        self,
        pdf_path: Path,
        *,
        table_style: StyleOption = "inline",
        equation_style: StyleOption = "inline",
        zotero_key: str,
        no_cache: bool = False,
        ocr: bool = False,
        table_mode: str = "fast",
        equation_mode: EquationMode = "image",
    ) -> ConversionResult: ...
