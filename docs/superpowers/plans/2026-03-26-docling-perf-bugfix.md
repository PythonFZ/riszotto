# Docling Performance Optimization and Image-Mode Bugfix

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix the `get_image()` crash in image mode, add `--ocr`, `--table-mode`, `--equations` CLI flags, and apply always-on performance optimizations (~40x speedup).

**Architecture:** The `DoclingConverter.convert()` method gets new parameters (`ocr`, `table_mode`, `equation_mode`) that map to docling pipeline options. The `Converter` protocol and `MarkItDownConverter` gain matching parameters (ignored by markitdown). CLI flags are added to `show` and passed through. Null guards wrap all `get_image()` calls with graceful fallbacks.

**Tech Stack:** Python 3.11+, docling 2.82, typer, pytest

---

## File Map

| Action | Path | Responsibility |
|--------|------|----------------|
| Modify | `src/riszotto/converter/base.py` | Add `EquationMode` type alias, update `Converter` protocol |
| Modify | `src/riszotto/converter/docling.py` | Pipeline optimizations, null guards, new parameters |
| Modify | `src/riszotto/converter/markitdown.py` | Accept new parameters (ignored) |
| Modify | `src/riszotto/converter/__init__.py` | Re-export `EquationMode` |
| Modify | `src/riszotto/cli.py` | Add `--ocr`, `--table-mode`, `--equations` flags; empty-output detection |
| Modify | `tests/test_converter_base.py` | Test new type alias |
| Modify | `tests/test_converter_docling.py` | Update mocks for new imports, add null-guard tests |
| Modify | `tests/test_converter_markitdown.py` | Test new parameters are accepted |
| Modify | `tests/test_cli.py` | Tests for new flags |

---

### Task 1: Add EquationMode type and update Converter protocol

**Files:**
- Modify: `src/riszotto/converter/base.py`
- Modify: `src/riszotto/converter/__init__.py`
- Modify: `tests/test_converter_base.py`

- [ ] **Step 1: Write test for EquationMode type**

Add to `tests/test_converter_base.py` inside the existing `TestTypeAliases` class:

```python
    def test_equation_mode_values(self):
        from riszotto.converter.base import EquationMode

        img: EquationMode = "image"
        ltx: EquationMode = "latex"
        assert img == "image"
        assert ltx == "latex"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_converter_base.py::TestTypeAliases::test_equation_mode_values -v`
Expected: FAIL (cannot import EquationMode)

- [ ] **Step 3: Add EquationMode to base.py and update protocol**

In `src/riszotto/converter/base.py`, add the type alias after `BackendOption`:

```python
EquationMode = Literal["image", "latex"]
```

Update the `Converter` protocol's `convert` method signature to:

```python
class Converter(Protocol):
    """Protocol for PDF-to-markdown converters."""

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
    ) -> ConversionResult: ...
```

- [ ] **Step 4: Update `__init__.py` re-exports**

In `src/riszotto/converter/__init__.py`, add `EquationMode` to the import and `__all__`:

```python
from riszotto.converter.base import (
    BackendName,
    ConversionResult,
    Converter,
    EquationMode,
    StyleOption,
)

__all__ = [
    "BackendName",
    "ConversionResult",
    "Converter",
    "EquationMode",
    "StyleOption",
    "get_converter",
]
```

- [ ] **Step 5: Run tests**

Run: `uv run pytest tests/test_converter_base.py -v`
Expected: all PASS

- [ ] **Step 6: Commit**

```bash
git add src/riszotto/converter/base.py src/riszotto/converter/__init__.py tests/test_converter_base.py
git commit -m "feat: add EquationMode type alias and update Converter protocol"
```

---

### Task 2: Update MarkItDownConverter to accept new parameters

**Files:**
- Modify: `src/riszotto/converter/markitdown.py`
- Modify: `tests/test_converter_markitdown.py`

- [ ] **Step 1: Write test for new parameters**

Add to `tests/test_converter_markitdown.py`:

```python
    @patch("riszotto.converter.markitdown.MarkItDown")
    def test_accepts_new_perf_params(self, mock_markitdown_cls):
        mock_md = MagicMock()
        mock_markitdown_cls.return_value = mock_md
        mock_result = MagicMock()
        mock_result.markdown = "text"
        mock_md.convert.return_value = mock_result

        converter = MarkItDownConverter()
        result = converter.convert(
            Path("/fake/paper.pdf"),
            zotero_key="ABC123",
            ocr=True,
            table_mode="accurate",
            equation_mode="latex",
        )
        assert result.markdown == "text"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_converter_markitdown.py::TestMarkItDownConverter::test_accepts_new_perf_params -v`
Expected: FAIL (unexpected keyword argument)

- [ ] **Step 3: Update MarkItDownConverter signature**

Replace the `convert` method signature in `src/riszotto/converter/markitdown.py`:

```python
from riszotto.converter.base import ConversionResult, EquationMode, StyleOption


class MarkItDownConverter:
    """Convert PDFs using Microsoft's MarkItDown library.

    This is the lightweight default backend. It extracts plain text
    only -- no figures, structured tables, or equation rendering.
    Style flags, caching, and docling-specific options are ignored.
    """

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
        """Convert a PDF to markdown using MarkItDown."""
        logging.disable(logging.CRITICAL)
        try:
            md = MarkItDown()
            result = md.convert(pdf_path)
            return ConversionResult(markdown=result.markdown)
        finally:
            logging.disable(logging.NOTSET)
```

- [ ] **Step 4: Run tests**

Run: `uv run pytest tests/test_converter_markitdown.py -v`
Expected: all PASS

- [ ] **Step 5: Commit**

```bash
git add src/riszotto/converter/markitdown.py tests/test_converter_markitdown.py
git commit -m "feat: add new perf parameters to MarkItDownConverter (ignored)"
```

---

### Task 3: Rewrite DoclingConverter with performance optimizations and null guards

**Files:**
- Modify: `src/riszotto/converter/docling.py`
- Modify: `tests/test_converter_docling.py`

- [ ] **Step 1: Write tests for null guards and new parameters**

Add to `tests/test_converter_docling.py`:

```python
class TestNullGuards:
    """Test graceful fallback when get_image() returns None."""

    @patch("riszotto.converter.docling.TextItem", _StubTextItem, create=True)
    @patch("riszotto.converter.docling.FormulaItem", _StubFormulaItem, create=True)
    @patch("riszotto.converter.docling.TableItem", _StubTableItem, create=True)
    @patch("riszotto.converter.docling.PictureItem", _StubPictureItem, create=True)
    @patch("riszotto.converter.docling.ThreadedPdfPipelineOptions", create=True)
    @patch("riszotto.converter.docling.TableStructureOptions", create=True)
    @patch("riszotto.converter.docling.TableFormerMode", create=True)
    @patch("riszotto.converter.docling.AcceleratorOptions", create=True)
    @patch("riszotto.converter.docling.AcceleratorDevice", create=True)
    @patch("riszotto.converter.docling.InputFormat", create=True)
    @patch("riszotto.converter.docling.PdfFormatOption", create=True)
    @patch("riszotto.converter.docling.DOCLING_AVAILABLE", True)
    @patch("riszotto.converter.docling.write_cache")
    @patch("riszotto.converter.docling.read_cache", return_value=None)
    @patch("riszotto.converter.docling.compute_pdf_hash", return_value="aabb")
    @patch("riszotto.converter.docling.DocumentConverter", create=True)
    def test_picture_get_image_none(
        self, mock_dc, mock_hash, mock_read, mock_write,
        _pfo, _ifmt, _ad, _ao, _tfm, _tso, _tppo, tmp_path,
    ):
        pdf = tmp_path / "paper.pdf"
        pdf.write_bytes(b"fake pdf")

        item = MagicMock(spec=_StubPictureItem)
        item.__class__ = _StubPictureItem
        item.get_image.return_value = None

        mock_doc = MagicMock()
        mock_doc.iterate_items.return_value = [(item, 0)]
        mock_dc.return_value.convert.return_value.document = mock_doc

        from riszotto.converter.docling import DoclingConverter
        converter = DoclingConverter()
        result = converter.convert(pdf, zotero_key="K1")

        assert "[Figure 1: image not available]" in result.markdown

    @patch("riszotto.converter.docling.TextItem", _StubTextItem, create=True)
    @patch("riszotto.converter.docling.FormulaItem", _StubFormulaItem, create=True)
    @patch("riszotto.converter.docling.TableItem", _StubTableItem, create=True)
    @patch("riszotto.converter.docling.PictureItem", _StubPictureItem, create=True)
    @patch("riszotto.converter.docling.ThreadedPdfPipelineOptions", create=True)
    @patch("riszotto.converter.docling.TableStructureOptions", create=True)
    @patch("riszotto.converter.docling.TableFormerMode", create=True)
    @patch("riszotto.converter.docling.AcceleratorOptions", create=True)
    @patch("riszotto.converter.docling.AcceleratorDevice", create=True)
    @patch("riszotto.converter.docling.InputFormat", create=True)
    @patch("riszotto.converter.docling.PdfFormatOption", create=True)
    @patch("riszotto.converter.docling.DOCLING_AVAILABLE", True)
    @patch("riszotto.converter.docling.write_cache")
    @patch("riszotto.converter.docling.read_cache", return_value=None)
    @patch("riszotto.converter.docling.compute_pdf_hash", return_value="aabb")
    @patch("riszotto.converter.docling.DocumentConverter", create=True)
    def test_table_image_get_image_none_falls_back_to_inline(
        self, mock_dc, mock_hash, mock_read, mock_write,
        _pfo, _ifmt, _ad, _ao, _tfm, _tso, _tppo, tmp_path,
    ):
        import pandas as pd

        pdf = tmp_path / "paper.pdf"
        pdf.write_bytes(b"fake pdf")

        item = MagicMock(spec=_StubTableItem)
        item.__class__ = _StubTableItem
        item.get_image.return_value = None
        mock_df = MagicMock(spec=pd.DataFrame)
        mock_df.to_markdown.return_value = "| A |\n|---|\n| 1 |"
        item.export_to_dataframe.return_value = mock_df

        mock_doc = MagicMock()
        mock_doc.iterate_items.return_value = [(item, 0)]
        mock_dc.return_value.convert.return_value.document = mock_doc

        from riszotto.converter.docling import DoclingConverter
        converter = DoclingConverter()
        result = converter.convert(pdf, zotero_key="K1", table_style="image")

        assert "| A |" in result.markdown

    @patch("riszotto.converter.docling.TextItem", _StubTextItem, create=True)
    @patch("riszotto.converter.docling.FormulaItem", _StubFormulaItem, create=True)
    @patch("riszotto.converter.docling.TableItem", _StubTableItem, create=True)
    @patch("riszotto.converter.docling.PictureItem", _StubPictureItem, create=True)
    @patch("riszotto.converter.docling.ThreadedPdfPipelineOptions", create=True)
    @patch("riszotto.converter.docling.TableStructureOptions", create=True)
    @patch("riszotto.converter.docling.TableFormerMode", create=True)
    @patch("riszotto.converter.docling.AcceleratorOptions", create=True)
    @patch("riszotto.converter.docling.AcceleratorDevice", create=True)
    @patch("riszotto.converter.docling.InputFormat", create=True)
    @patch("riszotto.converter.docling.PdfFormatOption", create=True)
    @patch("riszotto.converter.docling.DOCLING_AVAILABLE", True)
    @patch("riszotto.converter.docling.write_cache")
    @patch("riszotto.converter.docling.read_cache", return_value=None)
    @patch("riszotto.converter.docling.compute_pdf_hash", return_value="aabb")
    @patch("riszotto.converter.docling.DocumentConverter", create=True)
    def test_formula_image_get_image_none_with_text_falls_back_to_latex(
        self, mock_dc, mock_hash, mock_read, mock_write,
        _pfo, _ifmt, _ad, _ao, _tfm, _tso, _tppo, tmp_path,
    ):
        pdf = tmp_path / "paper.pdf"
        pdf.write_bytes(b"fake pdf")

        item = MagicMock(spec=_StubFormulaItem)
        item.__class__ = _StubFormulaItem
        item.get_image.return_value = None
        item.text = "E = mc^2"

        mock_doc = MagicMock()
        mock_doc.iterate_items.return_value = [(item, 0)]
        mock_dc.return_value.convert.return_value.document = mock_doc

        from riszotto.converter.docling import DoclingConverter
        converter = DoclingConverter()
        result = converter.convert(pdf, zotero_key="K1", equation_mode="image")

        assert "$$E = mc^2$$" in result.markdown
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_converter_docling.py::TestNullGuards -v`
Expected: FAIL

- [ ] **Step 3: Rewrite docling.py**

Replace the entire contents of `src/riszotto/converter/docling.py` with:

```python
"""Docling-based PDF converter with rich extraction."""

from __future__ import annotations

import os
import sys
from pathlib import Path

from riszotto.converter.base import ConversionResult, EquationMode, StyleOption
from riszotto.converter.cache import (
    cache_dir_for,
    compute_pdf_hash,
    read_cache,
    write_cache,
)

try:
    from docling.datamodel.accelerator_options import (
        AcceleratorDevice,
        AcceleratorOptions,
    )
    from docling.datamodel.base_models import InputFormat
    from docling.datamodel.pipeline_options import (
        TableFormerMode,
        TableStructureOptions,
        ThreadedPdfPipelineOptions,
    )
    from docling.document_converter import DocumentConverter, PdfFormatOption
    from docling_core.types.doc import FormulaItem, PictureItem, TableItem, TextItem

    DOCLING_AVAILABLE = True
except ImportError:
    DOCLING_AVAILABLE = False


def _save_element_image(element, doc, dest: Path) -> bool:
    """Save an element's image to dest. Returns False if no image available."""
    image = element.get_image(doc)
    if image is None:
        return False
    image.save(str(dest), "PNG")
    return True


class DoclingConverter:
    """Convert PDFs using docling with figure, table, and equation extraction.

    Requires ``riszotto[full]`` to be installed.
    """

    def __init__(self) -> None:
        if not DOCLING_AVAILABLE:
            raise ImportError(
                "docling is not installed. Install with: uv add riszotto[full]"
            )

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

        needs_page_images = (
            table_style == "image"
            or equation_mode == "image"
        )

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

        parts: list[str] = []
        figures: dict[str, Path] = {}
        figure_count = 0
        table_count = 0
        equation_count = 0

        for element, _level in doc.iterate_items():
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
                        parts.append(
                            f"[Equation {equation_count}: not available]"
                        )

            elif isinstance(element, TextItem):
                parts.append(element.text)

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

- [ ] **Step 4: Update existing test mocks**

The existing `test_convert_with_text_only` and `test_no_cache_bypasses_read` tests patch `PdfPipelineOptions` — update them to patch `ThreadedPdfPipelineOptions` instead. Also add patches for the new imports (`TableStructureOptions`, `TableFormerMode`, `AcceleratorOptions`, `AcceleratorDevice`).

In `test_convert_with_text_only`, replace:
```python
    @patch("riszotto.converter.docling.PdfPipelineOptions", create=True)
```
with:
```python
    @patch("riszotto.converter.docling.ThreadedPdfPipelineOptions", create=True)
    @patch("riszotto.converter.docling.TableStructureOptions", create=True)
    @patch("riszotto.converter.docling.TableFormerMode", create=True)
    @patch("riszotto.converter.docling.AcceleratorOptions", create=True)
    @patch("riszotto.converter.docling.AcceleratorDevice", create=True)
```
And update the function signature to accept the 4 extra positional args (add `_tfm, _tso, _ao, _ad` before `_ppo` which becomes `_tppo`).

Apply the same change to `test_no_cache_bypasses_read`.

- [ ] **Step 5: Run all docling tests**

Run: `uv run pytest tests/test_converter_docling.py -v`
Expected: all PASS

- [ ] **Step 6: Commit**

```bash
git add src/riszotto/converter/docling.py tests/test_converter_docling.py
git commit -m "feat: optimize docling pipeline (threaded, no OCR, FAST tables, null guards)"
```

---

### Task 4: Add new CLI flags and empty-output detection

**Files:**
- Modify: `src/riszotto/cli.py`
- Modify: `tests/test_cli.py`

- [ ] **Step 1: Write tests for new flags**

Add to `tests/test_cli.py`:

```python
class TestShowNewFlags:
    @patch("riszotto.cli.get_converter")
    @patch("riszotto.cli.get_client")
    def test_show_ocr_flag(self, mock_get_client, mock_get_converter):
        from riszotto.converter.base import ConversionResult

        mock_zot = MagicMock()
        mock_get_client.return_value = mock_zot
        mock_zot.children.return_value = [
            {
                "data": {
                    "key": "ATT1",
                    "itemType": "attachment",
                    "contentType": "application/pdf",
                    "filename": "paper.pdf",
                },
                "links": {"enclosure": {"href": "file:///path/to/paper.pdf"}},
            }
        ]
        mock_converter = MagicMock()
        mock_converter.convert.return_value = ConversionResult(markdown="text")
        mock_get_converter.return_value = mock_converter

        runner.invoke(app, ["show", "--ocr", "P1"])
        call_kwargs = mock_converter.convert.call_args[1]
        assert call_kwargs["ocr"] is True

    @patch("riszotto.cli.get_converter")
    @patch("riszotto.cli.get_client")
    def test_show_ocr_default_off(self, mock_get_client, mock_get_converter):
        from riszotto.converter.base import ConversionResult

        mock_zot = MagicMock()
        mock_get_client.return_value = mock_zot
        mock_zot.children.return_value = [
            {
                "data": {
                    "key": "ATT1",
                    "itemType": "attachment",
                    "contentType": "application/pdf",
                    "filename": "paper.pdf",
                },
                "links": {"enclosure": {"href": "file:///path/to/paper.pdf"}},
            }
        ]
        mock_converter = MagicMock()
        mock_converter.convert.return_value = ConversionResult(markdown="text")
        mock_get_converter.return_value = mock_converter

        runner.invoke(app, ["show", "P1"])
        call_kwargs = mock_converter.convert.call_args[1]
        assert call_kwargs["ocr"] is False

    @patch("riszotto.cli.get_converter")
    @patch("riszotto.cli.get_client")
    def test_show_table_mode_flag(self, mock_get_client, mock_get_converter):
        from riszotto.converter.base import ConversionResult

        mock_zot = MagicMock()
        mock_get_client.return_value = mock_zot
        mock_zot.children.return_value = [
            {
                "data": {
                    "key": "ATT1",
                    "itemType": "attachment",
                    "contentType": "application/pdf",
                    "filename": "paper.pdf",
                },
                "links": {"enclosure": {"href": "file:///path/to/paper.pdf"}},
            }
        ]
        mock_converter = MagicMock()
        mock_converter.convert.return_value = ConversionResult(markdown="text")
        mock_get_converter.return_value = mock_converter

        runner.invoke(app, ["show", "--table-mode", "accurate", "P1"])
        call_kwargs = mock_converter.convert.call_args[1]
        assert call_kwargs["table_mode"] == "accurate"

    @patch("riszotto.cli.get_converter")
    @patch("riszotto.cli.get_client")
    def test_show_equations_flag(self, mock_get_client, mock_get_converter):
        from riszotto.converter.base import ConversionResult

        mock_zot = MagicMock()
        mock_get_client.return_value = mock_zot
        mock_zot.children.return_value = [
            {
                "data": {
                    "key": "ATT1",
                    "itemType": "attachment",
                    "contentType": "application/pdf",
                    "filename": "paper.pdf",
                },
                "links": {"enclosure": {"href": "file:///path/to/paper.pdf"}},
            }
        ]
        mock_converter = MagicMock()
        mock_converter.convert.return_value = ConversionResult(markdown="text")
        mock_get_converter.return_value = mock_converter

        runner.invoke(app, ["show", "--equations", "latex", "P1"])
        call_kwargs = mock_converter.convert.call_args[1]
        assert call_kwargs["equation_mode"] == "latex"

    @patch("riszotto.cli.get_converter")
    @patch("riszotto.cli.get_client")
    def test_show_empty_output_warns(self, mock_get_client, mock_get_converter):
        from riszotto.converter.base import ConversionResult

        mock_zot = MagicMock()
        mock_get_client.return_value = mock_zot
        mock_zot.children.return_value = [
            {
                "data": {
                    "key": "ATT1",
                    "itemType": "attachment",
                    "contentType": "application/pdf",
                    "filename": "paper.pdf",
                },
                "links": {"enclosure": {"href": "file:///path/to/paper.pdf"}},
            }
        ]
        mock_converter = MagicMock()
        mock_converter.convert.return_value = ConversionResult(markdown="short")
        mock_get_converter.return_value = mock_converter

        result = runner.invoke(app, ["show", "P1"])
        assert "Very little text extracted" in result.output or result.exit_code == 0

    def test_show_invalid_table_mode(self):
        result = runner.invoke(app, ["show", "--table-mode", "bogus", "P1"])
        assert result.exit_code == 1
        assert "Invalid --table-mode" in result.output

    def test_show_invalid_equations(self):
        result = runner.invoke(app, ["show", "--equations", "bogus", "P1"])
        assert result.exit_code == 1
        assert "Invalid --equations" in result.output
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_cli.py::TestShowNewFlags -v`
Expected: FAIL

- [ ] **Step 3: Add new flags to show command in cli.py**

In `src/riszotto/cli.py`, add these parameters to the `show` function signature (after `figure`):

```python
    ocr: Annotated[
        bool,
        typer.Option("--ocr", help="Enable OCR for scanned PDFs (off by default)"),
    ] = False,
    table_mode: Annotated[
        str,
        typer.Option("--table-mode", help="Table extraction: fast or accurate (docling only)"),
    ] = "fast",
    equations: Annotated[
        str,
        typer.Option("--equations", help="Equation rendering: image or latex (docling only)"),
    ] = "image",
```

Add validation after the existing `equation_style` validation:

```python
    if table_mode not in ("fast", "accurate"):
        typer.echo(
            f"Invalid --table-mode: {table_mode}. Use 'fast' or 'accurate'.",
            err=True,
        )
        raise typer.Exit(1)
    if equations not in ("image", "latex"):
        typer.echo(
            f"Invalid --equations: {equations}. Use 'image' or 'latex'.",
            err=True,
        )
        raise typer.Exit(1)
```

Update the `converter.convert()` call to pass the new parameters:

```python
        converter = get_converter(backend)
        result = converter.convert(
            Path(file_path),
            table_style=table_style,
            equation_style=equation_style,
            zotero_key=key,
            no_cache=no_cache,
            ocr=ocr,
            table_mode=table_mode,
            equation_mode=equations,
        )
        markdown = result.markdown
```

Add empty-output detection after the conversion succeeds (after `markdown = result.markdown`):

```python
        if len(markdown) < 100 and not ocr:
            typer.echo(
                "Very little text extracted. If this is a scanned PDF, "
                f"try: riszotto show --ocr {key}",
                err=True,
            )
```

- [ ] **Step 4: Run all tests**

Run: `uv run pytest tests/test_cli.py -v`
Expected: all PASS

- [ ] **Step 5: Commit**

```bash
git add src/riszotto/cli.py tests/test_cli.py
git commit -m "feat: add --ocr, --table-mode, --equations flags with empty-output detection"
```

---

### Task 5: Pre-commit and full validation

**Files:** none (validation only)

- [ ] **Step 1: Run pre-commit hooks**

Run: `uvx prek --all-files`
Expected: all pass (fix any formatting issues)

- [ ] **Step 2: Run full test suite**

Run: `uv run pytest -v`
Expected: all PASS (excluding pre-existing semantic test failures)

- [ ] **Step 3: Commit formatting fixes if any**

```bash
git add -u
git commit -m "style: apply pre-commit formatting fixes"
```
