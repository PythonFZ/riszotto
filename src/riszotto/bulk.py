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
