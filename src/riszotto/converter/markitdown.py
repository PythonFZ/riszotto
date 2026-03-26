"""MarkItDown-based PDF converter (lightweight default)."""

from __future__ import annotations

import logging
from pathlib import Path

from markitdown import MarkItDown

from riszotto.converter.base import ConversionResult, StyleOption


class MarkItDownConverter:
    """Convert PDFs using Microsoft's MarkItDown library.

    This is the lightweight default backend. It extracts plain text
    only -- no figures, structured tables, or equation rendering.
    Style flags and caching are ignored.
    """

    def convert(
        self,
        pdf_path: Path,
        *,
        table_style: StyleOption = "inline",
        equation_style: StyleOption = "inline",
        zotero_key: str,
        no_cache: bool = False,
    ) -> ConversionResult:
        """Convert a PDF to markdown using MarkItDown."""
        logging.disable(logging.CRITICAL)
        try:
            md = MarkItDown()
            result = md.convert(pdf_path)
            return ConversionResult(markdown=result.markdown)
        finally:
            logging.disable(logging.NOTSET)
