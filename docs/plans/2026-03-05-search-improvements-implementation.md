# Search Improvements Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Replace compact table search output with JSON envelope, revert default search mode to metadata-only, and remove the redundant `info` command.

**Architecture:** The `search` command outputs a JSON object with `page`, `limit`, `start`, and `results` fields. Each result contains `key`, `title`, `itemType`, `date`, `authors`, `abstract`, and `tags` extracted from the Zotero item dict. A `--max-value-size` option (default 200) truncates long string values using the existing `_filter_long_values` helper. The `info` command is removed entirely.

**Tech Stack:** Python, typer, pyzotero, pytest

---

### Task 1: Revert full_text default to False

**Files:**
- Modify: `src/riszotto/cli.py:53`

**Step 1: Change the default**

In `src/riszotto/cli.py`, change line 53 from:

```python
    full_text: Annotated[bool, typer.Option("--full-text/--no-full-text", help="Search all fields including full-text")] = True,
```

to:

```python
    full_text: Annotated[bool, typer.Option("--full-text/--no-full-text", help="Search all fields including full-text")] = False,
```

**Step 2: Run existing tests to verify nothing breaks**

Run: `uv run pytest tests/test_cli.py::TestSearch -v`
Expected: all tests PASS (existing tests already assumed `False` default — `test_search_limit_flag` and `test_search_page_flag` assert `qmode="titleCreatorYear"`)

**Step 3: Commit**

```bash
git add src/riszotto/cli.py
git commit -m "fix: revert search default to metadata-only mode"
```

---

### Task 2: Add _format_result helper and JSON output to search

**Files:**
- Modify: `src/riszotto/cli.py`
- Test: `tests/test_cli.py`

**Step 1: Write failing tests**

Replace `TestSearch.test_search_shows_table` and `test_search_no_results` in `tests/test_cli.py` with JSON-based tests. Also add a test for `--max-value-size`. Replace the entire `TestSearch` class:

```python
class TestSearch:
    @patch("riszotto.cli.get_client")
    def test_search_outputs_json_envelope(self, mock_get_client):
        mock_zot = MagicMock()
        mock_get_client.return_value = mock_zot
        mock_zot.items.return_value = [
            {
                "data": {
                    "key": "ABC12345",
                    "title": "Attention Is All You Need",
                    "itemType": "journalArticle",
                    "date": "2017-06-12",
                    "abstractNote": "We propose a new architecture.",
                    "creators": [
                        {"firstName": "Ashish", "lastName": "Vaswani", "creatorType": "author"},
                        {"firstName": "Noam", "lastName": "Shazeer", "creatorType": "author"},
                    ],
                    "tags": [{"tag": "transformers"}, {"tag": "NLP"}],
                },
                "meta": {"creatorSummary": "Vaswani et al."},
            }
        ]
        result = runner.invoke(app, ["search", "attention"])
        assert result.exit_code == 0
        parsed = json.loads(result.output)
        assert parsed["page"] == 1
        assert parsed["limit"] == 25
        assert parsed["start"] == 0
        assert len(parsed["results"]) == 1
        item = parsed["results"][0]
        assert item["key"] == "ABC12345"
        assert item["title"] == "Attention Is All You Need"
        assert item["itemType"] == "journalArticle"
        assert item["date"] == "2017-06-12"
        assert item["authors"] == ["Vaswani, Ashish", "Shazeer, Noam"]
        assert item["abstract"] == "We propose a new architecture."
        assert item["tags"] == ["transformers", "NLP"]

    @patch("riszotto.cli.get_client")
    def test_search_no_results(self, mock_get_client):
        mock_zot = MagicMock()
        mock_get_client.return_value = mock_zot
        mock_zot.items.return_value = []
        result = runner.invoke(app, ["search", "nonexistent"])
        assert result.exit_code == 0
        parsed = json.loads(result.output)
        assert parsed["results"] == []

    @patch("riszotto.cli.get_client")
    def test_search_full_text_flag(self, mock_get_client):
        mock_zot = MagicMock()
        mock_get_client.return_value = mock_zot
        mock_zot.items.return_value = []
        runner.invoke(app, ["search", "--full-text", "deep learning"])
        mock_zot.items.assert_called_once_with(q="deep learning", qmode="everything", limit=25, start=0)

    @patch("riszotto.cli.get_client")
    def test_search_limit_flag(self, mock_get_client):
        mock_zot = MagicMock()
        mock_get_client.return_value = mock_zot
        mock_zot.items.return_value = []
        runner.invoke(app, ["search", "--limit", "5", "test"])
        mock_zot.items.assert_called_once_with(q="test", qmode="titleCreatorYear", limit=5, start=0)

    @patch("riszotto.cli.get_client")
    def test_search_zotero_not_running(self, mock_get_client):
        mock_get_client.side_effect = ConnectionError("connection refused")
        result = runner.invoke(app, ["search", "test"])
        assert result.exit_code == 1
        assert "Zotero desktop is not running" in result.output

    @patch("riszotto.cli.get_client")
    def test_search_page_flag(self, mock_get_client):
        mock_zot = MagicMock()
        mock_get_client.return_value = mock_zot
        mock_zot.items.return_value = []
        runner.invoke(app, ["search", "--page", "3", "test"])
        mock_zot.items.assert_called_once_with(q="test", qmode="titleCreatorYear", limit=25, start=50)

    @patch("riszotto.cli.get_client")
    def test_search_page_in_envelope(self, mock_get_client):
        mock_zot = MagicMock()
        mock_get_client.return_value = mock_zot
        mock_zot.items.return_value = []
        result = runner.invoke(app, ["search", "--page", "2", "--limit", "10", "test"])
        assert result.exit_code == 0
        parsed = json.loads(result.output)
        assert parsed["page"] == 2
        assert parsed["limit"] == 10
        assert parsed["start"] == 10

    @patch("riszotto.cli.get_client")
    def test_search_max_value_size_truncates(self, mock_get_client):
        mock_zot = MagicMock()
        mock_get_client.return_value = mock_zot
        long_abstract = "A" * 300
        mock_zot.items.return_value = [
            {
                "data": {
                    "key": "ABC12345",
                    "title": "Short",
                    "itemType": "journalArticle",
                    "date": "2024",
                    "abstractNote": long_abstract,
                    "creators": [],
                    "tags": [],
                },
                "meta": {},
            }
        ]
        result = runner.invoke(app, ["search", "test"])
        assert result.exit_code == 0
        parsed = json.loads(result.output)
        assert parsed["results"][0]["abstract"] == "<hidden (300 chars)>"

    @patch("riszotto.cli.get_client")
    def test_search_max_value_size_zero_shows_all(self, mock_get_client):
        mock_zot = MagicMock()
        mock_get_client.return_value = mock_zot
        long_abstract = "A" * 300
        mock_zot.items.return_value = [
            {
                "data": {
                    "key": "ABC12345",
                    "title": "Short",
                    "itemType": "journalArticle",
                    "date": "2024",
                    "abstractNote": long_abstract,
                    "creators": [],
                    "tags": [],
                },
                "meta": {},
            }
        ]
        result = runner.invoke(app, ["search", "--max-value-size", "0", "test"])
        assert result.exit_code == 0
        parsed = json.loads(result.output)
        assert parsed["results"][0]["abstract"] == long_abstract

    @patch("riszotto.cli.get_client")
    def test_search_creator_name_field(self, mock_get_client):
        """Creators with 'name' instead of firstName/lastName (e.g. institutions)."""
        mock_zot = MagicMock()
        mock_get_client.return_value = mock_zot
        mock_zot.items.return_value = [
            {
                "data": {
                    "key": "X1",
                    "title": "T",
                    "itemType": "journalArticle",
                    "date": "2024",
                    "abstractNote": "",
                    "creators": [{"name": "WHO", "creatorType": "author"}],
                    "tags": [],
                },
                "meta": {},
            }
        ]
        result = runner.invoke(app, ["search", "test"])
        parsed = json.loads(result.output)
        assert parsed["results"][0]["authors"] == ["WHO"]
```

**Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_cli.py::TestSearch -v`
Expected: FAIL — output is still a table, not JSON

**Step 3: Add `_format_result` helper and rewrite search command**

In `src/riszotto/cli.py`, add a `_format_result` function and rewrite the `search` command body.

Remove the `_format_author` and `_format_year` helpers (no longer used).

Add this helper before the `search` command:

```python
def _format_creator(creator: dict) -> str:
    """Format a single Zotero creator dict as a string."""
    last = creator.get("lastName", "")
    first = creator.get("firstName", "")
    if last and first:
        return f"{last}, {first}"
    return creator.get("name", last or first)


def _format_result(item: dict, max_value_size: int) -> dict:
    """Extract display fields from a Zotero item."""
    data = item.get("data", {})
    result = {
        "key": data.get("key", ""),
        "title": data.get("title", ""),
        "itemType": data.get("itemType", ""),
        "date": data.get("date", ""),
        "authors": [_format_creator(c) for c in data.get("creators", [])],
        "abstract": data.get("abstractNote", ""),
        "tags": [t["tag"] for t in data.get("tags", [])],
    }
    return _filter_long_values(result, max_value_size)
```

Rewrite the `search` command:

```python
@app.command()
def search(
    terms: Annotated[list[str], typer.Argument(help="Search terms")],
    full_text: Annotated[bool, typer.Option("--full-text/--no-full-text", help="Search all fields including full-text")] = False,
    limit: Annotated[int, typer.Option("--limit", "-l", help="Maximum number of results")] = 25,
    page: Annotated[int, typer.Option("--page", "-p", help="Page number (1-indexed)")] = 1,
    max_value_size: Annotated[int, typer.Option("--max-value-size", help="Hide string values longer than this (0 = show all)")] = 200,
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

    envelope = {
        "page": page,
        "limit": limit,
        "start": start,
        "results": [_format_result(item, max_value_size) for item in results],
    }
    typer.echo(json.dumps(envelope, indent=2))
```

**Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_cli.py::TestSearch -v`
Expected: all PASS

**Step 5: Commit**

```bash
git add src/riszotto/cli.py tests/test_cli.py
git commit -m "feat: replace table output with JSON envelope in search"
```

---

### Task 3: Remove info command and its tests

**Files:**
- Modify: `src/riszotto/cli.py` (remove `info` function and `get_item` import)
- Modify: `tests/test_cli.py` (remove `TestInfo` and `TestInfoMaxValueSize` classes)

**Step 1: Remove the info command**

In `src/riszotto/cli.py`:
- Remove the `get_item` import from line 11 (keep `get_client`, `get_pdf_attachments`, `get_pdf_path`, `search_items`)
- Delete the entire `info` function (the `@app.command()` block at lines 91-113)

**Step 2: Remove info tests**

In `tests/test_cli.py`, delete the entire `TestInfo` class and `TestInfoMaxValueSize` class.

**Step 3: Run all tests**

Run: `uv run pytest tests/ -v`
Expected: all PASS

**Step 4: Commit**

```bash
git add src/riszotto/cli.py tests/test_cli.py
git commit -m "refactor: remove redundant info command"
```

---

### Task 4: Clean up unused code

**Files:**
- Modify: `src/riszotto/cli.py` (remove `_format_author`, `_format_year`)

**Step 1: Remove dead helpers**

In `src/riszotto/cli.py`, delete the `_format_author` and `_format_year` functions — they were only used by the old table output.

Also remove `Optional` from the typing imports if it's no longer used elsewhere — check the `show` command signature which uses `Optional[str]`. If still used, keep it.

**Step 2: Run all tests**

Run: `uv run pytest tests/ -v`
Expected: all PASS

**Step 3: Commit**

```bash
git add src/riszotto/cli.py
git commit -m "chore: remove unused table formatting helpers"
```

---

### Task 5: Manual smoke test

**Step 1: Test basic search**

Run: `uv run riszotto search d3 grimme`
Expected: JSON output with relevant Grimme D3 papers, not citation noise

**Step 2: Test with jq**

Run: `uv run riszotto search d3 grimme | jq '.results[].title'`
Expected: titles printed one per line

**Step 3: Test full-text opt-in**

Run: `uv run riszotto search --full-text d3 grimme | jq '.results | length'`
Expected: more results (including citation matches)

**Step 4: Test max-value-size**

Run: `uv run riszotto search --max-value-size 0 d3 grimme | jq '.results[0].abstract'`
Expected: full abstract text, not truncated

**Step 5: Verify info command is gone**

Run: `uv run riszotto info ABC12345`
Expected: error — "No such command 'info'"
