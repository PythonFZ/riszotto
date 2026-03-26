"""PDF converter backends with auto-detection."""

from __future__ import annotations

from riszotto.converter.base import (
    BackendName,
    ConversionResult,
    Converter,
    StyleOption,
)


def get_converter(backend: BackendName | None = None) -> Converter:
    """Get a PDF converter, auto-detecting the best available backend.

    Parameters
    ----------
    backend
        Explicit backend name. If None, tries docling first,
        falls back to markitdown.
    """
    from riszotto.converter.markitdown import MarkItDownConverter

    if backend == "markitdown":
        return MarkItDownConverter()
    if backend == "docling":
        from riszotto.converter.docling import DoclingConverter

        return DoclingConverter()
    try:
        from riszotto.converter.docling import DoclingConverter

        return DoclingConverter()
    except ImportError:
        return MarkItDownConverter()


__all__ = [
    "BackendName",
    "ConversionResult",
    "Converter",
    "StyleOption",
    "get_converter",
]
