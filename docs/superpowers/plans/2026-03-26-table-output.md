# Table Output Default Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make `search`, `recent`, and `collections` commands output human-readable tables by default instead of JSON, so agents stop piping output through Python one-liners.

**Architecture:** Add table formatting functions to `formatting.py`, add `--format` / `-f` flag (default `"table"`) to the three commands, and update the skill file. The `--format json` path preserves existing JSON output unchanged.

**Tech Stack:** Python, Typer CLI, pytest

**Spec:** `docs/superpowers/specs/2026-03-25-table-output-design.md`

---

### Task 1: Add `format_items_table` to `formatting.py`

**Files:**
- Modify: `src/riszotto/formatting.py`
- Create: `tests/test_formatting.py`

- [ ] **Step 1: Write failing tests for `format_items_table`**

```python
"""Tests for table formatting functions."""

from riszotto.formatting import format_items_table


class TestFormatItemsTable:
    def test_basic_table(self):
        results = [
            {
                "key": "ABC12345",
                "title": "Attention Is All You Need",
                "date": "2017-06-12",
                "authors": ["Vaswani, Ashish", "Shazeer, Noam"],
            },
        ]
        output = format_items_table(results)
        lines = output.strip().splitlines()
        assert lines[0].startswith("KEY")
        assert "DATE" in lines[0]
        assert "AUTHORS" in lines[0]
        assert "TITLE" in lines[0]
        assert "ABC12345" in lines[1]
        assert "2017" in lines[1]
        assert "Vaswani, Ashish" in lines[1]
        assert "Attention Is All You Need" in lines[1]

    def test_empty_results(self):
        output = format_items_table([])
        assert output == "No results found."

    def test_year_extraction(self):
        results = [
            {"key": "K1", "title": "T", "date": "2024-01-15", "authors": []},
        ]
        output = format_items_table(results)
        assert "2024" in output
        assert "2024-01-15" not in output

    def test_year_extraction_short_date(self):
        results = [
            {"key": "K1", "title": "T", "date": "2024", "authors": []},
        ]
        output = format_items_table(results)
        assert "2024" in output

    def test_missing_date(self):
        results = [
            {"key": "K1", "title": "T", "date": "", "authors": []},
        ]
        output = format_items_table(results)
        lines = output.strip().splitlines()
        # Should not crash, just empty date column
        assert "K1" in lines[1]

    def test_authors_joined_with_semicolon(self):
        results = [
            {"key": "K1", "title": "T", "date": "2024", "authors": ["A", "B", "C"]},
        ]
        output = format_items_table(results)
        assert "A; B; C" in output or "A; B; ..." in output

    def test_long_title_truncated(self):
        results = [
            {"key": "K1", "title": "A" * 200, "date": "2024", "authors": []},
        ]
        output = format_items_table(results)
        lines = output.strip().splitlines()
        assert lines[1].endswith("...")
        assert len(lines[1]) <= 120

    def test_long_authors_truncated(self):
        results = [
            {
                "key": "K1",
                "title": "T",
                "date": "2024",
                "authors": ["Very Long Author Name"] * 5,
            },
        ]
        output = format_items_table(results)
        lines = output.strip().splitlines()
        # Authors column is 25 chars wide, should truncate
        assert "..." in lines[1]

    def test_semantic_score_column(self):
        results = [
            {
                "key": "K1",
                "title": "T",
                "date": "2024",
                "authors": [],
                "score": 0.95,
            },
        ]
        output = format_items_table(results, semantic=True)
        lines = output.strip().splitlines()
        assert "SCORE" in lines[0]
        assert "0.95" in lines[1]

    def test_multiple_rows(self):
        results = [
            {"key": "K1", "title": "First Paper", "date": "2024", "authors": ["A"]},
            {"key": "K2", "title": "Second Paper", "date": "2023", "authors": ["B"]},
        ]
        output = format_items_table(results)
        lines = output.strip().splitlines()
        assert len(lines) == 3  # header + 2 rows
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_formatting.py -v`
Expected: ImportError — `format_items_table` does not exist yet.

- [ ] **Step 3: Implement `format_items_table`**

In `src/riszotto/formatting.py`, add:

```python
TABLE_WIDTH = 120
COL_KEY = 10
COL_DATE = 6
COL_AUTHORS = 25
COL_SCORE = 6


def _truncate(text: str, width: int) -> str:
    """Truncate text to width, adding '...' if needed."""
    if len(text) <= width:
        return text
    return text[: width - 3] + "..."


def _extract_year(date: str) -> str:
    """Extract first 4 digits as year from a Zotero date string."""
    return date[:4] if len(date) >= 4 else date


def format_items_table(results: list[dict], *, semantic: bool = False) -> str:
    """Format item result dicts as a fixed-width table.

    Parameters
    ----------
    results
        List of dicts from ``_format_result``, each with keys:
        key, title, date, authors (list[str]), and optionally score.
    semantic
        If True, include a SCORE column.

    Returns
    -------
    str
        Formatted table string, or "No results found." if empty.
    """
    if not results:
        return "No results found."

    col_title = TABLE_WIDTH - COL_KEY - COL_DATE - COL_AUTHORS
    if semantic:
        col_title -= COL_SCORE

    header_parts = [f"{'KEY':<{COL_KEY}}", f"{'DATE':<{COL_DATE}}", f"{'AUTHORS':<{COL_AUTHORS}}"]
    if semantic:
        header_parts.append(f"{'SCORE':<{COL_SCORE}}")
    header_parts.append("TITLE")
    header = "".join(header_parts)

    lines = [header]
    for r in results:
        authors = "; ".join(r.get("authors", []))
        row_parts = [
            f"{_truncate(r.get('key', ''), COL_KEY - 1):<{COL_KEY}}",
            f"{_extract_year(r.get('date', '')):<{COL_DATE}}",
            f"{_truncate(authors, COL_AUTHORS - 1):<{COL_AUTHORS}}",
        ]
        if semantic:
            score = r.get("score", 0)
            row_parts.append(f"{score:<{COL_SCORE}.2f}")
        row_parts.append(_truncate(r.get("title", ""), col_title))
        lines.append("".join(row_parts))

    return "\n".join(lines)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_formatting.py -v`
Expected: All PASS.

- [ ] **Step 5: Commit**

```bash
git add src/riszotto/formatting.py tests/test_formatting.py
git commit -m "feat: add format_items_table for human-readable search output"
```

---

### Task 2: Add `format_collections_table` to `formatting.py`

**Files:**
- Modify: `src/riszotto/formatting.py`
- Modify: `tests/test_formatting.py`

- [ ] **Step 1: Write failing tests**

Append to `tests/test_formatting.py`:

```python
from riszotto.formatting import format_collections_table


class TestFormatCollectionsTable:
    def test_basic_collections(self):
        collections = [
            {"key": "COL1", "name": "Physics"},
            {"key": "COL2", "name": "Machine Learning"},
        ]
        output = format_collections_table(collections)
        lines = output.strip().splitlines()
        assert "KEY" in lines[0]
        assert "NAME" in lines[0]
        assert "COL1" in lines[1]
        assert "Physics" in lines[1]
        assert "COL2" in lines[2]

    def test_empty_collections(self):
        output = format_collections_table([])
        assert output == "No results found."
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_formatting.py::TestFormatCollectionsTable -v`
Expected: ImportError.

- [ ] **Step 3: Implement `format_collections_table`**

Add to `src/riszotto/formatting.py`:

```python
def format_collections_table(collections: list[dict]) -> str:
    """Format collection dicts as a fixed-width table.

    Parameters
    ----------
    collections
        List of dicts with keys: key, name.

    Returns
    -------
    str
        Formatted table string, or "No results found." if empty.
    """
    if not collections:
        return "No results found."

    lines = [f"{'KEY':<{COL_KEY}}NAME"]
    for c in collections:
        lines.append(f"{c.get('key', ''):<{COL_KEY}}{c.get('name', '')}")
    return "\n".join(lines)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_formatting.py -v`
Expected: All PASS.

- [ ] **Step 5: Commit**

```bash
git add src/riszotto/formatting.py tests/test_formatting.py
git commit -m "feat: add format_collections_table"
```

---

### Task 3: Add `--format` flag and wire table output in `search` command

**Files:**
- Modify: `src/riszotto/cli.py`
- Modify: `tests/test_cli.py`

- [ ] **Step 1: Migrate existing search tests to use `--format json`**

In `tests/test_cli.py`, find every `runner.invoke(app, ["search", ...)` call within these tests that later calls `json.loads(result.output)`, and insert `"--format", "json"` into the args list. The affected tests in `TestSearch` (7 tests):

- `test_search_outputs_json_envelope`: line 41 → `["search", "--format", "json", "attention"]`
- `test_search_no_results`: line 62 → `["search", "--format", "json", "nonexistent"]`
- `test_search_page_in_envelope`: line 109 → `["search", "--format", "json", "--page", "2", "--limit", "10", "test"]`
- `test_search_max_value_size_truncates`: line 135 → `["search", "--format", "json", "test"]`
- `test_search_max_value_size_zero_shows_all`: line 159 → `["search", "--format", "json", "--max-value-size", "0", "test"]`
- `test_search_creator_name_field`: line 183 → `["search", "--format", "json", "test"]`
- `test_search_author_filters_results`: line 266 → `["search", "--format", "json", "--author", "smith", "test"]`

Also in `TestSearchSemantic` (3 tests):

- `test_semantic_search_outputs_envelope`: line 318 → `["search", "--format", "json", "--semantic", "attention mechanisms"]`
- `test_semantic_search_no_results`: line 336 → `["search", "--format", "json", "--semantic", "nonexistent"]`
- `test_semantic_search_author_filters`: line 406 → `["search", "--format", "json", "--semantic", "--author", "jones", "test"]`

Also in `TestFuzzyAuthorMatching` (4 tests):

- `test_diacritic_insensitive_by_default`: line 1259 → `["search", "--format", "json", "--author", "magdau", "ML"]`
- `test_fuzzy_needed_for_typo`: line 1288 → `["search", "--format", "json", "--author", "magdeu", "ML"]`
- `test_fuzzy_flag_matches_typo`: line 1316 → `["search", "--format", "json", "--author", "bogdau", "--fuzzy", "ML"]`
- `test_umlaut_matching`: line 1344 → `["search", "--format", "json", "--author", "schafer", "ML"]`

Also in `TestAllLibrariesSearch` (2 tests):

- `test_grouped_output`: line 1393 → `["search", "--format", "json", "--all-libraries", "test"]`
- `test_semantic_skips_unindexed`: line 1458 → `["search", "--format", "json", "--all-libraries", "--semantic", "test"]`

- [ ] **Step 2: Run migrated tests — they should fail (flag doesn't exist yet)**

Run: `uv run pytest tests/test_cli.py::TestSearch -v`
Expected: FAIL — `--format` is not a recognized option.

- [ ] **Step 3: Add `FormatOption` and `--format` to `search` command, wire table output**

In `src/riszotto/cli.py`:

1. Update the import from `formatting` (line 28):
```python
from riszotto.formatting import format_creator, format_items_table, format_collections_table
```

2. Add `FormatOption` after `LibraryOption` (after line 39):
```python
FormatOption = Annotated[
    str,
    typer.Option(
        "--format",
        "-f",
        help="Output format (table or json)",
    ),
]
```

3. Add `format: FormatOption = "table"` parameter to the `search` command (after the `all_libraries` param, before `) -> None:`).

4. Pass `format=format` to `_search_all_libraries` call (line 393-407). Add `format: str` parameter to `_search_all_libraries` signature (line 229).

5. Replace each `typer.echo(json.dumps(envelope, indent=2))` in `search` (lines 447, 476) and `_search_all_libraries` (line 314) with format-aware output:

For the semantic search path (line 447):
```python
if format == "json":
    typer.echo(json.dumps(envelope, indent=2))
else:
    typer.echo(format_items_table(envelope["results"], semantic=True))
```

For the normal search path (line 476):
```python
if format == "json":
    typer.echo(json.dumps(envelope, indent=2))
else:
    output = format_items_table(envelope["results"])
    typer.echo(output)
    if envelope["results"] and len(envelope["results"]) == limit:
        typer.echo(f"\nPage {page}. Next: riszotto search {' '.join(terms)} --page {page + 1}")
```

For `_search_all_libraries` (line 314):
```python
if format == "json":
    typer.echo(json.dumps(grouped, indent=2))
else:
    parts = []
    for lib_name, envelope in grouped.items():
        parts.append(f"── {lib_name} ──")
        parts.append(format_items_table(envelope["results"], semantic=semantic))
    typer.echo("\n\n".join(parts) if parts else "No results found.")
```

6. In the table path, use `max_value_size=0` when calling `_format_result` so the table formatter gets untruncated data. The simplest way: where `_format_result(item, max_value_size)` is called, use `_format_result(item, 0 if format == "table" else max_value_size)`. This applies in:
   - `search` normal path (line 474)
   - `search` semantic path (line 437)
   - `_search_all_libraries` both paths (lines 282, 303)

- [ ] **Step 4: Run all search tests**

Run: `uv run pytest tests/test_cli.py::TestSearch tests/test_cli.py::TestSearchSemantic tests/test_cli.py::TestFuzzyAuthorMatching tests/test_cli.py::TestAllLibrariesSearch -v`
Expected: All PASS.

- [ ] **Step 5: Add tests for default table output**

Add `import pytest` at the top of `tests/test_cli.py` (after the existing imports).

Add to `TestSearch` in `tests/test_cli.py`:

```python
@patch("riszotto.cli.get_client")
def test_search_no_results_table_output(self, mock_get_client):
    mock_zot = MagicMock()
    mock_get_client.return_value = mock_zot
    mock_zot.items.return_value = []
    result = runner.invoke(app, ["search", "nonexistent"])
    assert result.exit_code == 0
    assert "No results found." in result.output

@patch("riszotto.cli.get_client")
def test_search_default_table_output(self, mock_get_client):
    mock_zot = MagicMock()
    mock_get_client.return_value = mock_zot
    mock_zot.items.return_value = [
        {
            "data": {
                "key": "ABC12345",
                "title": "Attention Is All You Need",
                "itemType": "journalArticle",
                "date": "2017-06-12",
                "creators": [{"firstName": "Ashish", "lastName": "Vaswani", "creatorType": "author"}],
                "abstractNote": "",
                "tags": [],
            },
            "meta": {},
        }
    ]
    result = runner.invoke(app, ["search", "attention"])
    assert result.exit_code == 0
    assert "KEY" in result.output
    assert "ABC12345" in result.output
    assert "2017" in result.output
    assert "Vaswani, Ashish" in result.output
    # Verify it's NOT json
    import json
    with pytest.raises(json.JSONDecodeError):
        json.loads(result.output)
```

- [ ] **Step 6: Run the new tests**

Run: `uv run pytest tests/test_cli.py::TestSearch::test_search_no_results_table_output tests/test_cli.py::TestSearch::test_search_default_table_output -v`
Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add src/riszotto/cli.py tests/test_cli.py
git commit -m "feat: add --format flag to search, default to table output"
```

---

### Task 4: Add `--format` flag to `recent` and `collections` commands

**Files:**
- Modify: `src/riszotto/cli.py`
- Modify: `tests/test_cli.py`

- [ ] **Step 1: Migrate existing `recent` and `collections` tests to use `--format json`**

In `TestCollections` (3 tests):
- `test_list_collections`: line 857 → `["collections", "--format", "json"]`
- `test_collection_items`: line 882 → `["collections", "--format", "json", "COL1"]`
- `test_collection_items_pagination`: line 897 → `["collections", "--format", "json", "COL1", "--page", "3", "--limit", "10"]`

In `TestRecent` (2 tests):
- `test_recent_outputs_json`: line 927 → `["recent", "--format", "json"]`
- `test_recent_custom_limit`: line 939 → `["recent", "--format", "json", "--limit", "5"]`

- [ ] **Step 2: Run migrated tests — they should fail**

Run: `uv run pytest tests/test_cli.py::TestCollections tests/test_cli.py::TestRecent -v`
Expected: FAIL — `--format` not recognized.

- [ ] **Step 3: Add `--format` to `collections` command**

Add `format: FormatOption = "table"` parameter to `collections()`.

Replace `typer.echo(json.dumps(envelope, indent=2))` (line 691) with:

```python
if format == "json":
    typer.echo(json.dumps(envelope, indent=2))
elif key is None:
    typer.echo(format_collections_table(envelope["results"]))
else:
    output = format_items_table(envelope["results"])
    typer.echo(output)
    if envelope["results"] and len(envelope["results"]) == limit:
        typer.echo(f"\nPage {page}. Next: riszotto collections {key} --page {page + 1}")
```

For the items-in-collection path, use `max_value_size=0` when format is `"table"`:
Line 689: `_format_result(item, 0 if format == "table" else max_value_size)`

- [ ] **Step 4: Add `--format` to `recent` command**

Add `format: FormatOption = "table"` parameter to `recent()`.

Replace `typer.echo(json.dumps(envelope, indent=2))` (line 715) with:

```python
if format == "json":
    typer.echo(json.dumps(envelope, indent=2))
else:
    typer.echo(format_items_table(envelope["results"]))
```

Use `max_value_size=0` when format is `"table"`:
Line 713: `_format_result(item, 0 if format == "table" else max_value_size)`

- [ ] **Step 5: Run all affected tests**

Run: `uv run pytest tests/test_cli.py::TestCollections tests/test_cli.py::TestRecent -v`
Expected: All PASS.

- [ ] **Step 6: Add table output tests for `recent` and `collections`**

```python
# In TestRecent:
@patch("riszotto.cli.recent_items")
@patch("riszotto.cli.get_client")
def test_recent_default_table_output(self, mock_get_client, mock_recent_items):
    mock_get_client.return_value = MagicMock()
    mock_recent_items.return_value = [
        {
            "data": {
                "key": "R1",
                "title": "Recent Paper",
                "itemType": "journalArticle",
                "date": "2024",
                "creators": [],
                "abstractNote": "",
                "tags": [],
            },
            "meta": {},
        }
    ]
    result = runner.invoke(app, ["recent"])
    assert result.exit_code == 0
    assert "KEY" in result.output
    assert "R1" in result.output
    assert "Recent Paper" in result.output


# In TestCollections:
@patch("riszotto.cli.list_collections")
@patch("riszotto.cli.get_client")
def test_collections_default_table_output(self, mock_get_client, mock_list_collections):
    mock_get_client.return_value = MagicMock()
    mock_list_collections.return_value = [
        {"data": {"key": "COL1", "name": "Physics", "parentCollection": False}},
    ]
    result = runner.invoke(app, ["collections"])
    assert result.exit_code == 0
    assert "KEY" in result.output
    assert "NAME" in result.output
    assert "COL1" in result.output
    assert "Physics" in result.output
```

- [ ] **Step 7: Run new tests**

Run: `uv run pytest tests/test_cli.py::TestRecent::test_recent_default_table_output tests/test_cli.py::TestCollections::test_collections_default_table_output -v`
Expected: PASS.

- [ ] **Step 8: Commit**

```bash
git add src/riszotto/cli.py tests/test_cli.py
git commit -m "feat: add --format flag to recent and collections, default to table"
```

---

### Task 5: Run full test suite

**Files:** None (verification only)

- [ ] **Step 1: Run all tests**

Run: `uv run pytest tests/ -v`
Expected: All PASS. If any fail, fix before proceeding.

- [ ] **Step 2: Run pre-commit checks**

Run: `uvx prek --all-files`
Expected: All checks pass.

- [ ] **Step 3: Fix any issues and commit**

If pre-commit found formatting issues:
```bash
git add -u
git commit -m "style: fix formatting"
```

---

### Task 6: Update skill file

**Files:**
- Modify: `skills/using-riszotto/SKILL.md`

- [ ] **Step 1: Update the skill**

Replace the full contents of `skills/using-riszotto/SKILL.md` with:

```markdown
---
name: using-riszotto
description: Use when the user asks to search, read, or export papers from their Zotero library, including group libraries. Use when working with Zotero references, citations, PDFs, or bibliographies. Triggers on "find papers", "search Zotero", "read paper", "export BibTeX", "recent papers", "group library", "shared library".
---

# Using riszotto

CLI for searching, reading, and exporting papers from Zotero. Run via `uvx riszotto <command>`. Requires Zotero desktop running with local API enabled.

Default: personal library. Use `-L "Name"` for groups, `-A` for all libraries. Discover with `uvx riszotto libraries`.

## Dos and Don'ts

**Do:**
- Run `uvx riszotto search "query"` directly — output is a readable table
- Read the table output as-is — keys, dates, authors, and titles are all there
- Use `-l` / `--limit` to control result count
- Combine filters: `--author`, `--tag`, `--full-text` to narrow results
- Run multiple searches as separate commands

**Don't:**
- Pipe riszotto output through `python3 -c "import sys,json; ..."` — the table is already human-readable
- Use `--format json` unless you have a specific programmatic need (you almost never do)
- Use `2>/dev/null` to suppress stderr — let errors surface so you can act on them
- Truncate titles manually with `[:80]` — the table already truncates
- Parse table output with scripts — if you truly need structured data, use `--format json`, but question why first
- Chain multiple searches in a single shell command with `echo "---"` separators

## Quick Reference

| Task | Command |
|------|---------|
| List libraries | `uvx riszotto libraries` |
| Search keywords | `uvx riszotto search "query"` |
| Search all libraries | `uvx riszotto search -A "query"` |
| Search group library | `uvx riszotto search -L "Group" "query"` |
| Search all fields | `uvx riszotto search --full-text "query"` |
| Semantic search | `uvx riszotto search --semantic "query"` |
| Filter by author | `uvx riszotto search "topic" --author "Name"` |
| Fuzzy author match | `uvx riszotto search "topic" --author "Name" --fuzzy` |
| Filter by tag | `uvx riszotto search "topic" --tag "tag"` |
| Read paper | `uvx riszotto show <KEY>` |
| Search within PDF | `uvx riszotto show <KEY> --search "term"` |
| Export BibTeX | `uvx riszotto export <KEY>` |
| Collections | `uvx riszotto collections` |
| Recent papers | `uvx riszotto recent` |
| Build semantic index | `uvx riszotto index` |
| JSON output | `uvx riszotto search "query" --format json` |

## Search Strategy

Follow this cascade when searching:

1. **Keyword search** (default) — fast, precise for known titles/authors
2. **`--full-text`** — if 0 results, retry (searches all metadata fields)
3. **`--semantic`** — for natural language queries; requires `index` built first
4. **`-A`** — search across all libraries at once

Tips:
- Fewer terms = more hits (keyword mode uses AND logic)
- `--author "name"` handles diacritics automatically ("schafer" matches "Schäfer")
- `--fuzzy` with `--author` for uncertain spelling (Levenshtein distance <= 2)
- Check `libraries` output for `Indexed` column before using `--semantic`

## Common Mistakes

- **Zotero not running:** Start Zotero desktop with local API enabled
- **Semantic without index:** Run `uvx riszotto index` first (per library)
- **`show` needs parent key**, not attachment key; requires locally synced PDFs for group libraries
- **Flag conflict:** `-L` = `--library`, `-l` = `--limit`, `-f` = `--format`

Run `uvx riszotto <command> --help` for full options.
```

- [ ] **Step 2: Commit**

```bash
git add skills/using-riszotto/SKILL.md
git commit -m "docs: update using-riszotto skill with table output docs and dos/don'ts"
```

---

### Task 7: Final verification

- [ ] **Step 1: Run full test suite one last time**

Run: `uv run pytest tests/ -v`
Expected: All PASS.

- [ ] **Step 2: Run pre-commit**

Run: `uvx prek --all-files`
Expected: All pass.

- [ ] **Step 3: Verify table output manually (if Zotero is running)**

```bash
uv run riszotto search "test" -l 3
uv run riszotto recent -l 3
uv run riszotto collections
uv run riszotto search "test" -l 3 --format json
```

Verify: first three show tables, last one shows JSON.
