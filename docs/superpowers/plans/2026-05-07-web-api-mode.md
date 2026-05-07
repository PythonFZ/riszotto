# Zotero Web API Mode Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Enable riszotto to operate fully against the Zotero Web API (including `show` for synced PDF attachments), without a running local Zotero desktop.

**Architecture:** Migrate `config.py` to `pydantic-settings` with a `RISZOTTO_ZOTERO_*` env-var prefix and a new `mode = "auto" | "local" | "web"` field. Collapse the personal/group library client-selection split in `client.py: get_client()` into a single mode-driven rule. Add a new content-addressed PDF cache (`cache_dir/pdfs/{md5}.pdf`) and a `resolve_pdf_path()` helper that downloads attachments via `zot.dump()` on cache miss. The existing markdown cache (`converter/cache.py`) is untouched.

**Tech Stack:** Python 3.11+, `pydantic-settings>=2.13.1` (already a dep), `pyzotero>=1.5.0`, `typer`, `pytest`. uv for package management. Tests use `unittest.mock` patches and `tmp_path` fixtures.

**Constraints (hard):**
- **No migration shim or backwards-compat for the renamed env vars.** Old `ZOTERO_API_KEY` / `ZOTERO_USER_ID` are dropped clean. Affected users update their shell config; documented in CHANGELOG/README only.
- All tests use `uv run pytest`. Do not invoke `pytest` directly.
- Do not modify any test marked `@pytest.mark.protected`.
- Do not introduce a Python builtin shadow — the new permission-error class is named `ZoteroPermissionError`, not `PermissionError`.

**Spec:** `docs/superpowers/specs/2026-05-07-web-api-mode-design.md`

---

## File Structure

| File | Status | Responsibility |
|------|--------|----------------|
| `src/riszotto/config.py` | Modify | Pydantic-settings `Settings` class. Public API `load_config() -> Config` preserved (Config retained as a `pydantic.BaseModel`-derived alias for callers). Add `mode` field. |
| `src/riszotto/paths.py` | Modify | Add `PDF_CACHE_DIR = cache_dir() / "pdfs"`. |
| `src/riszotto/pdf_cache.py` | **Create** | Content-addressed PDF cache: `pdf_cache_path`, `read_pdf_cache`, `download_to_pdf_cache`, `clear_pdf_cache`, `pdf_cache_stats`. |
| `src/riszotto/client.py` | Modify | Refactor `get_client()` for mode-driven selection. Add `ConfigError`, `PdfNotOnStorageError`, `ZoteroPermissionError`. Add `resolve_pdf_path()`. Keep `get_pdf_path()` as an internal helper. |
| `src/riszotto/cli.py` | Modify | Replace `get_pdf_path()` call in `show` with `resolve_pdf_path()`. Surface new error classes. Extend `cache_show` / `cache_clear` for the PDF cache. |
| `tests/test_config.py` | Modify | Update env-var names to `RISZOTTO_ZOTERO_*`. Add tests for `mode`. |
| `tests/test_client.py` | Modify | Update `TestGetClient` for mode-driven behavior. Add tests for `resolve_pdf_path` and the new error classes. |
| `tests/test_pdf_cache.py` | **Create** | Unit tests for the PDF cache module. |
| `tests/test_paths.py` | Modify | Add a one-line assertion for `PDF_CACHE_DIR`. |
| `tests/test_cli.py` | Modify | Add show-error-path tests + cache-show/clear coverage of PDF cache. |
| `README.md` | Modify | Document `mode` config and new env-var names. |
| `CHANGELOG.md` | **Create** | Initial entry for the env-var rename and web-API mode. |

---

## Task 1: Migrate `config.py` to pydantic-settings

**Files:**
- Modify: `src/riszotto/config.py` (full rewrite of body, public API preserved)
- Modify: `tests/test_config.py` (rename env-var references, add `mode` tests)

- [ ] **Step 1.1: Write the failing tests in `tests/test_config.py`**

Replace the entire file with the following. The new tests use `RISZOTTO_ZOTERO_*` env vars and add `mode` coverage.

```python
import os
from unittest.mock import patch

import pytest

from riszotto.config import Config, load_config


class TestConfig:
    def test_defaults_when_no_file_no_env(self, tmp_path):
        with patch("riszotto.config.CONFIG_PATH", tmp_path / "config.toml"):
            config = load_config()
        assert config.api_key is None
        assert config.user_id is None
        assert config.mode == "auto"

    def test_reads_toml_file(self, tmp_path):
        config_file = tmp_path / "config.toml"
        config_file.write_text(
            '[zotero]\napi_key = "KEY123"\nuser_id = "456"\nmode = "web"\n'
        )
        with patch("riszotto.config.CONFIG_PATH", config_file):
            config = load_config()
        assert config.api_key == "KEY123"
        assert config.user_id == "456"
        assert config.mode == "web"

    def test_env_vars_override_file(self, tmp_path):
        config_file = tmp_path / "config.toml"
        config_file.write_text(
            '[zotero]\napi_key = "file_key"\nuser_id = "file_id"\nmode = "local"\n'
        )
        with (
            patch("riszotto.config.CONFIG_PATH", config_file),
            patch.dict(
                os.environ,
                {
                    "RISZOTTO_ZOTERO_API_KEY": "env_key",
                    "RISZOTTO_ZOTERO_USER_ID": "env_id",
                    "RISZOTTO_ZOTERO_MODE": "web",
                },
                clear=False,
            ),
        ):
            config = load_config()
        assert config.api_key == "env_key"
        assert config.user_id == "env_id"
        assert config.mode == "web"

    def test_env_vars_without_file(self, tmp_path):
        with (
            patch("riszotto.config.CONFIG_PATH", tmp_path / "config.toml"),
            patch.dict(
                os.environ, {"RISZOTTO_ZOTERO_API_KEY": "env_only"}, clear=False
            ),
        ):
            config = load_config()
        assert config.api_key == "env_only"
        assert config.user_id is None
        assert config.mode == "auto"

    def test_partial_toml(self, tmp_path):
        config_file = tmp_path / "config.toml"
        config_file.write_text('[zotero]\napi_key = "KEY123"\n')
        with patch("riszotto.config.CONFIG_PATH", config_file):
            config = load_config()
        assert config.api_key == "KEY123"
        assert config.user_id is None
        assert config.mode == "auto"

    def test_empty_toml(self, tmp_path):
        config_file = tmp_path / "config.toml"
        config_file.write_text("")
        with patch("riszotto.config.CONFIG_PATH", config_file):
            config = load_config()
        assert config.api_key is None
        assert config.user_id is None
        assert config.mode == "auto"

    def test_invalid_mode_raises(self, tmp_path):
        config_file = tmp_path / "config.toml"
        config_file.write_text('[zotero]\nmode = "bogus"\n')
        with patch("riszotto.config.CONFIG_PATH", config_file):
            with pytest.raises(Exception):  # pydantic ValidationError
                load_config()

    def test_old_env_vars_are_ignored(self, tmp_path):
        """ZOTERO_API_KEY (no RISZOTTO_ prefix) must NOT be read."""
        with (
            patch("riszotto.config.CONFIG_PATH", tmp_path / "config.toml"),
            patch.dict(
                os.environ,
                {"ZOTERO_API_KEY": "old_name", "ZOTERO_USER_ID": "old_id"},
                clear=False,
            ),
        ):
            config = load_config()
        assert config.api_key is None
        assert config.user_id is None

    def test_has_remote_credentials(self):
        c = Config(api_key="k", user_id="u")
        assert c.has_remote_credentials is True
        assert Config(api_key="k").has_remote_credentials is False
        assert Config(user_id="u").has_remote_credentials is False
        assert Config().has_remote_credentials is False
```

- [ ] **Step 1.2: Run the tests, verify they fail**

```
uv run pytest tests/test_config.py -v
```

Expected: failures on every test. Either `mode` attribute missing on `Config`, or env-var names not picked up, or `Config()` constructor signature mismatch.

- [ ] **Step 1.3: Rewrite `src/riszotto/config.py`**

Replace the file's contents with:

```python
"""Configuration loading via pydantic-settings.

Reads from defaults, then ``~/.riszotto/config.toml`` ([zotero] section),
then environment variables prefixed with ``RISZOTTO_ZOTERO_``.
"""

from __future__ import annotations

import tomllib
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel
from pydantic_settings import (
    BaseSettings,
    PydanticBaseSettingsSource,
    SettingsConfigDict,
)

from riszotto.paths import CONFIG_PATH

Mode = Literal["auto", "local", "web"]


class Config(BaseModel):
    """Zotero connection configuration (public API consumed by client/cli)."""

    api_key: str | None = None
    user_id: str | None = None
    mode: Mode = "auto"

    @property
    def has_remote_credentials(self) -> bool:
        """Check if both API key and user ID are configured."""
        return self.api_key is not None and self.user_id is not None


class _ZoteroTomlSource(PydanticBaseSettingsSource):
    """Read the ``[zotero]`` section of CONFIG_PATH as a flat dict."""

    def __init__(self, settings_cls, toml_path: Path):
        super().__init__(settings_cls)
        self._toml_path = toml_path

    def get_field_value(self, field, field_name):  # required override
        data = self._load()
        if field_name in data:
            return data[field_name], field_name, False
        return None, field_name, False

    def __call__(self) -> dict[str, Any]:
        return self._load()

    def _load(self) -> dict[str, Any]:
        if not self._toml_path.is_file():
            return {}
        with open(self._toml_path, "rb") as f:
            data = tomllib.load(f)
        zotero = data.get("zotero", {})
        return {k: v for k, v in zotero.items() if k in {"api_key", "user_id", "mode"}}


class _Settings(BaseSettings):
    """Internal pydantic-settings model. Use ``load_config()`` instead."""

    api_key: str | None = None
    user_id: str | None = None
    mode: Mode = "auto"

    model_config = SettingsConfigDict(
        env_prefix="RISZOTTO_ZOTERO_",
        case_sensitive=False,
        extra="ignore",
    )

    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls,
        init_settings,
        env_settings,
        dotenv_settings,
        file_secret_settings,
    ):
        # Precedence (highest first): init kwargs, env vars, TOML file, defaults.
        return (
            init_settings,
            env_settings,
            _ZoteroTomlSource(settings_cls, CONFIG_PATH),
        )


def load_config() -> Config:
    """Load the active configuration.

    Precedence (lowest to highest): defaults < TOML file < environment variables.
    """
    s = _Settings()
    return Config(api_key=s.api_key, user_id=s.user_id, mode=s.mode)
```

- [ ] **Step 1.4: Run the tests, verify they pass**

```
uv run pytest tests/test_config.py -v
```

Expected: all tests pass.

- [ ] **Step 1.5: Run the full suite to catch regressions in callers**

```
uv run pytest -q
```

Expected: only failures should be in `test_client.py::TestGetClient` (the next task fixes that). Note any other failures and address them in this task before continuing — they likely indicate a caller still using the old env var names.

- [ ] **Step 1.6: Commit**

```
git add src/riszotto/config.py tests/test_config.py
git commit -m "feat(config): migrate to pydantic-settings with RISZOTTO_ prefix and mode field"
```

---

## Task 2: Mode-driven `get_client()` and `ConfigError`

**Files:**
- Modify: `src/riszotto/client.py:88-156` (`get_client` + new error class)
- Modify: `tests/test_client.py` (`TestGetClient` rewrite)

- [ ] **Step 2.1: Write failing tests in `tests/test_client.py`**

Replace the existing `TestGetClient` class with:

```python
class TestGetClient:
    def _stub_config(self, monkeypatch, mode, api_key=None, user_id=None):
        from riszotto.config import Config

        monkeypatch.setattr(
            "riszotto.client.load_config",
            lambda: Config(api_key=api_key, user_id=user_id, mode=mode),
        )

    def test_auto_no_creds_returns_local(self, monkeypatch):
        self._stub_config(monkeypatch, mode="auto")
        with patch("riszotto.client.zotero.Zotero") as mock_zotero:
            get_client()
            mock_zotero.assert_called_once_with(
                library_id="0", library_type="user", api_key=None, local=True
            )

    def test_auto_with_creds_returns_remote(self, monkeypatch):
        self._stub_config(monkeypatch, mode="auto", api_key="k", user_id="123")
        with patch("riszotto.client.zotero.Zotero") as mock_zotero:
            get_client()
            mock_zotero.assert_called_once_with(
                library_id="123", library_type="user", api_key="k"
            )

    def test_local_forces_local_even_with_creds(self, monkeypatch):
        self._stub_config(monkeypatch, mode="local", api_key="k", user_id="123")
        with patch("riszotto.client.zotero.Zotero") as mock_zotero:
            get_client()
            mock_zotero.assert_called_once_with(
                library_id="0", library_type="user", api_key=None, local=True
            )

    def test_web_with_creds_returns_remote(self, monkeypatch):
        self._stub_config(monkeypatch, mode="web", api_key="k", user_id="123")
        with patch("riszotto.client.zotero.Zotero") as mock_zotero:
            get_client()
            mock_zotero.assert_called_once_with(
                library_id="123", library_type="user", api_key="k"
            )

    def test_web_without_creds_raises_config_error(self, monkeypatch):
        from riszotto.client import ConfigError

        self._stub_config(monkeypatch, mode="web")
        with pytest.raises(ConfigError, match="api_key"):
            get_client()
```

Also add `ConfigError` to the imports at the top of the test file:

```python
from riszotto.client import (
    AmbiguousLibraryError,
    ConfigError,
    DEFAULT_BIBTEX_EXCLUDE,
    LibraryNotFoundError,
    ...
)
```

- [ ] **Step 2.2: Run the tests, verify they fail**

```
uv run pytest tests/test_client.py::TestGetClient -v
```

Expected: ImportError on `ConfigError`, or assertion failures because `get_client()` always returns local.

- [ ] **Step 2.3: Add `ConfigError` and refactor `get_client()` in `src/riszotto/client.py`**

After the existing `class AmbiguousLibraryError(Exception):` block, add:

```python
class ConfigError(Exception):
    """Raised when configuration is incomplete or invalid for the requested mode."""
```

Replace the existing `def get_client(...)` function (currently lines ~88-156) with:

```python
def get_client(library: str | None = None) -> zotero.Zotero:
    """Create a pyzotero client, optionally targeting a group library.

    Selection is driven by ``config.mode``:

    - ``"local"``: always local (port 23119).
    - ``"web"``: always remote; raises ``ConfigError`` if creds missing.
    - ``"auto"`` (default): remote when creds present, else local.

    Parameters
    ----------
    library : str or None
        Group name or numeric ID. If None, returns the personal library client.

    Returns
    -------
    zotero.Zotero
        A configured pyzotero client.

    Raises
    ------
    ConfigError
        If ``mode="web"`` and credentials are not configured.
    LibraryNotFoundError
        If the requested group cannot be found in the resolved client.
    AmbiguousLibraryError
        If the name matches multiple groups.
    """
    config = load_config()
    use_web = _resolve_use_web(config)

    if library is None:
        return _make_personal_client(config, use_web)

    base = _make_personal_client(config, use_web)
    groups = base.groups()
    match = find_group(groups, library)
    if match is None:
        available = [g["data"]["name"] for g in groups]
        raise LibraryNotFoundError(
            f"Group '{library}' not found. Available: {available}"
        )

    if use_web:
        return zotero.Zotero(
            library_id=str(match["id"]),
            library_type="group",
            api_key=config.api_key,
        )
    return zotero.Zotero(
        library_id=str(match["id"]),
        library_type="group",
        local=True,
    )


def _resolve_use_web(config) -> bool:
    """Return True if the resolved mode wants the web API."""
    if config.mode == "local":
        return False
    if config.mode == "web":
        if not config.has_remote_credentials:
            raise ConfigError(
                "Web mode requires `api_key` and `user_id`. "
                "Configure in ~/.riszotto/config.toml [zotero] or set "
                "RISZOTTO_ZOTERO_API_KEY and RISZOTTO_ZOTERO_USER_ID."
            )
        return True
    # auto
    return config.has_remote_credentials


def _make_personal_client(config, use_web: bool) -> zotero.Zotero:
    if use_web:
        return zotero.Zotero(
            library_id=config.user_id,
            library_type="user",
            api_key=config.api_key,
        )
    return zotero.Zotero(
        library_id="0",
        library_type="user",
        api_key=None,
        local=True,
    )
```

- [ ] **Step 2.4: Run the targeted tests**

```
uv run pytest tests/test_client.py::TestGetClient -v
```

Expected: all five tests pass.

- [ ] **Step 2.5: Run the full suite**

```
uv run pytest -q
```

Expected: green. If `test_cli.py` has tests that mock `get_client`, they should still work since the public signature is unchanged.

- [ ] **Step 2.6: Commit**

```
git add src/riszotto/client.py tests/test_client.py
git commit -m "feat(client): mode-driven get_client; add ConfigError"
```

---

## Task 3: `paths.py: PDF_CACHE_DIR`

**Files:**
- Modify: `src/riszotto/paths.py`
- Modify: `tests/test_paths.py`

- [ ] **Step 3.1: Add the failing test in `tests/test_paths.py`**

Append to the file:

```python
def test_pdf_cache_dir_under_cache_dir():
    from riszotto.paths import PDF_CACHE_DIR, cache_dir

    assert PDF_CACHE_DIR == cache_dir() / "pdfs"
```

- [ ] **Step 3.2: Run, verify it fails**

```
uv run pytest tests/test_paths.py::test_pdf_cache_dir_under_cache_dir -v
```

Expected: ImportError on `PDF_CACHE_DIR`.

- [ ] **Step 3.3: Add the constant**

In `src/riszotto/paths.py`, after the existing `CONVERSION_CACHE_DIR = ...` line, add:

```python
PDF_CACHE_DIR = cache_dir() / "pdfs"
```

- [ ] **Step 3.4: Run, verify it passes**

```
uv run pytest tests/test_paths.py -v
```

Expected: green.

- [ ] **Step 3.5: Commit**

```
git add src/riszotto/paths.py tests/test_paths.py
git commit -m "feat(paths): add PDF_CACHE_DIR"
```

---

## Task 4: `pdf_cache.py` module

**Files:**
- Create: `src/riszotto/pdf_cache.py`
- Create: `tests/test_pdf_cache.py`

- [ ] **Step 4.1: Write failing tests in `tests/test_pdf_cache.py`**

```python
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from riszotto.pdf_cache import (
    clear_pdf_cache,
    download_to_pdf_cache,
    pdf_cache_path,
    pdf_cache_stats,
    read_pdf_cache,
)


class TestPdfCachePath:
    def test_path_is_md5_dot_pdf_under_cache_dir(self, tmp_path):
        with patch("riszotto.pdf_cache.PDF_CACHE_DIR", tmp_path):
            assert pdf_cache_path("abc123") == tmp_path / "abc123.pdf"


class TestReadPdfCache:
    def test_returns_none_when_missing(self, tmp_path):
        with patch("riszotto.pdf_cache.PDF_CACHE_DIR", tmp_path):
            assert read_pdf_cache("abc123") is None

    def test_returns_path_when_present(self, tmp_path):
        (tmp_path / "abc123.pdf").write_bytes(b"%PDF-1.4")
        with patch("riszotto.pdf_cache.PDF_CACHE_DIR", tmp_path):
            assert read_pdf_cache("abc123") == tmp_path / "abc123.pdf"


class TestDownloadToPdfCache:
    def _attachment(self, md5="abc123", filename="paper.pdf"):
        return {
            "key": "ITEMKEY1",
            "data": {"md5": md5, "filename": filename},
        }

    def test_downloads_when_missing_then_returns_path(self, tmp_path):
        zot = MagicMock()

        def fake_dump(item_key, filename, path):
            Path(path, filename).write_bytes(b"%PDF-1.4 downloaded")
            return str(Path(path, filename))

        zot.dump.side_effect = fake_dump

        with patch("riszotto.pdf_cache.PDF_CACHE_DIR", tmp_path):
            result = download_to_pdf_cache(zot, self._attachment())

        assert result == tmp_path / "abc123.pdf"
        assert result.read_bytes() == b"%PDF-1.4 downloaded"
        zot.dump.assert_called_once()

    def test_uses_cache_when_present(self, tmp_path):
        (tmp_path / "abc123.pdf").write_bytes(b"%PDF-1.4 cached")
        zot = MagicMock()
        with patch("riszotto.pdf_cache.PDF_CACHE_DIR", tmp_path):
            result = download_to_pdf_cache(zot, self._attachment())
        assert result == tmp_path / "abc123.pdf"
        zot.dump.assert_not_called()

    def test_raises_when_md5_missing(self, tmp_path):
        zot = MagicMock()
        bad = {"key": "ITEMKEY1", "data": {"md5": None, "filename": "x.pdf"}}
        with patch("riszotto.pdf_cache.PDF_CACHE_DIR", tmp_path):
            with pytest.raises(ValueError, match="md5"):
                download_to_pdf_cache(zot, bad)


class TestClearPdfCache:
    def test_removes_all_pdfs(self, tmp_path):
        (tmp_path / "a.pdf").write_bytes(b"x")
        (tmp_path / "b.pdf").write_bytes(b"y")
        (tmp_path / "not-pdf.txt").write_text("keep me")
        with patch("riszotto.pdf_cache.PDF_CACHE_DIR", tmp_path):
            n = clear_pdf_cache()
        assert n == 2
        assert not (tmp_path / "a.pdf").exists()
        assert (tmp_path / "not-pdf.txt").exists()

    def test_returns_zero_when_dir_missing(self, tmp_path):
        missing = tmp_path / "nope"
        with patch("riszotto.pdf_cache.PDF_CACHE_DIR", missing):
            assert clear_pdf_cache() == 0


class TestPdfCacheStats:
    def test_reports_count_and_bytes(self, tmp_path):
        (tmp_path / "a.pdf").write_bytes(b"abcd")
        (tmp_path / "b.pdf").write_bytes(b"efghi")
        (tmp_path / "x.txt").write_text("ignored")
        with patch("riszotto.pdf_cache.PDF_CACHE_DIR", tmp_path):
            stats = pdf_cache_stats()
        assert stats == {
            "count": 2,
            "total_bytes": 4 + 5,
            "path": str(tmp_path),
        }

    def test_empty_when_dir_missing(self, tmp_path):
        missing = tmp_path / "nope"
        with patch("riszotto.pdf_cache.PDF_CACHE_DIR", missing):
            stats = pdf_cache_stats()
        assert stats["count"] == 0
        assert stats["total_bytes"] == 0
```

- [ ] **Step 4.2: Run, verify tests fail**

```
uv run pytest tests/test_pdf_cache.py -v
```

Expected: ImportError because `riszotto.pdf_cache` does not exist.

- [ ] **Step 4.3: Create `src/riszotto/pdf_cache.py`**

```python
"""Content-addressed cache of PDF attachments downloaded from the Zotero web API.

Files are stored at ``PDF_CACHE_DIR / {md5}.pdf`` where md5 is the value
exposed by the Zotero API on synced storage attachments.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from riszotto.paths import PDF_CACHE_DIR


def pdf_cache_path(md5: str) -> Path:
    """Return the on-disk path for a given content hash."""
    return PDF_CACHE_DIR / f"{md5}.pdf"


def read_pdf_cache(md5: str) -> Path | None:
    """Return the cached PDF path if it exists, else ``None``."""
    p = pdf_cache_path(md5)
    return p if p.is_file() else None


def download_to_pdf_cache(zot: Any, attachment: dict[str, Any]) -> Path:
    """Ensure the attachment's PDF is in the cache; return the path.

    Parameters
    ----------
    zot : pyzotero.zotero.Zotero
        Configured pyzotero client (web mode).
    attachment : dict
        Zotero attachment item (must have ``data.md5`` and ``data.filename``).

    Returns
    -------
    Path
        Path to the cached PDF.

    Raises
    ------
    ValueError
        If ``attachment.data.md5`` is missing.
    """
    data = attachment.get("data", {})
    md5 = data.get("md5")
    if not md5:
        raise ValueError("attachment has no md5; file is not on Zotero storage")

    cached = read_pdf_cache(md5)
    if cached is not None:
        return cached

    PDF_CACHE_DIR.mkdir(parents=True, exist_ok=True)

    item_key = attachment["key"]
    cache_filename = f"{md5}.pdf"
    zot.dump(item_key, cache_filename, str(PDF_CACHE_DIR))

    return pdf_cache_path(md5)


def clear_pdf_cache() -> int:
    """Remove all cached PDFs. Return the count of files removed."""
    if not PDF_CACHE_DIR.exists():
        return 0
    n = 0
    for p in PDF_CACHE_DIR.iterdir():
        if p.is_file() and p.suffix == ".pdf":
            p.unlink()
            n += 1
    return n


def pdf_cache_stats() -> dict[str, Any]:
    """Return ``{count, total_bytes, path}`` for the PDF cache."""
    if not PDF_CACHE_DIR.exists():
        return {"count": 0, "total_bytes": 0, "path": str(PDF_CACHE_DIR)}
    count = 0
    total = 0
    for p in PDF_CACHE_DIR.iterdir():
        if p.is_file() and p.suffix == ".pdf":
            count += 1
            total += p.stat().st_size
    return {"count": count, "total_bytes": total, "path": str(PDF_CACHE_DIR)}
```

- [ ] **Step 4.4: Run the tests**

```
uv run pytest tests/test_pdf_cache.py -v
```

Expected: green.

- [ ] **Step 4.5: Commit**

```
git add src/riszotto/pdf_cache.py tests/test_pdf_cache.py
git commit -m "feat(pdf_cache): content-addressed cache for downloaded PDFs"
```

---

## Task 5: Errors + `resolve_pdf_path()` in `client.py`

**Files:**
- Modify: `src/riszotto/client.py` (new error classes + `resolve_pdf_path`)
- Modify: `tests/test_client.py` (new test class)

- [ ] **Step 5.1: Write failing tests in `tests/test_client.py`**

Append to the file:

```python
class TestResolvePdfPath:
    def _attachment(
        self,
        *,
        md5="abc123",
        filename="paper.pdf",
        enclosure_href=None,
    ):
        att = {
            "key": "ITEMKEY1",
            "data": {"md5": md5, "filename": filename},
        }
        if enclosure_href is not None:
            att["links"] = {"enclosure": {"href": enclosure_href}}
        return att

    def test_returns_local_path_when_enclosure_exists(self, tmp_path):
        from riszotto.client import resolve_pdf_path

        local = tmp_path / "paper.pdf"
        local.write_bytes(b"%PDF-1.4")
        zot = MagicMock()

        result = resolve_pdf_path(
            zot, self._attachment(enclosure_href=f"file://{local}")
        )
        assert result == local
        zot.dump.assert_not_called()

    def test_falls_through_when_enclosure_path_missing(self, tmp_path):
        from riszotto.client import resolve_pdf_path

        zot = MagicMock()

        def fake_dump(item_key, filename, path):
            Path(path, filename).write_bytes(b"%PDF-1.4")
            return str(Path(path, filename))

        zot.dump.side_effect = fake_dump

        with patch("riszotto.pdf_cache.PDF_CACHE_DIR", tmp_path):
            result = resolve_pdf_path(
                zot,
                self._attachment(enclosure_href="file:///nonexistent/missing.pdf"),
            )
        assert result == tmp_path / "abc123.pdf"
        zot.dump.assert_called_once()

    def test_uses_pdf_cache_on_hit(self, tmp_path):
        from riszotto.client import resolve_pdf_path

        cached = tmp_path / "abc123.pdf"
        cached.write_bytes(b"%PDF-1.4")
        zot = MagicMock()

        with patch("riszotto.pdf_cache.PDF_CACHE_DIR", tmp_path):
            result = resolve_pdf_path(zot, self._attachment())
        assert result == cached
        zot.dump.assert_not_called()

    def test_md5_none_raises_pdf_not_on_storage(self, tmp_path):
        from riszotto.client import PdfNotOnStorageError, resolve_pdf_path

        zot = MagicMock()
        att = self._attachment(md5=None)
        att["data"]["url"] = "https://example.com/paper.pdf"

        with patch("riszotto.pdf_cache.PDF_CACHE_DIR", tmp_path):
            with pytest.raises(PdfNotOnStorageError) as exc_info:
                resolve_pdf_path(zot, att)
        assert "ITEMKEY1" in str(exc_info.value)
        assert "https://example.com/paper.pdf" in str(exc_info.value)

    def test_dump_404_raises_pdf_not_on_storage(self, tmp_path):
        from pyzotero.zotero_errors import ResourceNotFoundError

        from riszotto.client import PdfNotOnStorageError, resolve_pdf_path

        zot = MagicMock()
        zot.dump.side_effect = ResourceNotFoundError("Not found")

        with patch("riszotto.pdf_cache.PDF_CACHE_DIR", tmp_path):
            with pytest.raises(PdfNotOnStorageError):
                resolve_pdf_path(zot, self._attachment())

    def test_dump_403_raises_zotero_permission_error(self, tmp_path):
        from pyzotero.zotero_errors import UserNotAuthorisedError

        from riszotto.client import ZoteroPermissionError, resolve_pdf_path

        zot = MagicMock()
        zot.dump.side_effect = UserNotAuthorisedError("forbidden")

        with patch("riszotto.pdf_cache.PDF_CACHE_DIR", tmp_path):
            with pytest.raises(ZoteroPermissionError):
                resolve_pdf_path(zot, self._attachment())
```

Verify the actual exception class names exist in pyzotero before relying on them:

```
uv run python -c "from pyzotero.zotero_errors import ResourceNotFoundError, UserNotAuthorisedError; print('ok')"
```

If either name is wrong (older pyzotero), substitute the correct class found in the local `.venv/lib/python3.11/site-packages/pyzotero/zotero_errors.py` and update the test imports and the implementation in step 5.3 to match.

- [ ] **Step 5.2: Run, verify tests fail**

```
uv run pytest tests/test_client.py::TestResolvePdfPath -v
```

Expected: ImportError on `resolve_pdf_path`, `PdfNotOnStorageError`, `ZoteroPermissionError`.

- [ ] **Step 5.3: Add error classes and `resolve_pdf_path` to `src/riszotto/client.py`**

After the existing `class ConfigError(Exception):` block (added in Task 2), add:

```python
class PdfNotOnStorageError(Exception):
    """Raised when an attachment's PDF cannot be retrieved via the web API.

    Either ``data.md5`` is ``None`` (file never uploaded to Zotero storage)
    or the storage download returns 404 (deleted or quota-exceeded).
    """

    def __init__(self, attachment_key: str, source_url: str | None = None):
        self.attachment_key = attachment_key
        self.source_url = source_url
        msg = (
            f"PDF for {attachment_key} is not on Zotero storage "
            "(file sync disabled or metadata-only attachment)."
        )
        if source_url:
            msg += f" Source URL: {source_url}."
        msg += (
            " Run riszotto with `mode = \"local\"` and Zotero desktop running, "
            "or enable file sync in Zotero preferences."
        )
        super().__init__(msg)


class ZoteroPermissionError(Exception):
    """Raised when the API key lacks permission to download a file."""
```

Add the new top-level imports near the top of the file (after the existing pyzotero imports):

```python
from pathlib import Path

from pyzotero.zotero_errors import ResourceNotFoundError, UserNotAuthorisedError
```

(If your installed pyzotero uses different class names, adjust per step 5.1's check.)

After the existing `def get_pdf_path(...)` function, add:

```python
def resolve_pdf_path(zot: zotero.Zotero, attachment: dict[str, Any]) -> Path:
    """Return a local Path to the attachment's PDF, downloading if needed.

    Resolution order:

    1. If the attachment's ``links.enclosure`` is a ``file://`` URL pointing at
       an existing file (local Zotero), return it.
    2. Otherwise consult the on-disk PDF cache; download via ``zot.dump`` on miss.

    Raises
    ------
    PdfNotOnStorageError
        If ``attachment.data.md5`` is missing or the download returns 404.
    ZoteroPermissionError
        If the API key lacks file-read permission for the library.
    """
    from riszotto.pdf_cache import download_to_pdf_cache  # local import: avoid cycle

    local = get_pdf_path(attachment)
    if local:
        local_path = Path(local)
        if local_path.is_file():
            return local_path

    md5 = attachment.get("data", {}).get("md5")
    if not md5:
        raise PdfNotOnStorageError(
            attachment_key=attachment.get("key", "<unknown>"),
            source_url=attachment.get("data", {}).get("url"),
        )

    try:
        return download_to_pdf_cache(zot, attachment)
    except ResourceNotFoundError:
        raise PdfNotOnStorageError(
            attachment_key=attachment.get("key", "<unknown>"),
            source_url=attachment.get("data", {}).get("url"),
        )
    except UserNotAuthorisedError as e:
        raise ZoteroPermissionError(
            "API key lacks file-read permission for this library. "
            "Update key permissions at zotero.org/settings/keys."
        ) from e
```

- [ ] **Step 5.4: Run the new tests**

```
uv run pytest tests/test_client.py::TestResolvePdfPath -v
```

Expected: green.

- [ ] **Step 5.5: Run the full suite**

```
uv run pytest -q
```

Expected: green except for any `cli.py` show tests that already exist and reference the old `get_pdf_path`-based error path. Note these — they will be updated in Task 6.

- [ ] **Step 5.6: Commit**

```
git add src/riszotto/client.py tests/test_client.py
git commit -m "feat(client): resolve_pdf_path with web-API download support"
```

---

## Task 6: Wire `resolve_pdf_path()` into `cli.py: show`

**Files:**
- Modify: `src/riszotto/cli.py:670-683` (the `get_pdf_path` block in `show`)
- Modify: `tests/test_cli.py` (new tests for the error paths)

- [ ] **Step 6.1: Identify the existing show-error tests**

Run:

```
uv run pytest tests/test_cli.py -k show --collect-only -q
```

Make a note of any tests that exercise the "PDF not available locally" branch — they will need their assertions adjusted to match the new error messages.

- [ ] **Step 6.2: Write new failing tests in `tests/test_cli.py`**

Append to the file (after the existing show-related tests):

```python
class TestShowResolvePdfPathErrors:
    def test_pdf_not_on_storage_surfaces_to_stderr(self, monkeypatch, capsys):
        from typer.testing import CliRunner

        from riszotto.cli import app
        from riszotto.client import PdfNotOnStorageError

        runner = CliRunner()

        zot = MagicMock()
        monkeypatch.setattr("riszotto.cli.get_client", lambda library=None: zot)
        monkeypatch.setattr(
            "riszotto.cli.get_pdf_attachments",
            lambda zot, key: [{"key": "A", "data": {"md5": None}}],
        )

        def boom(zot, attachment):
            raise PdfNotOnStorageError(
                attachment_key="A", source_url="https://x/y.pdf"
            )

        monkeypatch.setattr("riszotto.cli.resolve_pdf_path", boom)

        result = runner.invoke(app, ["show", "ITEMKEY1"])
        assert result.exit_code == 1
        assert "not on Zotero storage" in result.output
        assert "https://x/y.pdf" in result.output

    def test_zotero_permission_error_surfaces_to_stderr(self, monkeypatch):
        from typer.testing import CliRunner

        from riszotto.cli import app
        from riszotto.client import ZoteroPermissionError

        runner = CliRunner()

        zot = MagicMock()
        monkeypatch.setattr("riszotto.cli.get_client", lambda library=None: zot)
        monkeypatch.setattr(
            "riszotto.cli.get_pdf_attachments",
            lambda zot, key: [{"key": "A", "data": {"md5": "x"}}],
        )

        def boom(zot, attachment):
            raise ZoteroPermissionError("nope")

        monkeypatch.setattr("riszotto.cli.resolve_pdf_path", boom)

        result = runner.invoke(app, ["show", "ITEMKEY1"])
        assert result.exit_code == 1
        assert "permission" in result.output.lower()
```

- [ ] **Step 6.3: Run, verify tests fail**

```
uv run pytest tests/test_cli.py::TestShowResolvePdfPathErrors -v
```

Expected: ImportError on `resolve_pdf_path` from `riszotto.cli`, or assertions fail because the cli still uses `get_pdf_path`.

- [ ] **Step 6.4: Update `src/riszotto/cli.py` imports**

Find the existing import block:

```python
from riszotto.client import (
    ...
    get_pdf_attachments,
    get_pdf_path,
    ...
)
```

Replace with:

```python
from riszotto.client import (
    ...
    PdfNotOnStorageError,
    ZoteroPermissionError,
    get_pdf_attachments,
    resolve_pdf_path,
    ...
)
```

(Drop `get_pdf_path` from the import — it stays defined in `client.py` as an internal helper used by `resolve_pdf_path`.)

- [ ] **Step 6.5: Replace the `get_pdf_path` block in the `show` handler**

Locate this block (around `cli.py:669-682`):

```python
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
```

Replace with:

```python
    selected = pdfs[attachment - 1]
    try:
        resolved_path = resolve_pdf_path(zot, selected)
    except PdfNotOnStorageError as e:
        typer.echo(str(e), err=True)
        raise typer.Exit(1)
    except ZoteroPermissionError as e:
        typer.echo(str(e), err=True)
        raise typer.Exit(1)
    file_path = str(resolved_path)
```

The downstream `Path(file_path)` call at the converter step keeps working unchanged.

- [ ] **Step 6.6: Run the new tests**

```
uv run pytest tests/test_cli.py::TestShowResolvePdfPathErrors -v
```

Expected: green.

- [ ] **Step 6.7: Update any pre-existing show tests that asserted the old error text**

Search:

```
uv run pytest tests/test_cli.py -k show -v
```

For each failure caused by changed error wording, update the assertion to match the new text or replace the test entirely with one of the new error-class-aware tests above. Do not preserve the old error text.

- [ ] **Step 6.8: Run the full suite**

```
uv run pytest -q
```

Expected: green.

- [ ] **Step 6.9: Commit**

```
git add src/riszotto/cli.py tests/test_cli.py
git commit -m "feat(cli): wire resolve_pdf_path into show; surface new errors"
```

---

## Task 7: Extend `cache show` and `cache clear` for the PDF cache

**Files:**
- Modify: `src/riszotto/cli.py` (the `cache_app` group at the bottom of the file)
- Modify: `tests/test_cli.py` (extend existing cache tests)

- [ ] **Step 7.1: Write failing tests in `tests/test_cli.py`**

Append:

```python
class TestCacheCommandsWithPdfCache:
    def test_cache_show_reports_both_caches(self, monkeypatch, tmp_path):
        from typer.testing import CliRunner

        from riszotto.cli import app

        runner = CliRunner()

        monkeypatch.setattr(
            "riszotto.cli.get_cache_stats",
            lambda key=None: {
                "paper_count": 2,
                "total_bytes": 1024,
                "path": "/conv",
                "papers": [],
            },
        )
        monkeypatch.setattr(
            "riszotto.cli.pdf_cache_stats",
            lambda: {"count": 3, "total_bytes": 5_000_000, "path": "/pdfs"},
        )

        result = runner.invoke(app, ["cache", "show"])
        assert result.exit_code == 0
        assert "2 paper" in result.output  # markdown cache
        assert "3" in result.output  # pdf count
        assert "/pdfs" in result.output

    def test_cache_clear_clears_both_by_default(self, monkeypatch):
        from typer.testing import CliRunner

        from riszotto.cli import app

        runner = CliRunner()

        calls = {"conv": 0, "pdfs": 0}

        def fake_clear_cache(*, key=None, older_than_days=None):
            calls["conv"] += 1
            return 5

        def fake_clear_pdf_cache():
            calls["pdfs"] += 1
            return 7

        monkeypatch.setattr("riszotto.cli.clear_cache", fake_clear_cache)
        monkeypatch.setattr("riszotto.cli.clear_pdf_cache", fake_clear_pdf_cache)

        result = runner.invoke(app, ["cache", "clear"])
        assert result.exit_code == 0
        assert calls == {"conv": 1, "pdfs": 1}
        assert "5" in result.output
        assert "7" in result.output

    def test_cache_clear_only_conversions(self, monkeypatch):
        from typer.testing import CliRunner

        from riszotto.cli import app

        runner = CliRunner()
        calls = {"conv": 0, "pdfs": 0}
        monkeypatch.setattr(
            "riszotto.cli.clear_cache",
            lambda **kw: calls.__setitem__("conv", calls["conv"] + 1) or 1,
        )
        monkeypatch.setattr(
            "riszotto.cli.clear_pdf_cache",
            lambda: calls.__setitem__("pdfs", calls["pdfs"] + 1) or 1,
        )

        result = runner.invoke(app, ["cache", "clear", "--only", "conversions"])
        assert result.exit_code == 0
        assert calls == {"conv": 1, "pdfs": 0}

    def test_cache_clear_only_pdfs(self, monkeypatch):
        from typer.testing import CliRunner

        from riszotto.cli import app

        runner = CliRunner()
        calls = {"conv": 0, "pdfs": 0}
        monkeypatch.setattr(
            "riszotto.cli.clear_cache",
            lambda **kw: calls.__setitem__("conv", calls["conv"] + 1) or 1,
        )
        monkeypatch.setattr(
            "riszotto.cli.clear_pdf_cache",
            lambda: calls.__setitem__("pdfs", calls["pdfs"] + 1) or 1,
        )

        result = runner.invoke(app, ["cache", "clear", "--only", "pdfs"])
        assert result.exit_code == 0
        assert calls == {"conv": 0, "pdfs": 1}

    def test_cache_clear_with_key_does_not_clear_pdfs(self, monkeypatch):
        """--key only scopes the markdown cache; PDF cache is content-keyed."""
        from typer.testing import CliRunner

        from riszotto.cli import app

        runner = CliRunner()
        calls = {"conv_kwargs": None, "pdfs": 0}

        def fake_clear_cache(*, key=None, older_than_days=None):
            calls["conv_kwargs"] = {"key": key, "older_than_days": older_than_days}
            return 1

        def fake_clear_pdf_cache():
            calls["pdfs"] += 1
            return 0

        monkeypatch.setattr("riszotto.cli.clear_cache", fake_clear_cache)
        monkeypatch.setattr("riszotto.cli.clear_pdf_cache", fake_clear_pdf_cache)

        result = runner.invoke(app, ["cache", "clear", "--key", "ABC123"])
        assert result.exit_code == 0
        assert calls["conv_kwargs"] == {"key": "ABC123", "older_than_days": None}
        assert calls["pdfs"] == 0
```

- [ ] **Step 7.2: Run, verify tests fail**

```
uv run pytest tests/test_cli.py::TestCacheCommandsWithPdfCache -v
```

Expected: failures because `pdf_cache_stats` / `clear_pdf_cache` are not yet imported in `cli.py` and `--only` is not a flag.

- [ ] **Step 7.3: Update `src/riszotto/cli.py` imports**

Add to existing imports:

```python
from riszotto.pdf_cache import clear_pdf_cache, pdf_cache_stats
```

- [ ] **Step 7.4: Replace `cache_show`**

Find the existing `def cache_show(...)` (around `cli.py:1052`). Replace its body with:

```python
@cache_app.command("show")
def cache_show(
    key: Annotated[
        Optional[str],
        typer.Option("--key", "-k", help="Show cache for a specific paper"),
    ] = None,
) -> None:
    """Show cache statistics."""
    md_stats = get_cache_stats(key=key)
    if key and md_stats["paper_count"] == 0:
        typer.echo(f"No cached data for {key}.")
    else:
        typer.echo(
            f"Markdown cache: {md_stats['paper_count']} paper(s), "
            f"{_format_bytes(md_stats['total_bytes'])}. "
            f"Path: {md_stats['path']}"
        )
        if md_stats.get("papers"):
            for p in md_stats["papers"]:
                typer.echo(f"  {p['key']}: {_format_bytes(p['bytes'])}")

    if key is None:
        pdf_stats = pdf_cache_stats()
        typer.echo(
            f"PDF cache: {pdf_stats['count']} file(s), "
            f"{_format_bytes(pdf_stats['total_bytes'])}. "
            f"Path: {pdf_stats['path']}"
        )
```

- [ ] **Step 7.5: Replace `cache_clear`**

Find the existing `def cache_clear(...)` (around `cli.py:1081`). Replace it with:

```python
@cache_app.command("clear")
def cache_clear(
    key: Annotated[
        Optional[str],
        typer.Option("--key", "-k", help="Clear cache for a specific paper (markdown only)"),
    ] = None,
    older_than: Annotated[
        Optional[str],
        typer.Option(
            "--older-than", help="Clear entries older than duration (e.g., 30d)"
        ),
    ] = None,
    only: Annotated[
        Optional[str],
        typer.Option(
            "--only",
            help="Restrict to one cache: 'conversions' or 'pdfs'",
        ),
    ] = None,
) -> None:
    """Clear cached conversions and downloaded PDFs.

    Without --only, both caches are cleared. ``--key`` only scopes the
    markdown (conversions) cache; the PDF cache is content-keyed and not
    associated with a specific Zotero key.
    """
    if only is not None and only not in ("conversions", "pdfs"):
        typer.echo("Invalid --only value. Use 'conversions' or 'pdfs'.", err=True)
        raise typer.Exit(1)

    older_than_days = None
    if older_than is not None:
        older_than_days = _parse_duration(older_than)
        if older_than_days is None:
            typer.echo(
                "Invalid duration format. Use <N>d, e.g., --older-than 30d",
                err=True,
            )
            raise typer.Exit(1)

    if only in (None, "conversions"):
        md_cleared = clear_cache(key=key, older_than_days=older_than_days)
        typer.echo(f"Cleared {md_cleared} paper(s) from markdown cache.")

    if only in (None, "pdfs"):
        if key is not None and only is None:
            # Default --key behavior: only conversions get scoped; PDF cache untouched.
            pass
        elif only == "pdfs" and key is not None:
            typer.echo(
                "--key has no effect on the PDF cache (content-keyed). "
                "Run without --key to clear all cached PDFs.",
                err=True,
            )
            raise typer.Exit(1)
        else:
            pdf_cleared = clear_pdf_cache()
            typer.echo(f"Cleared {pdf_cleared} file(s) from PDF cache.")
```

- [ ] **Step 7.6: Run the new tests**

```
uv run pytest tests/test_cli.py::TestCacheCommandsWithPdfCache -v
```

Expected: green. If `test_cache_clear_with_key_does_not_clear_pdfs` fails because the implementation took the wrong branch, re-read step 7.5 carefully — the rule is: with `--key` and no `--only`, only the markdown cache is touched.

- [ ] **Step 7.7: Run the full suite**

```
uv run pytest -q
```

Expected: green.

- [ ] **Step 7.8: Commit**

```
git add src/riszotto/cli.py tests/test_cli.py
git commit -m "feat(cli): cache show/clear cover PDF cache; --only flag"
```

---

## Task 8: README + CHANGELOG

**Files:**
- Modify: `README.md`
- Create: `CHANGELOG.md`

- [ ] **Step 8.1: Update `README.md`**

Find the existing config example in `README.md` (around line 75 — the `api_key`/`user_id` block). Replace that block with:

````markdown
## Configuration

riszotto reads `~/.riszotto/config.toml`:

```toml
[zotero]
api_key = "..."   # from zotero.org/settings/keys
user_id = "..."   # numeric user ID
mode = "auto"     # "auto" (default) | "local" | "web"
```

Mode resolution:

| `mode` | creds set | result |
|--------|-----------|--------|
| `auto` (default) | yes | use the Zotero Web API |
| `auto` | no | use the local Zotero desktop |
| `local` | — | always local |
| `web` | yes | always web |
| `web` | no | error: web mode requires creds |

Environment variables (override the TOML file):

- `RISZOTTO_ZOTERO_API_KEY`
- `RISZOTTO_ZOTERO_USER_ID`
- `RISZOTTO_ZOTERO_MODE`

In web mode, `show` downloads attachment PDFs into a content-addressed
cache at `~/.cache/riszotto/pdfs/{md5}.pdf` (deduplicated across libraries).
The PDF must be on Zotero storage — attachments with `md5 = null` (file
sync disabled, metadata-only attachments) cannot be retrieved over the
web API.
````

- [ ] **Step 8.2: Create `CHANGELOG.md`**

Create the file with:

```markdown
# Changelog

## Unreleased

### Added
- `mode` config field (`auto` | `local` | `web`) selects between the local
  Zotero desktop and the Zotero Web API for both personal and group libraries.
- `show` works against the Web API by downloading attachment PDFs into a
  content-addressed cache (`~/.cache/riszotto/pdfs/{md5}.pdf`).
- `cache show` reports the new PDF cache. `cache clear` clears it; new
  `--only conversions|pdfs` flag for selective clearing.

### Changed (breaking)
- Environment variables are renamed to use the `RISZOTTO_` prefix:
  `ZOTERO_API_KEY` → `RISZOTTO_ZOTERO_API_KEY`,
  `ZOTERO_USER_ID` → `RISZOTTO_ZOTERO_USER_ID`. The old names are no
  longer read. Update your shell config; TOML config is unchanged.
- With credentials configured, the personal library now uses the Web API
  (previous behavior: local-only for personal, Web for groups).
  Set `mode = "local"` to keep the previous personal-library behavior.
```

- [ ] **Step 8.3: Run the full suite one last time**

```
uv run pytest -q
```

Expected: green.

- [ ] **Step 8.4: Commit**

```
git add README.md CHANGELOG.md
git commit -m "docs: README and CHANGELOG for web-API mode and env-var rename"
```

---

## Final verification

- [ ] **Run the full suite**

```
uv run pytest -q
```

Expected: all tests pass.

- [ ] **Lint check (if a `lint` script exists)**

```
uvx prek --all-files
```

Address any formatting/linting feedback before declaring done.

- [ ] **Smoke-test the CLI without running Zotero desktop**

```
RISZOTTO_ZOTERO_API_KEY=... RISZOTTO_ZOTERO_USER_ID=... \
  uv run riszotto recent
```

Expected: returns recent items from the personal library over the Web API.

```
RISZOTTO_ZOTERO_API_KEY=... RISZOTTO_ZOTERO_USER_ID=... \
  uv run riszotto show -L "ICP Bib" <ITEM_WITH_PDF>
```

Expected: downloads the PDF on first invocation, returns markdown; second invocation is fast and offline.

```
RISZOTTO_ZOTERO_API_KEY=... RISZOTTO_ZOTERO_USER_ID=... \
  uv run riszotto show <PERSONAL_ITEM_WITHOUT_FILE_SYNC>
```

Expected: clean `PdfNotOnStorageError` message with the source URL, exit code 1.

- [ ] **Open a PR** against `main` from `feat/web-api-mode` once the user approves the local results. Do not open the PR autonomously.
