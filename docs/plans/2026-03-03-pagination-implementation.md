# Pagination & Filtering Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add pagination to `search` and `show`, value-size filtering to `info`, and heading-based section search to `show`.

**Architecture:** Extend existing CLI commands with new flags. Search pagination uses pyzotero's native `start` param. Show pagination slices converted markdown by line count. Section search splits on markdown headings and filters by substring match. Info filtering replaces long string values inline.

**Tech Stack:** Python 3.11, typer, pyzotero, markitdown, re (stdlib)

---

### Task 1: Search pagination — client `start` param

**Files:**
- Modify: `tests/test_client.py`
- Modify: `src/riszotto/client.py`

**Step 1: Write failing test for start param**

Append to `tests/test_client.py` inside `TestSearchItems`:

```python
    def test_search_with_start_offset(self):
        mock_zot = MagicMock()
        mock_zot.items.return_value = []
        search_items(mock_zot, "test", full_text=False, limit=25, start=50)
        mock_zot.items.assert_called_once_with(q="test", qmode="titleCreatorYear", limit=25, start=50)

    def test_search_default_start_is_zero(self):
        mock_zot = MagicMock()
        mock_zot.items.return_value = []
        search_items(mock_zot, "test", full_text=False, limit=25)
        mock_zot.items.assert_called_once_with(q="test", qmode="titleCreatorYear", limit=25, start=0)
```

**Step 2: Run tests to verify they fail**

```bash
uv run pytest tests/test_client.py::TestSearchItems -v
```

Expected: FAIL — `search_items` doesn't accept `start` yet, and existing test for default mode doesn't pass `start=0`.

**Step 3: Update search_items in client.py**

Replace the `search_items` function in `src/riszotto/client.py`:

```python
def search_items(
    zot: zotero.Zotero,
    query: str,
    *,
    full_text: bool = False,
    limit: int = 25,
    start: int = 0,
) -> list[dict[str, Any]]:
    """Search the Zotero library."""
    qmode = "everything" if full_text else "titleCreatorYear"
    return zot.items(q=query, qmode=qmode, limit=limit, start=start)
```

**Step 4: Fix existing tests that don't expect `start=0`**

Update the two existing tests in `TestSearchItems` to expect `start=0` in the mock assertion:

In `test_search_default_mode`, change:
```python
        mock_zot.items.assert_called_once_with(q="test query", qmode="titleCreatorYear", limit=25)
```
to:
```python
        mock_zot.items.assert_called_once_with(q="test query", qmode="titleCreatorYear", limit=25, start=0)
```

In `test_search_full_text_mode`, change:
```python
        mock_zot.items.assert_called_once_with(q="test query", qmode="everything", limit=10)
```
to:
```python
        mock_zot.items.assert_called_once_with(q="test query", qmode="everything", limit=10, start=0)
```

**Step 5: Run tests to verify they pass**

```bash
uv run pytest tests/test_client.py::TestSearchItems -v
```

Expected: All PASS.

**Step 6: Commit**

```bash
git add src/riszotto/client.py tests/test_client.py
git commit -m "feat: add start offset param to search_items"
```

---

### Task 2: Search pagination — CLI `--page` flag

**Files:**
- Modify: `tests/test_cli.py`
- Modify: `src/riszotto/cli.py`

**Step 1: Write failing tests for --page flag**

Append to `tests/test_cli.py` inside `TestSearch`:

```python
    @patch("riszotto.cli.get_client")
    def test_search_page_flag(self, mock_get_client):
        mock_zot = MagicMock()
        mock_get_client.return_value = mock_zot
        mock_zot.items.return_value = []
        runner.invoke(app, ["search", "--page", "3", "test"])
        mock_zot.items.assert_called_once_with(q="test", qmode="titleCreatorYear", limit=25, start=50)

    @patch("riszotto.cli.get_client")
    def test_search_page_footer(self, mock_get_client):
        mock_zot = MagicMock()
        mock_get_client.return_value = mock_zot
        mock_zot.items.return_value = [
            {
                "data": {"key": "ABC12345", "title": "Paper", "date": "2024", "creators": []},
                "meta": {},
            }
        ]
        result = runner.invoke(app, ["search", "test"])
        assert result.exit_code == 0
        assert "Page 1" in result.output
        assert "--page 2" in result.output
```

**Step 2: Run tests to verify they fail**

```bash
uv run pytest tests/test_cli.py::TestSearch::test_search_page_flag tests/test_cli.py::TestSearch::test_search_page_footer -v
```

Expected: FAIL — search command doesn't have `--page` yet.

**Step 3: Update search command in cli.py**

Replace the `search` function in `src/riszotto/cli.py`:

```python
@app.command()
def search(
    terms: Annotated[list[str], typer.Argument(help="Search terms")],
    full_text: Annotated[bool, typer.Option("--full-text", help="Search all fields including full-text")] = False,
    limit: Annotated[int, typer.Option("--limit", "-l", help="Maximum number of results")] = 25,
    page: Annotated[int, typer.Option("--page", "-p", help="Page number (1-indexed)")] = 1,
) -> None:
    """Search for papers in your Zotero library."""
    query = " ".join(terms)
    start = (page - 1) * limit
    try:
        zot = get_client()
        results = search_items(zot, query, full_text=full_text, limit=limit, start=start)
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

    # Footer
    first = start + 1
    last = start + len(results)
    typer.echo(f"\nPage {page} (results {first}-{last}). Next: riszotto search --page {page + 1} \"{query}\"")
```

**Step 4: Fix existing CLI tests that now receive `start=0`**

In `TestSearch`, update `test_search_full_text_flag`:
```python
        mock_zot.items.assert_called_once_with(q="deep learning", qmode="everything", limit=25, start=0)
```

Update `test_search_limit_flag`:
```python
        mock_zot.items.assert_called_once_with(q="test", qmode="titleCreatorYear", limit=5, start=0)
```

**Step 5: Run tests to verify they pass**

```bash
uv run pytest tests/test_cli.py::TestSearch -v
```

Expected: All PASS (7 tests).

**Step 6: Commit**

```bash
git add src/riszotto/cli.py tests/test_cli.py
git commit -m "feat: add --page flag to search command"
```

---

### Task 3: Info command — `--max-value-size` flag

**Files:**
- Modify: `tests/test_cli.py`
- Modify: `src/riszotto/cli.py`

**Step 1: Write failing tests for --max-value-size**

Append to `tests/test_cli.py` inside `TestInfo`:

```python
    @patch("riszotto.cli.get_client")
    def test_info_hides_long_values(self, mock_get_client):
        mock_zot = MagicMock()
        mock_get_client.return_value = mock_zot
        mock_zot.item.return_value = {
            "data": {
                "key": "ABC12345",
                "title": "Short",
                "abstractNote": "A" * 300,
            }
        }
        result = runner.invoke(app, ["info", "ABC12345"])
        assert result.exit_code == 0
        parsed = json.loads(result.output)
        assert parsed["title"] == "Short"
        assert parsed["abstractNote"] == "<hidden (300 chars)>"

    @patch("riszotto.cli.get_client")
    def test_info_max_value_size_zero_shows_all(self, mock_get_client):
        mock_zot = MagicMock()
        mock_get_client.return_value = mock_zot
        long_abstract = "A" * 300
        mock_zot.item.return_value = {
            "data": {
                "key": "ABC12345",
                "title": "Short",
                "abstractNote": long_abstract,
            }
        }
        result = runner.invoke(app, ["info", "--max-value-size", "0", "ABC12345"])
        assert result.exit_code == 0
        parsed = json.loads(result.output)
        assert parsed["abstractNote"] == long_abstract

    @patch("riszotto.cli.get_client")
    def test_info_max_value_size_custom(self, mock_get_client):
        mock_zot = MagicMock()
        mock_get_client.return_value = mock_zot
        mock_zot.item.return_value = {
            "data": {
                "key": "ABC12345",
                "title": "Short title",
                "abstractNote": "A" * 100,
            }
        }
        result = runner.invoke(app, ["info", "--max-value-size", "50", "ABC12345"])
        assert result.exit_code == 0
        parsed = json.loads(result.output)
        assert parsed["title"] == "Short title"  # 11 chars, under 50
        assert parsed["abstractNote"] == "<hidden (100 chars)>"
```

**Step 2: Run tests to verify they fail**

```bash
uv run pytest tests/test_cli.py::TestInfo -v
```

Expected: FAIL — `test_info_hides_long_values` fails because current `info` shows the full value.

**Step 3: Add helper and update info command in cli.py**

Add this helper function after `_format_year` in `src/riszotto/cli.py`:

```python
def _filter_long_values(data: dict, max_size: int) -> dict:
    """Replace string values longer than max_size with a placeholder."""
    if max_size <= 0:
        return data
    filtered = {}
    for k, v in data.items():
        if isinstance(v, str) and len(v) > max_size:
            filtered[k] = f"<hidden ({len(v)} chars)>"
        else:
            filtered[k] = v
    return filtered
```

Replace the `info` function in `src/riszotto/cli.py`:

```python
@app.command()
def info(
    key: Annotated[str, typer.Argument(help="Zotero item key")],
    max_value_size: Annotated[int, typer.Option("--max-value-size", help="Hide string values longer than this (0 = show all)")] = 200,
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

    data = item.get("data", {})
    data = _filter_long_values(data, max_value_size)
    typer.echo(json.dumps(data, indent=2))
```

**Step 4: Run tests to verify they pass**

```bash
uv run pytest tests/test_cli.py::TestInfo -v
```

Expected: All PASS (5 tests).

**Step 5: Commit**

```bash
git add src/riszotto/cli.py tests/test_cli.py
git commit -m "feat: add --max-value-size flag to info command"
```

---

### Task 4: Show pagination — `--page` and `--page-size` flags

**Files:**
- Modify: `tests/test_cli.py`
- Modify: `src/riszotto/cli.py`

**Step 1: Write failing tests for show pagination**

Append to `tests/test_cli.py` inside `TestShow`:

```python
    @patch("riszotto.cli.MarkItDown")
    @patch("riszotto.cli.get_client")
    def test_show_page_default_paginates(self, mock_get_client, mock_markitdown_cls):
        mock_zot = MagicMock()
        mock_get_client.return_value = mock_zot
        mock_zot.children.return_value = [
            {
                "data": {"key": "ATT1", "itemType": "attachment", "contentType": "application/pdf", "filename": "paper.pdf"},
                "links": {"enclosure": {"href": "file:///path/to/paper.pdf"}},
            }
        ]
        mock_md = MagicMock()
        mock_markitdown_cls.return_value = mock_md
        mock_result = MagicMock()
        # 10 lines of content, page_size=5
        mock_result.markdown = "\n".join(f"Line {i}" for i in range(1, 11))
        mock_md.convert.return_value = mock_result

        result = runner.invoke(app, ["show", "--page-size", "5", "PARENT1"])
        assert result.exit_code == 0
        assert "Line 1" in result.output
        assert "Line 5" in result.output
        assert "Line 6" not in result.output
        assert "Page 1/2" in result.output

    @patch("riszotto.cli.MarkItDown")
    @patch("riszotto.cli.get_client")
    def test_show_page_2(self, mock_get_client, mock_markitdown_cls):
        mock_zot = MagicMock()
        mock_get_client.return_value = mock_zot
        mock_zot.children.return_value = [
            {
                "data": {"key": "ATT1", "itemType": "attachment", "contentType": "application/pdf", "filename": "paper.pdf"},
                "links": {"enclosure": {"href": "file:///path/to/paper.pdf"}},
            }
        ]
        mock_md = MagicMock()
        mock_markitdown_cls.return_value = mock_md
        mock_result = MagicMock()
        mock_result.markdown = "\n".join(f"Line {i}" for i in range(1, 11))
        mock_md.convert.return_value = mock_result

        result = runner.invoke(app, ["show", "--page", "2", "--page-size", "5", "PARENT1"])
        assert result.exit_code == 0
        assert "Line 6" in result.output
        assert "Line 10" in result.output
        assert "Line 5" not in result.output

    @patch("riszotto.cli.MarkItDown")
    @patch("riszotto.cli.get_client")
    def test_show_page_zero_dumps_all(self, mock_get_client, mock_markitdown_cls):
        mock_zot = MagicMock()
        mock_get_client.return_value = mock_zot
        mock_zot.children.return_value = [
            {
                "data": {"key": "ATT1", "itemType": "attachment", "contentType": "application/pdf", "filename": "paper.pdf"},
                "links": {"enclosure": {"href": "file:///path/to/paper.pdf"}},
            }
        ]
        mock_md = MagicMock()
        mock_markitdown_cls.return_value = mock_md
        mock_result = MagicMock()
        mock_result.markdown = "\n".join(f"Line {i}" for i in range(1, 11))
        mock_md.convert.return_value = mock_result

        result = runner.invoke(app, ["show", "--page", "0", "--page-size", "5", "PARENT1"])
        assert result.exit_code == 0
        assert "Line 1" in result.output
        assert "Line 10" in result.output

    @patch("riszotto.cli.MarkItDown")
    @patch("riszotto.cli.get_client")
    def test_show_page_out_of_range(self, mock_get_client, mock_markitdown_cls):
        mock_zot = MagicMock()
        mock_get_client.return_value = mock_zot
        mock_zot.children.return_value = [
            {
                "data": {"key": "ATT1", "itemType": "attachment", "contentType": "application/pdf", "filename": "paper.pdf"},
                "links": {"enclosure": {"href": "file:///path/to/paper.pdf"}},
            }
        ]
        mock_md = MagicMock()
        mock_markitdown_cls.return_value = mock_md
        mock_result = MagicMock()
        mock_result.markdown = "Short doc"
        mock_md.convert.return_value = mock_result

        result = runner.invoke(app, ["show", "--page", "99", "--page-size", "5", "PARENT1"])
        assert result.exit_code == 1
        assert "out of range" in result.output.lower()
```

**Step 2: Run tests to verify they fail**

```bash
uv run pytest tests/test_cli.py::TestShow::test_show_page_default_paginates tests/test_cli.py::TestShow::test_show_page_2 tests/test_cli.py::TestShow::test_show_page_zero_dumps_all tests/test_cli.py::TestShow::test_show_page_out_of_range -v
```

Expected: FAIL — show doesn't have `--page` yet.

**Step 3: Replace show command in cli.py**

Replace the `show` function in `src/riszotto/cli.py`:

```python
@app.command()
def show(
    key: Annotated[str, typer.Argument(help="Zotero item key")],
    attachment: Annotated[int, typer.Option("--attachment", "-a", help="PDF attachment index (1-indexed)")] = 1,
    page: Annotated[int, typer.Option("--page", "-p", help="Page number (1-indexed, 0 = show all)")] = 1,
    page_size: Annotated[int, typer.Option("--page-size", help="Lines per page")] = 500,
    search: Annotated[Optional[str], typer.Option("--search", "-s", help="Show only sections matching this term")] = None,
) -> None:
    """Convert a paper's PDF attachment to markdown."""
    if search is not None and page != 1:
        typer.echo("--search and --page cannot be used together.", err=True)
        raise typer.Exit(1)

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
        typer.echo("Could not determine local file path for attachment.", err=True)
        raise typer.Exit(1)

    try:
        md = MarkItDown()
        result = md.convert(file_path)
        markdown = result.markdown
    except Exception as e:
        typer.echo(f"Failed to convert PDF to markdown: {e}", err=True)
        raise typer.Exit(1)

    if search is not None:
        _show_search(markdown, search)
        return

    _show_paginated(markdown, page, page_size, key)
```

Add these two helper functions after `_filter_long_values` in `src/riszotto/cli.py`:

```python
def _show_paginated(markdown: str, page: int, page_size: int, key: str) -> None:
    """Print a page of markdown lines."""
    lines = markdown.splitlines()
    total_lines = len(lines)

    if page == 0:
        typer.echo(markdown)
        return

    total_pages = max(1, -(-total_lines // page_size))  # ceil division
    if page > total_pages:
        typer.echo(f"Page {page} out of range. Document has {total_pages} page(s).", err=True)
        raise typer.Exit(1)

    start = (page - 1) * page_size
    end = start + page_size
    typer.echo("\n".join(lines[start:end]))

    if total_pages > 1:
        typer.echo(f"\nPage {page}/{total_pages}. Next: riszotto show --page {page + 1} {key}")


def _show_search(markdown: str, term: str) -> None:
    """Print markdown sections matching a search term."""
    pass  # implemented in Task 5
```

**Step 4: Update existing test_show_converts_pdf**

The existing `test_show_converts_pdf` test creates a short markdown (2 lines) which fits in one page, so it will still pass. But the output now might include a footer. The test checks `assert "# Paper Title" in result.output` which will still be true. No change needed for existing tests.

**Step 5: Run tests to verify they pass**

```bash
uv run pytest tests/test_cli.py::TestShow -v
```

Expected: All PASS (7 tests).

**Step 6: Commit**

```bash
git add src/riszotto/cli.py tests/test_cli.py
git commit -m "feat: add --page and --page-size flags to show command"
```

---

### Task 5: Show search — `--search` flag with heading-based sections

**Files:**
- Modify: `tests/test_cli.py`
- Modify: `src/riszotto/cli.py`

**Step 1: Write failing tests for --search**

Append to `tests/test_cli.py` inside `TestShow`:

```python
    @patch("riszotto.cli.MarkItDown")
    @patch("riszotto.cli.get_client")
    def test_show_search_finds_sections(self, mock_get_client, mock_markitdown_cls):
        mock_zot = MagicMock()
        mock_get_client.return_value = mock_zot
        mock_zot.children.return_value = [
            {
                "data": {"key": "ATT1", "itemType": "attachment", "contentType": "application/pdf", "filename": "paper.pdf"},
                "links": {"enclosure": {"href": "file:///path/to/paper.pdf"}},
            }
        ]
        mock_md = MagicMock()
        mock_markitdown_cls.return_value = mock_md
        mock_result = MagicMock()
        mock_result.markdown = (
            "# Introduction\n\nThis paper studies regression.\n\n"
            "## Methods\n\nWe used a neural network.\n\n"
            "## Results\n\nRegression analysis showed improvement.\n\n"
            "## Conclusion\n\nFuture work needed."
        )
        mock_md.convert.return_value = mock_result

        result = runner.invoke(app, ["show", "--search", "regression", "PARENT1"])
        assert result.exit_code == 0
        assert "# Introduction" in result.output
        assert "## Results" in result.output
        assert "## Methods" not in result.output
        assert "## Conclusion" not in result.output

    @patch("riszotto.cli.MarkItDown")
    @patch("riszotto.cli.get_client")
    def test_show_search_no_match(self, mock_get_client, mock_markitdown_cls):
        mock_zot = MagicMock()
        mock_get_client.return_value = mock_zot
        mock_zot.children.return_value = [
            {
                "data": {"key": "ATT1", "itemType": "attachment", "contentType": "application/pdf", "filename": "paper.pdf"},
                "links": {"enclosure": {"href": "file:///path/to/paper.pdf"}},
            }
        ]
        mock_md = MagicMock()
        mock_markitdown_cls.return_value = mock_md
        mock_result = MagicMock()
        mock_result.markdown = "# Introduction\n\nSome content.\n\n## Methods\n\nMore content."
        mock_md.convert.return_value = mock_result

        result = runner.invoke(app, ["show", "--search", "nonexistent", "PARENT1"])
        assert result.exit_code == 0
        assert "No sections matching" in result.output

    @patch("riszotto.cli.MarkItDown")
    @patch("riszotto.cli.get_client")
    def test_show_search_case_insensitive(self, mock_get_client, mock_markitdown_cls):
        mock_zot = MagicMock()
        mock_get_client.return_value = mock_zot
        mock_zot.children.return_value = [
            {
                "data": {"key": "ATT1", "itemType": "attachment", "contentType": "application/pdf", "filename": "paper.pdf"},
                "links": {"enclosure": {"href": "file:///path/to/paper.pdf"}},
            }
        ]
        mock_md = MagicMock()
        mock_markitdown_cls.return_value = mock_md
        mock_result = MagicMock()
        mock_result.markdown = "# Introduction\n\nMachine Learning is great.\n\n## Methods\n\nOther stuff."
        mock_md.convert.return_value = mock_result

        result = runner.invoke(app, ["show", "--search", "MACHINE LEARNING", "PARENT1"])
        assert result.exit_code == 0
        assert "# Introduction" in result.output
        assert "## Methods" not in result.output
```

**Step 2: Run tests to verify they fail**

```bash
uv run pytest tests/test_cli.py::TestShow::test_show_search_finds_sections tests/test_cli.py::TestShow::test_show_search_no_match tests/test_cli.py::TestShow::test_show_search_case_insensitive -v
```

Expected: FAIL — `_show_search` is a stub.

**Step 3: Implement _show_search in cli.py**

Add `import re` at the top of `src/riszotto/cli.py` (with the other imports).

Replace the `_show_search` stub:

```python
def _show_search(markdown: str, term: str) -> None:
    """Print markdown sections matching a search term."""
    sections: list[str] = []
    current: list[str] = []

    for line in markdown.splitlines():
        if re.match(r"^#{1,6}\s", line) and current:
            sections.append("\n".join(current))
            current = []
        current.append(line)
    if current:
        sections.append("\n".join(current))

    term_lower = term.lower()
    matches = [s for s in sections if term_lower in s.lower()]

    if not matches:
        typer.echo(f"No sections matching '{term}' found.")
        return

    typer.echo("\n\n".join(matches))
```

**Step 4: Run tests to verify they pass**

```bash
uv run pytest tests/test_cli.py::TestShow -v
```

Expected: All PASS (10 tests).

**Step 5: Run full test suite**

```bash
uv run pytest tests/ -v
```

Expected: All tests PASS.

**Step 6: Commit**

```bash
git add src/riszotto/cli.py tests/test_cli.py
git commit -m "feat: add --search flag to show command with heading-based section filtering"
```

---

### Task 6: Smoke test all new features

**Prerequisite:** Zotero desktop must be running with the local API enabled.

**Step 1: Test search pagination**

```bash
uv run riszotto search machine learning
uv run riszotto search --page 2 machine learning
```

Expected: Page 1 shows results 1-25 with footer. Page 2 shows results 26-50.

**Step 2: Test info filtering**

```bash
uv run riszotto info <KEY>
uv run riszotto info --max-value-size 0 <KEY>
```

Expected: Default hides long abstractNote. `--max-value-size 0` shows everything.

**Step 3: Test show pagination**

```bash
uv run riszotto show <KEY>
uv run riszotto show --page 2 <KEY>
uv run riszotto show --page 0 <KEY>
```

Expected: Page 1 shows first 500 lines with footer. Page 2 shows next chunk. Page 0 dumps all.

**Step 4: Test show search**

```bash
uv run riszotto show --search "results" <KEY>
```

Expected: Only sections containing "results" are printed.

**Step 5: Commit any fixes if needed**
