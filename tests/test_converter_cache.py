# tests/test_converter_cache.py
import json
import time
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

import pytest

from riszotto.converter.cache import (
    CacheMeta,
    cache_dir_for,
    compute_pdf_hash,
    read_cache,
    write_cache,
    clear_cache,
    get_cache_stats,
)
from riszotto.converter.base import ConversionResult


class TestComputePdfHash:
    def test_returns_12_char_hex(self, tmp_path):
        pdf = tmp_path / "test.pdf"
        pdf.write_bytes(b"%PDF-1.4 fake content")
        h = compute_pdf_hash(pdf)
        assert len(h) == 12
        assert all(c in "0123456789abcdef" for c in h)

    def test_different_content_different_hash(self, tmp_path):
        a = tmp_path / "a.pdf"
        b = tmp_path / "b.pdf"
        a.write_bytes(b"content A")
        b.write_bytes(b"content B")
        assert compute_pdf_hash(a) != compute_pdf_hash(b)

    def test_same_content_same_hash(self, tmp_path):
        a = tmp_path / "a.pdf"
        b = tmp_path / "b.pdf"
        a.write_bytes(b"same content")
        b.write_bytes(b"same content")
        assert compute_pdf_hash(a) == compute_pdf_hash(b)


class TestCacheMeta:
    def test_roundtrip_json(self):
        meta = CacheMeta(
            created=datetime(2026, 3, 26, tzinfo=timezone.utc),
            backend="docling",
            table_style="inline",
            equation_style="inline",
            pdf_hash="abc123def456",
        )
        json_str = meta.model_dump_json()
        restored = CacheMeta.model_validate_json(json_str)
        assert restored.backend == "docling"
        assert restored.pdf_hash == "abc123def456"
        assert restored.table_style == "inline"


class TestWriteAndReadCache:
    def test_write_then_read(self, tmp_path):
        with patch("riszotto.converter.cache.CONVERSION_CACHE_DIR", tmp_path):
            figures = {"figure_1.png": tmp_path / "src_fig.png"}
            (tmp_path / "src_fig.png").write_bytes(b"PNG_DATA")

            write_cache(
                zotero_key="KEY1",
                pdf_hash="aabbccddee11",
                markdown="# Hello\n\n![Figure 1](figure_1.png)",
                figures=figures,
                backend="docling",
                table_style="inline",
                equation_style="inline",
            )

            result = read_cache(
                zotero_key="KEY1",
                pdf_hash="aabbccddee11",
                table_style="inline",
                equation_style="inline",
            )
            assert result is not None
            assert "# Hello" in result.markdown
            assert "figure_1.png" in result.figures

    def test_read_returns_none_on_missing(self, tmp_path):
        with patch("riszotto.converter.cache.CONVERSION_CACHE_DIR", tmp_path):
            result = read_cache(
                zotero_key="MISSING",
                pdf_hash="000000000000",
                table_style="inline",
                equation_style="inline",
            )
            assert result is None

    def test_style_mismatch_returns_none(self, tmp_path):
        with patch("riszotto.converter.cache.CONVERSION_CACHE_DIR", tmp_path):
            figures = {}
            write_cache(
                zotero_key="KEY1",
                pdf_hash="aabbccddee11",
                markdown="text",
                figures=figures,
                backend="docling",
                table_style="inline",
                equation_style="inline",
            )
            result = read_cache(
                zotero_key="KEY1",
                pdf_hash="aabbccddee11",
                table_style="image",
                equation_style="inline",
            )
            assert result is None

    def test_old_hash_dir_removed_on_new_write(self, tmp_path):
        with patch("riszotto.converter.cache.CONVERSION_CACHE_DIR", tmp_path):
            write_cache(
                zotero_key="KEY1",
                pdf_hash="old_hash_0001",
                markdown="old",
                figures={},
                backend="docling",
                table_style="inline",
                equation_style="inline",
            )
            assert (tmp_path / "KEY1" / "old_hash_0001").exists()

            write_cache(
                zotero_key="KEY1",
                pdf_hash="new_hash_0002",
                markdown="new",
                figures={},
                backend="docling",
                table_style="inline",
                equation_style="inline",
            )
            assert not (tmp_path / "KEY1" / "old_hash_0001").exists()
            assert (tmp_path / "KEY1" / "new_hash_0002").exists()


class TestClearCache:
    def test_clear_all(self, tmp_path):
        with patch("riszotto.converter.cache.CONVERSION_CACHE_DIR", tmp_path):
            write_cache(
                zotero_key="K1", pdf_hash="h1h1h1h1h1h1",
                markdown="a", figures={},
                backend="docling", table_style="inline", equation_style="inline",
            )
            write_cache(
                zotero_key="K2", pdf_hash="h2h2h2h2h2h2",
                markdown="b", figures={},
                backend="docling", table_style="inline", equation_style="inline",
            )
            cleared = clear_cache()
            assert cleared == 2
            assert not (tmp_path / "K1").exists()
            assert not (tmp_path / "K2").exists()

    def test_clear_by_key(self, tmp_path):
        with patch("riszotto.converter.cache.CONVERSION_CACHE_DIR", tmp_path):
            write_cache(
                zotero_key="K1", pdf_hash="h1h1h1h1h1h1",
                markdown="a", figures={},
                backend="docling", table_style="inline", equation_style="inline",
            )
            write_cache(
                zotero_key="K2", pdf_hash="h2h2h2h2h2h2",
                markdown="b", figures={},
                backend="docling", table_style="inline", equation_style="inline",
            )
            cleared = clear_cache(key="K1")
            assert cleared == 1
            assert not (tmp_path / "K1").exists()
            assert (tmp_path / "K2").exists()

    def test_clear_empty_cache(self, tmp_path):
        with patch("riszotto.converter.cache.CONVERSION_CACHE_DIR", tmp_path):
            cleared = clear_cache()
            assert cleared == 0


class TestGetCacheStats:
    def test_empty_cache(self, tmp_path):
        with patch("riszotto.converter.cache.CONVERSION_CACHE_DIR", tmp_path):
            stats = get_cache_stats()
            assert stats["paper_count"] == 0
            assert stats["total_bytes"] == 0
            assert stats["path"] == str(tmp_path)

    def test_populated_cache(self, tmp_path):
        with patch("riszotto.converter.cache.CONVERSION_CACHE_DIR", tmp_path):
            write_cache(
                zotero_key="K1", pdf_hash="h1h1h1h1h1h1",
                markdown="content here", figures={},
                backend="docling", table_style="inline", equation_style="inline",
            )
            stats = get_cache_stats()
            assert stats["paper_count"] == 1
            assert stats["total_bytes"] > 0

    def test_stats_for_specific_key(self, tmp_path):
        with patch("riszotto.converter.cache.CONVERSION_CACHE_DIR", tmp_path):
            write_cache(
                zotero_key="K1", pdf_hash="h1h1h1h1h1h1",
                markdown="a", figures={},
                backend="docling", table_style="inline", equation_style="inline",
            )
            stats = get_cache_stats(key="K1")
            assert stats["paper_count"] == 1

            stats_missing = get_cache_stats(key="NOPE")
            assert stats_missing["paper_count"] == 0
