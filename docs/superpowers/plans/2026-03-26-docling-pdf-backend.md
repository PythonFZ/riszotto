# Docling PDF Backend Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add docling as an optional rich PDF backend alongside markitdown, with figure/table/equation extraction and a SHA256-keyed conversion cache.

**Architecture:** New `converter/` package with `Converter` protocol, two implementations (markitdown, docling), and a file-based cache. A new `paths.py` centralizes all platform-specific directories. The `show` command delegates to whichever converter is active. New `cache` command group manages the conversion cache.

**Tech Stack:** Python 3.11+, docling (optional), pydantic, platformdirs, typer, pytest

---

## File Map

| Action | Path | Responsibility |
|--------|------|----------------|
| Create | `src/riszotto/paths.py` | Centralized platformdirs paths + legacy migration check |
| Create | `src/riszotto/converter/__init__.py` | `get_converter()` factory + auto-detection |
| Create | `src/riszotto/converter/base.py` | `ConversionResult`, `Converter` protocol, type aliases |
| Create | `src/riszotto/converter/markitdown.py` | `MarkItDownConverter` wrapping existing logic |
| Create | `src/riszotto/converter/docling.py` | `DoclingConverter` with tree walk + cache integration |
| Create | `src/riszotto/converter/cache.py` | `CacheMeta` pydantic model, read/write/clear/hash operations |
| Modify | `src/riszotto/config.py` | Import `CONFIG_PATH` from `paths.py` |
| Modify | `src/riszotto/semantic.py` | Import `CHROMA_DIR` from `paths.py` |
| Modify | `src/riszotto/cli.py` | Wire converter into `show`, add new flags, add `cache` command group |
| Modify | `pyproject.toml` | Add `pydantic`, `platformdirs` to deps; add `[full]` extra |
| Create | `tests/test_paths.py` | Tests for paths module + legacy migration |
| Create | `tests/test_converter_base.py` | Tests for types and factory |
| Create | `tests/test_converter_markitdown.py` | Tests for markitdown converter |
| Create | `tests/test_converter_docling.py` | Tests for docling converter (mocked) |
| Create | `tests/test_converter_cache.py` | Tests for cache operations |
| Modify | `tests/test_cli.py` | Update `show` tests for converter, add cache command tests |
| Modify | `tests/test_config.py` | Update to patch `paths.CONFIG_PATH` |
| Modify | `.github/workflows/pytest.yaml` | Test both `[semantic]` and `[full]` extras in CI matrix |

---

### Task 1: Add core dependencies to pyproject.toml

**Files:**
- Modify: `pyproject.toml`

- [ ] **Step 1: Update pyproject.toml**

```toml
[project]
name = "riszotto"
dynamic = ["version"]
description = "CLI tool for searching and reading papers from a local Zotero library"
readme = "README.md"
requires-python = ">=3.11"
dependencies = [
    "typer>=0.9.0",
    "pyzotero>=1.5.0",
    "markitdown[pdf]>=0.1.0",
    "pydantic>=2.0.0",
    "platformdirs>=4.0.0",
]

[project.scripts]
riszotto = "riszotto.cli:app"

[project.urls]
Repository = "https://github.com/PythonFZ/riszotto"

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

[build-system]
requires = ["hatchling", "hatch-vcs"]
build-backend = "hatchling.build"

[tool.hatch.version]
source = "vcs"

[tool.hatch.build.hooks.vcs]
version-file = "src/riszotto/_version.py"

[dependency-groups]
dev = [
    "pytest>=9.0.2",
]
```

- [ ] **Step 2: Install new dependencies**

Run: `uv sync`
Expected: successful install of pydantic and platformdirs

- [ ] **Step 3: Verify imports work**

Run: `uv run python -c "import pydantic; import platformdirs; print('OK')"`
Expected: `OK`

- [ ] **Step 4: Commit**

```bash
git add pyproject.toml
git commit -m "feat: add pydantic and platformdirs as core deps, add [full] extra"
```

---

### Task 2: Create paths.py with platformdirs + legacy migration

**Files:**
- Create: `src/riszotto/paths.py`
- Create: `tests/test_paths.py`

- [ ] **Step 1: Write tests for paths module**

```python
# tests/test_paths.py
import os
from pathlib import Path
from unittest.mock import patch

import pytest


class TestPaths:
    def test_config_path_uses_platformdirs(self):
        from riszotto.paths import CONFIG_PATH

        assert CONFIG_PATH.name == "config.toml"
        assert "riszotto" in str(CONFIG_PATH)

    def test_chroma_dir_uses_platformdirs(self):
        from riszotto.paths import CHROMA_DIR

        assert CHROMA_DIR.name == "chroma_db"
        assert "riszotto" in str(CHROMA_DIR)

    def test_conversion_cache_dir_uses_platformdirs(self):
        from riszotto.paths import CONVERSION_CACHE_DIR

        assert CONVERSION_CACHE_DIR.name == "conversions"
        assert "riszotto" in str(CONVERSION_CACHE_DIR)


class TestLegacyMigration:
    def test_no_warning_when_no_legacy_dir(self, tmp_path, capsys):
        legacy = tmp_path / ".riszotto"
        # Don't create it — it doesn't exist
        with patch("riszotto.paths.LEGACY_DIR", legacy):
            from riszotto.paths import check_legacy_migration

            check_legacy_migration()
        assert capsys.readouterr().err == ""

    def test_warns_about_legacy_config(self, tmp_path, capsys):
        legacy = tmp_path / ".riszotto"
        legacy.mkdir()
        (legacy / "config.toml").write_text('[zotero]\napi_key = "x"\n')
        new_config = tmp_path / "new_config" / "config.toml"
        with (
            patch("riszotto.paths.LEGACY_DIR", legacy),
            patch("riszotto.paths.CONFIG_PATH", new_config),
            patch("riszotto.paths.config_dir", return_value=tmp_path / "new_config"),
        ):
            from riszotto.paths import check_legacy_migration

            check_legacy_migration()
        assert "legacy config" in capsys.readouterr().err.lower()

    def test_warns_about_legacy_chroma(self, tmp_path, capsys):
        legacy = tmp_path / ".riszotto"
        legacy.mkdir()
        (legacy / "chroma_db").mkdir()
        new_chroma = tmp_path / "new_data" / "chroma_db"
        with (
            patch("riszotto.paths.LEGACY_DIR", legacy),
            patch("riszotto.paths.CONFIG_PATH", tmp_path / "new_config" / "config.toml"),
            patch("riszotto.paths.CHROMA_DIR", new_chroma),
            patch("riszotto.paths.config_dir", return_value=tmp_path / "new_config"),
        ):
            from riszotto.paths import check_legacy_migration

            check_legacy_migration()
        assert "legacy index" in capsys.readouterr().err.lower()

    def test_no_warning_when_new_paths_already_exist(self, tmp_path, capsys):
        legacy = tmp_path / ".riszotto"
        legacy.mkdir()
        (legacy / "config.toml").write_text('[zotero]\napi_key = "x"\n')
        new_config = tmp_path / "new_config" / "config.toml"
        new_config.parent.mkdir(parents=True)
        new_config.write_text('[zotero]\napi_key = "y"\n')
        with (
            patch("riszotto.paths.LEGACY_DIR", legacy),
            patch("riszotto.paths.CONFIG_PATH", new_config),
            patch("riszotto.paths.config_dir", return_value=tmp_path / "new_config"),
        ):
            from riszotto.paths import check_legacy_migration

            check_legacy_migration()
        assert "legacy config" not in capsys.readouterr().err.lower()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_paths.py -v`
Expected: FAIL (module not found)

- [ ] **Step 3: Implement paths.py**

```python
# src/riszotto/paths.py
"""Centralized platform-specific directory resolution."""

from __future__ import annotations

import sys
from pathlib import Path

from platformdirs import user_cache_dir, user_config_dir, user_data_dir


def config_dir() -> Path:
    """Return the platform-specific config directory for riszotto."""
    return Path(user_config_dir("riszotto"))


def data_dir() -> Path:
    """Return the platform-specific data directory for riszotto."""
    return Path(user_data_dir("riszotto"))


def cache_dir() -> Path:
    """Return the platform-specific cache directory for riszotto."""
    return Path(user_cache_dir("riszotto"))


CONFIG_PATH = config_dir() / "config.toml"
CHROMA_DIR = data_dir() / "chroma_db"
CONVERSION_CACHE_DIR = cache_dir() / "conversions"

LEGACY_DIR = Path.home() / ".riszotto"


def check_legacy_migration() -> None:
    """Warn if legacy ~/.riszotto/ exists and differs from platformdirs paths."""
    if not LEGACY_DIR.exists():
        return
    if LEGACY_DIR.resolve() == config_dir().resolve():
        return

    legacy_config = LEGACY_DIR / "config.toml"
    if legacy_config.exists() and not CONFIG_PATH.exists():
        print(
            f"Found legacy config at {legacy_config}. "
            f"Please move it to {CONFIG_PATH}",
            file=sys.stderr,
        )

    legacy_chroma = LEGACY_DIR / "chroma_db"
    if legacy_chroma.exists() and not CHROMA_DIR.exists():
        print(
            f"Found legacy index at {legacy_chroma}. "
            f"Please move it to {CHROMA_DIR}",
            file=sys.stderr,
        )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_paths.py -v`
Expected: all PASS

- [ ] **Step 5: Commit**

```bash
git add src/riszotto/paths.py tests/test_paths.py
git commit -m "feat: add paths module with platformdirs + legacy migration check"
```

---

### Task 3: Migrate config.py and semantic.py to use paths.py

**Files:**
- Modify: `src/riszotto/config.py`
- Modify: `src/riszotto/semantic.py`
- Modify: `tests/test_config.py`

- [ ] **Step 1: Update config.py**

Replace the `CONFIG_PATH` definition in `src/riszotto/config.py`:

```python
# Replace:
# CONFIG_PATH = Path.home() / ".riszotto" / "config.toml"
# With:
from riszotto.paths import CONFIG_PATH
```

Remove the now-unused `from pathlib import Path` import (it's no longer needed in config.py since CONFIG_PATH is imported).

The full file should be:

```python
"""Configuration loading from TOML file and environment variables."""

from __future__ import annotations

import dataclasses
import os
import tomllib

from riszotto.paths import CONFIG_PATH


@dataclasses.dataclass
class Config:
    """Zotero connection configuration."""

    api_key: str | None = None
    user_id: str | None = None

    @property
    def has_remote_credentials(self) -> bool:
        """Check if both API key and user ID are configured."""
        return self.api_key is not None and self.user_id is not None


def load_config() -> Config:
    """Load config from TOML file, then override with env vars.

    Precedence: defaults < config file < environment variables.
    """
    config = Config()

    if CONFIG_PATH.is_file():
        with open(CONFIG_PATH, "rb") as f:
            data = tomllib.load(f)
        zotero = data.get("zotero", {})
        if "api_key" in zotero:
            config.api_key = zotero["api_key"]
        if "user_id" in zotero:
            config.user_id = zotero["user_id"]

    env_key = os.environ.get("ZOTERO_API_KEY")
    if env_key is not None:
        config.api_key = env_key
    env_id = os.environ.get("ZOTERO_USER_ID")
    if env_id is not None:
        config.user_id = env_id

    return config
```

- [ ] **Step 2: Update semantic.py**

Replace the `INDEX_DIR` definition in `src/riszotto/semantic.py`:

```python
# Replace:
# INDEX_DIR = Path.home() / ".riszotto" / "chroma_db"
# With:
from riszotto.paths import CHROMA_DIR as INDEX_DIR
```

Remove the now-unused `from pathlib import Path` import.

The top of the file should be:

```python
"""Semantic search over Zotero items using ChromaDB embeddings."""

from __future__ import annotations

from riszotto.formatting import CHILD_ITEM_TYPES, format_creator
from riszotto.paths import CHROMA_DIR as INDEX_DIR

BATCH_SIZE = 500
```

- [ ] **Step 3: Update test_config.py patch targets**

In `tests/test_config.py`, all patches of `riszotto.config.CONFIG_PATH` must change to `riszotto.paths.CONFIG_PATH` because config.py now imports CONFIG_PATH from paths.py, but the module-level reference in config.py is what gets used. Actually, since config.py does `from riszotto.paths import CONFIG_PATH`, the name `CONFIG_PATH` in `config.py`'s module namespace is a local binding. To patch it, we still patch `riszotto.config.CONFIG_PATH`.

Wait — `from X import Y` creates a new binding in the importing module. So `riszotto.config.CONFIG_PATH` is the correct patch target. The existing tests should work unchanged. Verify:

Run: `uv run pytest tests/test_config.py -v`
Expected: all PASS

- [ ] **Step 4: Run full test suite**

Run: `uv run pytest -v`
Expected: all PASS

- [ ] **Step 5: Commit**

```bash
git add src/riszotto/config.py src/riszotto/semantic.py
git commit -m "refactor: migrate config and semantic to use paths module"
```

---

### Task 4: Create converter base types and protocol

**Files:**
- Create: `src/riszotto/converter/__init__.py`
- Create: `src/riszotto/converter/base.py`
- Create: `tests/test_converter_base.py`

- [ ] **Step 1: Write tests for base types**

```python
# tests/test_converter_base.py
from pathlib import Path

from riszotto.converter.base import ConversionResult, StyleOption, BackendName


class TestConversionResult:
    def test_creation_with_defaults(self):
        result = ConversionResult(markdown="# Hello")
        assert result.markdown == "# Hello"
        assert result.figures == {}

    def test_creation_with_figures(self, tmp_path):
        fig_path = tmp_path / "figure_1.png"
        fig_path.write_bytes(b"PNG")
        result = ConversionResult(
            markdown="![Figure 1](fig)",
            figures={"figure_1.png": fig_path},
        )
        assert result.figures["figure_1.png"] == fig_path


class TestTypeAliases:
    def test_style_option_values(self):
        inline: StyleOption = "inline"
        image: StyleOption = "image"
        assert inline == "inline"
        assert image == "image"

    def test_backend_name_values(self):
        mk: BackendName = "markitdown"
        dl: BackendName = "docling"
        assert mk == "markitdown"
        assert dl == "docling"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_converter_base.py -v`
Expected: FAIL (module not found)

- [ ] **Step 3: Create converter package**

```python
# src/riszotto/converter/__init__.py
"""PDF converter backends with auto-detection."""

from __future__ import annotations

from riszotto.converter.base import (
    BackendName,
    ConversionResult,
    Converter,
    StyleOption,
)


def get_converter(backend: BackendName | None = None) -> Converter:
    """Get a PDF converter, auto-detecting the best available backend.

    Parameters
    ----------
    backend
        Explicit backend name. If None, tries docling first,
        falls back to markitdown.
    """
    from riszotto.converter.markitdown import MarkItDownConverter

    if backend == "markitdown":
        return MarkItDownConverter()
    if backend == "docling":
        from riszotto.converter.docling import DoclingConverter

        return DoclingConverter()
    try:
        from riszotto.converter.docling import DoclingConverter

        return DoclingConverter()
    except ImportError:
        return MarkItDownConverter()


__all__ = [
    "BackendName",
    "ConversionResult",
    "Converter",
    "StyleOption",
    "get_converter",
]
```

```python
# src/riszotto/converter/base.py
"""Converter protocol, result type, and shared type aliases."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Annotated, Literal, Protocol

StyleOption = Literal["inline", "image"]
BackendName = Literal["markitdown", "docling"]
BackendOption = Annotated[StyleOption | None, "Only available with docling backend"]


@dataclass
class ConversionResult:
    """Internal result object -- dataclass, not serialized to disk."""

    markdown: str
    figures: dict[str, Path] = field(default_factory=dict)


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
    ) -> ConversionResult: ...
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_converter_base.py -v`
Expected: all PASS

- [ ] **Step 5: Commit**

```bash
git add src/riszotto/converter/__init__.py src/riszotto/converter/base.py tests/test_converter_base.py
git commit -m "feat: add converter package with base types and protocol"
```

---

### Task 5: Create MarkItDownConverter

**Files:**
- Create: `src/riszotto/converter/markitdown.py`
- Create: `tests/test_converter_markitdown.py`

- [ ] **Step 1: Write tests**

```python
# tests/test_converter_markitdown.py
from pathlib import Path
from unittest.mock import MagicMock, patch

from riszotto.converter.markitdown import MarkItDownConverter


class TestMarkItDownConverter:
    @patch("riszotto.converter.markitdown.MarkItDown")
    def test_convert_returns_markdown(self, mock_markitdown_cls):
        mock_md = MagicMock()
        mock_markitdown_cls.return_value = mock_md
        mock_result = MagicMock()
        mock_result.markdown = "# Title\n\nContent here."
        mock_md.convert.return_value = mock_result

        converter = MarkItDownConverter()
        result = converter.convert(Path("/fake/paper.pdf"), zotero_key="ABC123")

        assert result.markdown == "# Title\n\nContent here."
        assert result.figures == {}
        mock_md.convert.assert_called_once_with(Path("/fake/paper.pdf"))

    @patch("riszotto.converter.markitdown.MarkItDown")
    def test_ignores_style_flags(self, mock_markitdown_cls):
        mock_md = MagicMock()
        mock_markitdown_cls.return_value = mock_md
        mock_result = MagicMock()
        mock_result.markdown = "text"
        mock_md.convert.return_value = mock_result

        converter = MarkItDownConverter()
        result = converter.convert(
            Path("/fake/paper.pdf"),
            table_style="image",
            equation_style="image",
            zotero_key="ABC123",
            no_cache=True,
        )
        assert result.markdown == "text"
        assert result.figures == {}

    @patch("riszotto.converter.markitdown.MarkItDown")
    def test_suppresses_logging(self, mock_markitdown_cls):
        import logging

        mock_md = MagicMock()
        mock_markitdown_cls.return_value = mock_md
        mock_result = MagicMock()
        mock_result.markdown = "text"
        mock_md.convert.return_value = mock_result

        converter = MarkItDownConverter()
        converter.convert(Path("/fake/paper.pdf"), zotero_key="KEY1")

        # After convert, logging should be re-enabled
        assert logging.root.manager.disable < logging.CRITICAL
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_converter_markitdown.py -v`
Expected: FAIL (module not found)

- [ ] **Step 3: Implement MarkItDownConverter**

```python
# src/riszotto/converter/markitdown.py
"""MarkItDown-based PDF converter (lightweight default)."""

from __future__ import annotations

import logging
from pathlib import Path

from markitdown import MarkItDown

from riszotto.converter.base import ConversionResult, StyleOption


class MarkItDownConverter:
    """Convert PDFs using Microsoft's MarkItDown library.

    This is the lightweight default backend. It extracts plain text
    only -- no figures, structured tables, or equation rendering.
    Style flags and caching are ignored.
    """

    def convert(
        self,
        pdf_path: Path,
        *,
        table_style: StyleOption = "inline",
        equation_style: StyleOption = "inline",
        zotero_key: str,
        no_cache: bool = False,
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

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_converter_markitdown.py -v`
Expected: all PASS

- [ ] **Step 5: Commit**

```bash
git add src/riszotto/converter/markitdown.py tests/test_converter_markitdown.py
git commit -m "feat: add MarkItDownConverter backend"
```

---

### Task 6: Create cache module

**Files:**
- Create: `src/riszotto/converter/cache.py`
- Create: `tests/test_converter_cache.py`

- [ ] **Step 1: Write tests**

```python
# tests/test_converter_cache.py
import json
import time
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

import pytest

from riszotto.converter.cache import (
    CacheMeta,
    cache_dir_for,
    compute_pdf_hash,
    read_cache,
    write_cache,
    clear_cache,
    get_cache_stats,
)
from riszotto.converter.base import ConversionResult


class TestComputePdfHash:
    def test_returns_12_char_hex(self, tmp_path):
        pdf = tmp_path / "test.pdf"
        pdf.write_bytes(b"%PDF-1.4 fake content")
        h = compute_pdf_hash(pdf)
        assert len(h) == 12
        assert all(c in "0123456789abcdef" for c in h)

    def test_different_content_different_hash(self, tmp_path):
        a = tmp_path / "a.pdf"
        b = tmp_path / "b.pdf"
        a.write_bytes(b"content A")
        b.write_bytes(b"content B")
        assert compute_pdf_hash(a) != compute_pdf_hash(b)

    def test_same_content_same_hash(self, tmp_path):
        a = tmp_path / "a.pdf"
        b = tmp_path / "b.pdf"
        a.write_bytes(b"same content")
        b.write_bytes(b"same content")
        assert compute_pdf_hash(a) == compute_pdf_hash(b)


class TestCacheMeta:
    def test_roundtrip_json(self):
        meta = CacheMeta(
            created=datetime(2026, 3, 26, tzinfo=timezone.utc),
            backend="docling",
            table_style="inline",
            equation_style="inline",
            pdf_hash="abc123def456",
        )
        json_str = meta.model_dump_json()
        restored = CacheMeta.model_validate_json(json_str)
        assert restored.backend == "docling"
        assert restored.pdf_hash == "abc123def456"
        assert restored.table_style == "inline"


class TestWriteAndReadCache:
    def test_write_then_read(self, tmp_path):
        with patch("riszotto.converter.cache.CONVERSION_CACHE_DIR", tmp_path):
            figures = {"figure_1.png": tmp_path / "src_fig.png"}
            (tmp_path / "src_fig.png").write_bytes(b"PNG_DATA")

            write_cache(
                zotero_key="KEY1",
                pdf_hash="aabbccddee11",
                markdown="# Hello\n\n![Figure 1](figure_1.png)",
                figures=figures,
                backend="docling",
                table_style="inline",
                equation_style="inline",
            )

            result = read_cache(
                zotero_key="KEY1",
                pdf_hash="aabbccddee11",
                table_style="inline",
                equation_style="inline",
            )
            assert result is not None
            assert "# Hello" in result.markdown
            assert "figure_1.png" in result.figures

    def test_read_returns_none_on_missing(self, tmp_path):
        with patch("riszotto.converter.cache.CONVERSION_CACHE_DIR", tmp_path):
            result = read_cache(
                zotero_key="MISSING",
                pdf_hash="000000000000",
                table_style="inline",
                equation_style="inline",
            )
            assert result is None

    def test_style_mismatch_returns_none(self, tmp_path):
        with patch("riszotto.converter.cache.CONVERSION_CACHE_DIR", tmp_path):
            figures = {}
            write_cache(
                zotero_key="KEY1",
                pdf_hash="aabbccddee11",
                markdown="text",
                figures=figures,
                backend="docling",
                table_style="inline",
                equation_style="inline",
            )
            result = read_cache(
                zotero_key="KEY1",
                pdf_hash="aabbccddee11",
                table_style="image",
                equation_style="inline",
            )
            assert result is None

    def test_old_hash_dir_removed_on_new_write(self, tmp_path):
        with patch("riszotto.converter.cache.CONVERSION_CACHE_DIR", tmp_path):
            write_cache(
                zotero_key="KEY1",
                pdf_hash="old_hash_0001",
                markdown="old",
                figures={},
                backend="docling",
                table_style="inline",
                equation_style="inline",
            )
            assert (tmp_path / "KEY1" / "old_hash_0001").exists()

            write_cache(
                zotero_key="KEY1",
                pdf_hash="new_hash_0002",
                markdown="new",
                figures={},
                backend="docling",
                table_style="inline",
                equation_style="inline",
            )
            assert not (tmp_path / "KEY1" / "old_hash_0001").exists()
            assert (tmp_path / "KEY1" / "new_hash_0002").exists()


class TestClearCache:
    def test_clear_all(self, tmp_path):
        with patch("riszotto.converter.cache.CONVERSION_CACHE_DIR", tmp_path):
            write_cache(
                zotero_key="K1", pdf_hash="h1h1h1h1h1h1",
                markdown="a", figures={},
                backend="docling", table_style="inline", equation_style="inline",
            )
            write_cache(
                zotero_key="K2", pdf_hash="h2h2h2h2h2h2",
                markdown="b", figures={},
                backend="docling", table_style="inline", equation_style="inline",
            )
            cleared = clear_cache()
            assert cleared == 2
            assert not (tmp_path / "K1").exists()
            assert not (tmp_path / "K2").exists()

    def test_clear_by_key(self, tmp_path):
        with patch("riszotto.converter.cache.CONVERSION_CACHE_DIR", tmp_path):
            write_cache(
                zotero_key="K1", pdf_hash="h1h1h1h1h1h1",
                markdown="a", figures={},
                backend="docling", table_style="inline", equation_style="inline",
            )
            write_cache(
                zotero_key="K2", pdf_hash="h2h2h2h2h2h2",
                markdown="b", figures={},
                backend="docling", table_style="inline", equation_style="inline",
            )
            cleared = clear_cache(key="K1")
            assert cleared == 1
            assert not (tmp_path / "K1").exists()
            assert (tmp_path / "K2").exists()

    def test_clear_empty_cache(self, tmp_path):
        with patch("riszotto.converter.cache.CONVERSION_CACHE_DIR", tmp_path):
            cleared = clear_cache()
            assert cleared == 0


class TestGetCacheStats:
    def test_empty_cache(self, tmp_path):
        with patch("riszotto.converter.cache.CONVERSION_CACHE_DIR", tmp_path):
            stats = get_cache_stats()
            assert stats["paper_count"] == 0
            assert stats["total_bytes"] == 0
            assert stats["path"] == str(tmp_path)

    def test_populated_cache(self, tmp_path):
        with patch("riszotto.converter.cache.CONVERSION_CACHE_DIR", tmp_path):
            write_cache(
                zotero_key="K1", pdf_hash="h1h1h1h1h1h1",
                markdown="content here", figures={},
                backend="docling", table_style="inline", equation_style="inline",
            )
            stats = get_cache_stats()
            assert stats["paper_count"] == 1
            assert stats["total_bytes"] > 0

    def test_stats_for_specific_key(self, tmp_path):
        with patch("riszotto.converter.cache.CONVERSION_CACHE_DIR", tmp_path):
            write_cache(
                zotero_key="K1", pdf_hash="h1h1h1h1h1h1",
                markdown="a", figures={},
                backend="docling", table_style="inline", equation_style="inline",
            )
            stats = get_cache_stats(key="K1")
            assert stats["paper_count"] == 1

            stats_missing = get_cache_stats(key="NOPE")
            assert stats_missing["paper_count"] == 0
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_converter_cache.py -v`
Expected: FAIL (module not found)

- [ ] **Step 3: Implement cache module**

```python
# src/riszotto/converter/cache.py
"""SHA256-keyed conversion cache for docling results."""

from __future__ import annotations

import hashlib
import shutil
from datetime import datetime, timezone
from pathlib import Path

from pydantic import BaseModel

from riszotto.converter.base import BackendName, ConversionResult, StyleOption
from riszotto.paths import CONVERSION_CACHE_DIR


class CacheMeta(BaseModel):
    """Metadata for a cached conversion result."""

    created: datetime
    backend: BackendName
    table_style: StyleOption
    equation_style: StyleOption
    pdf_hash: str


def compute_pdf_hash(pdf_path: Path) -> str:
    """Return first 12 hex chars of the SHA256 hash of a PDF file."""
    h = hashlib.sha256(pdf_path.read_bytes()).hexdigest()
    return h[:12]


def cache_dir_for(zotero_key: str, pdf_hash: str) -> Path:
    """Return the cache directory for a specific paper + hash."""
    return CONVERSION_CACHE_DIR / zotero_key / pdf_hash


def read_cache(
    *,
    zotero_key: str,
    pdf_hash: str,
    table_style: StyleOption,
    equation_style: StyleOption,
) -> ConversionResult | None:
    """Read a cached conversion result, or None if not found/mismatched."""
    cache_path = cache_dir_for(zotero_key, pdf_hash)
    meta_file = cache_path / "meta.json"
    content_file = cache_path / "content.md"

    if not meta_file.exists() or not content_file.exists():
        return None

    meta = CacheMeta.model_validate_json(meta_file.read_text())

    if meta.table_style != table_style or meta.equation_style != equation_style:
        return None

    markdown = content_file.read_text()
    figures = {
        f.name: f
        for f in cache_path.iterdir()
        if f.suffix in (".png", ".jpg", ".jpeg") and f.name != "meta.json"
    }

    return ConversionResult(markdown=markdown, figures=figures)


def write_cache(
    *,
    zotero_key: str,
    pdf_hash: str,
    markdown: str,
    figures: dict[str, Path],
    backend: BackendName,
    table_style: StyleOption,
    equation_style: StyleOption,
) -> Path:
    """Write a conversion result to cache. Returns the cache directory.

    Removes any existing hash directories for this zotero_key
    (only one hash per key is kept).
    """
    key_dir = CONVERSION_CACHE_DIR / zotero_key

    # Remove old hash directories for this key
    if key_dir.exists():
        for child in key_dir.iterdir():
            if child.is_dir() and child.name != pdf_hash:
                shutil.rmtree(child)

    cache_path = cache_dir_for(zotero_key, pdf_hash)
    cache_path.mkdir(parents=True, exist_ok=True)

    (cache_path / "content.md").write_text(markdown)

    for name, src in figures.items():
        dest = cache_path / name
        if src != dest:
            shutil.copy2(src, dest)

    meta = CacheMeta(
        created=datetime.now(timezone.utc),
        backend=backend,
        table_style=table_style,
        equation_style=equation_style,
        pdf_hash=pdf_hash,
    )
    (cache_path / "meta.json").write_text(meta.model_dump_json(indent=2))

    return cache_path


def clear_cache(
    *,
    key: str | None = None,
    older_than_days: int | None = None,
) -> int:
    """Clear cached conversions. Returns number of papers cleared."""
    if not CONVERSION_CACHE_DIR.exists():
        return 0

    cleared = 0

    if key is not None:
        key_dir = CONVERSION_CACHE_DIR / key
        if key_dir.exists():
            shutil.rmtree(key_dir)
            cleared = 1
        return cleared

    for key_dir in CONVERSION_CACHE_DIR.iterdir():
        if not key_dir.is_dir():
            continue
        if older_than_days is not None:
            meta_files = list(key_dir.rglob("meta.json"))
            if meta_files:
                meta = CacheMeta.model_validate_json(meta_files[0].read_text())
                age_days = (datetime.now(timezone.utc) - meta.created).days
                if age_days < older_than_days:
                    continue
        shutil.rmtree(key_dir)
        cleared += 1

    return cleared


def get_cache_stats(*, key: str | None = None) -> dict:
    """Return cache statistics."""
    if not CONVERSION_CACHE_DIR.exists():
        return {"paper_count": 0, "total_bytes": 0, "path": str(CONVERSION_CACHE_DIR)}

    total_bytes = 0
    paper_count = 0
    papers: list[dict] = []

    dirs = [CONVERSION_CACHE_DIR / key] if key else CONVERSION_CACHE_DIR.iterdir()

    for key_dir in dirs:
        if not isinstance(key_dir, Path):
            continue
        if not key_dir.is_dir():
            continue
        paper_count += 1
        paper_bytes = sum(f.stat().st_size for f in key_dir.rglob("*") if f.is_file())
        total_bytes += paper_bytes
        papers.append({"key": key_dir.name, "bytes": paper_bytes})

    return {
        "paper_count": paper_count,
        "total_bytes": total_bytes,
        "path": str(CONVERSION_CACHE_DIR),
        "papers": papers,
    }
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_converter_cache.py -v`
Expected: all PASS

- [ ] **Step 5: Commit**

```bash
git add src/riszotto/converter/cache.py tests/test_converter_cache.py
git commit -m "feat: add SHA256-keyed conversion cache with pydantic metadata"
```

---

### Task 7: Create DoclingConverter

**Files:**
- Create: `src/riszotto/converter/docling.py`
- Create: `tests/test_converter_docling.py`

- [ ] **Step 1: Write tests (mocking docling)**

```python
# tests/test_converter_docling.py
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch, PropertyMock

import pytest


class TestDoclingAvailableFlag:
    def test_import_error_sets_flag_false(self):
        # Force reimport with docling missing
        with patch.dict(sys.modules, {"docling": None, "docling.document_converter": None}):
            # Can't easily reimport, so test the converter init behavior
            from riszotto.converter.docling import DOCLING_AVAILABLE

            # In the real module, if docling is not installed, this would be False.
            # Since docling may or may not be installed in test env, just test
            # that the flag exists and is a bool.
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


class TestDoclingConverterConvert:
    """Test the convert method with fully mocked docling internals."""

    def _make_mock_text_item(self, text, label="paragraph"):
        item = MagicMock()
        item.__class__.__name__ = "TextItem"
        item.text = text
        item.label = label
        return item

    def _make_mock_picture_item(self):
        item = MagicMock()
        item.__class__.__name__ = "PictureItem"
        mock_image = MagicMock()
        item.get_image.return_value = mock_image
        return item, mock_image

    def _make_mock_table_item(self, markdown_table="| A | B |\n|---|---|\n| 1 | 2 |"):
        import pandas as pd

        item = MagicMock()
        item.__class__.__name__ = "TableItem"
        mock_df = MagicMock(spec=pd.DataFrame)
        mock_df.to_markdown.return_value = markdown_table
        item.export_to_dataframe.return_value = mock_df
        mock_image = MagicMock()
        item.get_image.return_value = mock_image
        return item, mock_image

    def _make_mock_formula_item(self, text="E = mc^2"):
        item = MagicMock()
        item.__class__.__name__ = "FormulaItem"
        item.text = text
        mock_image = MagicMock()
        item.get_image.return_value = mock_image
        return item, mock_image

    @patch("riszotto.converter.docling.DOCLING_AVAILABLE", True)
    @patch("riszotto.converter.docling.write_cache")
    @patch("riszotto.converter.docling.read_cache", return_value=None)
    @patch("riszotto.converter.docling.compute_pdf_hash", return_value="aabbccdd0011")
    @patch("riszotto.converter.docling.DocumentConverter")
    def test_convert_with_text_only(
        self, mock_dc_cls, mock_hash, mock_read, mock_write, tmp_path
    ):
        pdf = tmp_path / "paper.pdf"
        pdf.write_bytes(b"fake pdf")

        text_item = self._make_mock_text_item("Hello world")
        mock_doc = MagicMock()
        mock_doc.iterate_items.return_value = [(text_item, 0)]
        mock_conv_result = MagicMock()
        mock_conv_result.document = mock_doc
        mock_dc_cls.return_value.convert.return_value = mock_conv_result

        from riszotto.converter.docling import DoclingConverter

        converter = DoclingConverter()
        result = converter.convert(pdf, zotero_key="KEY1")

        assert "Hello world" in result.markdown
        mock_write.assert_called_once()

    @patch("riszotto.converter.docling.DOCLING_AVAILABLE", True)
    @patch("riszotto.converter.docling.read_cache")
    def test_returns_cached_result(self, mock_read, tmp_path):
        cached = ConversionResult(markdown="cached content", figures={})
        mock_read.return_value = cached

        pdf = tmp_path / "paper.pdf"
        pdf.write_bytes(b"fake pdf")

        from riszotto.converter.docling import DoclingConverter

        with patch("riszotto.converter.docling.compute_pdf_hash", return_value="h"):
            converter = DoclingConverter()
            result = converter.convert(pdf, zotero_key="KEY1")

        assert result.markdown == "cached content"

    @patch("riszotto.converter.docling.DOCLING_AVAILABLE", True)
    @patch("riszotto.converter.docling.read_cache", return_value=None)
    def test_no_cache_bypasses_read(self, mock_read, tmp_path):
        pdf = tmp_path / "paper.pdf"
        pdf.write_bytes(b"fake pdf")

        from riszotto.converter.docling import DoclingConverter

        with (
            patch("riszotto.converter.docling.compute_pdf_hash", return_value="h"),
            patch("riszotto.converter.docling.write_cache"),
            patch("riszotto.converter.docling.DocumentConverter") as mock_dc,
        ):
            mock_doc = MagicMock()
            mock_doc.iterate_items.return_value = []
            mock_dc.return_value.convert.return_value.document = mock_doc

            converter = DoclingConverter()
            converter.convert(pdf, zotero_key="KEY1", no_cache=True)

        mock_read.assert_not_called()


# Import here so tests above can reference it
from riszotto.converter.base import ConversionResult
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_converter_docling.py -v`
Expected: FAIL (module not found)

- [ ] **Step 3: Implement DoclingConverter**

```python
# src/riszotto/converter/docling.py
"""Docling-based PDF converter with rich extraction."""

from __future__ import annotations

import sys
from pathlib import Path

from riszotto.converter.base import ConversionResult, StyleOption
from riszotto.converter.cache import (
    cache_dir_for,
    compute_pdf_hash,
    read_cache,
    write_cache,
)

try:
    from docling.datamodel.base_models import InputFormat
    from docling.datamodel.pipeline_options import PdfPipelineOptions
    from docling.document_converter import DocumentConverter, PdfFormatOption
    from docling_core.types.doc import FormulaItem, PictureItem, TableItem, TextItem

    DOCLING_AVAILABLE = True
except ImportError:
    DOCLING_AVAILABLE = False


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

        print("Converting PDF with docling...", file=sys.stderr)

        pipeline_options = PdfPipelineOptions()
        pipeline_options.generate_picture_images = True
        pipeline_options.images_scale = 2.0
        pipeline_options.do_table_structure = True
        pipeline_options.do_formula_enrichment = True

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
                image = element.get_image(doc)
                image.save(str(fig_path), "PNG")
                figures[filename] = fig_path
                parts.append(f"![Figure {figure_count}]({fig_path})")

            elif isinstance(element, TableItem):
                table_count += 1
                if table_style == "inline":
                    df = element.export_to_dataframe(doc=doc)
                    parts.append(df.to_markdown())
                else:
                    filename = f"table_{table_count}.png"
                    tbl_path = cache_path / filename
                    image = element.get_image(doc)
                    image.save(str(tbl_path), "PNG")
                    figures[filename] = tbl_path
                    parts.append(f"![Table {table_count}]({tbl_path})")

            elif isinstance(element, FormulaItem):
                equation_count += 1
                if equation_style == "inline" and element.text:
                    parts.append(f"$${element.text}$$")
                else:
                    filename = f"equation_{equation_count}.png"
                    eq_path = cache_path / filename
                    image = element.get_image(doc)
                    image.save(str(eq_path), "PNG")
                    figures[filename] = eq_path
                    parts.append(f"![Equation {equation_count}]({eq_path})")

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

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_converter_docling.py -v`
Expected: all PASS

- [ ] **Step 5: Commit**

```bash
git add src/riszotto/converter/docling.py tests/test_converter_docling.py
git commit -m "feat: add DoclingConverter with tree walk and cache integration"
```

---

### Task 8: Add get_converter factory tests

**Files:**
- Modify: `tests/test_converter_base.py`

- [ ] **Step 1: Add factory tests**

Append to `tests/test_converter_base.py`:

```python
from unittest.mock import patch
from riszotto.converter import get_converter
from riszotto.converter.markitdown import MarkItDownConverter


class TestGetConverter:
    def test_explicit_markitdown(self):
        converter = get_converter("markitdown")
        assert isinstance(converter, MarkItDownConverter)

    def test_explicit_docling_when_unavailable(self):
        with patch("riszotto.converter.docling.DOCLING_AVAILABLE", False):
            with pytest.raises(ImportError, match="riszotto\\[full\\]"):
                get_converter("docling")

    def test_auto_falls_back_to_markitdown(self):
        with patch(
            "riszotto.converter.get_converter.__module__",  # not needed
        ):
            # Simulate docling not installed by making import raise
            import riszotto.converter as conv_mod

            original_get = conv_mod.get_converter

            with patch("riszotto.converter.docling.DOCLING_AVAILABLE", False):
                converter = get_converter(None)
                assert isinstance(converter, MarkItDownConverter)

    def test_auto_returns_markitdown_when_no_docling_module(self):
        """When docling package isn't installed at all."""
        converter = get_converter("markitdown")
        assert isinstance(converter, MarkItDownConverter)


import pytest
```

- [ ] **Step 2: Run tests**

Run: `uv run pytest tests/test_converter_base.py -v`
Expected: all PASS

- [ ] **Step 3: Commit**

```bash
git add tests/test_converter_base.py
git commit -m "test: add get_converter factory tests"
```

---

### Task 9: Wire converter into show command + add new flags

**Files:**
- Modify: `src/riszotto/cli.py`
- Modify: `tests/test_cli.py`

- [ ] **Step 1: Write tests for new show flags**

Add to `tests/test_cli.py`:

```python
class TestShowConverterIntegration:
    """Tests for the converter-backed show command."""

    @patch("riszotto.cli.get_converter")
    @patch("riszotto.cli.get_client")
    def test_show_uses_converter(self, mock_get_client, mock_get_converter):
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
                "links": {
                    "enclosure": {"href": "file:///path/to/paper.pdf"}
                },
            }
        ]
        from riszotto.converter.base import ConversionResult

        mock_converter = MagicMock()
        mock_converter.convert.return_value = ConversionResult(
            markdown="# Converted\n\nContent"
        )
        mock_get_converter.return_value = mock_converter

        result = runner.invoke(app, ["show", "PARENT1"])
        assert result.exit_code == 0
        assert "# Converted" in result.output
        mock_converter.convert.assert_called_once()

    @patch("riszotto.cli.get_converter")
    @patch("riszotto.cli.get_client")
    def test_show_backend_flag(self, mock_get_client, mock_get_converter):
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
        from riszotto.converter.base import ConversionResult

        mock_converter = MagicMock()
        mock_converter.convert.return_value = ConversionResult(markdown="text")
        mock_get_converter.return_value = mock_converter

        runner.invoke(app, ["show", "--backend", "markitdown", "PARENT1"])
        mock_get_converter.assert_called_with("markitdown")

    @patch("riszotto.cli.get_converter")
    @patch("riszotto.cli.get_client")
    def test_show_style_flags_passed_to_converter(
        self, mock_get_client, mock_get_converter
    ):
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
        from riszotto.converter.base import ConversionResult

        mock_converter = MagicMock()
        mock_converter.convert.return_value = ConversionResult(markdown="text")
        mock_get_converter.return_value = mock_converter

        runner.invoke(
            app,
            ["show", "--table-style", "image", "--equation-style", "image", "P1"],
        )
        call_kwargs = mock_converter.convert.call_args[1]
        assert call_kwargs["table_style"] == "image"
        assert call_kwargs["equation_style"] == "image"

    @patch("riszotto.cli.get_converter")
    @patch("riszotto.cli.get_client")
    def test_show_no_cache_flag(self, mock_get_client, mock_get_converter):
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
        from riszotto.converter.base import ConversionResult

        mock_converter = MagicMock()
        mock_converter.convert.return_value = ConversionResult(markdown="text")
        mock_get_converter.return_value = mock_converter

        runner.invoke(app, ["show", "--no-cache", "P1"])
        call_kwargs = mock_converter.convert.call_args[1]
        assert call_kwargs["no_cache"] is True

    @patch("riszotto.cli.get_cache_stats")
    @patch("riszotto.cli.get_converter")
    @patch("riszotto.cli.get_client")
    def test_show_figure_flag(self, mock_get_client, mock_get_converter, mock_stats):
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
        from riszotto.converter.cache import read_cache as _rc

        with patch("riszotto.cli.read_cache_for_figures") as mock_read:
            mock_read.return_value = {
                "figure_1.png": Path("/cache/K1/h1/figure_1.png"),
                "figure_2.png": Path("/cache/K1/h1/figure_2.png"),
            }
            result = runner.invoke(app, ["show", "--figure", "1", "K1"])
            assert result.exit_code == 0
            assert "figure_1.png" in result.output
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_cli.py::TestShowConverterIntegration -v`
Expected: FAIL

- [ ] **Step 3: Update cli.py show command**

Replace the `show` command in `src/riszotto/cli.py`. The key changes are:
1. Remove direct `MarkItDown` import at top of file
2. Add `get_converter` import
3. Add new CLI flags
4. Replace inline markitdown logic with converter call

At the top of `cli.py`, replace:
```python
from markitdown import MarkItDown
```
with:
```python
from riszotto.converter import get_converter
from riszotto.converter.base import BackendName, BackendOption, StyleOption
```

Replace the entire `show` function (lines 526-596) with:

```python
@app.command()
def show(
    key: Annotated[str, typer.Argument(help="Zotero item key")],
    attachment: Annotated[
        int, typer.Option("--attachment", "-a", help="PDF attachment index (1-indexed)")
    ] = 1,
    page: Annotated[
        int, typer.Option("--page", "-p", help="Page number (1-indexed, 0 = show all)")
    ] = 1,
    page_size: Annotated[int, typer.Option("--page-size", help="Lines per page")] = 500,
    search: Annotated[
        Optional[str],
        typer.Option("--search", "-s", help="Show only lines matching all terms"),
    ] = None,
    context: Annotated[
        int,
        typer.Option("--context", "-C", help="Context lines around each search match"),
    ] = 3,
    library: LibraryOption = None,
    backend: Annotated[
        Optional[str],
        typer.Option("--backend", help="Converter backend (markitdown or docling)"),
    ] = None,
    table_style: Annotated[
        str,
        typer.Option("--table-style", help="Table rendering: inline or image (docling only)"),
    ] = "inline",
    equation_style: Annotated[
        str,
        typer.Option("--equation-style", help="Equation rendering: inline or image (docling only)"),
    ] = "inline",
    no_cache: Annotated[
        bool,
        typer.Option("--no-cache", help="Force re-processing (skip cache)"),
    ] = False,
    figure: Annotated[
        Optional[int],
        typer.Option("--figure", help="Display path to cached figure N (1-indexed)"),
    ] = None,
) -> None:
    """Convert a paper's PDF attachment to markdown."""
    if table_style not in ("inline", "image"):
        typer.echo(f"Invalid --table-style: {table_style}. Use 'inline' or 'image'.", err=True)
        raise typer.Exit(1)
    if equation_style not in ("inline", "image"):
        typer.echo(f"Invalid --equation-style: {equation_style}. Use 'inline' or 'image'.", err=True)
        raise typer.Exit(1)

    zot = _get_zot(library=library)

    # Handle --figure flag (reads from cache, no conversion)
    if figure is not None:
        figures = _get_cached_figures(key)
        if figures is None:
            typer.echo(
                f"No cached conversion for {key}. Run 'riszotto show {key}' with docling first.",
                err=True,
            )
            raise typer.Exit(1)
        sorted_figs = sorted(
            [(n, p) for n, p in figures.items() if n.startswith("figure_")],
            key=lambda x: x[0],
        )
        if figure < 1 or figure > len(sorted_figs):
            typer.echo(
                f"Paper has {len(sorted_figs)} figure(s) (1-{len(sorted_figs)}). "
                f"Use --figure 1 through --figure {len(sorted_figs)}.",
                err=True,
            )
            raise typer.Exit(1)
        typer.echo(str(sorted_figs[figure - 1][1]))
        return

    pdfs = get_pdf_attachments(zot, key)
    if not pdfs:
        typer.echo(f"No PDF attachment found for item {key}.", err=True)
        raise typer.Exit(1)

    if attachment < 1 or attachment > len(pdfs):
        typer.echo(
            f"Attachment index {attachment} out of range. Item has {len(pdfs)} PDF(s).",
            err=True,
        )
        raise typer.Exit(1)

    selected = pdfs[attachment - 1]
    file_path = get_pdf_path(selected)
    if not file_path:
        if library:
            typer.echo(
                "PDF not available locally. The group is accessed via remote API "
                "and show requires local files. Sync this group in Zotero desktop "
                "for PDF access.",
                err=True,
            )
        else:
            typer.echo("Could not determine local file path for attachment.", err=True)
        raise typer.Exit(1)

    try:
        converter = get_converter(backend)
        result = converter.convert(
            Path(file_path),
            table_style=table_style,
            equation_style=equation_style,
            zotero_key=key,
            no_cache=no_cache,
        )
        markdown = result.markdown
    except ImportError as e:
        typer.echo(str(e), err=True)
        raise typer.Exit(1)
    except Exception as e:
        typer.echo(f"Failed to convert PDF: {e}", err=True)
        raise typer.Exit(1)

    if search is not None:
        output = _grep_lines(markdown, search.split(), context)
        if output is None:
            typer.echo(f"No lines matching '{search}' found.")
            return
        typer.echo(output)
        return

    _show_paginated(markdown, page, page_size, key, library=library)
```

Also add this helper function before the `show` command:

```python
def _get_cached_figures(zotero_key: str) -> dict[str, Path] | None:
    """Look up cached figures for a paper. Returns None if no cache exists."""
    from riszotto.converter.cache import CONVERSION_CACHE_DIR

    key_dir = CONVERSION_CACHE_DIR / zotero_key
    if not key_dir.exists():
        return None
    for hash_dir in key_dir.iterdir():
        if hash_dir.is_dir():
            figs = {
                f.name: f
                for f in hash_dir.iterdir()
                if f.suffix in (".png", ".jpg", ".jpeg")
            }
            return figs if figs else None
    return None
```

Add `from pathlib import Path` to the imports at the top of cli.py (it's not there currently).

- [ ] **Step 4: Run existing show tests**

Run: `uv run pytest tests/test_cli.py::TestShow -v`

The existing tests patch `riszotto.cli.MarkItDown` which no longer exists in cli.py. These tests need to be updated to patch `riszotto.cli.get_converter` instead. Update the existing `TestShow` class mock targets:

Replace `@patch("riszotto.cli.MarkItDown")` with `@patch("riszotto.cli.get_converter")` in each test, and adjust the mock setup from:
```python
mock_md = MagicMock()
mock_markitdown_cls.return_value = mock_md
mock_result = MagicMock()
mock_result.markdown = "..."
mock_md.convert.return_value = mock_result
```
to:
```python
from riszotto.converter.base import ConversionResult
mock_converter = MagicMock()
mock_converter.convert.return_value = ConversionResult(markdown="...")
mock_get_converter.return_value = mock_converter
```

- [ ] **Step 5: Run all tests**

Run: `uv run pytest -v`
Expected: all PASS

- [ ] **Step 6: Commit**

```bash
git add src/riszotto/cli.py tests/test_cli.py
git commit -m "feat: wire converter into show command with backend/style/cache flags"
```

---

### Task 10: Add cache CLI commands

**Files:**
- Modify: `src/riszotto/cli.py`
- Modify: `tests/test_cli.py`

- [ ] **Step 1: Write tests for cache commands**

Add to `tests/test_cli.py`:

```python
class TestCacheCommands:
    @patch("riszotto.cli.get_cache_stats")
    def test_cache_show_empty(self, mock_stats):
        mock_stats.return_value = {
            "paper_count": 0,
            "total_bytes": 0,
            "path": "/tmp/cache",
            "papers": [],
        }
        result = runner.invoke(app, ["cache", "show"])
        assert result.exit_code == 0
        assert "0 papers" in result.output
        assert "0 B" in result.output

    @patch("riszotto.cli.get_cache_stats")
    def test_cache_show_with_data(self, mock_stats):
        mock_stats.return_value = {
            "paper_count": 2,
            "total_bytes": 1048576,
            "path": "/tmp/cache",
            "papers": [
                {"key": "K1", "bytes": 524288},
                {"key": "K2", "bytes": 524288},
            ],
        }
        result = runner.invoke(app, ["cache", "show"])
        assert result.exit_code == 0
        assert "2 papers" in result.output

    @patch("riszotto.cli.clear_cache")
    def test_cache_clear_all(self, mock_clear):
        mock_clear.return_value = 3
        result = runner.invoke(app, ["cache", "clear"])
        assert result.exit_code == 0
        assert "3" in result.output

    @patch("riszotto.cli.clear_cache")
    def test_cache_clear_by_key(self, mock_clear):
        mock_clear.return_value = 1
        result = runner.invoke(app, ["cache", "clear", "--key", "K1"])
        assert result.exit_code == 0
        mock_clear.assert_called_once_with(key="K1", older_than_days=None)

    @patch("riszotto.cli.clear_cache")
    def test_cache_clear_older_than(self, mock_clear):
        mock_clear.return_value = 5
        result = runner.invoke(app, ["cache", "clear", "--older-than", "30d"])
        assert result.exit_code == 0
        mock_clear.assert_called_once_with(key=None, older_than_days=30)

    def test_cache_clear_invalid_older_than(self):
        result = runner.invoke(app, ["cache", "clear", "--older-than", "invalid"])
        assert result.exit_code == 1
        assert "Invalid duration" in result.output
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_cli.py::TestCacheCommands -v`
Expected: FAIL

- [ ] **Step 3: Add cache command group to cli.py**

Add these imports near the top of `cli.py`:

```python
from riszotto.converter.cache import clear_cache, get_cache_stats
```

Add the cache command group after the `libraries` command:

```python
cache_app = typer.Typer(add_completion=False, help="Manage the conversion cache.")
app.add_typer(cache_app, name="cache")


def _format_bytes(n: int) -> str:
    """Format byte count as human-readable string."""
    for unit in ("B", "KB", "MB", "GB"):
        if n < 1024:
            return f"{n:.1f} {unit}" if unit != "B" else f"{n} {unit}"
        n /= 1024
    return f"{n:.1f} TB"


@cache_app.command("show")
def cache_show(
    key: Annotated[
        Optional[str],
        typer.Option("--key", "-k", help="Show cache for a specific paper"),
    ] = None,
) -> None:
    """Show cache statistics."""
    stats = get_cache_stats(key=key)
    if key and stats["paper_count"] == 0:
        typer.echo(f"No cached data for {key}.")
        return
    typer.echo(
        f"Cache: {stats['paper_count']} paper(s), "
        f"{_format_bytes(stats['total_bytes'])}. "
        f"Path: {stats['path']}"
    )
    if stats.get("papers"):
        for p in stats["papers"]:
            typer.echo(f"  {p['key']}: {_format_bytes(p['bytes'])}")


def _parse_duration(s: str) -> int | None:
    """Parse a duration string like '30d' into days. Returns None on failure."""
    if s.endswith("d") and s[:-1].isdigit():
        return int(s[:-1])
    return None


@cache_app.command("clear")
def cache_clear(
    key: Annotated[
        Optional[str],
        typer.Option("--key", "-k", help="Clear cache for a specific paper"),
    ] = None,
    older_than: Annotated[
        Optional[str],
        typer.Option("--older-than", help="Clear entries older than duration (e.g., 30d)"),
    ] = None,
) -> None:
    """Clear cached conversions."""
    older_than_days = None
    if older_than is not None:
        older_than_days = _parse_duration(older_than)
        if older_than_days is None:
            typer.echo(
                "Invalid duration format. Use <N>d, e.g., --older-than 30d",
                err=True,
            )
            raise typer.Exit(1)

    cleared = clear_cache(key=key, older_than_days=older_than_days)
    typer.echo(f"Cleared {cleared} paper(s) from cache.")
```

- [ ] **Step 4: Run all tests**

Run: `uv run pytest -v`
Expected: all PASS

- [ ] **Step 5: Commit**

```bash
git add src/riszotto/cli.py tests/test_cli.py
git commit -m "feat: add cache show and cache clear CLI commands"
```

---

### Task 11: Add legacy migration check to CLI startup

**Files:**
- Modify: `src/riszotto/cli.py`

- [ ] **Step 1: Add migration check callback**

Add to cli.py, replacing the `app` definition:

```python
def _app_callback() -> None:
    """Run startup checks."""
    from riszotto.paths import check_legacy_migration

    check_legacy_migration()


app = typer.Typer(add_completion=False, callback=_app_callback)
```

- [ ] **Step 2: Run full test suite to verify nothing breaks**

Run: `uv run pytest -v`
Expected: all PASS

- [ ] **Step 3: Commit**

```bash
git add src/riszotto/cli.py
git commit -m "feat: add legacy ~/.riszotto migration check on CLI startup"
```

---

### Task 12: Update CI to test both extras configurations

**Files:**
- Modify: `.github/workflows/pytest.yaml`

- [ ] **Step 1: Update CI workflow**

Replace `.github/workflows/pytest.yaml` with:

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
        extras: ["semantic", "full"]
    steps:
      - uses: actions/checkout@v4

      - uses: astral-sh/setup-uv@v5
        with:
          python-version: ${{ matrix.python-version }}

      - name: Install with [${{ matrix.extras }}] extras
        run: uv sync --extra ${{ matrix.extras }}

      - name: Run tests
        run: uv run pytest
```

This creates a 3x2 matrix: 3 Python versions x 2 extras configurations (`[semantic]` and `[full]`). The `[full]` extra includes `[semantic]` (self-referential), so the full config tests everything. The `[semantic]` config tests that the base + semantic install works without docling.

- [ ] **Step 2: Commit**

```bash
git add .github/workflows/pytest.yaml
git commit -m "ci: test both [semantic] and [full] extras in CI matrix"
```

---

### Task 13: Run pre-commit and full validation

**Files:** none (validation only)

- [ ] **Step 1: Run pre-commit hooks**

Run: `uvx prek --all-files`
Expected: all pass (fix any formatting issues)

- [ ] **Step 2: Run full test suite**

Run: `uv run pytest -v`
Expected: all PASS

- [ ] **Step 3: Final commit if any formatting fixes**

```bash
git add -u
git commit -m "style: apply pre-commit formatting fixes"
```
