"""Integration tests for DoclingConverter using a real arxiv PDF."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch
from urllib.request import urlretrieve

import pytest

docling = pytest.importorskip("docling")

from riszotto.converter.docling import DoclingConverter  # noqa: E402

ARXIV_ID = "2310.06825"
ARXIV_URL = f"https://arxiv.org/pdf/{ARXIV_ID}"
CACHE_DIR = Path(__file__).parent / ".cache"
CACHED_PDF = CACHE_DIR / f"{ARXIV_ID}.pdf"


@pytest.fixture(scope="module")
def arxiv_pdf() -> Path:
    """Download an arxiv PDF once and cache it locally."""
    if CACHED_PDF.exists():
        return CACHED_PDF
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    urlretrieve(ARXIV_URL, CACHED_PDF)
    return CACHED_PDF


@pytest.fixture(scope="module")
def conversion_result(arxiv_pdf, tmp_path_factory):
    """Run DoclingConverter.convert() once, share the result."""
    tmp = tmp_path_factory.mktemp("docling_integration")
    with patch("riszotto.converter.cache.CONVERSION_CACHE_DIR", tmp):
        converter = DoclingConverter()
        result = converter.convert(
            arxiv_pdf,
            zotero_key="TEST_INTEGRATION",
        )
    return result


def test_produces_nonempty_markdown(conversion_result):
    assert len(conversion_result.markdown) > 100


def test_extracts_text(conversion_result):
    md = conversion_result.markdown
    # Paper 2310.06825 is "Docling Technical Report" — check for distinctive words
    assert "docling" in md.lower() or "document" in md.lower()


def test_extracts_figures(conversion_result):
    assert len(conversion_result.figures) > 0
    for name, path in conversion_result.figures.items():
        assert path.exists(), f"Figure file missing: {path}"
        assert path.stat().st_size > 0, f"Figure file empty: {path}"


def test_cache_roundtrip(arxiv_pdf, tmp_path):
    with patch("riszotto.converter.cache.CONVERSION_CACHE_DIR", tmp_path):
        converter = DoclingConverter()
        first = converter.convert(arxiv_pdf, zotero_key="CACHE_TEST")
        second = converter.convert(arxiv_pdf, zotero_key="CACHE_TEST")
    assert second.markdown == first.markdown


def test_different_table_styles(arxiv_pdf, tmp_path):
    with patch("riszotto.converter.cache.CONVERSION_CACHE_DIR", tmp_path):
        converter = DoclingConverter()
        inline_result = converter.convert(
            arxiv_pdf,
            zotero_key="TABLE_INLINE",
            table_style="inline",
        )
        image_result = converter.convert(
            arxiv_pdf,
            zotero_key="TABLE_IMAGE",
            table_style="image",
        )
    assert len(inline_result.markdown) > 100
    assert len(image_result.markdown) > 100
