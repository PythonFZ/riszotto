# New Commands Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add tag/type/sort/since filters to search, a collections command, and a recent command.

**Architecture:** New flags on `search` pass through to pyzotero's `.items()` kwargs. New client functions wrap `zot.collections()`, `zot.collection_items()`, and `zot.items(sort=..., direction=...)`. CLI commands output the same JSON envelope format. A shared `_zotero_connection` context manager DRYs up the repeated connection error handling.

**Tech Stack:** Python, typer, pyzotero, pytest

---

### Task 1: Extract shared connection error handling

The same try/except pattern for Zotero connection errors appears in `search` and `show`. Before adding more commands, DRY this up.

**Files:**
- Modify: `src/riszotto/cli.py`
- Test: `tests/test_cli.py`

**Step 1: Write failing test**

Add to `tests/test_cli.py`:

```python
class TestConnectionError:
    @patch("riszotto.cli.get_client")
    def test_collections_zotero_not_running(self, mock_get_client):
        mock_get_client.side_effect = ConnectionError("connection refused")
        result = runner.invoke(app, ["collections"])
        assert result.exit_code == 1
        assert "Zotero desktop is not running" in result.output
```

**Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_cli.py::TestConnectionError -v`
Expected: FAIL — `collections` command doesn't exist yet

**Step 3: Add `_get_zot` helper and stub `collections` command**

In `src/riszotto/cli.py`, add a helper that wraps `get_client()` with the connection error handling, and a minimal `collections` command:

```python
def _get_zot() -> zotero.Zotero:
    """Get Zotero client, raising typer.Exit on connection failure."""
    try:
        return get_client()
    except (ConnectionError, Exception) as e:
        if "connection" in str(e).lower() or "refused" in str(e).lower():
            typer.echo(
                "Zotero desktop is not running. Start Zotero and ensure the local API is enabled.",
                err=True,
            )
            raise typer.Exit(1)
        raise
```

Add the import at top of `cli.py`:

```python
from pyzotero import zotero
```

Then refactor `search` and `show` to use `_get_zot()` instead of the inline try/except. Replace:

```python
    try:
        zot = get_client()
        results = search_items(zot, query, ...)
    except (ConnectionError, Exception) as e:
        if "connection" in str(e).lower() or "refused" in str(e).lower():
            typer.echo("Zotero desktop is not running...", err=True)
            raise typer.Exit(1)
        raise
```

With:

```python
    zot = _get_zot()
    results = search_items(zot, query, ...)
```

Do the same for `show`. Then add a stub `collections` command:

```python
@app.command()
def collections(
    key: Annotated[Optional[str], typer.Argument(help="Collection key (omit to list all)")] = None,
) -> None:
    """List collections or items in a collection."""
    zot = _get_zot()
    typer.echo(json.dumps({"results": []}, indent=2))
```

**Step 4: Run all tests**

Run: `uv run pytest tests/ -v`
Expected: all PASS (existing tests still work with refactored error handling, new test passes)

**Step 5: Commit**

```bash
git add src/riszotto/cli.py tests/test_cli.py
git commit -m "refactor: extract shared Zotero connection error handling

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>"
```

---

### Task 2: Add search filters (--tag, --item-type, --since, --sort, --direction)

**Files:**
- Modify: `src/riszotto/client.py` — extend `search_items` signature
- Modify: `src/riszotto/cli.py` — add new flags to `search` command
- Test: `tests/test_client.py`, `tests/test_cli.py`

**Step 1: Write failing client tests**

Add to `tests/test_client.py` in `TestSearchItems`:

```python
    def test_search_with_tag_filter(self):
        mock_zot = MagicMock()
        mock_zot.items.return_value = []
        search_items(mock_zot, "test", tag=["machine learning"])
        mock_zot.items.assert_called_once_with(
            q="test", qmode="titleCreatorYear", limit=25, start=0,
            tag="machine learning",
        )

    def test_search_with_multiple_tags(self):
        mock_zot = MagicMock()
        mock_zot.items.return_value = []
        search_items(mock_zot, "test", tag=["ml", "physics"])
        mock_zot.items.assert_called_once_with(
            q="test", qmode="titleCreatorYear", limit=25, start=0,
            tag=["ml", "physics"],
        )

    def test_search_with_item_type(self):
        mock_zot = MagicMock()
        mock_zot.items.return_value = []
        search_items(mock_zot, "test", item_type="journalArticle")
        mock_zot.items.assert_called_once_with(
            q="test", qmode="titleCreatorYear", limit=25, start=0,
            itemType="journalArticle",
        )

    def test_search_with_since(self):
        mock_zot = MagicMock()
        mock_zot.items.return_value = []
        search_items(mock_zot, "test", since="2024-01-01")
        mock_zot.items.assert_called_once_with(
            q="test", qmode="titleCreatorYear", limit=25, start=0,
            since="2024-01-01",
        )

    def test_search_with_sort(self):
        mock_zot = MagicMock()
        mock_zot.items.return_value = []
        search_items(mock_zot, "test", sort="dateModified", direction="asc")
        mock_zot.items.assert_called_once_with(
            q="test", qmode="titleCreatorYear", limit=25, start=0,
            sort="dateModified", direction="asc",
        )
```

**Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_client.py::TestSearchItems::test_search_with_tag_filter -v`
Expected: FAIL — `search_items` doesn't accept `tag` parameter

**Step 3: Extend `search_items` in client.py**

Replace the `search_items` function in `src/riszotto/client.py`:

```python
def search_items(
    zot: zotero.Zotero,
    query: str,
    *,
    full_text: bool = False,
    limit: int = 25,
    start: int = 0,
    tag: list[str] | None = None,
    item_type: str | None = None,
    since: str | None = None,
    sort: str | None = None,
    direction: str | None = None,
) -> list[dict[str, Any]]:
    """Search the Zotero library, resolving child items to their parents."""
    qmode = "everything" if full_text else "titleCreatorYear"
    kwargs: dict[str, Any] = {"q": query, "qmode": qmode, "limit": limit, "start": start}
    if tag is not None:
        kwargs["tag"] = tag if len(tag) > 1 else tag[0]
    if item_type is not None:
        kwargs["itemType"] = item_type
    if since is not None:
        kwargs["since"] = since
    if sort is not None:
        kwargs["sort"] = sort
    if direction is not None:
        kwargs["direction"] = direction
    raw = zot.items(**kwargs)

    results: list[dict[str, Any]] = []
    seen_keys: set[str] = set()

    for item in raw:
        data = item.get("data", {})
        if data.get("itemType") in _CHILD_ITEM_TYPES:
            parent_key = data.get("parentItem")
            if not parent_key or parent_key in seen_keys:
                continue
            seen_keys.add(parent_key)
            results.append(zot.item(parent_key))
        else:
            key = data.get("key", "")
            if key in seen_keys:
                continue
            seen_keys.add(key)
            results.append(item)

    return results
```

**Step 4: Run client tests**

Run: `uv run pytest tests/test_client.py::TestSearchItems -v`
Expected: all PASS

**Step 5: Write failing CLI tests**

Add to `TestSearch` in `tests/test_cli.py`:

```python
    @patch("riszotto.cli.get_client")
    def test_search_tag_flag(self, mock_get_client):
        mock_zot = MagicMock()
        mock_get_client.return_value = mock_zot
        mock_zot.items.return_value = []
        runner.invoke(app, ["search", "--tag", "physics", "test"])
        mock_zot.items.assert_called_once_with(
            q="test", qmode="titleCreatorYear", limit=25, start=0,
            tag="physics",
        )

    @patch("riszotto.cli.get_client")
    def test_search_multiple_tags(self, mock_get_client):
        mock_zot = MagicMock()
        mock_get_client.return_value = mock_zot
        mock_zot.items.return_value = []
        runner.invoke(app, ["search", "--tag", "ml", "--tag", "physics", "test"])
        mock_zot.items.assert_called_once_with(
            q="test", qmode="titleCreatorYear", limit=25, start=0,
            tag=["ml", "physics"],
        )

    @patch("riszotto.cli.get_client")
    def test_search_item_type_flag(self, mock_get_client):
        mock_zot = MagicMock()
        mock_get_client.return_value = mock_zot
        mock_zot.items.return_value = []
        runner.invoke(app, ["search", "--item-type", "book", "test"])
        mock_zot.items.assert_called_once_with(
            q="test", qmode="titleCreatorYear", limit=25, start=0,
            itemType="book",
        )

    @patch("riszotto.cli.get_client")
    def test_search_sort_flags(self, mock_get_client):
        mock_zot = MagicMock()
        mock_get_client.return_value = mock_zot
        mock_zot.items.return_value = []
        runner.invoke(app, ["search", "--sort", "dateModified", "--direction", "asc", "test"])
        mock_zot.items.assert_called_once_with(
            q="test", qmode="titleCreatorYear", limit=25, start=0,
            sort="dateModified", direction="asc",
        )
```

**Step 6: Add flags to `search` command in cli.py**

Update the `search` function signature to add new parameters:

```python
@app.command()
def search(
    terms: Annotated[list[str], typer.Argument(help="Search terms")],
    full_text: Annotated[bool, typer.Option("--full-text/--no-full-text", help="Search all fields including full-text")] = False,
    limit: Annotated[int, typer.Option("--limit", "-l", help="Maximum number of results")] = 25,
    page: Annotated[int, typer.Option("--page", "-p", help="Page number (1-indexed)")] = 1,
    max_value_size: Annotated[int, typer.Option("--max-value-size", help="Hide string values longer than this (0 = show all)")] = 200,
    tag: Annotated[Optional[list[str]], typer.Option("--tag", "-t", help="Filter by tag (repeatable, AND logic)")] = None,
    item_type: Annotated[Optional[str], typer.Option("--item-type", help="Filter by item type (e.g. journalArticle, book)")] = None,
    since: Annotated[Optional[str], typer.Option("--since", help="Only items modified after this date")] = None,
    sort: Annotated[Optional[str], typer.Option("--sort", help="Sort field (e.g. dateModified, title, creator)")] = None,
    direction: Annotated[Optional[str], typer.Option("--direction", help="Sort direction (asc or desc)")] = None,
) -> None:
    """Search for papers in your Zotero library."""
    query = " ".join(terms)
    start = (page - 1) * limit
    zot = _get_zot()
    results = search_items(
        zot, query, full_text=full_text, limit=limit, start=start,
        tag=tag, item_type=item_type, since=since, sort=sort, direction=direction,
    )

    envelope = {
        "page": page,
        "limit": limit,
        "start": start,
        "results": [_format_result(item, max_value_size) for item in results],
    }
    typer.echo(json.dumps(envelope, indent=2))
```

Update the import at top of `cli.py` to include `search_items` kwargs — no change needed since `search_items` is already imported.

**Step 7: Run all tests**

Run: `uv run pytest tests/ -v`
Expected: all PASS

**Step 8: Commit**

```bash
git add src/riszotto/client.py src/riszotto/cli.py tests/test_client.py tests/test_cli.py
git commit -m "feat: add tag, item-type, since, sort, direction filters to search

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>"
```

---

### Task 3: Implement `collections` command

**Files:**
- Modify: `src/riszotto/client.py` — add `list_collections` and `collection_items` functions
- Modify: `src/riszotto/cli.py` — flesh out `collections` command
- Test: `tests/test_client.py`, `tests/test_cli.py`

**Step 1: Write failing client tests**

Add to `tests/test_client.py`:

```python
from riszotto.client import get_client, search_items, get_item, get_pdf_attachments, get_pdf_path, list_collections, collection_items


class TestListCollections:
    def test_returns_all_collections(self):
        mock_zot = MagicMock()
        mock_zot.collections.return_value = [
            {"data": {"key": "COL1", "name": "Physics", "parentCollection": False}},
            {"data": {"key": "COL2", "name": "DFT", "parentCollection": "COL1"}},
        ]
        result = list_collections(mock_zot)
        mock_zot.collections.assert_called_once()
        assert len(result) == 2
        assert result[0]["data"]["name"] == "Physics"


class TestCollectionItems:
    def test_returns_items_in_collection(self):
        mock_zot = MagicMock()
        mock_zot.collection_items.return_value = [
            {"data": {"key": "P1", "itemType": "journalArticle", "title": "Paper 1"}},
        ]
        result = collection_items(mock_zot, "COL1", limit=25, start=0)
        mock_zot.collection_items.assert_called_once_with("COL1", limit=25, start=0)
        assert len(result) == 1
```

**Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_client.py::TestListCollections -v`
Expected: FAIL — `list_collections` not defined

**Step 3: Implement client functions**

Add to `src/riszotto/client.py`:

```python
def list_collections(zot: zotero.Zotero) -> list[dict[str, Any]]:
    """Get all collections in the library."""
    return zot.collections()


def collection_items(
    zot: zotero.Zotero,
    collection_key: str,
    *,
    limit: int = 25,
    start: int = 0,
) -> list[dict[str, Any]]:
    """Get items in a specific collection."""
    return zot.collection_items(collection_key, limit=limit, start=start)
```

**Step 4: Run client tests**

Run: `uv run pytest tests/test_client.py -v`
Expected: all PASS

**Step 5: Write failing CLI tests**

Add to `tests/test_cli.py`:

```python
class TestCollections:
    @patch("riszotto.cli.get_client")
    def test_list_collections(self, mock_get_client):
        mock_zot = MagicMock()
        mock_get_client.return_value = mock_zot
        mock_zot.collections.return_value = [
            {"data": {"key": "COL1", "name": "Physics", "parentCollection": False}},
            {"data": {"key": "COL2", "name": "DFT", "parentCollection": "COL1"}},
        ]
        result = runner.invoke(app, ["collections"])
        assert result.exit_code == 0
        parsed = json.loads(result.output)
        assert len(parsed["results"]) == 2
        assert parsed["results"][0] == {"key": "COL1", "name": "Physics", "parentCollection": False}
        assert parsed["results"][1] == {"key": "COL2", "name": "DFT", "parentCollection": "COL1"}

    @patch("riszotto.cli.get_client")
    def test_collection_items(self, mock_get_client):
        mock_zot = MagicMock()
        mock_get_client.return_value = mock_zot
        mock_zot.collection_items.return_value = [
            {
                "data": {
                    "key": "P1", "title": "Paper 1", "itemType": "journalArticle",
                    "date": "2024", "abstractNote": "", "creators": [], "tags": [],
                },
                "meta": {},
            }
        ]
        result = runner.invoke(app, ["collections", "COL1"])
        assert result.exit_code == 0
        parsed = json.loads(result.output)
        assert parsed["page"] == 1
        assert len(parsed["results"]) == 1
        assert parsed["results"][0]["key"] == "P1"

    @patch("riszotto.cli.get_client")
    def test_collection_items_pagination(self, mock_get_client):
        mock_zot = MagicMock()
        mock_get_client.return_value = mock_zot
        mock_zot.collection_items.return_value = []
        runner.invoke(app, ["collections", "--page", "2", "--limit", "10", "COL1"])
        mock_zot.collection_items.assert_called_once_with("COL1", limit=10, start=10)
```

**Step 6: Implement `collections` CLI command**

Replace the stub `collections` command in `src/riszotto/cli.py` with the full implementation. Update the import line to include the new client functions:

```python
from riszotto.client import (
    get_client, get_pdf_attachments, get_pdf_path, search_items,
    list_collections, collection_items,
)
```

Add a helper to format a collection:

```python
def _format_collection(col: dict) -> dict:
    """Extract display fields from a Zotero collection."""
    data = col.get("data", {})
    return {
        "key": data.get("key", ""),
        "name": data.get("name", ""),
        "parentCollection": data.get("parentCollection", False),
    }
```

Replace the `collections` command:

```python
@app.command()
def collections(
    key: Annotated[Optional[str], typer.Argument(help="Collection key (omit to list all)")] = None,
    limit: Annotated[int, typer.Option("--limit", "-l", help="Maximum number of results")] = 25,
    page: Annotated[int, typer.Option("--page", "-p", help="Page number (1-indexed)")] = 1,
    max_value_size: Annotated[int, typer.Option("--max-value-size", help="Hide string values longer than this (0 = show all)")] = 200,
) -> None:
    """List collections or items in a collection."""
    zot = _get_zot()
    if key is None:
        cols = list_collections(zot)
        envelope = {
            "results": [_format_collection(c) for c in cols],
        }
    else:
        start = (page - 1) * limit
        items = collection_items(zot, key, limit=limit, start=start)
        envelope = {
            "page": page,
            "limit": limit,
            "start": start,
            "results": [_format_result(item, max_value_size) for item in items],
        }
    typer.echo(json.dumps(envelope, indent=2))
```

**Step 7: Run all tests**

Run: `uv run pytest tests/ -v`
Expected: all PASS

**Step 8: Commit**

```bash
git add src/riszotto/client.py src/riszotto/cli.py tests/test_client.py tests/test_cli.py
git commit -m "feat: add collections command

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>"
```

---

### Task 4: Implement `recent` command

**Files:**
- Modify: `src/riszotto/client.py` — add `recent_items` function
- Modify: `src/riszotto/cli.py` — add `recent` command
- Test: `tests/test_client.py`, `tests/test_cli.py`

**Step 1: Write failing client test**

Add to `tests/test_client.py`:

```python
from riszotto.client import get_client, search_items, get_item, get_pdf_attachments, get_pdf_path, list_collections, collection_items, recent_items


class TestRecentItems:
    def test_returns_recent_items(self):
        mock_zot = MagicMock()
        mock_zot.items.return_value = [
            {"data": {"key": "P1", "itemType": "journalArticle", "title": "New Paper"}},
        ]
        result = recent_items(mock_zot, limit=10)
        mock_zot.items.assert_called_once_with(
            sort="dateAdded", direction="desc", limit=10, itemType="-attachment",
        )
        assert len(result) == 1
```

**Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_client.py::TestRecentItems -v`
Expected: FAIL — `recent_items` not defined

**Step 3: Implement `recent_items` in client.py**

Add to `src/riszotto/client.py`:

```python
def recent_items(
    zot: zotero.Zotero,
    *,
    limit: int = 10,
) -> list[dict[str, Any]]:
    """Get recently added items, excluding attachments."""
    return zot.items(sort="dateAdded", direction="desc", limit=limit, itemType="-attachment")
```

**Step 4: Run client tests**

Run: `uv run pytest tests/test_client.py -v`
Expected: all PASS

**Step 5: Write failing CLI tests**

Add to `tests/test_cli.py`:

```python
class TestRecent:
    @patch("riszotto.cli.get_client")
    def test_recent_outputs_json(self, mock_get_client):
        mock_zot = MagicMock()
        mock_get_client.return_value = mock_zot
        mock_zot.items.return_value = [
            {
                "data": {
                    "key": "P1", "title": "New Paper", "itemType": "journalArticle",
                    "date": "2024", "abstractNote": "", "creators": [], "tags": [],
                },
                "meta": {},
            }
        ]
        result = runner.invoke(app, ["recent"])
        assert result.exit_code == 0
        parsed = json.loads(result.output)
        assert len(parsed["results"]) == 1
        assert parsed["results"][0]["key"] == "P1"
        assert parsed["limit"] == 10

    @patch("riszotto.cli.get_client")
    def test_recent_custom_limit(self, mock_get_client):
        mock_zot = MagicMock()
        mock_get_client.return_value = mock_zot
        mock_zot.items.return_value = []
        runner.invoke(app, ["recent", "--limit", "5"])
        mock_zot.items.assert_called_once_with(
            sort="dateAdded", direction="desc", limit=5, itemType="-attachment",
        )

    @patch("riszotto.cli.get_client")
    def test_recent_zotero_not_running(self, mock_get_client):
        mock_get_client.side_effect = ConnectionError("connection refused")
        result = runner.invoke(app, ["recent"])
        assert result.exit_code == 1
        assert "Zotero desktop is not running" in result.output
```

**Step 6: Implement `recent` CLI command**

Update the import line in `src/riszotto/cli.py`:

```python
from riszotto.client import (
    get_client, get_pdf_attachments, get_pdf_path, search_items,
    list_collections, collection_items, recent_items,
)
```

Add the command:

```python
@app.command()
def recent(
    limit: Annotated[int, typer.Option("--limit", "-l", help="Maximum number of results")] = 10,
    max_value_size: Annotated[int, typer.Option("--max-value-size", help="Hide string values longer than this (0 = show all)")] = 200,
) -> None:
    """Show recently added papers."""
    zot = _get_zot()
    items = recent_items(zot, limit=limit)
    envelope = {
        "limit": limit,
        "results": [_format_result(item, max_value_size) for item in items],
    }
    typer.echo(json.dumps(envelope, indent=2))
```

**Step 7: Run all tests**

Run: `uv run pytest tests/ -v`
Expected: all PASS

**Step 8: Commit**

```bash
git add src/riszotto/client.py src/riszotto/cli.py tests/test_client.py tests/test_cli.py
git commit -m "feat: add recent command

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>"
```

---

### Task 5: Smoke test all new features

**Step 1: Test search with tag filter**

Run: `uv run riszotto search --tag "density functional theory" grimme`
Expected: JSON results filtered to items tagged "density functional theory"

**Step 2: Test search with item type**

Run: `uv run riszotto search --item-type book grimme`
Expected: only books by Grimme (or empty if none)

**Step 3: Test search with sort**

Run: `uv run riszotto search --sort dateModified --direction desc grimme`
Expected: results sorted by modification date, newest first

**Step 4: Test collections list**

Run: `uv run riszotto collections | python3 -c "import sys,json; d=json.load(sys.stdin); [print(r['name']) for r in d['results']]"`
Expected: collection names printed

**Step 5: Test collection items**

Pick a collection key from Step 4, then:
Run: `uv run riszotto collections <KEY> | python3 -c "import sys,json; d=json.load(sys.stdin); print(len(d['results']), 'items')"`

**Step 6: Test recent**

Run: `uv run riszotto recent --limit 3`
Expected: 3 most recently added papers as JSON
