# Test Suite Redesign Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace mock-heavy docling converter tests with real integration tests and surgical edge-case tests, simplify CI matrix.

**Architecture:** Extract item-processing logic from `DoclingConverter.convert()` into `_process_items()` so edge cases can be tested without mocking the pipeline. Integration tests download a real arxiv PDF and run the full converter. CI drops the redundant `semantic` matrix.

**Tech Stack:** pytest, docling, urllib (for arxiv download)

---

### Task 1: Extract `_process_items()` from `DoclingConverter.convert()`

**Files:**
- Modify: `src/riszotto/converter/docling.py:117-167`

- [ ] **Step 1: Extract the item-processing loop into `_process_items()`**

Add this function above the `DoclingConverter` class in `src/riszotto/converter/docling.py`:

```python
def _process_items(items, doc, cache_path: Path, *, table_style: StyleOption, equation_mode: EquationMode):
    """Convert docling document items into markdown parts and figure paths.

    Parameters
    ----------
    items
        Iterable of ``(element, level)`` tuples from ``doc.iterate_items()``.
    doc
        The docling document object (passed to ``get_image`` / ``export_to_dataframe``).
    cache_path
        Directory where extracted images are saved.
    table_style
        ``"inline"`` for markdown tables, ``"image"`` for PNG screenshots.
    equation_mode
        ``"latex"`` for LaTeX fallback, ``"image"`` for PNG screenshots.

    Returns
    -------
    tuple[list[str], dict[str, Path]]
        ``(parts, figures)`` — markdown fragments and a mapping of
        filename to saved image path.
    """
    parts: list[str] = []
    figures: dict[str, Path] = {}
    figure_count = 0
    table_count = 0
    equation_count = 0

    for element, _level in items:
        if isinstance(element, PictureItem):
            figure_count += 1
            filename = f"figure_{figure_count}.png"
            fig_path = cache_path / filename
            if _save_element_image(element, doc, fig_path):
                figures[filename] = fig_path
                parts.append(f"![Figure {figure_count}]({fig_path})")
            else:
                parts.append(f"[Figure {figure_count}: image not available]")

        elif isinstance(element, TableItem):
            table_count += 1
            if table_style == "inline":
                df = element.export_to_dataframe(doc=doc)
                parts.append(df.to_markdown())
            else:
                filename = f"table_{table_count}.png"
                tbl_path = cache_path / filename
                if _save_element_image(element, doc, tbl_path):
                    figures[filename] = tbl_path
                    parts.append(f"![Table {table_count}]({tbl_path})")
                else:
                    df = element.export_to_dataframe(doc=doc)
                    parts.append(df.to_markdown())

        elif isinstance(element, FormulaItem):
            equation_count += 1
            if equation_mode == "latex" and element.text:
                parts.append(f"$${element.text}$$")
            else:
                filename = f"equation_{equation_count}.png"
                eq_path = cache_path / filename
                if _save_element_image(element, doc, eq_path):
                    figures[filename] = eq_path
                    parts.append(f"![Equation {equation_count}]({eq_path})")
                elif element.text:
                    parts.append(f"$${element.text}$$")
                else:
                    parts.append(f"[Equation {equation_count}: not available]")

        elif isinstance(element, TextItem):
            parts.append(element.text)

    return parts, figures
```

- [ ] **Step 2: Update `convert()` to call `_process_items()`**

Replace lines 117-167 in the `convert()` method (everything from `parts: list[str] = []` through `markdown = "\n\n".join(parts)`) with:

```python
        parts, figures = _process_items(
            doc.iterate_items(),
            doc,
            cache_path,
            table_style=table_style,
            equation_mode=equation_mode,
        )

        markdown = "\n\n".join(parts)
```

The full `convert()` method should now look like:

```python
    def convert(
        self,
        pdf_path: Path,
        *,
        table_style: StyleOption = "inline",
        equation_style: StyleOption = "inline",
        zotero_key: str,
        no_cache: bool = False,
        ocr: bool = False,
        table_mode: str = "fast",
        equation_mode: EquationMode = "image",
    ) -> ConversionResult:
        """Convert a PDF to markdown with rich extraction."""
        pdf_hash = compute_pdf_hash(pdf_path)

        if not no_cache:
            cached = read_cache(
                zotero_key=zotero_key,
                pdf_hash=pdf_hash,
                table_style=table_style,
                equation_style=equation_style,
            )
            if cached is not None:
                return cached

        needs_page_images = table_style == "image" or equation_mode == "image"

        print("Converting PDF with docling...", file=sys.stderr)

        pipeline_options = ThreadedPdfPipelineOptions()
        pipeline_options.do_ocr = ocr
        pipeline_options.generate_picture_images = True
        pipeline_options.generate_page_images = needs_page_images
        pipeline_options.images_scale = 2.0 if needs_page_images else 1.0
        pipeline_options.do_table_structure = True
        pipeline_options.table_structure_options = TableStructureOptions(
            do_cell_matching=True,
            mode=(
                TableFormerMode.ACCURATE
                if table_mode == "accurate"
                else TableFormerMode.FAST
            ),
        )
        pipeline_options.do_formula_enrichment = equation_mode == "latex"
        pipeline_options.accelerator_options = AcceleratorOptions(
            num_threads=os.cpu_count() or 4,
            device=AcceleratorDevice.AUTO,
        )

        converter = DocumentConverter(
            format_options={
                InputFormat.PDF: PdfFormatOption(pipeline_options=pipeline_options)
            }
        )
        doc_result = converter.convert(pdf_path)
        doc = doc_result.document

        cache_path = cache_dir_for(zotero_key, pdf_hash)
        cache_path.mkdir(parents=True, exist_ok=True)

        parts, figures = _process_items(
            doc.iterate_items(),
            doc,
            cache_path,
            table_style=table_style,
            equation_mode=equation_mode,
        )

        markdown = "\n\n".join(parts)

        write_cache(
            zotero_key=zotero_key,
            pdf_hash=pdf_hash,
            markdown=markdown,
            figures=figures,
            backend="docling",
            table_style=table_style,
            equation_style=equation_style,
        )

        return ConversionResult(markdown=markdown, figures=figures)
```

- [ ] **Step 3: Verify existing tests still pass**

Run: `uv run pytest tests/test_converter_docling.py -v`

Expected: all existing tests pass (the refactor is purely structural — `_process_items` is called the same way the inline code was).

- [ ] **Step 4: Commit**

```bash
git add src/riszotto/converter/docling.py
git commit -m "refactor: extract _process_items() from DoclingConverter.convert()"
```

---

### Task 2: Add `.gitignore` entry for test cache

**Files:**
- Modify: `.gitignore`

- [ ] **Step 1: Add test cache directory to `.gitignore`**

Append to `.gitignore`:

```
# Test fixtures cache
tests/.cache/
```

- [ ] **Step 2: Commit**

```bash
git add .gitignore
git commit -m "chore: gitignore tests/.cache/"
```

---

### Task 3: Write integration test fixtures and smoke test

**Files:**
- Create: `tests/test_converter_docling_integration.py`

- [ ] **Step 1: Write the test file with fixtures and smoke test**

Create `tests/test_converter_docling_integration.py`:

```python
"""Integration tests for DoclingConverter using a real arxiv PDF."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch
from urllib.request import urlretrieve

import pytest

docling = pytest.importorskip("docling")

from riszotto.converter.docling import DoclingConverter

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
```

- [ ] **Step 2: Run test to verify it passes**

Run: `uv run pytest tests/test_converter_docling_integration.py::test_produces_nonempty_markdown -v`

Expected: PASS (downloads PDF on first run, converts, markdown is non-empty).

- [ ] **Step 3: Commit**

```bash
git add tests/test_converter_docling_integration.py
git commit -m "test: add integration smoke test with real arxiv PDF"
```

---

### Task 4: Add remaining integration tests

**Files:**
- Modify: `tests/test_converter_docling_integration.py`

- [ ] **Step 1: Add text extraction test**

Append to `tests/test_converter_docling_integration.py`:

```python
def test_extracts_text(conversion_result):
    md = conversion_result.markdown
    # Paper 2310.06825 is "Docling Technical Report" — check for distinctive words
    assert "docling" in md.lower() or "document" in md.lower()
```

- [ ] **Step 2: Add figure extraction test**

Append:

```python
def test_extracts_figures(conversion_result):
    assert len(conversion_result.figures) > 0
    for name, path in conversion_result.figures.items():
        assert path.exists(), f"Figure file missing: {path}"
        assert path.stat().st_size > 0, f"Figure file empty: {path}"
```

- [ ] **Step 3: Add cache round-trip test**

Append:

```python
def test_cache_roundtrip(arxiv_pdf, tmp_path):
    with patch("riszotto.converter.cache.CONVERSION_CACHE_DIR", tmp_path):
        converter = DoclingConverter()
        first = converter.convert(arxiv_pdf, zotero_key="CACHE_TEST")
        second = converter.convert(arxiv_pdf, zotero_key="CACHE_TEST")
    assert second.markdown == first.markdown
```

- [ ] **Step 4: Add table style test**

Append:

```python
def test_different_table_styles(arxiv_pdf, tmp_path):
    with patch("riszotto.converter.cache.CONVERSION_CACHE_DIR", tmp_path):
        converter = DoclingConverter()
        inline_result = converter.convert(
            arxiv_pdf, zotero_key="TABLE_INLINE", table_style="inline",
        )
        image_result = converter.convert(
            arxiv_pdf, zotero_key="TABLE_IMAGE", table_style="image",
        )
    assert len(inline_result.markdown) > 100
    assert len(image_result.markdown) > 100
```

- [ ] **Step 5: Run all integration tests**

Run: `uv run pytest tests/test_converter_docling_integration.py -v`

Expected: all 5 tests PASS.

- [ ] **Step 6: Commit**

```bash
git add tests/test_converter_docling_integration.py
git commit -m "test: add integration tests for text, figures, cache, table styles"
```

---

### Task 5: Write edge-case tests using `_process_items()`

**Files:**
- Create: `tests/test_converter_docling_edge_cases.py`

- [ ] **Step 1: Write edge-case test file with all four tests**

Create `tests/test_converter_docling_edge_cases.py`:

```python
"""Edge-case tests for _process_items() with surgical mocks."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

docling = pytest.importorskip("docling")

from docling_core.types.doc import FormulaItem, PictureItem, TableItem

from riszotto.converter.docling import _process_items


class TestProcessItemsEdgeCases:
    def test_picture_get_image_none(self, tmp_path):
        item = MagicMock(spec=PictureItem)
        item.get_image.return_value = None

        parts, figures = _process_items(
            [(item, 0)],
            doc=MagicMock(),
            cache_path=tmp_path,
            table_style="inline",
            equation_mode="image",
        )

        assert len(parts) == 1
        assert "image not available" in parts[0]
        assert len(figures) == 0

    def test_table_image_fallback_to_inline(self, tmp_path):
        mock_df = MagicMock()
        mock_df.to_markdown.return_value = "| A |\n|---|\n| 1 |"

        item = MagicMock(spec=TableItem)
        item.get_image.return_value = None
        item.export_to_dataframe.return_value = mock_df

        parts, figures = _process_items(
            [(item, 0)],
            doc=MagicMock(),
            cache_path=tmp_path,
            table_style="image",
            equation_mode="image",
        )

        assert len(parts) == 1
        assert "| A |" in parts[0]
        assert len(figures) == 0

    def test_formula_image_fallback_to_latex(self, tmp_path):
        item = MagicMock(spec=FormulaItem)
        item.get_image.return_value = None
        item.text = "E = mc^2"

        parts, figures = _process_items(
            [(item, 0)],
            doc=MagicMock(),
            cache_path=tmp_path,
            table_style="inline",
            equation_mode="image",
        )

        assert len(parts) == 1
        assert "$$E = mc^2$$" in parts[0]
        assert len(figures) == 0

    def test_formula_no_image_no_text(self, tmp_path):
        item = MagicMock(spec=FormulaItem)
        item.get_image.return_value = None
        item.text = ""

        parts, figures = _process_items(
            [(item, 0)],
            doc=MagicMock(),
            cache_path=tmp_path,
            table_style="inline",
            equation_mode="image",
        )

        assert len(parts) == 1
        assert "not available" in parts[0]
        assert len(figures) == 0
```

- [ ] **Step 2: Run edge-case tests**

Run: `uv run pytest tests/test_converter_docling_edge_cases.py -v`

Expected: all 4 tests PASS.

- [ ] **Step 3: Commit**

```bash
git add tests/test_converter_docling_edge_cases.py
git commit -m "test: add edge-case tests for _process_items() with surgical mocks"
```

---

### Task 6: Delete old mock tests and clean up `test_converter_docling.py`

**Files:**
- Modify: `tests/test_converter_docling.py`

- [ ] **Step 1: Replace the entire file**

Rewrite `tests/test_converter_docling.py` to keep only the two non-docling-dependent tests:

```python
# tests/test_converter_docling.py
"""Tests for docling converter availability and init behavior.

These tests do NOT require docling to be installed — they verify
the graceful-degradation path (DOCLING_AVAILABLE flag, ImportError).

Integration tests live in test_converter_docling_integration.py.
Edge-case tests live in test_converter_docling_edge_cases.py.
"""

import sys
from unittest.mock import patch

import pytest


class TestDoclingAvailableFlag:
    def test_import_error_sets_flag_false(self):
        with patch.dict(
            sys.modules, {"docling": None, "docling.document_converter": None}
        ):
            from riszotto.converter.docling import DOCLING_AVAILABLE

            assert isinstance(DOCLING_AVAILABLE, bool)


class TestDoclingConverterInit:
    def test_raises_if_docling_not_available(self):
        from riszotto.converter import docling as docling_module

        original = docling_module.DOCLING_AVAILABLE
        try:
            docling_module.DOCLING_AVAILABLE = False
            with pytest.raises(ImportError, match="riszotto\\[full\\]"):
                docling_module.DoclingConverter()
        finally:
            docling_module.DOCLING_AVAILABLE = original
```

- [ ] **Step 2: Run the trimmed file**

Run: `uv run pytest tests/test_converter_docling.py -v`

Expected: 2 tests PASS.

- [ ] **Step 3: Run full suite to confirm nothing broke**

Run: `uv run pytest -v`

Expected: all tests PASS across all test files.

- [ ] **Step 4: Commit**

```bash
git add tests/test_converter_docling.py
git commit -m "test: remove mock-heavy docling tests, keep availability checks"
```

---

### Task 7: Simplify CI matrix

**Files:**
- Modify: `.github/workflows/pytest.yaml`

- [ ] **Step 1: Update the workflow**

Replace the entire contents of `.github/workflows/pytest.yaml` with:

```yaml
name: Tests

on:
  push:
    branches: [main]
  pull_request:

jobs:
  test:
    runs-on: ubuntu-latest
    strategy:
      matrix:
        python-version: ["3.11", "3.12", "3.13"]
    steps:
      - uses: actions/checkout@v4

      - uses: astral-sh/setup-uv@v5
        with:
          python-version: ${{ matrix.python-version }}

      - name: Install with [full] extras
        run: uv sync --extra full

      - name: Run tests
        run: uv run pytest
```

- [ ] **Step 2: Commit**

```bash
git add .github/workflows/pytest.yaml
git commit -m "ci: simplify matrix to full-only, drop redundant semantic runs"
```

---

### Task 8: Final verification

- [ ] **Step 1: Run full test suite one last time**

Run: `uv run pytest -v`

Expected: all tests pass — old mock tests gone, new integration + edge-case tests green.

- [ ] **Step 2: Verify no leftover imports or dead code**

Run: `grep -rn "_Stub" tests/` — should return nothing.

Run: `grep -rn "create=True" tests/` — should return nothing.
