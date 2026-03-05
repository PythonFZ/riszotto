# riszotto Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Build a CLI tool (`uvx riszotto`) that searches, inspects, and reads papers from a local Zotero library.

**Architecture:** Typer CLI with 3 commands (search, info, show) backed by a thin pyzotero wrapper connecting to Zotero desktop's local API on localhost:23119. PDF-to-markdown conversion via markitdown.

**Tech Stack:** Python 3.11, typer, pyzotero, markitdown, uv

---

### Task 1: Project scaffolding and dependencies

**Files:**
- Modify: `pyproject.toml`
- Create: `src/riszotto/__init__.py`
- Create: `src/riszotto/cli.py`
- Create: `src/riszotto/client.py`
- Delete: `main.py` (replaced by package)

**Step 1: Update pyproject.toml with dependencies and entry point**

Replace the contents of `pyproject.toml`:

```toml
[project]
name = "riszotto"
version = "0.1.0"
description = "CLI tool for searching and reading papers from a local Zotero library"
readme = "README.md"
requires-python = ">=3.11"
dependencies = [
    "typer>=0.9.0",
    "pyzotero>=1.5.0",
    "markitdown>=0.1.0",
]

[project.scripts]
riszotto = "riszotto.cli:app"

[build-system]
requires = ["uv_build>=0.10.7,<0.11.0"]
build-backend = "uv_build"
```

**Step 2: Create package structure**

Create `src/riszotto/__init__.py`:

```python
"""riszotto - CLI tool for searching and reading papers from a local Zotero library."""
```

Create `src/riszotto/cli.py` (minimal stub):

```python
import typer

app = typer.Typer()


@app.command()
def search():
    """Search for papers in your Zotero library."""
    typer.echo("search: not implemented")


@app.command()
def info():
    """Show metadata for a paper."""
    typer.echo("info: not implemented")


@app.command()
def show():
    """Convert a paper's PDF to markdown."""
    typer.echo("show: not implemented")
```

Create `src/riszotto/client.py` (minimal stub):

```python
"""Thin wrapper around pyzotero for local Zotero API access."""
```

**Step 3: Delete main.py**

```bash
rm main.py
```

**Step 4: Install dependencies and verify the CLI runs**

```bash
uv sync
uv run riszotto --help
```

Expected: Help output showing `search`, `info`, `show` commands.

**Step 5: Commit**

```bash
git add pyproject.toml src/ && git rm main.py
git commit -m "feat: scaffold riszotto package with typer CLI and dependencies"
```

---

### Task 2: Client module — Zotero connection and helpers

**Files:**
- Create: `tests/test_client.py`
- Modify: `src/riszotto/client.py`

**Step 1: Write failing tests for client functions**

Create `tests/test_client.py`:

```python
from unittest.mock import MagicMock, patch

from riszotto.client import get_client, search_items, get_item, get_pdf_attachments, get_pdf_path


class TestGetClient:
    def test_returns_zotero_instance(self):
        with patch("riszotto.client.zotero.Zotero") as mock_zotero:
            client = get_client()
            mock_zotero.assert_called_once_with(
                library_id="0",
                library_type="user",
                api_key=None,
                local=True,
            )


class TestSearchItems:
    def test_search_default_mode(self):
        mock_zot = MagicMock()
        mock_zot.items.return_value = [
            {
                "data": {
                    "key": "ABC123",
                    "title": "Test Paper",
                    "date": "2024-01-15",
                    "creators": [{"firstName": "John", "lastName": "Doe", "creatorType": "author"}],
                },
                "meta": {"creatorSummary": "Doe et al."},
            }
        ]
        results = search_items(mock_zot, "test query", full_text=False, limit=25)
        mock_zot.items.assert_called_once_with(q="test query", qmode="titleCreatorYear", limit=25)
        assert len(results) == 1
        assert results[0]["data"]["key"] == "ABC123"

    def test_search_full_text_mode(self):
        mock_zot = MagicMock()
        mock_zot.items.return_value = []
        search_items(mock_zot, "test query", full_text=True, limit=10)
        mock_zot.items.assert_called_once_with(q="test query", qmode="everything", limit=10)


class TestGetItem:
    def test_returns_item(self):
        mock_zot = MagicMock()
        mock_zot.item.return_value = {"data": {"key": "ABC123", "title": "Test"}}
        result = get_item(mock_zot, "ABC123")
        mock_zot.item.assert_called_once_with("ABC123")
        assert result["data"]["title"] == "Test"


class TestGetPdfAttachments:
    def test_filters_pdf_children(self):
        mock_zot = MagicMock()
        mock_zot.children.return_value = [
            {
                "data": {"key": "ATT1", "itemType": "attachment", "contentType": "application/pdf", "filename": "paper.pdf"},
                "links": {"enclosure": {"href": "file:///path/to/paper.pdf"}},
            },
            {
                "data": {"key": "NOTE1", "itemType": "note"},
                "links": {},
            },
        ]
        pdfs = get_pdf_attachments(mock_zot, "PARENT1")
        assert len(pdfs) == 1
        assert pdfs[0]["data"]["key"] == "ATT1"

    def test_no_attachments(self):
        mock_zot = MagicMock()
        mock_zot.children.return_value = []
        pdfs = get_pdf_attachments(mock_zot, "PARENT1")
        assert pdfs == []


class TestGetPdfPath:
    def test_extracts_file_path(self):
        attachment = {
            "links": {
                "enclosure": {
                    "href": "file:///Users/me/Zotero/storage/ABC123/paper.pdf",
                }
            }
        }
        path = get_pdf_path(attachment)
        assert path == "/Users/me/Zotero/storage/ABC123/paper.pdf"

    def test_no_enclosure_returns_none(self):
        attachment = {"links": {}}
        path = get_pdf_path(attachment)
        assert path is None
```

**Step 2: Run tests to verify they fail**

```bash
uv run pytest tests/test_client.py -v
```

Expected: FAIL — functions not defined yet.

**Step 3: Implement client.py**

Write `src/riszotto/client.py`:

```python
"""Thin wrapper around pyzotero for local Zotero API access."""

from __future__ import annotations

from typing import Any
from urllib.parse import unquote, urlparse

from pyzotero import zotero


def get_client() -> zotero.Zotero:
    """Create a pyzotero client connected to the local Zotero instance."""
    return zotero.Zotero(
        library_id="0",
        library_type="user",
        api_key=None,
        local=True,
    )


def search_items(
    zot: zotero.Zotero,
    query: str,
    *,
    full_text: bool = False,
    limit: int = 25,
) -> list[dict[str, Any]]:
    """Search the Zotero library."""
    qmode = "everything" if full_text else "titleCreatorYear"
    return zot.items(q=query, qmode=qmode, limit=limit)


def get_item(zot: zotero.Zotero, key: str) -> dict[str, Any]:
    """Get a single item by key."""
    return zot.item(key)


def get_pdf_attachments(zot: zotero.Zotero, key: str) -> list[dict[str, Any]]:
    """Get PDF attachments for an item."""
    children = zot.children(key)
    return [
        child
        for child in children
        if child.get("data", {}).get("contentType") == "application/pdf"
    ]


def get_pdf_path(attachment: dict[str, Any]) -> str | None:
    """Extract the local file path from an attachment's enclosure link."""
    href = attachment.get("links", {}).get("enclosure", {}).get("href")
    if not href:
        return None
    parsed = urlparse(href)
    if parsed.scheme == "file":
        return unquote(parsed.path)
    return None
```

**Step 4: Run tests to verify they pass**

```bash
uv run pytest tests/test_client.py -v
```

Expected: All PASS.

**Step 5: Commit**

```bash
git add src/riszotto/client.py tests/test_client.py
git commit -m "feat: add client module with local Zotero API helpers"
```

---

### Task 3: Search command

**Files:**
- Create: `tests/test_cli.py`
- Modify: `src/riszotto/cli.py`

**Step 1: Write failing test for search command**

Create `tests/test_cli.py`:

```python
from unittest.mock import MagicMock, patch

from typer.testing import CliRunner

from riszotto.cli import app

runner = CliRunner()


class TestSearch:
    @patch("riszotto.cli.get_client")
    def test_search_shows_table(self, mock_get_client):
        mock_zot = MagicMock()
        mock_get_client.return_value = mock_zot
        mock_zot.items.return_value = [
            {
                "data": {
                    "key": "ABC12345",
                    "title": "Attention Is All You Need",
                    "date": "2017-06-12",
                    "creators": [
                        {"firstName": "Ashish", "lastName": "Vaswani", "creatorType": "author"},
                        {"firstName": "Noam", "lastName": "Shazeer", "creatorType": "author"},
                    ],
                },
                "meta": {"creatorSummary": "Vaswani et al."},
            }
        ]
        result = runner.invoke(app, ["search", "attention"])
        assert result.exit_code == 0
        assert "ABC12345" in result.output
        assert "2017" in result.output
        assert "Vaswani" in result.output
        assert "Attention Is All You Need" in result.output

    @patch("riszotto.cli.get_client")
    def test_search_no_results(self, mock_get_client):
        mock_zot = MagicMock()
        mock_get_client.return_value = mock_zot
        mock_zot.items.return_value = []
        result = runner.invoke(app, ["search", "nonexistent"])
        assert result.exit_code == 0
        assert "KEY" in result.output  # header still present

    @patch("riszotto.cli.get_client")
    def test_search_full_text_flag(self, mock_get_client):
        mock_zot = MagicMock()
        mock_get_client.return_value = mock_zot
        mock_zot.items.return_value = []
        runner.invoke(app, ["search", "--full-text", "deep learning"])
        mock_zot.items.assert_called_once_with(q="deep learning", qmode="everything", limit=25)

    @patch("riszotto.cli.get_client")
    def test_search_limit_flag(self, mock_get_client):
        mock_zot = MagicMock()
        mock_get_client.return_value = mock_zot
        mock_zot.items.return_value = []
        runner.invoke(app, ["search", "--limit", "5", "test"])
        mock_zot.items.assert_called_once_with(q="test", qmode="titleCreatorYear", limit=5)

    @patch("riszotto.cli.get_client")
    def test_search_zotero_not_running(self, mock_get_client):
        mock_get_client.side_effect = ConnectionError("connection refused")
        result = runner.invoke(app, ["search", "test"])
        assert result.exit_code == 1
        assert "Zotero desktop is not running" in result.output
```

**Step 2: Run tests to verify they fail**

```bash
uv run pytest tests/test_cli.py::TestSearch -v
```

Expected: FAIL — search command is a stub.

**Step 3: Implement search command in cli.py**

Replace `src/riszotto/cli.py`:

```python
"""riszotto CLI — search and read papers from your local Zotero library."""

from __future__ import annotations

import json
import sys
from typing import Annotated, Optional

import typer

from riszotto.client import get_client, get_item, get_pdf_attachments, get_pdf_path, search_items

app = typer.Typer(add_completion=False)


def _format_author(item: dict) -> str:
    """Extract a short author string from an item."""
    summary = item.get("meta", {}).get("creatorSummary", "")
    if summary:
        return summary
    creators = item.get("data", {}).get("creators", [])
    if not creators:
        return ""
    first = creators[0]
    name = first.get("lastName", first.get("name", ""))
    if len(creators) > 1:
        return f"{name} et al."
    return name


def _format_year(item: dict) -> str:
    """Extract year from an item's date field."""
    date = item.get("data", {}).get("date", "")
    return date[:4] if len(date) >= 4 else ""


@app.command()
def search(
    terms: Annotated[list[str], typer.Argument(help="Search terms")],
    full_text: Annotated[bool, typer.Option("--full-text", help="Search all fields including full-text")] = False,
    limit: Annotated[int, typer.Option("--limit", "-l", help="Maximum number of results")] = 25,
) -> None:
    """Search for papers in your Zotero library."""
    query = " ".join(terms)
    try:
        zot = get_client()
        results = search_items(zot, query, full_text=full_text, limit=limit)
    except (ConnectionError, Exception) as e:
        if "connection" in str(e).lower() or "refused" in str(e).lower():
            typer.echo("Zotero desktop is not running. Start Zotero and ensure the local API is enabled.", err=True)
            raise typer.Exit(1)
        raise

    # Print compact table
    typer.echo(f"{'KEY':<11}{'YEAR':<6}{'AUTHOR':<20}{'TITLE'}")
    for item in results:
        data = item.get("data", {})
        key = data.get("key", "")
        year = _format_year(item)
        author = _format_author(item)
        title = data.get("title", "")
        # Truncate long values
        if len(author) > 18:
            author = author[:17] + "…"
        if len(title) > 60:
            title = title[:59] + "…"
        typer.echo(f"{key:<11}{year:<6}{author:<20}{title}")


@app.command()
def info(
    key: Annotated[str, typer.Argument(help="Zotero item key")],
) -> None:
    """Show JSON metadata for a paper."""
    typer.echo("info: not implemented")


@app.command()
def show(
    key: Annotated[str, typer.Argument(help="Zotero item key")],
) -> None:
    """Convert a paper's PDF attachment to markdown."""
    typer.echo("show: not implemented")
```

**Step 4: Run tests to verify they pass**

```bash
uv run pytest tests/test_cli.py::TestSearch -v
```

Expected: All PASS.

**Step 5: Commit**

```bash
git add src/riszotto/cli.py tests/test_cli.py
git commit -m "feat: implement search command with compact table output"
```

---

### Task 4: Info command

**Files:**
- Modify: `tests/test_cli.py`
- Modify: `src/riszotto/cli.py`

**Step 1: Write failing tests for info command**

Append to `tests/test_cli.py`:

```python
class TestInfo:
    @patch("riszotto.cli.get_client")
    def test_info_outputs_json(self, mock_get_client):
        mock_zot = MagicMock()
        mock_get_client.return_value = mock_zot
        mock_zot.item.return_value = {
            "data": {
                "key": "ABC12345",
                "title": "Test Paper",
                "DOI": "10.1234/test",
                "itemType": "journalArticle",
            }
        }
        result = runner.invoke(app, ["info", "ABC12345"])
        assert result.exit_code == 0
        parsed = json.loads(result.output)
        assert parsed["title"] == "Test Paper"
        assert parsed["DOI"] == "10.1234/test"

    @patch("riszotto.cli.get_client")
    def test_info_invalid_key(self, mock_get_client):
        mock_zot = MagicMock()
        mock_get_client.return_value = mock_zot
        mock_zot.item.side_effect = Exception("Item not found")
        result = runner.invoke(app, ["info", "BADKEY"])
        assert result.exit_code == 1
        assert "not found" in result.output.lower()
```

Add `import json` at the top of the test file if not present.

**Step 2: Run tests to verify they fail**

```bash
uv run pytest tests/test_cli.py::TestInfo -v
```

Expected: FAIL — info is a stub.

**Step 3: Implement info command**

Replace the `info` function in `src/riszotto/cli.py`:

```python
@app.command()
def info(
    key: Annotated[str, typer.Argument(help="Zotero item key")],
) -> None:
    """Show JSON metadata for a paper."""
    try:
        zot = get_client()
    except (ConnectionError, Exception) as e:
        if "connection" in str(e).lower() or "refused" in str(e).lower():
            typer.echo("Zotero desktop is not running. Start Zotero and ensure the local API is enabled.", err=True)
            raise typer.Exit(1)
        raise

    try:
        item = get_item(zot, key)
    except Exception:
        typer.echo(f"Item '{key}' not found in your library.", err=True)
        raise typer.Exit(1)

    typer.echo(json.dumps(item.get("data", {}), indent=2))
```

**Step 4: Run tests to verify they pass**

```bash
uv run pytest tests/test_cli.py::TestInfo -v
```

Expected: All PASS.

**Step 5: Commit**

```bash
git add src/riszotto/cli.py tests/test_cli.py
git commit -m "feat: implement info command with JSON output"
```

---

### Task 5: Show command

**Files:**
- Modify: `tests/test_cli.py`
- Modify: `src/riszotto/cli.py`

**Step 1: Write failing tests for show command**

Append to `tests/test_cli.py`:

```python
class TestShow:
    @patch("riszotto.cli.MarkItDown")
    @patch("riszotto.cli.get_client")
    def test_show_converts_pdf(self, mock_get_client, mock_markitdown_cls):
        mock_zot = MagicMock()
        mock_get_client.return_value = mock_zot
        mock_zot.children.return_value = [
            {
                "data": {"key": "ATT1", "itemType": "attachment", "contentType": "application/pdf", "filename": "paper.pdf"},
                "links": {"enclosure": {"href": "file:///Users/me/Zotero/storage/ATT1/paper.pdf"}},
            }
        ]
        mock_md = MagicMock()
        mock_markitdown_cls.return_value = mock_md
        mock_result = MagicMock()
        mock_result.markdown = "# Paper Title\n\nSome content here."
        mock_md.convert.return_value = mock_result

        result = runner.invoke(app, ["show", "PARENT1"])
        assert result.exit_code == 0
        assert "# Paper Title" in result.output
        mock_md.convert.assert_called_once_with("/Users/me/Zotero/storage/ATT1/paper.pdf")

    @patch("riszotto.cli.get_client")
    def test_show_no_pdf_attachment(self, mock_get_client):
        mock_zot = MagicMock()
        mock_get_client.return_value = mock_zot
        mock_zot.children.return_value = [
            {"data": {"key": "NOTE1", "itemType": "note"}, "links": {}},
        ]
        result = runner.invoke(app, ["show", "PARENT1"])
        assert result.exit_code == 1
        assert "No PDF attachment" in result.output

    @patch("riszotto.cli.MarkItDown")
    @patch("riszotto.cli.get_client")
    def test_show_attachment_flag(self, mock_get_client, mock_markitdown_cls):
        mock_zot = MagicMock()
        mock_get_client.return_value = mock_zot
        mock_zot.children.return_value = [
            {
                "data": {"key": "ATT1", "itemType": "attachment", "contentType": "application/pdf", "filename": "paper1.pdf"},
                "links": {"enclosure": {"href": "file:///path/to/paper1.pdf"}},
            },
            {
                "data": {"key": "ATT2", "itemType": "attachment", "contentType": "application/pdf", "filename": "paper2.pdf"},
                "links": {"enclosure": {"href": "file:///path/to/paper2.pdf"}},
            },
        ]
        mock_md = MagicMock()
        mock_markitdown_cls.return_value = mock_md
        mock_result = MagicMock()
        mock_result.markdown = "Second PDF content"
        mock_md.convert.return_value = mock_result

        result = runner.invoke(app, ["show", "--attachment", "2", "PARENT1"])
        assert result.exit_code == 0
        mock_md.convert.assert_called_once_with("/path/to/paper2.pdf")
```

**Step 2: Run tests to verify they fail**

```bash
uv run pytest tests/test_cli.py::TestShow -v
```

Expected: FAIL — show is a stub.

**Step 3: Implement show command**

Replace the `show` function in `src/riszotto/cli.py`. Also add the markitdown import at the top:

```python
from markitdown import MarkItDown
```

```python
@app.command()
def show(
    key: Annotated[str, typer.Argument(help="Zotero item key")],
    attachment: Annotated[int, typer.Option("--attachment", "-a", help="PDF attachment index (1-indexed)")] = 1,
) -> None:
    """Convert a paper's PDF attachment to markdown."""
    try:
        zot = get_client()
    except (ConnectionError, Exception) as e:
        if "connection" in str(e).lower() or "refused" in str(e).lower():
            typer.echo("Zotero desktop is not running. Start Zotero and ensure the local API is enabled.", err=True)
            raise typer.Exit(1)
        raise

    pdfs = get_pdf_attachments(zot, key)
    if not pdfs:
        typer.echo(f"No PDF attachment found for item {key}.", err=True)
        raise typer.Exit(1)

    if attachment < 1 or attachment > len(pdfs):
        typer.echo(f"Attachment index {attachment} out of range. Item has {len(pdfs)} PDF(s).", err=True)
        raise typer.Exit(1)

    selected = pdfs[attachment - 1]
    file_path = get_pdf_path(selected)
    if not file_path:
        typer.echo(f"Could not determine local file path for attachment.", err=True)
        raise typer.Exit(1)

    try:
        md = MarkItDown()
        result = md.convert(file_path)
        typer.echo(result.markdown)
    except Exception as e:
        typer.echo(f"Failed to convert PDF to markdown: {e}", err=True)
        raise typer.Exit(1)
```

**Step 4: Run tests to verify they pass**

```bash
uv run pytest tests/test_cli.py::TestShow -v
```

Expected: All PASS.

**Step 5: Run full test suite**

```bash
uv run pytest tests/ -v
```

Expected: All tests PASS.

**Step 6: Commit**

```bash
git add src/riszotto/cli.py tests/test_cli.py
git commit -m "feat: implement show command with markitdown PDF conversion"
```

---

### Task 6: Manual smoke test against live Zotero

**Prerequisite:** Zotero desktop must be running with the local API enabled.

**Step 1: Test search**

```bash
uv run riszotto search machine learning
```

Expected: Compact table with results from your library.

**Step 2: Test info**

Pick a key from the search results and run:

```bash
uv run riszotto info <KEY>
```

Expected: Formatted JSON metadata.

**Step 3: Test show**

```bash
uv run riszotto show <KEY>
```

Expected: Markdown conversion of the first PDF attachment printed to stdout.

**Step 4: Test error cases**

```bash
uv run riszotto info BADKEY123
uv run riszotto show BADKEY123
```

Expected: Clear error messages, exit code 1.

**Step 5: Commit any fixes if needed**

---

### Task 7: Final cleanup

**Files:**
- Modify: `README.md`

**Step 1: Write a minimal README**

```markdown
# riszotto

CLI tool for searching and reading papers from your local Zotero library.

Requires Zotero desktop to be running with the local API enabled.

## Install

```
uvx riszotto --help
```

## Usage

```bash
# Search your library
riszotto search machine learning transformers

# Search full-text content
riszotto search --full-text "attention mechanism"

# View paper metadata as JSON
riszotto info ABC12345

# Read a paper's PDF as markdown
riszotto show ABC12345

# Select a specific PDF attachment (1-indexed)
riszotto show --attachment 2 ABC12345
```
```

**Step 2: Commit**

```bash
git add README.md
git commit -m "docs: add README with usage examples"
```
