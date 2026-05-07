from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from riszotto.pdf_cache import (
    clear_pdf_cache,
    download_to_pdf_cache,
    pdf_cache_path,
    pdf_cache_stats,
    read_pdf_cache,
)


class TestPdfCachePath:
    def test_path_is_md5_dot_pdf_under_cache_dir(self, tmp_path):
        with patch("riszotto.pdf_cache.PDF_CACHE_DIR", tmp_path):
            assert pdf_cache_path("abc123") == tmp_path / "abc123.pdf"


class TestReadPdfCache:
    def test_returns_none_when_missing(self, tmp_path):
        with patch("riszotto.pdf_cache.PDF_CACHE_DIR", tmp_path):
            assert read_pdf_cache("abc123") is None

    def test_returns_path_when_present(self, tmp_path):
        (tmp_path / "abc123.pdf").write_bytes(b"%PDF-1.4")
        with patch("riszotto.pdf_cache.PDF_CACHE_DIR", tmp_path):
            assert read_pdf_cache("abc123") == tmp_path / "abc123.pdf"


class TestDownloadToPdfCache:
    def _attachment(self, md5="abc123", filename="paper.pdf"):
        return {
            "key": "ITEMKEY1",
            "data": {"md5": md5, "filename": filename},
        }

    def test_downloads_when_missing_then_returns_path(self, tmp_path):
        zot = MagicMock()

        def fake_dump(item_key, filename, path):
            Path(path, filename).write_bytes(b"%PDF-1.4 downloaded")
            return str(Path(path, filename))

        zot.dump.side_effect = fake_dump

        with patch("riszotto.pdf_cache.PDF_CACHE_DIR", tmp_path):
            result = download_to_pdf_cache(zot, self._attachment())

        assert result == tmp_path / "abc123.pdf"
        assert result.read_bytes() == b"%PDF-1.4 downloaded"
        zot.dump.assert_called_once()

    def test_uses_cache_when_present(self, tmp_path):
        (tmp_path / "abc123.pdf").write_bytes(b"%PDF-1.4 cached")
        zot = MagicMock()
        with patch("riszotto.pdf_cache.PDF_CACHE_DIR", tmp_path):
            result = download_to_pdf_cache(zot, self._attachment())
        assert result == tmp_path / "abc123.pdf"
        zot.dump.assert_not_called()

    def test_raises_when_md5_missing(self, tmp_path):
        zot = MagicMock()
        bad = {"key": "ITEMKEY1", "data": {"md5": None, "filename": "x.pdf"}}
        with patch("riszotto.pdf_cache.PDF_CACHE_DIR", tmp_path):
            with pytest.raises(ValueError, match="md5"):
                download_to_pdf_cache(zot, bad)


class TestClearPdfCache:
    def test_removes_all_pdfs(self, tmp_path):
        (tmp_path / "a.pdf").write_bytes(b"x")
        (tmp_path / "b.pdf").write_bytes(b"y")
        (tmp_path / "not-pdf.txt").write_text("keep me")
        with patch("riszotto.pdf_cache.PDF_CACHE_DIR", tmp_path):
            n = clear_pdf_cache()
        assert n == 2
        assert not (tmp_path / "a.pdf").exists()
        assert (tmp_path / "not-pdf.txt").exists()

    def test_returns_zero_when_dir_missing(self, tmp_path):
        missing = tmp_path / "nope"
        with patch("riszotto.pdf_cache.PDF_CACHE_DIR", missing):
            assert clear_pdf_cache() == 0


class TestPdfCacheStats:
    def test_reports_count_and_bytes(self, tmp_path):
        (tmp_path / "a.pdf").write_bytes(b"abcd")
        (tmp_path / "b.pdf").write_bytes(b"efghi")
        (tmp_path / "x.txt").write_text("ignored")
        with patch("riszotto.pdf_cache.PDF_CACHE_DIR", tmp_path):
            stats = pdf_cache_stats()
        assert stats == {
            "count": 2,
            "total_bytes": 4 + 5,
            "path": str(tmp_path),
        }

    def test_empty_when_dir_missing(self, tmp_path):
        missing = tmp_path / "nope"
        with patch("riszotto.pdf_cache.PDF_CACHE_DIR", missing):
            stats = pdf_cache_stats()
        assert stats["count"] == 0
        assert stats["total_bytes"] == 0
