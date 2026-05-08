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
