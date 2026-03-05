# Semantic Search Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add ChromaDB-powered semantic search as an optional feature, enabling natural language queries against the Zotero library.

**Architecture:** A new `semantic.py` module wraps ChromaDB for index building and querying. The CLI gets a new `index` command and a `--semantic` flag on `search`. ChromaDB + sentence-transformers are optional extras — base riszotto stays lightweight. The index persists at `~/.riszotto/chroma_db/` with all-MiniLM-L6-v2 as the embedding model.

**Tech Stack:** Python, typer, chromadb, sentence-transformers, pytest

---

### Task 1: Add optional dependency group

**Files:**
- Modify: `pyproject.toml`

**Step 1: Add semantic extras**

In `pyproject.toml`, add after the `[project.scripts]` section and before `[build-system]`:

```toml
[project.optional-dependencies]
semantic = [
    "chromadb>=0.4.0",
    "sentence-transformers>=2.2.0",
]
```

**Step 2: Install the extras**

Run: `uv sync --extra semantic`
Expected: chromadb and sentence-transformers installed

**Step 3: Verify base install still works without extras**

Run: `uv sync && uv run python -c "import riszotto; print('ok')"`
Expected: prints "ok" — no chromadb imported at module level

**Step 4: Commit**

```bash
git add pyproject.toml
git commit -m "feat: add optional semantic search dependency group"
```

---

### Task 2: Create semantic.py with document text construction

**Files:**
- Create: `src/riszotto/semantic.py`
- Create: `tests/test_semantic.py`

**Step 1: Write failing tests for document text construction**

Create `tests/test_semantic.py`:

```python
import pytest

from riszotto.semantic import _build_document_text


class TestBuildDocumentText:
    def test_full_item(self):
        item = {
            "data": {
                "key": "ABC123",
                "title": "Attention Is All You Need",
                "itemType": "journalArticle",
                "abstractNote": "We propose a new architecture.",
                "creators": [
                    {"firstName": "Ashish", "lastName": "Vaswani", "creatorType": "author"},
                    {"firstName": "Noam", "lastName": "Shazeer", "creatorType": "author"},
                ],
                "tags": [{"tag": "transformers"}, {"tag": "NLP"}],
            }
        }
        text = _build_document_text(item)
        assert "Attention Is All You Need" in text
        assert "Vaswani, Ashish" in text
        assert "Shazeer, Noam" in text
        assert "We propose a new architecture." in text
        assert "transformers" in text
        assert "NLP" in text

    def test_missing_fields(self):
        item = {"data": {"key": "X1", "title": "Just a Title"}}
        text = _build_document_text(item)
        assert "Just a Title" in text

    def test_empty_item(self):
        item = {"data": {}}
        text = _build_document_text(item)
        assert isinstance(text, str)

    def test_institution_creator(self):
        item = {
            "data": {
                "title": "Report",
                "creators": [{"name": "WHO", "creatorType": "author"}],
                "tags": [],
            }
        }
        text = _build_document_text(item)
        assert "WHO" in text
```

**Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_semantic.py::TestBuildDocumentText -v`
Expected: FAIL — `riszotto.semantic` does not exist

**Step 3: Create semantic.py with document text builder**

Create `src/riszotto/semantic.py`:

```python
"""Semantic search over Zotero library using ChromaDB embeddings."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from riszotto.cli import _format_creator

INDEX_DIR = Path.home() / ".riszotto" / "chroma_db"


def _build_document_text(item: dict) -> str:
    """Concatenate item fields into a single string for embedding."""
    data = item.get("data", {})
    parts: list[str] = []

    title = data.get("title", "")
    if title:
        parts.append(title)

    for creator in data.get("creators", []):
        name = _format_creator(creator)
        if name:
            parts.append(name)

    abstract = data.get("abstractNote", "")
    if abstract:
        parts.append(abstract)

    for tag_obj in data.get("tags", []):
        tag = tag_obj.get("tag", "")
        if tag:
            parts.append(tag)

    return " ".join(parts)
```

**Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_semantic.py::TestBuildDocumentText -v`
Expected: all PASS

**Step 5: Commit**

```bash
git add src/riszotto/semantic.py tests/test_semantic.py
git commit -m "feat: add document text construction for semantic indexing"
```

---

### Task 3: Add build_index function

**Files:**
- Modify: `src/riszotto/semantic.py`
- Modify: `tests/test_semantic.py`

This task adds the ChromaDB indexing logic. The `build_index` function fetches all items from Zotero, constructs document text, and upserts into ChromaDB. ChromaDB imports are deferred (inside the function) so the base package doesn't require them.

**Step 1: Write failing tests for build_index**

Add to `tests/test_semantic.py`:

```python
from unittest.mock import MagicMock, patch, ANY

from riszotto.semantic import build_index, INDEX_DIR


class TestBuildIndex:
    @patch("riszotto.semantic._get_collection")
    def test_indexes_items(self, mock_get_collection):
        mock_collection = MagicMock()
        mock_get_collection.return_value = mock_collection
        mock_collection.get.return_value = {"ids": []}

        mock_zot = MagicMock()
        mock_zot.items.return_value = [
            {
                "data": {
                    "key": "P1",
                    "title": "Paper One",
                    "itemType": "journalArticle",
                    "abstractNote": "Abstract one.",
                    "creators": [],
                    "tags": [],
                },
            },
            {
                "data": {
                    "key": "P2",
                    "title": "Paper Two",
                    "itemType": "journalArticle",
                    "abstractNote": "Abstract two.",
                    "creators": [],
                    "tags": [],
                },
            },
        ]

        stats = build_index(mock_zot)
        mock_collection.upsert.assert_called_once()
        call_kwargs = mock_collection.upsert.call_args
        assert set(call_kwargs[1]["ids"]) == {"P1", "P2"}
        assert len(call_kwargs[1]["documents"]) == 2
        assert stats["indexed"] == 2

    @patch("riszotto.semantic._get_collection")
    def test_skips_child_items(self, mock_get_collection):
        mock_collection = MagicMock()
        mock_get_collection.return_value = mock_collection
        mock_collection.get.return_value = {"ids": []}

        mock_zot = MagicMock()
        mock_zot.items.return_value = [
            {"data": {"key": "P1", "title": "Paper", "itemType": "journalArticle", "creators": [], "tags": []}},
            {"data": {"key": "ATT1", "itemType": "attachment", "parentItem": "P1"}},
            {"data": {"key": "N1", "itemType": "note", "parentItem": "P1"}},
        ]

        stats = build_index(mock_zot)
        call_kwargs = mock_collection.upsert.call_args
        assert call_kwargs[1]["ids"] == ["P1"]
        assert stats["indexed"] == 1
        assert stats["skipped"] == 2

    @patch("riszotto.semantic._get_collection")
    def test_incremental_skips_existing(self, mock_get_collection):
        mock_collection = MagicMock()
        mock_get_collection.return_value = mock_collection
        mock_collection.get.return_value = {"ids": ["P1"]}

        mock_zot = MagicMock()
        mock_zot.items.return_value = [
            {"data": {"key": "P1", "title": "Old Paper", "itemType": "journalArticle", "creators": [], "tags": []}},
            {"data": {"key": "P2", "title": "New Paper", "itemType": "journalArticle", "creators": [], "tags": []}},
        ]

        stats = build_index(mock_zot)
        call_kwargs = mock_collection.upsert.call_args
        assert call_kwargs[1]["ids"] == ["P2"]
        assert stats["indexed"] == 1
        assert stats["skipped"] == 1

    @patch("riszotto.semantic._get_collection")
    def test_rebuild_indexes_all(self, mock_get_collection):
        mock_collection = MagicMock()
        mock_get_collection.return_value = mock_collection
        # rebuild=True ignores existing IDs
        mock_collection.get.return_value = {"ids": ["P1"]}

        mock_zot = MagicMock()
        mock_zot.items.return_value = [
            {"data": {"key": "P1", "title": "Old Paper", "itemType": "journalArticle", "creators": [], "tags": []}},
            {"data": {"key": "P2", "title": "New Paper", "itemType": "journalArticle", "creators": [], "tags": []}},
        ]

        stats = build_index(mock_zot, rebuild=True)
        call_kwargs = mock_collection.upsert.call_args
        assert set(call_kwargs[1]["ids"]) == {"P1", "P2"}
        assert stats["indexed"] == 2

    @patch("riszotto.semantic._get_collection")
    def test_no_items_to_index(self, mock_get_collection):
        mock_collection = MagicMock()
        mock_get_collection.return_value = mock_collection
        mock_collection.get.return_value = {"ids": []}

        mock_zot = MagicMock()
        mock_zot.items.return_value = []

        stats = build_index(mock_zot)
        mock_collection.upsert.assert_not_called()
        assert stats["indexed"] == 0

    @patch("riszotto.semantic._get_collection")
    def test_limit_caps_fetch(self, mock_get_collection):
        mock_collection = MagicMock()
        mock_get_collection.return_value = mock_collection
        mock_collection.get.return_value = {"ids": []}

        mock_zot = MagicMock()
        mock_zot.items.return_value = []

        build_index(mock_zot, limit=100)
        call_args = mock_zot.items.call_args
        assert call_args[1]["limit"] == 100
```

**Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_semantic.py::TestBuildIndex -v`
Expected: FAIL — `build_index` and `_get_collection` not defined

**Step 3: Implement build_index and _get_collection**

Replace `src/riszotto/semantic.py` with:

```python
"""Semantic search over Zotero library using ChromaDB embeddings."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from pyzotero import zotero

from riszotto.cli import _format_creator

INDEX_DIR = Path.home() / ".riszotto" / "chroma_db"

_CHILD_ITEM_TYPES = {"attachment", "note", "annotation"}

BATCH_SIZE = 500


def _build_document_text(item: dict) -> str:
    """Concatenate item fields into a single string for embedding."""
    data = item.get("data", {})
    parts: list[str] = []

    title = data.get("title", "")
    if title:
        parts.append(title)

    for creator in data.get("creators", []):
        name = _format_creator(creator)
        if name:
            parts.append(name)

    abstract = data.get("abstractNote", "")
    if abstract:
        parts.append(abstract)

    for tag_obj in data.get("tags", []):
        tag = tag_obj.get("tag", "")
        if tag:
            parts.append(tag)

    return " ".join(parts)


def _get_collection(*, rebuild: bool = False):
    """Get or create the ChromaDB collection. Deferred import."""
    import chromadb
    from chromadb.config import Settings

    client = chromadb.PersistentClient(
        path=str(INDEX_DIR),
        settings=Settings(anonymized_telemetry=False, allow_reset=True),
    )

    if rebuild:
        try:
            client.delete_collection(name="zotero")
        except ValueError:
            pass  # collection doesn't exist yet

    return client.get_or_create_collection(name="zotero")


def build_index(
    zot: zotero.Zotero,
    *,
    rebuild: bool = False,
    limit: int | None = None,
) -> dict[str, int]:
    """Build or update the semantic search index.

    Returns dict with keys: indexed, skipped.
    """
    collection = _get_collection(rebuild=rebuild)

    fetch_limit = limit if limit is not None else 100
    all_items = zot.items(limit=fetch_limit, itemType="-attachment")

    # Get existing IDs for incremental mode
    existing_ids: set[str] = set()
    if not rebuild:
        existing = collection.get()
        existing_ids = set(existing["ids"])

    ids: list[str] = []
    documents: list[str] = []
    metadatas: list[dict[str, str]] = []
    skipped = 0

    for item in all_items:
        data = item.get("data", {})
        item_type = data.get("itemType", "")

        if item_type in _CHILD_ITEM_TYPES:
            skipped += 1
            continue

        key = data.get("key", "")
        if not key:
            skipped += 1
            continue

        if not rebuild and key in existing_ids:
            skipped += 1
            continue

        doc_text = _build_document_text(item)
        if not doc_text.strip():
            skipped += 1
            continue

        ids.append(key)
        documents.append(doc_text)
        metadatas.append({
            "title": data.get("title", ""),
            "itemType": item_type,
        })

    if ids:
        # Upsert in batches to avoid ChromaDB size limits
        for i in range(0, len(ids), BATCH_SIZE):
            end = i + BATCH_SIZE
            collection.upsert(
                ids=ids[i:end],
                documents=documents[i:end],
                metadatas=metadatas[i:end],
            )

    return {"indexed": len(ids), "skipped": skipped}
```

**Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_semantic.py -v`
Expected: all PASS

**Step 5: Commit**

```bash
git add src/riszotto/semantic.py tests/test_semantic.py
git commit -m "feat: add ChromaDB index building with incremental updates"
```

---

### Task 4: Add semantic_search function

**Files:**
- Modify: `src/riszotto/semantic.py`
- Modify: `tests/test_semantic.py`

**Step 1: Write failing tests for semantic_search**

Add to `tests/test_semantic.py`:

```python
from riszotto.semantic import semantic_search


class TestSemanticSearch:
    @patch("riszotto.semantic._get_collection")
    def test_returns_results_with_scores(self, mock_get_collection):
        mock_collection = MagicMock()
        mock_get_collection.return_value = mock_collection
        mock_collection.query.return_value = {
            "ids": [["P1", "P2"]],
            "distances": [[0.3, 0.7]],
            "metadatas": [[
                {"title": "Close Match", "itemType": "journalArticle"},
                {"title": "Far Match", "itemType": "book"},
            ]],
            "documents": [["doc text 1", "doc text 2"]],
        }

        results = semantic_search("attention mechanisms", limit=10)
        mock_collection.query.assert_called_once_with(
            query_texts=["attention mechanisms"],
            n_results=10,
        )
        assert len(results) == 2
        assert results[0]["key"] == "P1"
        assert results[0]["title"] == "Close Match"
        assert results[0]["score"] == pytest.approx(0.7, abs=0.01)
        assert results[1]["key"] == "P2"
        assert results[1]["score"] == pytest.approx(0.3, abs=0.01)

    @patch("riszotto.semantic._get_collection")
    def test_empty_results(self, mock_get_collection):
        mock_collection = MagicMock()
        mock_get_collection.return_value = mock_collection
        mock_collection.query.return_value = {
            "ids": [[]],
            "distances": [[]],
            "metadatas": [[]],
            "documents": [[]],
        }

        results = semantic_search("nonexistent topic")
        assert results == []
```

**Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_semantic.py::TestSemanticSearch -v`
Expected: FAIL — `semantic_search` not defined

**Step 3: Implement semantic_search**

Add to `src/riszotto/semantic.py`, after `build_index`:

```python
def semantic_search(query: str, *, limit: int = 10) -> list[dict[str, Any]]:
    """Search the index by semantic similarity.

    Returns list of dicts with keys: key, title, itemType, score.
    Score is 0-1 where 1 is most similar (converted from ChromaDB distance).
    """
    collection = _get_collection()
    raw = collection.query(query_texts=[query], n_results=limit)

    results: list[dict[str, Any]] = []
    ids = raw["ids"][0]
    distances = raw["distances"][0]
    metadatas = raw["metadatas"][0]

    for i, key in enumerate(ids):
        results.append({
            "key": key,
            "title": metadatas[i].get("title", ""),
            "itemType": metadatas[i].get("itemType", ""),
            "score": round(1 - distances[i], 4),
        })

    return results
```

**Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_semantic.py -v`
Expected: all PASS

**Step 5: Commit**

```bash
git add src/riszotto/semantic.py tests/test_semantic.py
git commit -m "feat: add semantic search query function"
```

---

### Task 5: Add get_index_status function

**Files:**
- Modify: `src/riszotto/semantic.py`
- Modify: `tests/test_semantic.py`

**Step 1: Write failing tests**

Add to `tests/test_semantic.py`:

```python
from riszotto.semantic import get_index_status


class TestGetIndexStatus:
    @patch("riszotto.semantic._get_collection")
    def test_returns_count_and_path(self, mock_get_collection):
        mock_collection = MagicMock()
        mock_get_collection.return_value = mock_collection
        mock_collection.count.return_value = 42

        status = get_index_status()
        assert status["count"] == 42
        assert status["path"] == str(INDEX_DIR)

    @patch("riszotto.semantic._get_collection")
    def test_empty_index(self, mock_get_collection):
        mock_collection = MagicMock()
        mock_get_collection.return_value = mock_collection
        mock_collection.count.return_value = 0

        status = get_index_status()
        assert status["count"] == 0
```

**Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_semantic.py::TestGetIndexStatus -v`
Expected: FAIL — `get_index_status` not defined

**Step 3: Implement get_index_status**

Add to `src/riszotto/semantic.py`:

```python
def get_index_status() -> dict[str, Any]:
    """Return index statistics."""
    collection = _get_collection()
    return {
        "count": collection.count(),
        "path": str(INDEX_DIR),
    }
```

**Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_semantic.py -v`
Expected: all PASS

**Step 5: Commit**

```bash
git add src/riszotto/semantic.py tests/test_semantic.py
git commit -m "feat: add index status reporting"
```

---

### Task 6: Add `index` CLI command

**Files:**
- Modify: `src/riszotto/cli.py`
- Modify: `tests/test_cli.py`

The `index` command must gracefully handle the case where chromadb is not installed (the `[semantic]` extras were not installed). It does this by catching `ImportError` when importing from `riszotto.semantic`.

**Step 1: Write failing tests**

Add to `tests/test_cli.py`:

```python
class TestIndex:
    @patch("riszotto.cli.get_client")
    @patch("riszotto.cli._import_semantic")
    def test_index_builds(self, mock_import_semantic, mock_get_client):
        mock_zot = MagicMock()
        mock_get_client.return_value = mock_zot
        mock_semantic = MagicMock()
        mock_import_semantic.return_value = mock_semantic
        mock_semantic.build_index.return_value = {"indexed": 10, "skipped": 2}

        result = runner.invoke(app, ["index"])
        assert result.exit_code == 0
        assert "10" in result.output
        mock_semantic.build_index.assert_called_once_with(mock_zot, rebuild=False, limit=None)

    @patch("riszotto.cli.get_client")
    @patch("riszotto.cli._import_semantic")
    def test_index_rebuild(self, mock_import_semantic, mock_get_client):
        mock_zot = MagicMock()
        mock_get_client.return_value = mock_zot
        mock_semantic = MagicMock()
        mock_import_semantic.return_value = mock_semantic
        mock_semantic.build_index.return_value = {"indexed": 5, "skipped": 0}

        result = runner.invoke(app, ["index", "--rebuild"])
        assert result.exit_code == 0
        mock_semantic.build_index.assert_called_once_with(mock_zot, rebuild=True, limit=None)

    @patch("riszotto.cli.get_client")
    @patch("riszotto.cli._import_semantic")
    def test_index_status(self, mock_import_semantic, mock_get_client):
        mock_get_client.return_value = MagicMock()
        mock_semantic = MagicMock()
        mock_import_semantic.return_value = mock_semantic
        mock_semantic.get_index_status.return_value = {"count": 42, "path": "/home/user/.riszotto/chroma_db"}

        result = runner.invoke(app, ["index", "--status"])
        assert result.exit_code == 0
        parsed = json.loads(result.output)
        assert parsed["count"] == 42
        assert parsed["path"] == "/home/user/.riszotto/chroma_db"

    @patch("riszotto.cli._import_semantic")
    def test_index_missing_extras(self, mock_import_semantic):
        mock_import_semantic.return_value = None

        result = runner.invoke(app, ["index"])
        assert result.exit_code == 1
        assert "semantic" in result.output.lower()
```

**Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_cli.py::TestIndex -v`
Expected: FAIL — no `index` command registered

**Step 3: Implement the index command**

In `src/riszotto/cli.py`, add a helper function to lazily import semantic module (place it after the existing imports, before `_get_zot`):

```python
def _import_semantic():
    """Import semantic module, returning None if extras not installed."""
    try:
        from riszotto import semantic
        return semantic
    except ImportError:
        return None
```

Then add the `index` command at the end of the file (after the `recent` command):

```python
@app.command()
def index(
    rebuild: Annotated[bool, typer.Option("--rebuild", help="Drop and rebuild the entire index")] = False,
    status: Annotated[bool, typer.Option("--status", help="Show index statistics")] = False,
    limit: Annotated[Optional[int], typer.Option("--limit", "-l", help="Maximum items to fetch from Zotero")] = None,
) -> None:
    """Build or update the semantic search index."""
    semantic = _import_semantic()
    if semantic is None:
        typer.echo(
            "Semantic search extras not installed. Run: uv pip install riszotto[semantic]",
            err=True,
        )
        raise typer.Exit(1)

    if status:
        info = semantic.get_index_status()
        typer.echo(json.dumps(info, indent=2))
        return

    zot = _get_zot()
    stats = semantic.build_index(zot, rebuild=rebuild, limit=limit)
    typer.echo(f"Indexed {stats['indexed']} items ({stats['skipped']} skipped).")
```

**Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_cli.py::TestIndex -v`
Expected: all PASS

**Step 5: Run all tests**

Run: `uv run pytest tests/ -v`
Expected: all PASS

**Step 6: Commit**

```bash
git add src/riszotto/cli.py tests/test_cli.py
git commit -m "feat: add index command for semantic search indexing"
```

---

### Task 7: Add `--semantic` flag to search command

**Files:**
- Modify: `src/riszotto/cli.py`
- Modify: `tests/test_cli.py`

The `--semantic` flag triggers semantic search instead of keyword search. It reuses the same JSON envelope format but adds a `score` field to each result. Since semantic search returns only keys and scores (not full Zotero item dicts), the search command fetches full items from Zotero to format them with `_format_result`.

**Step 1: Write failing tests**

Add to `tests/test_cli.py`:

```python
class TestSearchSemantic:
    @patch("riszotto.cli.get_client")
    @patch("riszotto.cli._import_semantic")
    def test_semantic_search_outputs_envelope(self, mock_import_semantic, mock_get_client):
        mock_zot = MagicMock()
        mock_get_client.return_value = mock_zot
        mock_semantic = MagicMock()
        mock_import_semantic.return_value = mock_semantic
        mock_semantic.semantic_search.return_value = [
            {"key": "P1", "title": "Paper One", "itemType": "journalArticle", "score": 0.95},
            {"key": "P2", "title": "Paper Two", "itemType": "book", "score": 0.80},
        ]
        mock_zot.item.side_effect = lambda key: {
            "P1": {
                "data": {
                    "key": "P1", "title": "Paper One", "itemType": "journalArticle",
                    "date": "2024", "abstractNote": "Abstract 1.", "creators": [], "tags": [],
                },
            },
            "P2": {
                "data": {
                    "key": "P2", "title": "Paper Two", "itemType": "book",
                    "date": "2023", "abstractNote": "Abstract 2.", "creators": [], "tags": [],
                },
            },
        }[key]

        result = runner.invoke(app, ["search", "--semantic", "attention mechanisms"])
        assert result.exit_code == 0
        parsed = json.loads(result.output)
        assert len(parsed["results"]) == 2
        assert parsed["results"][0]["key"] == "P1"
        assert parsed["results"][0]["score"] == 0.95
        assert parsed["results"][0]["title"] == "Paper One"
        assert parsed["results"][1]["key"] == "P2"
        assert parsed["results"][1]["score"] == 0.80

    @patch("riszotto.cli.get_client")
    @patch("riszotto.cli._import_semantic")
    def test_semantic_search_no_results(self, mock_import_semantic, mock_get_client):
        mock_get_client.return_value = MagicMock()
        mock_semantic = MagicMock()
        mock_import_semantic.return_value = mock_semantic
        mock_semantic.semantic_search.return_value = []

        result = runner.invoke(app, ["search", "--semantic", "nonexistent"])
        assert result.exit_code == 0
        parsed = json.loads(result.output)
        assert parsed["results"] == []

    @patch("riszotto.cli._import_semantic")
    def test_semantic_search_missing_extras(self, mock_import_semantic):
        mock_import_semantic.return_value = None

        result = runner.invoke(app, ["search", "--semantic", "test"])
        assert result.exit_code == 1
        assert "semantic" in result.output.lower()

    @patch("riszotto.cli.get_client")
    @patch("riszotto.cli._import_semantic")
    def test_semantic_search_respects_limit(self, mock_import_semantic, mock_get_client):
        mock_get_client.return_value = MagicMock()
        mock_semantic = MagicMock()
        mock_import_semantic.return_value = mock_semantic
        mock_semantic.semantic_search.return_value = []

        runner.invoke(app, ["search", "--semantic", "--limit", "5", "test"])
        mock_semantic.semantic_search.assert_called_once_with("test", limit=5)
```

**Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_cli.py::TestSearchSemantic -v`
Expected: FAIL — `--semantic` flag not recognized

**Step 3: Add --semantic flag to search command**

In `src/riszotto/cli.py`, modify the `search` command. Add a `semantic` parameter and a branch for semantic search:

```python
@app.command()
def search(
    terms: Annotated[list[str], typer.Argument(help="Search terms")],
    full_text: Annotated[bool, typer.Option("--full-text/--no-full-text", help="Search all fields including full-text")] = False,
    semantic: Annotated[bool, typer.Option("--semantic", help="Use semantic similarity search")] = False,
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

    if semantic:
        sem = _import_semantic()
        if sem is None:
            typer.echo(
                "Semantic search extras not installed. Run: uv pip install riszotto[semantic]",
                err=True,
            )
            raise typer.Exit(1)

        zot = _get_zot()
        hits = sem.semantic_search(query, limit=limit)
        results = []
        for hit in hits:
            item = zot.item(hit["key"])
            formatted = _format_result(item, max_value_size)
            formatted["score"] = hit["score"]
            results.append(formatted)

        envelope = {
            "page": 1,
            "limit": limit,
            "start": 0,
            "results": results,
        }
        typer.echo(json.dumps(envelope, indent=2))
        return

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

**Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_cli.py::TestSearchSemantic -v`
Expected: all PASS

**Step 5: Run ALL tests to check nothing broke**

Run: `uv run pytest tests/ -v`
Expected: all PASS

**Step 6: Commit**

```bash
git add src/riszotto/cli.py tests/test_cli.py
git commit -m "feat: add --semantic flag to search command"
```

---

### Task 8: Fix circular import — extract _format_creator to shared module

**Files:**
- Create: `src/riszotto/formatting.py`
- Modify: `src/riszotto/cli.py`
- Modify: `src/riszotto/semantic.py`

`semantic.py` imports `_format_creator` from `cli.py`, but `cli.py` imports from `semantic.py` (via `_import_semantic`). This creates a circular dependency risk. Extract shared formatters to a dedicated module.

**Step 1: Create formatting.py**

Create `src/riszotto/formatting.py`:

```python
"""Shared formatting helpers for riszotto."""

from __future__ import annotations


def format_creator(creator: dict) -> str:
    """Format a single Zotero creator dict as a string."""
    last = creator.get("lastName", "")
    first = creator.get("firstName", "")
    if last and first:
        return f"{last}, {first}"
    return creator.get("name", last or first)
```

**Step 2: Update cli.py imports**

In `src/riszotto/cli.py`:
- Add `from riszotto.formatting import format_creator` to imports
- Replace the `_format_creator` function definition with nothing (delete it)
- In `_format_result`, change `_format_creator(c)` to `format_creator(c)`

**Step 3: Update semantic.py import**

In `src/riszotto/semantic.py`:
- Change `from riszotto.cli import _format_creator` to `from riszotto.formatting import format_creator`
- Update `_build_document_text` to call `format_creator` instead of `_format_creator`

**Step 4: Run all tests**

Run: `uv run pytest tests/ -v`
Expected: all PASS

**Step 5: Commit**

```bash
git add src/riszotto/formatting.py src/riszotto/cli.py src/riszotto/semantic.py
git commit -m "refactor: extract format_creator to shared formatting module"
```

---

### Task 9: Smoke test

**Step 1: Build the index**

Run: `uv run riszotto index`
Expected: "Indexed N items (M skipped)." with some positive number

**Step 2: Check index status**

Run: `uv run riszotto index --status`
Expected: JSON with `count` > 0 and `path` showing `~/.riszotto/chroma_db`

**Step 3: Semantic search**

Run: `uv run riszotto search --semantic "molecular dynamics force fields"`
Expected: JSON envelope with results, each having a `score` field. Results should be semantically relevant papers.

**Step 4: Compare with keyword search**

Run: `uv run riszotto search "molecular dynamics"`
Expected: Different result ordering — keyword search matches exact terms, semantic finds conceptually related papers.

**Step 5: Test with jq**

Run: `uv run riszotto search --semantic "attention mechanisms" | jq '.results[] | {title, score}'`
Expected: titles with scores printed

**Step 6: Verify extras-not-installed error**

Run: `uv pip install riszotto && uv run riszotto search --semantic "test"`
Expected: Error message about missing semantic extras (only run this if you want to verify; skip if inconvenient to uninstall/reinstall)
