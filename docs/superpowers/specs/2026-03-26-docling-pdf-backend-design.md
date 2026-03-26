# Docling PDF Backend Design

**Date**: 2026-03-26
**Status**: Approved
**Goal**: Add docling as a richer backend alongside markitdown for better PDF extraction of scientific papers -- figures as image references, tables as markdown, equations as LaTeX -- while keeping the base install lightweight.

## Problem

riszotto currently uses markitdown for PDF-to-markdown conversion. markitdown produces OCR-level text only: no figures, no structured tables, no equation rendering. For scientific papers, this means losing critical information carried in figures, complex tables, and mathematical notation. markitdown remains the lightweight default; this design adds a richer alternative.

## Solution Overview

Add docling as an optional heavy backend (`riszotto[full]`), behind a converter abstraction layer. The base install stays lightweight with markitdown. When docling is available, it is auto-detected and used by default.

Key behaviors:
- Figures are always extracted as images and referenced in markdown as `![Figure N](path)`
- Tables default to inline markdown, optionally rendered as images
- Equations default to inline LaTeX, optionally rendered as images
- Conversion results are cached to avoid repeated slow processing
- Search-within-PDF (`--search`) works with both backends; results differ because docling produces richer markdown

## Architecture

### Module Structure

```
src/riszotto/converter/
  __init__.py       # get_converter() factory + auto-detection
  base.py           # ConversionResult dataclass + Converter Protocol
  markitdown.py     # wraps existing MarkItDown logic
  docling.py        # docling backend
  cache.py          # sha256-keyed file cache
```

### Converter Protocol

```python
# base.py
from dataclasses import dataclass, field
from pathlib import Path
from typing import Protocol

@dataclass
class ConversionResult:
    """Internal result object -- dataclass, not serialized to disk."""
    markdown: str                    # full markdown with image refs injected
    figures: dict[str, Path] = field(default_factory=dict)  # {"figure_1.png": Path(...)}

class Converter(Protocol):
    def convert(
        self,
        pdf_path: Path,
        *,
        table_style: str = "inline",
        equation_style: str = "inline",
        zotero_key: str | None = None,
        no_cache: bool = False,
    ) -> ConversionResult: ...
```

### Auto-Detection Factory

```python
# __init__.py
def get_converter(backend: str | None = None) -> Converter:
    if backend == "markitdown":
        return MarkItDownConverter()
    if backend == "docling":
        return DoclingConverter()  # raises ImportError if not installed
    # Auto: try docling first, fall back to markitdown
    try:
        return DoclingConverter()
    except ImportError:
        return MarkItDownConverter()
```

### MarkItDownConverter

Extracts the existing `MarkItDown().convert(path).markdown` logic from `cli.py`. Returns `ConversionResult(markdown=..., figures={})` -- no figures, same behavior as today. Ignores `table_style`, `equation_style`, `zotero_key`, and `no_cache` parameters.

### DoclingConverter

#### Conversion flow

1. **Check cache** -- hash PDF contents with sha256, look for cached result
2. **Cache hit** -- validate style flags match `meta.json`, read `content.md`, glob figures, return `ConversionResult`
3. **Cache miss** (or style mismatch, or `no_cache`) -- run docling pipeline:

```python
pipeline_options = PdfPipelineOptions()
pipeline_options.generate_picture_images = True
pipeline_options.images_scale = 2.0
pipeline_options.do_table_structure = True
pipeline_options.do_formula_enrichment = True

converter = DocumentConverter(
    format_options={InputFormat.PDF: PdfFormatOption(pipeline_options=pipeline_options)}
)
result = converter.convert(pdf_path)
```

4. **Post-process based on style flags**:
   - `table_style="inline"` -- tables stay as markdown pipe tables
   - `table_style="image"` -- iterate `TableItem`s, save via `element.get_image(doc)`, replace in markdown with `![Table N](cache_path/table_N.png)`
   - `equation_style="inline"` -- LaTeX stays as `$$...$$`
   - `equation_style="image"` -- save equation region images, replace with `![Equation N](cache_path/equation_N.png)`
   - **Figures always become images** -- `PictureItem`s saved to cache, referenced as `![Figure N](cache_path/figure_N.png)`
   - **Failed equation enrichment** -- if docling returns empty text for an equation, fall back to image regardless of `equation_style`

5. **Write cache** -- save `content.md` + all image files + `meta.json`
6. **Return** `ConversionResult`

#### Import guard

```python
try:
    from docling.document_converter import DocumentConverter, PdfFormatOption
    from docling.datamodel.pipeline_options import PdfPipelineOptions
    from docling.datamodel.base_models import InputFormat
    from docling_core.types.doc import PictureItem, TableItem
    from docling.datamodel.image_ref_mode import ImageRefMode
    DOCLING_AVAILABLE = True
except ImportError:
    DOCLING_AVAILABLE = False
```

`DoclingConverter.__init__()` raises `ImportError("Install riszotto[full] for docling support")` if `DOCLING_AVAILABLE` is False.

## Cache System

### Location

Uses `platformdirs.user_cache_dir("riszotto")` for platform-appropriate paths:
- macOS: `~/Library/Caches/riszotto`
- Linux: `~/.cache/riszotto`
- Windows: `C:\Users\<user>\AppData\Local\riszotto\Cache`

### Directory structure

```
<cache_dir>/
  <zotero_key>/
    <sha256[:12]>/
      content.md
      figure_1.png
      figure_2.png
      table_1.png         # only if table_style="image"
      equation_1.png      # only if equation_style="image"
      meta.json
```

### Cache key design

- **Outer key**: Zotero item key (human-navigable, easy to clear per-paper)
- **Inner key**: `sha256(pdf_bytes)[:12]` (auto-invalidates when PDF changes)
- Only one hash directory kept per Zotero key -- new hash detected removes old directory automatically

### Cache metadata (Pydantic)

```python
from pydantic import BaseModel
from datetime import datetime

class CacheMeta(BaseModel):
    created: datetime
    backend: str
    table_style: str
    equation_style: str
    pdf_hash: str
```

### Cache invalidation

Cache is invalidated when:
- PDF content changes (different sha256 hash)
- Style flags differ from cached `meta.json` (e.g., request `--table-style image` but cache has `inline`)
- User passes `--no-cache`

### `--no-cache` behavior

Bypasses cache read but still writes to cache after processing, so subsequent calls benefit.

## CLI Changes

### `show` command -- new flags

```
riszotto show KEY [existing flags...]
    --backend markitdown|docling    # override auto-detected backend
    --table-style inline|image      # default: inline (docling only)
    --equation-style inline|image   # default: inline (docling only)
    --no-cache                      # force re-processing
    --figure N                      # display path to cached figure N
```

- `--backend docling` when docling not installed: error with install instructions
- `--table-style` / `--equation-style` when backend is markitdown: error explaining these require docling
- `--figure N` reads from cache; errors if paper hasn't been processed with docling yet

### New `cache` command group

```
riszotto cache show                     # total size, paper count, cache path
riszotto cache show --key KEY           # size + file listing for one paper
riszotto cache clear                    # clear entire cache
riszotto cache clear --key KEY          # clear one paper
riszotto cache clear --older-than 30d   # age-based cleanup
```

### Integration in `show`

```python
converter = get_converter(backend=backend)
result = converter.convert(
    pdf_path,
    table_style=table_style,
    equation_style=equation_style,
    zotero_key=key,
    no_cache=no_cache,
)
# result.markdown flows into existing pagination/search logic unchanged
```

Existing pagination (`--page`, `--page-size`) and search (`--search`, `--context`) operate on `result.markdown` regardless of backend.

## Packaging

### `pyproject.toml`

```toml
[project]
dependencies = [
    "typer>=0.9.0",
    "pyzotero>=1.5.0",
    "markitdown[pdf]>=0.1.0",
    "pydantic>=2.0.0",
    "platformdirs>=4.0.0",
]

[project.optional-dependencies]
semantic = [
    "chromadb>=0.4.0",
    "sentence-transformers>=2.2.0",
    "tqdm>=4.0.0",
]
full = [
    "docling>=2.70.0",
    "riszotto[semantic]",
]
```

Install paths:
- `uv add riszotto` -- lightweight, markitdown only
- `uv add riszotto[semantic]` -- adds semantic search
- `uv add riszotto[full]` -- docling + semantic + everything

### Import isolation

- `converter/docling.py` uses import guard; `DOCLING_AVAILABLE` flag
- `converter/markitdown.py` always works (markitdown is a core dep)
- Cache module works regardless of backend (read/clear operations are filesystem only)

## What Doesn't Change

- Pagination (`--page`, `--page-size`)
- Search-within-PDF (`--search`, `--context`) -- works with both backends; results differ because docling produces richer markdown
- Export (`export` command)
- Collections, recent, libraries, index commands
- All existing flags on all commands
- Config file location and format (`~/.riszotto/config.toml`)
- ChromaDB location (`~/.riszotto/chroma_db/`)
