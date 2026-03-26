# Docling Performance Optimization and Image-Mode Bugfix

## Problem

1. **Bug**: `--table-style image` / `--equation-style image` crash with `'NoneType' object has no attribute 'save'` because `get_image()` returns `None` when page images aren't rendered.
2. **Speed**: Default conversion takes ~4 minutes per paper. Formula enrichment alone costs ~30s/page (loads CodeFormulaV2 VLM). OCR runs by default but is unnecessary for text-based PDFs.

## Root Cause Analysis

### Image-mode bug

`TableItem.get_image(doc)` and `FormulaItem.get_image(doc)` work by:
1. Checking `self.image` — populated only if `generate_table_images = True`
2. Falling back to `DocItem.get_image(doc)` which crops from `page.image`
3. `page.image` is `None` because `generate_page_images = False` (the default)

`PictureItem` works because `generate_picture_images = True` populates `self.image` directly from the embedded bitmap — no page rendering needed.

**Fix**: Set `generate_page_images = True` when image-mode is requested. Add null guards as safety net with graceful fallback.

### Performance

Benchmarked on the BMIM-BF4 paper (17 pages):

| Configuration | Time |
|---|---|
| Current defaults (OCR on, formula enrichment, ACCURATE tables) | ~240s |
| Optimized (no OCR, no formula enrichment, FAST tables, threaded, AUTO accelerator) | ~6s |
| Formula enrichment alone (1 page) | ~200s |

Pipeline cost ranking (most to least expensive):
1. Formula enrichment (CodeFormulaV2 VLM) — dominates by far
2. OCR — roughly doubles total time
3. Table structure (ACCURATE mode)
4. PDF parsing — cheapest

## Design

### Always-on optimizations (no CLI flags)

These are strictly better with no user-facing trade-offs:

- **`ThreadedPdfPipelineOptions`** instead of `PdfPipelineOptions` — multi-threaded page processing pipeline
- **`AcceleratorDevice.AUTO`** — uses MPS on Mac, CUDA on NVIDIA
- **`num_threads=os.cpu_count()`** — use all available cores (docling defaults to 4)

### New CLI flags on `show`

#### `--ocr` (bool flag, default: off)

Most academic PDFs from the last ~15 years have embedded text. OCR is the second most expensive pipeline stage and unnecessary for these documents.

- Default: OCR disabled
- `--ocr`: enables OCR for scanned PDFs

**Empty-output detection**: When OCR is off and extracted text is < 100 characters for a multi-page PDF, print to stderr:
```
Very little text extracted. If this is a scanned PDF, try: riszotto show --ocr KEY
```

#### `--table-mode fast|accurate` (default: `fast`)

Controls `TableFormerMode`. `FAST` is adequate for most academic paper tables. `ACCURATE` available when precision matters.

#### `--equations image|latex` (default: `image`)

Without formula enrichment, docling still detects `FormulaItem` elements via layout analysis — but `element.text` is `None`. With enrichment, the CodeFormulaV2 VLM model produces LaTeX strings at ~30s/page cost.

| Value | Behavior | `do_formula_enrichment` | Speed |
|---|---|---|---|
| `image` | Formulas rendered as cropped PNGs from page (requires `generate_page_images`) | `False` | Fast |
| `latex` | Formulas rendered as `$$...$$` LaTeX via VLM | `True` | ~30s/page |

When `--equations image` and `get_image()` returns `None` (safety fallback), skip the formula with `[Equation N: image not available]`.

When `--equations latex` and `element.text` is `None` (VLM failed), fall back to image if page images are available, otherwise skip.

### Pipeline option mapping

| CLI state | Pipeline option | Value |
|---|---|---|
| always | `ThreadedPdfPipelineOptions` | (use instead of `PdfPipelineOptions`) |
| always | `accelerator_options` | `AcceleratorDevice.AUTO`, `num_threads=os.cpu_count()` |
| always | `generate_picture_images` | `True` |
| `--ocr` absent | `do_ocr` | `False` |
| `--ocr` present | `do_ocr` | `True` |
| `--table-mode fast` | `table_structure_options.mode` | `TableFormerMode.FAST` |
| `--table-mode accurate` | `table_structure_options.mode` | `TableFormerMode.ACCURATE` |
| `--equations image` | `do_formula_enrichment` | `False` |
| `--equations image` | `generate_page_images` | `True` |
| `--equations latex` | `do_formula_enrichment` | `True` |
| `--table-style image` | `generate_page_images` | `True` |
| `--table-style image` | `images_scale` | `2.0` |
| otherwise | `images_scale` | `1.0` |

### Null guards in element processing

All `get_image()` calls get null checks with graceful fallbacks:

- **`PictureItem`**: `None` → `[Figure N: image not available]`
- **`TableItem` (image mode)**: `None` → fall back to inline markdown table
- **`FormulaItem` (image mode)**: `None` → fall back to LaTeX if available, else skip text
- **`FormulaItem` (latex mode)**: `text is None` → fall back to image if available, else skip

### Files changed

| File | Change |
|---|---|
| `src/riszotto/converter/docling.py` | Pipeline options, null guards, new parameters |
| `src/riszotto/converter/base.py` | Add `EquationMode` type alias |
| `src/riszotto/cli.py` | Add `--ocr`, `--table-mode`, `--equations` flags; empty-output detection |
| `tests/test_converter_docling.py` | Update mocks, add null-guard tests |
| `tests/test_cli.py` | Add tests for new flags |

### What this does NOT include

- Progress bar (no docling callback API exists)
- DoclingParseV2 backend (beta, has memory leak issues)
- Per-page streaming output
