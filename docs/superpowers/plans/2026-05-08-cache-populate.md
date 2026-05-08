# `riszotto cache populate` Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add `riszotto cache populate` — a bulk-conversion command that walks a Zotero library, downloads every item's first PDF attachment, and converts each to markdown, reusing both existing caches so re-runs are idempotent and resumable.

**Architecture:** New module `src/riszotto/bulk.py` owns the loop and a `PopulateResult` dataclass; new helper `client.all_items()` enumerates parent items (with optional collection scope and limit). CLI wrapper in `src/riszotto/cli.py` parses flags, resolves library + collection, drives a `rich.progress`-backed reporter (or non-TTY logger), and prints the summary. Per-item failures are caught and bucketed; the run continues. `KeyboardInterrupt` is converted to a partial result + exit code 130.

**Tech Stack:** Python 3.11+, `typer`, `pyzotero`, `rich` (transitive via typer), `pytest`. uv for package management. Tests use `unittest.mock` and Typer's `CliRunner`.

**Constraints (hard):**
- All tests use `uv run pytest`. Do not invoke `pytest` directly.
- Do not modify any test marked `@pytest.mark.protected`.
- Reuse `resolve_pdf_path()`, `get_pdf_attachments()`, `get_converter()`, `Converter.convert()` and the existing caches verbatim — no parallel pipelines.
- `--no-cache` only forwards to the converter; the PDF cache stays a hit (content-addressed by md5).

**Spec:** `docs/superpowers/specs/2026-05-08-cache-populate-design.md`

---

## File Structure

| File | Status | Responsibility |
|------|--------|----------------|
| `src/riszotto/client.py` | Modify | Add `all_items()` returning parent items, with optional `collection_key` and `limit`. |
| `src/riszotto/bulk.py` | **Create** | `PopulateResult` dataclass, `ProgressReporter` protocol, `_NullProgress` no-op, `populate_library()` loop. |
| `src/riszotto/cli.py` | Modify | New `@cache_app.command("populate")` and `_resolve_collection_key()` helper. Imports `populate_library` and a rich-backed reporter from `bulk`. |
| `tests/test_client.py` | Modify | Add `TestAllItems` covering library, collection, pagination, limit. |
| `tests/test_bulk.py` | **Create** | Unit tests for `populate_library` against mocked Zotero + monkeypatched converter. |
| `tests/test_cli.py` | Modify | Add `TestCachePopulate` covering flag wiring, exit codes, summary text. |
| `README.md` | Modify | Document the new command. |
| `CHANGELOG.md` | Modify | New entry under the next release. |

---

## Task 1: Add `all_items()` helper in `client.py`

**Files:**
- Modify: `src/riszotto/client.py` (append a new function near `recent_items`, around line 300)
- Modify: `tests/test_client.py` (add a new `TestAllItems` class)

- [ ] **Step 1.1: Write the failing tests**

Append the following class to `tests/test_client.py` (place it after the existing `TestRecentItems` class):

```python
class TestAllItems:
    def test_returns_parent_items_via_everything_when_no_limit(self):
        zot = MagicMock()
        zot.top.return_value = "TOP_QUERY"
        zot.everything.return_value = [
            {"key": "A", "data": {"itemType": "journalArticle"}},
            {"key": "B", "data": {"itemType": "book"}},
        ]
        from riszotto.client import all_items

        result = all_items(zot)

        zot.top.assert_called_once_with()
        zot.everything.assert_called_once_with("TOP_QUERY")
        assert [item["key"] for item in result] == ["A", "B"]

    def test_uses_collection_items_top_when_collection_key_given(self):
        zot = MagicMock()
        zot.collection_items_top.return_value = "COLL_QUERY"
        zot.everything.return_value = [{"key": "X", "data": {"itemType": "preprint"}}]
        from riszotto.client import all_items

        result = all_items(zot, collection_key="COLL123")

        zot.collection_items_top.assert_called_once_with("COLL123")
        zot.everything.assert_called_once_with("COLL_QUERY")
        assert [item["key"] for item in result] == ["X"]

    def test_paginates_manually_when_limit_set(self):
        zot = MagicMock()
        zot.top.return_value = [
            {"key": "A", "data": {"itemType": "journalArticle"}},
            {"key": "B", "data": {"itemType": "book"}},
            {"key": "C", "data": {"itemType": "preprint"}},
        ]
        from riszotto.client import all_items

        result = all_items(zot, limit=2)

        zot.top.assert_called_once_with(limit=2, start=0)
        zot.everything.assert_not_called()
        assert [item["key"] for item in result] == ["A", "B"]

    def test_limit_with_collection(self):
        zot = MagicMock()
        zot.collection_items_top.return_value = [
            {"key": "A", "data": {"itemType": "journalArticle"}},
        ]
        from riszotto.client import all_items

        result = all_items(zot, collection_key="COLL", limit=5)

        zot.collection_items_top.assert_called_once_with("COLL", limit=5, start=0)
        zot.everything.assert_not_called()
        assert [item["key"] for item in result] == ["A"]
```

- [ ] **Step 1.2: Run tests to verify they fail**

Run: `uv run pytest tests/test_client.py::TestAllItems -v`
Expected: FAIL with `ImportError: cannot import name 'all_items' from 'riszotto.client'`.

- [ ] **Step 1.3: Implement `all_items()`**

Add the following function to `src/riszotto/client.py`, immediately after `recent_items` (around line 300):

```python
def all_items(
    zot: zotero.Zotero,
    *,
    collection_key: str | None = None,
    limit: int | None = None,
) -> list[dict[str, Any]]:
    """Return all parent (top-level) items in the library or a collection.

    Parameters
    ----------
    zot
        Configured pyzotero client.
    collection_key
        If given, restrict to items in this collection (top-level only).
    limit
        If given, cap the number of items returned. When ``None`` (default),
        every parent item is fetched via ``zot.everything()``.

    Returns
    -------
    list of dict
        Parent (top-level) Zotero items. Child items (attachments, notes)
        are not returned because the underlying ``top`` / ``collection_items_top``
        endpoints already filter to parents.
    """
    if limit is None:
        if collection_key is not None:
            query = zot.collection_items_top(collection_key)
        else:
            query = zot.top()
        return zot.everything(query)

    if collection_key is not None:
        return zot.collection_items_top(collection_key, limit=limit, start=0)
    return zot.top(limit=limit, start=0)
```

- [ ] **Step 1.4: Run tests to verify they pass**

Run: `uv run pytest tests/test_client.py::TestAllItems -v`
Expected: 4 passed.

- [ ] **Step 1.5: Commit**

```bash
git add src/riszotto/client.py tests/test_client.py
git commit -m "feat(client): add all_items() for library enumeration

Parent-item enumeration with optional collection scope and limit.
Used by the upcoming cache populate command; uses zot.everything()
for unbounded fetches and manual pagination when limit is set."
```

---

## Task 2: Scaffold `bulk.py` with `PopulateResult` and `ProgressReporter`

**Files:**
- Create: `src/riszotto/bulk.py`
- Create: `tests/test_bulk.py`

- [ ] **Step 2.1: Write the failing tests**

Create `tests/test_bulk.py` with the following content:

```python
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
        assert r.total_processed() == 14

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
```

- [ ] **Step 2.2: Run tests to verify they fail**

Run: `uv run pytest tests/test_bulk.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'riszotto.bulk'`.

- [ ] **Step 2.3: Create the module skeleton**

Create `src/riszotto/bulk.py` with:

```python
"""Bulk PDF download + conversion across an entire Zotero library."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol


@dataclass
class PopulateResult:
    """Outcome of a `populate_library` run.

    Attributes
    ----------
    ok
        Items whose PDF was successfully downloaded and converted (or already
        cached on disk and re-validated).
    skipped
        Mapping of skip reason to count. Reasons:
        ``no_pdf``, ``not_on_storage``, ``permission``.
    failed
        Mapping of failure reason to a list of ``"KEY: message"`` strings.
        Reasons: ``download_failed``, ``convert_failed``.
    elapsed_seconds
        Wall-clock time for the run.
    interrupted
        True when the loop terminated early via ``KeyboardInterrupt``.
    """

    ok: int = 0
    skipped: dict[str, int] = field(default_factory=dict)
    failed: dict[str, list[str]] = field(default_factory=dict)
    elapsed_seconds: float = 0.0
    interrupted: bool = False

    def skipped_count(self) -> int:
        return sum(self.skipped.values())

    def failed_count(self) -> int:
        return sum(len(v) for v in self.failed.values())

    def total_processed(self) -> int:
        return self.ok + self.skipped_count() + self.failed_count()


class ProgressReporter(Protocol):
    """Minimal protocol the loop uses to report progress.

    Implementations: ``_NullProgress`` (tests), ``_RichProgress`` (TTY CLI),
    ``_PlainProgress`` (non-TTY CLI).
    """

    def start(
        self, *, total: int, library_label: str, scope_label: str | None
    ) -> None: ...

    def advance(self, *, label: str) -> None: ...

    def log(self, message: str) -> None: ...

    def finish(self) -> None: ...


class _NullProgress:
    """No-op reporter used by tests and as a default when none is supplied."""

    def start(
        self, *, total: int, library_label: str, scope_label: str | None
    ) -> None:
        pass

    def advance(self, *, label: str) -> None:
        pass

    def log(self, message: str) -> None:
        pass

    def finish(self) -> None:
        pass
```

- [ ] **Step 2.4: Run tests to verify they pass**

Run: `uv run pytest tests/test_bulk.py -v`
Expected: 5 passed.

- [ ] **Step 2.5: Commit**

```bash
git add src/riszotto/bulk.py tests/test_bulk.py
git commit -m "feat(bulk): scaffold PopulateResult and ProgressReporter protocol

Dataclass + protocol skeleton for the upcoming populate_library loop.
A no-op reporter is included for tests and as a default."
```

---

## Task 3: Implement `populate_library()`

**Files:**
- Modify: `src/riszotto/bulk.py`
- Modify: `tests/test_bulk.py`

- [ ] **Step 3.1: Write the failing tests**

Append the following to `tests/test_bulk.py`:

```python
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
```

- [ ] **Step 3.2: Run tests to verify they fail**

Run: `uv run pytest tests/test_bulk.py -v`
Expected: import error or `AttributeError` on `populate_library`. Existing 5 tests still pass.

- [ ] **Step 3.3: Implement `populate_library`**

Append the following to `src/riszotto/bulk.py` (add the imports at the top; rest at the bottom):

```python
# add at top of file, below the existing `from __future__ import annotations`
import time
from pathlib import Path
from typing import Any

from riszotto.client import (
    PdfNotOnStorageError,
    ZoteroPermissionError,
    all_items,
    get_pdf_attachments,
    resolve_pdf_path,
)
from riszotto.converter import get_converter
```

```python
# add at bottom of file
def _format_label(item: dict[str, Any]) -> str:
    """Short human label for progress display: '<KEY> <Title…>'."""
    key = item.get("key", "?")
    title = item.get("data", {}).get("title", "") or "(untitled)"
    if len(title) > 60:
        title = title[:57] + "..."
    return f"{key} {title}"


def populate_library(
    zot: Any,
    *,
    collection_key: str | None = None,
    limit: int | None = None,
    backend: str | None = None,
    no_cache: bool = False,
    dry_run: bool = False,
    progress: ProgressReporter | None = None,
) -> PopulateResult:
    """Walk a library and warm both caches for every item with a PDF.

    Sequential: pyzotero rate limits cap I/O parallelism and docling is heavy
    enough that multi-process conversion risks OOM/contention. Both caches
    short-circuit on hit, so re-runs are cheap.

    Parameters
    ----------
    zot
        Configured pyzotero client (already scoped to the desired library).
    collection_key
        If given, restrict to a single collection (top-level items only).
    limit
        Maximum number of items to process (after discovery).
    backend
        Converter backend (``"markitdown"`` / ``"docling"``); ``None`` =
        auto-detect.
    no_cache
        Forwarded to ``Converter.convert``: forces re-conversion of markdown.
        The PDF cache is unaffected (content-addressed by md5).
    dry_run
        Skip downloading and converting; only enumerate.
    progress
        Reporter used to drive a progress bar (CLI) or stay quiet (tests).
    """
    progress = progress or _NullProgress()
    converter = get_converter(backend) if not dry_run else None

    items = all_items(zot, collection_key=collection_key, limit=limit)
    progress.start(
        total=len(items),
        library_label=getattr(zot, "library_id", "library"),
        scope_label=collection_key,
    )

    result = PopulateResult()
    started = time.monotonic()

    try:
        for item in items:
            label = _format_label(item)
            progress.advance(label=label)
            key = item["key"]

            attachments = get_pdf_attachments(zot, key)
            if not attachments:
                result.skipped["no_pdf"] = result.skipped.get("no_pdf", 0) + 1
                progress.log(f"{key} skip:no_pdf")
                continue

            if dry_run:
                result.ok += 1
                progress.log(f"{key} dry-run pdf=Y")
                continue

            attachment = attachments[0]
            try:
                pdf_path = resolve_pdf_path(zot, attachment)
            except PdfNotOnStorageError:
                result.skipped["not_on_storage"] = (
                    result.skipped.get("not_on_storage", 0) + 1
                )
                progress.log(f"{key} skip:not_on_storage")
                continue
            except ZoteroPermissionError:
                result.skipped["permission"] = (
                    result.skipped.get("permission", 0) + 1
                )
                progress.log(f"{key} skip:permission")
                continue
            except KeyboardInterrupt:
                result.interrupted = True
                break
            except Exception as e:
                result.failed.setdefault("download_failed", []).append(
                    f"{key}: {e}"
                )
                progress.log(f"{key} fail:download_failed: {e}")
                continue

            try:
                converter.convert(
                    Path(pdf_path),
                    zotero_key=key,
                    no_cache=no_cache,
                )
            except KeyboardInterrupt:
                result.interrupted = True
                break
            except ImportError:
                # Backend extras missing -- abort the whole run.
                raise
            except Exception as e:
                result.failed.setdefault("convert_failed", []).append(
                    f"{key}: {e}"
                )
                progress.log(f"{key} fail:convert_failed: {e}")
                continue

            result.ok += 1
            progress.log(f"{key} ok")

    except KeyboardInterrupt:
        result.interrupted = True
    finally:
        result.elapsed_seconds = time.monotonic() - started
        progress.finish()

    return result
```

- [ ] **Step 3.4: Run tests to verify they pass**

Run: `uv run pytest tests/test_bulk.py -v`
Expected: all tests pass (5 from Task 2 + the new ones).

- [ ] **Step 3.5: Commit**

```bash
git add src/riszotto/bulk.py tests/test_bulk.py
git commit -m "feat(bulk): implement populate_library loop

Sequential walk over items with continue-on-error semantics, bucketed
skip/fail counts, KeyboardInterrupt → partial result, ImportError
aborts the run, dry-run mode skips download + convert."
```

---

## Task 4: CLI command `cache populate`

**Files:**
- Modify: `src/riszotto/cli.py`
- Modify: `tests/test_cli.py`

- [ ] **Step 4.1: Write the failing tests**

Append the following to `tests/test_cli.py` (place after existing cache-command tests). The fixture `runner` and helper `_zot_mock` may already exist in this file — match the existing style; if not, the snippet below is self-contained.

```python
class TestCachePopulate:
    """riszotto cache populate"""

    def _zot(self):
        zot = MagicMock()
        zot.collections.return_value = []
        return zot

    def test_invokes_populate_library_and_prints_summary(self, monkeypatch):
        from riszotto import cli as cli_mod
        from riszotto.bulk import PopulateResult

        result = PopulateResult(
            ok=2,
            skipped={"no_pdf": 1},
            failed={"convert_failed": ["X: boom"]},
            elapsed_seconds=42.0,
        )
        monkeypatch.setattr(cli_mod, "_get_zot", lambda library=None: self._zot())
        monkeypatch.setattr(
            cli_mod, "populate_library", MagicMock(return_value=result)
        )

        from typer.testing import CliRunner

        out = CliRunner().invoke(cli_mod.app, ["cache", "populate"])

        assert out.exit_code == 0
        assert "2 ok" in out.stdout
        assert "1 skipped" in out.stdout
        assert "1 failed" in out.stdout

    def test_exit_code_1_when_zero_ok_and_failures(self, monkeypatch):
        from riszotto import cli as cli_mod
        from riszotto.bulk import PopulateResult

        monkeypatch.setattr(cli_mod, "_get_zot", lambda library=None: self._zot())
        monkeypatch.setattr(
            cli_mod,
            "populate_library",
            MagicMock(
                return_value=PopulateResult(
                    ok=0, failed={"convert_failed": ["A: x"]}
                )
            ),
        )

        from typer.testing import CliRunner

        out = CliRunner().invoke(cli_mod.app, ["cache", "populate"])
        assert out.exit_code == 1

    def test_exit_code_130_on_interrupt(self, monkeypatch):
        from riszotto import cli as cli_mod
        from riszotto.bulk import PopulateResult

        monkeypatch.setattr(cli_mod, "_get_zot", lambda library=None: self._zot())
        monkeypatch.setattr(
            cli_mod,
            "populate_library",
            MagicMock(return_value=PopulateResult(ok=1, interrupted=True)),
        )

        from typer.testing import CliRunner

        out = CliRunner().invoke(cli_mod.app, ["cache", "populate"])
        assert out.exit_code == 130
        assert "Interrupted" in out.stdout

    def test_collection_resolves_to_key(self, monkeypatch):
        from riszotto import cli as cli_mod
        from riszotto.bulk import PopulateResult

        zot = self._zot()
        zot.collections.return_value = [
            {"data": {"key": "COLL1", "name": "ML papers"}},
            {"data": {"key": "COLL2", "name": "Physics"}},
        ]
        monkeypatch.setattr(cli_mod, "_get_zot", lambda library=None: zot)
        captured = {}

        def fake_populate(z, **kwargs):
            captured.update(kwargs)
            return PopulateResult(ok=1)

        monkeypatch.setattr(cli_mod, "populate_library", fake_populate)

        from typer.testing import CliRunner

        out = CliRunner().invoke(
            cli_mod.app, ["cache", "populate", "--collection", "ML"]
        )
        assert out.exit_code == 0
        assert captured["collection_key"] == "COLL1"

    def test_ambiguous_collection_exits_1(self, monkeypatch):
        from riszotto import cli as cli_mod

        zot = self._zot()
        zot.collections.return_value = [
            {"data": {"key": "C1", "name": "Machine Learning"}},
            {"data": {"key": "C2", "name": "Machine Vision"}},
        ]
        monkeypatch.setattr(cli_mod, "_get_zot", lambda library=None: zot)

        from typer.testing import CliRunner

        out = CliRunner().invoke(
            cli_mod.app, ["cache", "populate", "--collection", "Machine"]
        )
        assert out.exit_code == 1
        assert "Ambiguous" in out.stdout or "ambiguous" in out.stdout

    def test_unknown_collection_exits_1(self, monkeypatch):
        from riszotto import cli as cli_mod

        zot = self._zot()
        zot.collections.return_value = [
            {"data": {"key": "C1", "name": "Physics"}},
        ]
        monkeypatch.setattr(cli_mod, "_get_zot", lambda library=None: zot)

        from typer.testing import CliRunner

        out = CliRunner().invoke(
            cli_mod.app, ["cache", "populate", "--collection", "Biology"]
        )
        assert out.exit_code == 1
```

- [ ] **Step 4.2: Run tests to verify they fail**

Run: `uv run pytest tests/test_cli.py::TestCachePopulate -v`
Expected: FAIL — `cache populate` is not yet a registered command, so Typer exits with code 2 ("No such command").

- [ ] **Step 4.3: Add the CLI command and helper**

Add the following imports near the top of `src/riszotto/cli.py`, alongside the other `riszotto.*` imports (look for `from riszotto.client import ...`):

```python
from riszotto.bulk import PopulateResult, populate_library
```

Add the helper function (place it near `_get_zot`, around line 87):

```python
def _resolve_collection_key(zot: zotero.Zotero, name: str) -> str:
    """Resolve a partial collection name to its Zotero key.

    Mirrors `_match_library` semantics: case-insensitive prefix/substring
    match. Single hit wins; zero or multiple hits print candidates and
    raise `typer.Exit(1)`.
    """
    needle = name.casefold()
    cols = zot.collections()
    matches = [
        c for c in cols if needle in c["data"]["name"].casefold()
    ]
    if not matches:
        typer.echo(
            f"No collection matching '{name}'. Run 'riszotto collections' to see available collections.",
            err=True,
        )
        raise typer.Exit(1)
    if len(matches) > 1:
        names = ", ".join(c["data"]["name"] for c in matches)
        typer.echo(
            f"Ambiguous collection '{name}'. Candidates: {names}", err=True
        )
        raise typer.Exit(1)
    return matches[0]["data"]["key"]
```

Append the new command to the cache_app block (after `cache_clear`, around line 1176 — i.e. at the very end of the file):

```python
@cache_app.command("populate")
def cache_populate(
    library: LibraryOption = None,
    collection: Annotated[
        Optional[str],
        typer.Option(
            "--collection", "-c", help="Restrict to a single Zotero collection."
        ),
    ] = None,
    limit: Annotated[
        Optional[int],
        typer.Option(
            "--limit", "-n", help="Maximum number of items to process."
        ),
    ] = None,
    backend: Annotated[
        Optional[str],
        typer.Option(
            "--backend", help="Converter backend ('markitdown' or 'docling')."
        ),
    ] = None,
    dry_run: Annotated[
        bool,
        typer.Option(
            "--dry-run", help="List items that would be processed; do not download or convert."
        ),
    ] = False,
    no_cache: Annotated[
        bool,
        typer.Option(
            "--no-cache",
            help="Force re-conversion of markdown (PDF cache stays a hit).",
        ),
    ] = False,
) -> None:
    """Download and convert every PDF in a library, warming both caches."""
    zot = _get_zot(library=library)

    collection_key: str | None = None
    if collection is not None:
        collection_key = _resolve_collection_key(zot, collection)

    try:
        result = populate_library(
            zot,
            collection_key=collection_key,
            limit=limit,
            backend=backend,
            no_cache=no_cache,
            dry_run=dry_run,
        )
    except ImportError as e:
        typer.echo(str(e), err=True)
        raise typer.Exit(1)

    _print_populate_summary(result)

    if result.interrupted:
        raise typer.Exit(130)
    if result.ok == 0 and result.failed_count() > 0:
        raise typer.Exit(1)


def _print_populate_summary(result: PopulateResult) -> None:
    """Print the end-of-run summary to stdout."""
    if result.interrupted:
        typer.echo(f"Interrupted at {result.total_processed()} items processed.")

    elapsed = _format_elapsed(result.elapsed_seconds)
    typer.echo(
        f"Done. {result.ok} ok, {result.skipped_count()} skipped, "
        f"{result.failed_count()} failed in {elapsed}."
    )

    if result.skipped:
        parts = ", ".join(f"{n} {reason}" for reason, n in result.skipped.items())
        typer.echo(f"  skipped: {parts}")
    if result.failed:
        parts = ", ".join(
            f"{len(msgs)} {reason}" for reason, msgs in result.failed.items()
        )
        typer.echo(f"  failed:  {parts}")
        for reason, msgs in result.failed.items():
            for msg in msgs:
                typer.echo(f"    {reason}: {msg}", err=True)

    if result.ok + result.skipped_count() + result.failed_count() > 0 and not result.interrupted:
        typer.echo(
            "Re-run the same command to retry — cached items are skipped instantly."
        )


def _format_elapsed(seconds: float) -> str:
    """Format a duration like '4h 12m' or '53s'."""
    seconds = int(seconds)
    if seconds < 60:
        return f"{seconds}s"
    if seconds < 3600:
        return f"{seconds // 60}m {seconds % 60}s"
    h, rem = divmod(seconds, 3600)
    return f"{h}h {rem // 60}m"
```

- [ ] **Step 4.4: Run tests to verify they pass**

Run: `uv run pytest tests/test_cli.py::TestCachePopulate -v`
Expected: 6 passed.

- [ ] **Step 4.5: Run the full test suite to catch regressions**

Run: `uv run pytest -q`
Expected: All previously-passing tests still pass; the new tests pass.

- [ ] **Step 4.6: Commit**

```bash
git add src/riszotto/cli.py tests/test_cli.py
git commit -m "feat(cli): add 'riszotto cache populate' command

Subcommand under cache_app drives populate_library, resolves the target
library and (optional) collection, prints an end-of-run summary, and
chooses an exit code (0/1/130) based on the result."
```

---

## Task 5: Add a rich-backed progress reporter for the CLI

**Files:**
- Modify: `src/riszotto/bulk.py` (add `_RichProgress` and `_PlainProgress`, plus a `make_cli_progress()` factory)
- Modify: `src/riszotto/cli.py` (pass `make_cli_progress()` into `populate_library`)
- Modify: `tests/test_bulk.py` (cover the factory's TTY/non-TTY branch)

- [ ] **Step 5.1: Write the failing tests**

Append to `tests/test_bulk.py`:

```python
class TestMakeCliProgress:
    def test_returns_rich_progress_when_tty(self, monkeypatch):
        from riszotto.bulk import _RichProgress, make_cli_progress

        class Stream:
            def isatty(self):
                return True

        prog = make_cli_progress(stream=Stream())
        assert isinstance(prog, _RichProgress)

    def test_returns_plain_progress_when_not_tty(self):
        from riszotto.bulk import _PlainProgress, make_cli_progress

        class Stream:
            def isatty(self):
                return False

        prog = make_cli_progress(stream=Stream())
        assert isinstance(prog, _PlainProgress)


class TestPlainProgress:
    def test_log_writes_to_stream(self):
        from io import StringIO

        from riszotto.bulk import _PlainProgress

        buf = StringIO()
        p = _PlainProgress(stream=buf)
        p.start(total=2, library_label="lib", scope_label=None)
        p.advance(label="A")
        p.log("A ok")
        p.finish()

        text = buf.getvalue()
        assert "[1/2]" in text
        assert "A ok" in text
```

- [ ] **Step 5.2: Run tests to verify they fail**

Run: `uv run pytest tests/test_bulk.py::TestMakeCliProgress tests/test_bulk.py::TestPlainProgress -v`
Expected: FAIL — `make_cli_progress`, `_RichProgress`, `_PlainProgress` not defined.

- [ ] **Step 5.3: Implement the reporters and factory**

Append the following to `src/riszotto/bulk.py`:

```python
# imports — add near the top alongside existing imports
import sys
from typing import IO


class _PlainProgress:
    """Non-TTY reporter: prints one line per item to stderr."""

    def __init__(self, stream: IO[str] | None = None) -> None:
        self._stream = stream if stream is not None else sys.stderr
        self._total = 0
        self._n = 0

    def start(
        self, *, total: int, library_label: str, scope_label: str | None
    ) -> None:
        self._total = total
        scope = f", scope: {scope_label}" if scope_label else ""
        self._stream.write(
            f"Populating cache for {library_label} ({total} items{scope})\n"
        )

    def advance(self, *, label: str) -> None:
        self._n += 1
        self._stream.write(f"[{self._n}/{self._total}] {label}\n")

    def log(self, message: str) -> None:
        self._stream.write(f"{message}\n")

    def finish(self) -> None:
        self._stream.flush()


class _RichProgress:
    """TTY reporter backed by rich.progress."""

    def __init__(self) -> None:
        from rich.console import Console
        from rich.progress import (
            BarColumn,
            MofNCompleteColumn,
            Progress,
            TextColumn,
            TimeRemainingColumn,
        )

        self._console = Console(stderr=True)
        self._progress = Progress(
            TextColumn("[bold]{task.description}"),
            BarColumn(),
            MofNCompleteColumn(),
            TimeRemainingColumn(),
            TextColumn("{task.fields[label]}"),
            console=self._console,
            transient=False,
        )
        self._task_id = None

    def start(
        self, *, total: int, library_label: str, scope_label: str | None
    ) -> None:
        scope = f" — {scope_label}" if scope_label else ""
        self._progress.start()
        self._task_id = self._progress.add_task(
            f"Populating {library_label}{scope}",
            total=total,
            label="",
        )

    def advance(self, *, label: str) -> None:
        if self._task_id is not None:
            self._progress.update(self._task_id, label=label, advance=1)

    def log(self, message: str) -> None:
        # Per-item log lines would compete with the bar; let the bar speak instead.
        pass

    def finish(self) -> None:
        self._progress.stop()


def make_cli_progress(*, stream: IO[str] | None = None) -> ProgressReporter:
    """Pick a reporter based on whether stderr is a TTY."""
    s = stream if stream is not None else sys.stderr
    if hasattr(s, "isatty") and s.isatty():
        return _RichProgress()
    return _PlainProgress(stream=s)
```

In `src/riszotto/cli.py`, update the import and the `populate_library(...)` call:

```python
# update import line added in Task 4
from riszotto.bulk import PopulateResult, make_cli_progress, populate_library
```

```python
# inside cache_populate, replace the populate_library() call with:
    progress = make_cli_progress()
    try:
        result = populate_library(
            zot,
            collection_key=collection_key,
            limit=limit,
            backend=backend,
            no_cache=no_cache,
            dry_run=dry_run,
            progress=progress,
        )
    except ImportError as e:
        typer.echo(str(e), err=True)
        raise typer.Exit(1)
```

- [ ] **Step 5.4: Run tests to verify they pass**

Run: `uv run pytest tests/test_bulk.py -v`
Expected: all bulk tests pass.

Run: `uv run pytest tests/test_cli.py::TestCachePopulate -v`
Expected: still 6 passed (the CLI tests don't pin the reporter type — `make_cli_progress` returns `_PlainProgress` under `CliRunner` because its captured stderr is not a TTY).

- [ ] **Step 5.5: Smoke-test the command end-to-end (interactive only — skip if no Zotero credentials)**

This step is optional and only meaningful with a real configured library:

```bash
uv run riszotto cache populate --library "potentialsciences" --limit 3 --dry-run
```

Expected: 3 lines + summary. If no credentials are configured, expect `Exit 1` with a "Zotero desktop is not running" or config error. That confirms the command is wired correctly.

- [ ] **Step 5.6: Commit**

```bash
git add src/riszotto/bulk.py src/riszotto/cli.py tests/test_bulk.py
git commit -m "feat(bulk): rich progress bar (TTY) + per-line log (non-TTY)

make_cli_progress() picks the reporter based on stderr's TTY-ness.
Rich progress shows ETA + current item; plain progress prints
'[N/M] KEY title' + per-item status lines."
```

---

## Task 6: Documentation

**Files:**
- Modify: `README.md`
- Modify: `CHANGELOG.md`

- [ ] **Step 6.1: Add a Usage section to README.md**

Open `README.md` and find the existing line documenting `riszotto cache show` (look for "cache show" or `## Cache` near the bottom of the Usage section). Add the following block after the `riszotto cache clear` example (or, if there's no dedicated cache subsection, append after the `riszotto index` examples around line 65):

```markdown
### Bulk-populate the cache

Download every PDF and convert each to markdown for an entire library.
Re-runs are idempotent: cached items are skipped instantly.

```bash
# Whole library
riszotto cache populate --library "potentialsciences"

# Just one collection, limited to the first 50 items (useful for testing)
riszotto cache populate --library "potentialsciences" \
    --collection "ML papers" --limit 50

# Dry-run: list items that would be processed
riszotto cache populate --dry-run
```

The command prints a progress bar to stderr and an end-of-run summary
to stdout. Per-item failures are logged but do not abort the run.
```

- [ ] **Step 6.2: Add a CHANGELOG entry**

Open `CHANGELOG.md` and add a new entry at the top of the unreleased section (create the section if it does not exist). The entry text:

```markdown
### Added

- `riszotto cache populate` — bulk download + convert every PDF in a library.
  Reuses the existing PDF and markdown caches so re-runs are idempotent.
  Supports `--library`, `--collection`, `--limit`, `--backend`, `--dry-run`,
  and `--no-cache`. Continues past per-item failures and prints a summary
  at the end.
```

- [ ] **Step 6.3: Run the full test suite one last time**

Run: `uv run pytest -q`
Expected: all tests pass.

- [ ] **Step 6.4: Commit**

```bash
git add README.md CHANGELOG.md
git commit -m "docs: document 'riszotto cache populate'"
```

---

## Self-Review Notes

**Spec coverage check:**

- Command shape (Task 4) — covered, all flags implemented.
- `--no-cache` semantics (PDF cache stays a hit) — relies on `Converter.convert` semantics; not tested directly here (out of scope for this command), but the docstring of `cache_populate` is explicit.
- New module `bulk.py` (Tasks 2–3) — covered.
- `client.all_items()` (Task 1) — covered.
- Item-pipeline error categories (`no_pdf`, `not_on_storage`, `permission`, `download_failed`, `convert_failed`) — covered in Task 3 tests.
- Multi-PDF "first attachment only" — covered via `attachments[0]`; matches `show`.
- `--dry-run` skips download + convert — covered (`TestPopulateLibraryDryRun`).
- TTY vs non-TTY progress — Task 5.
- End-of-run summary on stdout, errors on stderr — Task 4 implementation, asserted in tests.
- Exit codes 0/1/130 — Task 4 tests.
- `KeyboardInterrupt` → partial result — Task 3 tests.
- `ImportError` aborts — Task 3 tests.
- README + CHANGELOG — Task 6.

**Risks / open questions for the implementer:**

- `zotero.Zotero.collections()` may need pagination for libraries with hundreds of collections. The implementation calls it directly; if this turns out to be a real issue in practice, wrap it in `zot.everything(zot.collections())`. Out of scope for v1 because partial-name match across many collections isn't dangerous, just slow.
- `library_id` is read off the `zot` client for the progress label via `getattr`. If the attribute name in pyzotero changes, the label will fall back to `"library"`. Cosmetic only.
