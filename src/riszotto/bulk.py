"""Bulk PDF download + conversion across an entire Zotero library."""

from __future__ import annotations

import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import IO, Any, Protocol

from riszotto.client import (
    PdfNotOnStorageError,
    ZoteroPermissionError,
    all_items,
    get_pdf_attachments,
    resolve_pdf_path,
)
from riszotto.converter import get_converter


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
