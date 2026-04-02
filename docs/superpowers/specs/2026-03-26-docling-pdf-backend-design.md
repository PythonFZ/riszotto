# Docling PDF Backend Design

**Date**: 2026-03-26
**Status**: Approved
**Goal**: Add docling as a richer backend alongside markitdown for better PDF extraction of scientific papers -- figures as image references, tables as markdown, equations as LaTeX -- while keeping the base install lightweight.

## Problem

riszotto currently uses markitdown for PDF-to-markdown conversion. markitdown extracts plain text only: no figures, no structured tables, no equation rendering. For scientific papers, this means losing critical information carried in figures, complex tables, and mathematical notation. markitdown remains the lightweight default; this design adds a richer alternative.

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
  base.py           # ConversionResult dataclass + Converter Protocol + shared types
  markitdown.py     # wraps existing MarkItDown logic
  docling.py        # docling backend
  cache.py          # sha256-keyed file cache
```

Additionally, a new `paths.py` module at `src/riszotto/paths.py` centralizes all platform-specific directory resolution (see Platform Directories section).

### Type Definitions

```python
# base.py
from typing import Annotated, Literal

StyleOption = Literal["inline", "image"]
BackendName = Literal["markitdown", "docling"]

# For CLI flags that only apply when docling is the active backend.
# None means "not specified" (use backend default / ignore).
BackendOption = Annotated[StyleOption | None, "Only available with docling backend"]
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
        table_style: StyleOption = "inline",
        equation_style: StyleOption = "inline",
        zotero_key: str,
        no_cache: bool = False,
    ) -> ConversionResult: ...
```

Note: `zotero_key` is required (not optional) since the cache directory depends on it and `show` always has a key. Standalone PDF conversion outside Zotero is not a supported use case.

### Auto-Detection Factory

```python
# __init__.py
def get_converter(backend: BackendName | None = None) -> Converter:
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

Extracts the existing `MarkItDown().convert(path).markdown` logic from `cli.py`. Returns `ConversionResult(markdown=..., figures={})` -- no figures, same behavior as today. Ignores `table_style`, `equation_style`, and `no_cache` parameters (cache is not used for markitdown since it's fast enough).

### DoclingConverter

#### Markdown generation strategy

The converter uses a **manual document tree walk** rather than `export_to_markdown()` + string replacement. This avoids fragile regex-based post-processing on markdown output.

1. Run the docling pipeline to get a `ConversionResult` with `result.document`
2. Iterate items via `result.document.iterate_items()` to walk the document tree in reading order
3. For each element, decide rendering based on type and style flags:
   - **`TextItem`** (paragraphs, headings, captions): render as markdown text
   - **`PictureItem`**: always save `element.get_image(result.document)` to cache, emit `![Figure N](cache_path/figure_N.png)`
   - **`TableItem`** with `table_style="inline"`: use `element.export_to_dataframe(doc=result.document).to_markdown()`
   - **`TableItem`** with `table_style="image"`: save `element.get_image(result.document)` to cache, emit `![Table N](cache_path/table_N.png)`
   - **`FormulaItem`** with `equation_style="inline"` and non-empty `.text`: emit as `$$...$$` LaTeX block
   - **`FormulaItem`** with `equation_style="image"` or empty `.text` (failed enrichment): save equation region image to cache, emit `![Equation N](cache_path/equation_N.png)`
4. Assemble the final markdown string from the rendered elements

This approach gives full control over how each element is rendered and avoids the fragility of string replacement.

#### Conversion flow

1. **Check cache** -- hash PDF contents with sha256, look for cached result
2. **Cache hit** -- validate style flags match `meta.json`, read `content.md`, glob images, return `ConversionResult`
3. **Cache miss** (or style mismatch, or `no_cache`) -- run docling pipeline:

```python
pipeline_options = PdfPipelineOptions()
pipeline_options.generate_picture_images = True
pipeline_options.images_scale = 2.0
pipeline_options.do_table_structure = True
pipeline_options.do_formula_enrichment = True  # off by default in docling, enabled explicitly

converter = DocumentConverter(
    format_options={InputFormat.PDF: PdfFormatOption(pipeline_options=pipeline_options)}
)
result = converter.convert(pdf_path)
```

4. **Build markdown** via document tree walk (see strategy above)
5. **Write cache** -- save `content.md` + all image files + `meta.json`
6. **Return** `ConversionResult`

#### Import guard

```python
try:
    from docling.document_converter import DocumentConverter, PdfFormatOption
    from docling.datamodel.pipeline_options import PdfPipelineOptions
    from docling.datamodel.base_models import InputFormat
    from docling_core.types.doc import PictureItem, TableItem, FormulaItem
    DOCLING_AVAILABLE = True
except ImportError:
    DOCLING_AVAILABLE = False
```

`DoclingConverter.__init__()` raises `ImportError("Install riszotto[full] for docling support")` if `DOCLING_AVAILABLE` is False.

## Platform Directories

### Migration from `~/.riszotto/`

All riszotto paths move to platform-appropriate locations via `platformdirs`:

| Purpose | Old path | New path (macOS) | New path (Linux) |
|---------|----------|-------------------|-------------------|
| Config | `~/.riszotto/config.toml` | `~/Library/Application Support/riszotto/config.toml` | `~/.config/riszotto/config.toml` |
| ChromaDB | `~/.riszotto/chroma_db/` | `~/Library/Application Support/riszotto/chroma_db/` | `~/.local/share/riszotto/chroma_db/` |
| Cache | _(new)_ | `~/Library/Caches/riszotto/` | `~/.cache/riszotto/` |

### Centralized path module

```python
# src/riszotto/paths.py
from pathlib import Path
from platformdirs import user_config_dir, user_data_dir, user_cache_dir

def config_dir() -> Path:
    return Path(user_config_dir("riszotto"))

def data_dir() -> Path:
    return Path(user_data_dir("riszotto"))

def cache_dir() -> Path:
    return Path(user_cache_dir("riszotto"))

CONFIG_PATH = config_dir() / "config.toml"
CHROMA_DIR = data_dir() / "chroma_db"
CONVERSION_CACHE_DIR = cache_dir() / "conversions"
```

### Legacy path migration

On startup (in `paths.py`), check if `~/.riszotto/` exists and differs from the new platformdirs paths. If so:

```python
LEGACY_DIR = Path.home() / ".riszotto"

def check_legacy_migration() -> None:
    """Warn if legacy ~/.riszotto/ exists and differs from platformdirs paths."""
    if not LEGACY_DIR.exists():
        return
    if LEGACY_DIR.resolve() == config_dir().resolve():
        return  # same path (e.g., XDG_CONFIG_HOME set to ~/.riszotto)
    # Check for config.toml
    legacy_config = LEGACY_DIR / "config.toml"
    if legacy_config.exists() and not CONFIG_PATH.exists():
        typer.echo(
            f"Found legacy config at {legacy_config}. "
            f"Please move it to {CONFIG_PATH}",
            err=True,
        )
    # Check for chroma_db
    legacy_chroma = LEGACY_DIR / "chroma_db"
    if legacy_chroma.exists() and not CHROMA_DIR.exists():
        typer.echo(
            f"Found legacy index at {legacy_chroma}. "
            f"Please move it to {CHROMA_DIR}",
            err=True,
        )
```

This is a warning-only migration -- no automatic file moves. The user moves files at their convenience. After migration, they can delete `~/.riszotto/`.

### Updates to existing modules

- `config.py`: replace `CONFIG_PATH = Path.home() / ".riszotto" / "config.toml"` with import from `paths.py`
- `semantic.py`: replace `INDEX_DIR = Path.home() / ".riszotto" / "chroma_db"` with import from `paths.py`

## Cache System

### Location

Uses `CONVERSION_CACHE_DIR` from `paths.py` (i.e., `platformdirs.user_cache_dir("riszotto") / "conversions"`).

### Directory structure

```
<cache_dir>/conversions/
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
    backend: BackendName
    table_style: StyleOption
    equation_style: StyleOption
    pdf_hash: str
```

Serialized via `meta.model_dump_json()`, deserialized via `CacheMeta.model_validate_json(path.read_text())`.

### Cache invalidation

Cache is invalidated when:
- PDF content changes (different sha256 hash)
- Style flags differ from cached `meta.json` (e.g., request `--table-style image` but cache has `inline`)
- User passes `--no-cache`

**Known limitation**: style-only changes re-run the full docling pipeline. A future optimization could cache the raw docling document object separately and only re-run the lightweight post-processing step. Not in scope for v1.

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

- `--backend docling` when docling not installed: error with `"docling not installed. Install with: uv add riszotto[full]"`
- `--table-style` / `--equation-style` when backend is markitdown: error with `"--table-style requires docling backend. Install with: uv add riszotto[full]"`
- `--figure N`: outputs only the file path to figure N (no markdown output). 1-indexed. Mutually exclusive with `--search` and `--page`. Out-of-range N produces an error listing available figures with `"Paper has N figures (1-N). Use --figure 1 through --figure N."`
- `--figure N` when paper has no cache: error with `"No cached conversion for KEY. Run 'riszotto show KEY' with docling first."`

### New `cache` command group

```
riszotto cache show                     # total size, paper count, cache path
riszotto cache show --key KEY           # size + file listing for one paper
riszotto cache clear                    # clear entire cache
riszotto cache clear --key KEY          # clear one paper
riszotto cache clear --older-than 30d   # age-based cleanup (accepts <N>d for days)
```

Error handling:
- No cache directory yet (first run): `"Cache is empty (0 papers, 0 B). Path: <cache_dir>"`
- `--key KEY` with no cache entry: `"No cached data for KEY."`
- Invalid `--older-than` format: `"Invalid duration format. Use <N>d, e.g., --older-than 30d"`

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

### Performance expectations

First `riszotto show` with docling takes ~30-120 seconds depending on paper length (model loading + inference). Subsequent views of the same paper are near-instant from cache. A progress message is shown to stderr during conversion: `"Converting PDF with docling..."`.

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
    "docling>=2.80.0",
    "riszotto[semantic]",
]
```

Note: `docling>=2.80.0` floor chosen to ensure all referenced API features (`do_formula_enrichment`, `generate_picture_images`, `FormulaItem`, etc.) are available. The `[full]` extra includes `[semantic]` -- this is intentional so that `uv add riszotto[full]` gets everything. Users wanting only docling without semantic search should install docling separately.

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

## What Changes Beyond the Docling Feature

- Config path moves from `~/.riszotto/config.toml` to `platformdirs.user_config_dir("riszotto")/config.toml`
- ChromaDB path moves from `~/.riszotto/chroma_db/` to `platformdirs.user_data_dir("riszotto")/chroma_db/`
- Legacy `~/.riszotto/` detected on startup with migration guidance
- `pydantic` and `platformdirs` added as core dependencies
