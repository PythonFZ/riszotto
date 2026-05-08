"""Tests for the bulk-population module."""

from __future__ import annotations

import pytest

from riszotto.bulk import PopulateResult, _NullProgress


class TestPopulateResult:
    def test_defaults_are_empty(self):
        r = PopulateResult()
        assert r.ok == 0
        assert r.skipped == {}
        assert r.failed == {}
        assert r.elapsed_seconds == 0.0
        assert r.interrupted is False

    def test_total_processed_counts_ok_skipped_failed(self):
        r = PopulateResult(
            ok=10,
            skipped={"no_pdf": 3, "permission": 1},
            failed={"convert_failed": ["KEY1: boom"]},
            elapsed_seconds=12.5,
        )
        assert r.total_processed() == 15

    def test_failed_count_sums_lists(self):
        r = PopulateResult(
            failed={"convert_failed": ["A: x", "B: y"], "download_failed": ["C: z"]},
        )
        assert r.failed_count() == 3

    def test_skipped_count_sums_values(self):
        r = PopulateResult(skipped={"no_pdf": 2, "permission": 5})
        assert r.skipped_count() == 7


class TestNullProgress:
    def test_methods_are_no_ops(self):
        p = _NullProgress()
        p.start(total=10, library_label="L1", scope_label=None)
        p.advance(label="paper-1")
        p.log("hello")
        p.finish()


from pathlib import Path
from unittest.mock import MagicMock, patch

from riszotto.bulk import populate_library
from riszotto.client import PdfNotOnStorageError, ZoteroPermissionError


def _item(key: str, title: str = "Title") -> dict:
    return {"key": key, "data": {"title": title, "itemType": "journalArticle"}}


def _attachment(key: str = "ATT") -> dict:
    return {"key": key, "data": {"contentType": "application/pdf", "md5": "abc"}}


@pytest.fixture
def stub_converter(monkeypatch):
    """Replace get_converter() to return a MagicMock convertor."""
    fake = MagicMock()
    fake.convert.return_value = MagicMock(markdown="# md", figures={})
    monkeypatch.setattr("riszotto.bulk.get_converter", lambda backend=None: fake)
    return fake


@pytest.fixture
def stub_pipeline(monkeypatch):
    """Replace get_pdf_attachments + resolve_pdf_path with controllable mocks."""
    pdfs = MagicMock(side_effect=lambda zot, key: [_attachment(key)])
    resolve = MagicMock(side_effect=lambda zot, att: Path(f"/tmp/{att['key']}.pdf"))
    monkeypatch.setattr("riszotto.bulk.get_pdf_attachments", pdfs)
    monkeypatch.setattr("riszotto.bulk.resolve_pdf_path", resolve)
    return {"pdfs": pdfs, "resolve": resolve}


class TestPopulateLibraryHappyPath:
    def test_three_items_three_ok(self, stub_pipeline, stub_converter):
        zot = MagicMock()
        with patch(
            "riszotto.bulk.all_items",
            return_value=[_item("A"), _item("B"), _item("C")],
        ):
            result = populate_library(zot)
        assert result.ok == 3
        assert result.skipped == {}
        assert result.failed == {}
        assert result.interrupted is False
        assert stub_converter.convert.call_count == 3


class TestPopulateLibrarySkips:
    def test_no_pdf_attachment_is_skipped(self, monkeypatch, stub_converter):
        monkeypatch.setattr("riszotto.bulk.get_pdf_attachments", lambda zot, key: [])
        monkeypatch.setattr(
            "riszotto.bulk.resolve_pdf_path",
            MagicMock(side_effect=AssertionError("should not be called")),
        )
        zot = MagicMock()
        with patch("riszotto.bulk.all_items", return_value=[_item("A"), _item("B")]):
            result = populate_library(zot)
        assert result.ok == 0
        assert result.skipped == {"no_pdf": 2}
        assert result.failed == {}
        stub_converter.convert.assert_not_called()

    def test_pdf_not_on_storage_routes_to_skipped(
        self, monkeypatch, stub_converter
    ):
        monkeypatch.setattr(
            "riszotto.bulk.get_pdf_attachments",
            lambda zot, key: [_attachment(key)],
        )
        monkeypatch.setattr(
            "riszotto.bulk.resolve_pdf_path",
            MagicMock(side_effect=PdfNotOnStorageError("nope")),
        )
        zot = MagicMock()
        with patch("riszotto.bulk.all_items", return_value=[_item("A")]):
            result = populate_library(zot)
        assert result.ok == 0
        assert result.skipped == {"not_on_storage": 1}
        assert result.failed == {}

    def test_permission_error_routes_to_skipped(self, monkeypatch, stub_converter):
        monkeypatch.setattr(
            "riszotto.bulk.get_pdf_attachments",
            lambda zot, key: [_attachment(key)],
        )
        monkeypatch.setattr(
            "riszotto.bulk.resolve_pdf_path",
            MagicMock(side_effect=ZoteroPermissionError("403")),
        )
        zot = MagicMock()
        with patch("riszotto.bulk.all_items", return_value=[_item("A")]):
            result = populate_library(zot)
        assert result.ok == 0
        assert result.skipped == {"permission": 1}


class TestPopulateLibraryFailures:
    def test_download_failure_routes_to_failed(self, monkeypatch, stub_converter):
        monkeypatch.setattr(
            "riszotto.bulk.get_pdf_attachments",
            lambda zot, key: [_attachment(key)],
        )
        monkeypatch.setattr(
            "riszotto.bulk.resolve_pdf_path",
            MagicMock(side_effect=RuntimeError("network down")),
        )
        zot = MagicMock()
        with patch("riszotto.bulk.all_items", return_value=[_item("A")]):
            result = populate_library(zot)
        assert result.ok == 0
        assert result.skipped == {}
        assert result.failed == {"download_failed": ["A: network down"]}

    def test_convert_failure_routes_to_failed(self, stub_pipeline, monkeypatch):
        fake = MagicMock()
        fake.convert.side_effect = RuntimeError("docling crashed")
        monkeypatch.setattr("riszotto.bulk.get_converter", lambda backend=None: fake)
        zot = MagicMock()
        with patch("riszotto.bulk.all_items", return_value=[_item("A")]):
            result = populate_library(zot)
        assert result.ok == 0
        assert result.failed == {"convert_failed": ["A: docling crashed"]}

    def test_import_error_aborts_run(self, stub_pipeline, monkeypatch):
        fake = MagicMock()
        fake.convert.side_effect = ImportError("docling not installed")
        monkeypatch.setattr("riszotto.bulk.get_converter", lambda backend=None: fake)
        zot = MagicMock()
        with patch("riszotto.bulk.all_items", return_value=[_item("A"), _item("B")]):
            with pytest.raises(ImportError, match="docling not installed"):
                populate_library(zot)


class TestPopulateLibraryDryRun:
    def test_dry_run_skips_resolve_and_convert(self, monkeypatch, stub_converter):
        resolve = MagicMock(side_effect=AssertionError("should not be called"))
        monkeypatch.setattr(
            "riszotto.bulk.get_pdf_attachments",
            lambda zot, key: [_attachment(key)],
        )
        monkeypatch.setattr("riszotto.bulk.resolve_pdf_path", resolve)
        zot = MagicMock()
        with patch("riszotto.bulk.all_items", return_value=[_item("A"), _item("B")]):
            result = populate_library(zot, dry_run=True)
        assert result.ok == 2
        assert result.failed == {}
        stub_converter.convert.assert_not_called()


class TestPopulateLibraryLimit:
    def test_limit_is_forwarded_to_all_items(self, stub_pipeline, stub_converter):
        zot = MagicMock()
        with patch("riszotto.bulk.all_items", return_value=[_item("A")]) as m:
            populate_library(zot, limit=42)
        m.assert_called_once_with(zot, collection_key=None, limit=42)


class TestPopulateLibraryInterrupt:
    def test_keyboard_interrupt_returns_partial(self, monkeypatch):
        # Mid-loop KeyboardInterrupt: first item ok, second item raises during convert.
        fake = MagicMock()
        fake.convert.side_effect = [
            MagicMock(markdown="md", figures={}),
            KeyboardInterrupt(),
        ]
        monkeypatch.setattr("riszotto.bulk.get_converter", lambda backend=None: fake)
        monkeypatch.setattr(
            "riszotto.bulk.get_pdf_attachments",
            lambda zot, key: [_attachment(key)],
        )
        monkeypatch.setattr(
            "riszotto.bulk.resolve_pdf_path",
            lambda zot, att: Path(f"/tmp/{att['key']}.pdf"),
        )
        zot = MagicMock()
        with patch(
            "riszotto.bulk.all_items",
            return_value=[_item("A"), _item("B"), _item("C")],
        ):
            result = populate_library(zot)
        assert result.interrupted is True
        assert result.ok == 1
        # B is in-flight when interrupted; not counted as failed.
        assert result.failed == {}


class TestPopulateLibraryProgress:
    def test_progress_lifecycle_called(self, stub_pipeline, stub_converter):
        prog = MagicMock()
        zot = MagicMock()
        with patch(
            "riszotto.bulk.all_items",
            return_value=[_item("A", title="Paper A"), _item("B", title="Paper B")],
        ):
            populate_library(zot, progress=prog)
        prog.start.assert_called_once()
        assert prog.advance.call_count == 2
        prog.finish.assert_called_once()
