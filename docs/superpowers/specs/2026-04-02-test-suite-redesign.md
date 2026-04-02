# Test Suite Redesign: Integration Tests Over Mocks

**Date:** 2026-04-02
**Status:** Approved

## Problem

`test_converter_docling.py` relies on 11+ `@patch(..., create=True)` decorators per test to mock the entire docling pipeline. This:

- Makes tests brittle and hard to read (15 lines of decorators per test)
- Tests the mock setup more than the actual converter logic
- Caused a CI failure: `import pandas` in a test that runs under the `semantic` extra where pandas isn't installed
- The `semantic`/`full` CI matrix split is redundant since `full` is a superset of `semantic`

## Decisions

1. **Integration tests over mocks** for the docling converter
2. **Download a real arxiv PDF** as the test fixture
3. **Extract `_process_items()`** from `DoclingConverter.convert()` so edge cases can be tested without pipeline mocking
4. **Drop the `semantic` CI matrix** — run only `full` across 3 Python versions

## Changes

### 1. Refactor `src/riszotto/converter/docling.py`

Extract the item-processing loop from `convert()` into a standalone function:

```python
def _process_items(items, doc, cache_path, *, table_style, equation_mode):
    """Convert docling items into markdown parts and figure paths."""
    parts: list[str] = []
    figures: dict[str, Path] = {}
    figure_count = table_count = equation_count = 0

    for element, _level in items:
        # ... existing isinstance/branching logic moves here

    return parts, figures
```

`convert()` calls `_process_items()` after pipeline setup and before caching.

### 2. Rewrite `tests/test_converter_docling.py`

**Kept as-is:**
- `TestDoclingAvailableFlag` — tests `DOCLING_AVAILABLE` bool exists (no docling needed)
- `TestDoclingConverterInit` — tests `ImportError` when docling missing (no docling needed)

**New integration tests** (all guarded by `pytest.importorskip("docling")`):

- Module-scoped fixture: download a small arxiv PDF, cache to `tests/.cache/`
- Module-scoped fixture: run `DoclingConverter.convert()` once, share result
- `test_produces_nonempty_markdown` — smoke test
- `test_extracts_text` — markdown contains recognizable text from the paper
- `test_extracts_figures` — `result.figures` is non-empty, files exist on disk
- `test_cache_roundtrip` — convert twice, verify second call hits cache
- `test_different_table_styles` — both `inline` and `image` produce output

**New edge-case tests** (call `_process_items()` directly):

Uses `MagicMock(spec=RealDoclingType)` with the real docling types — one mock per item, zero pipeline mocking.

- `test_picture_get_image_none` — fallback text produced
- `test_table_image_fallback_to_inline` — falls back to markdown table
- `test_formula_image_fallback_to_latex` — falls back to `$$latex$$`
- `test_formula_no_image_no_text` — "not available" message

**Deleted:**
- All stub classes (`_StubTextItem`, `_StubPictureItem`, `_StubTableItem`, `_StubFormulaItem`)
- All 11-decorator mock test methods
- `import pandas as pd` in tests

### 3. Simplify `.github/workflows/pytest.yaml`

```yaml
# Before: 3 Python versions x 2 extras = 6 jobs
strategy:
  matrix:
    python-version: ["3.11", "3.12", "3.13"]
    extras: ["semantic", "full"]

# After: 3 Python versions x 1 = 3 jobs
strategy:
  matrix:
    python-version: ["3.11", "3.12", "3.13"]
```

Install step: `uv sync --extra full`

## Performance Budget

- Arxiv PDF download: cached after first run, ~1s when cached
- Single docling conversion: 10-30s depending on paper length
- Edge-case tests via `_process_items()`: instant
- Total expected CI time: under 2 minutes per Python version (well within the 10-minute limit)
