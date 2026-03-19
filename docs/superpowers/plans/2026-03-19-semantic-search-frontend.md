# Semantic Search Frontend Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add an interactive web frontend to riszotto for semantic search with a similarity graph, backed by FastAPI.

**Architecture:** FastAPI backend (thin wrapper around existing `semantic.py` and `client.py`) serves a Vite + React + MUI + ReactFlow frontend. Built assets are bundled into the Python package and served as static files. Launched via `riszotto web`.

**Tech Stack:** Python (FastAPI, uvicorn), TypeScript (React 18, MUI v6, ReactFlow v12, d3-force), Vite, bun

**Spec:** `docs/superpowers/specs/2026-03-19-semantic-search-frontend-design.md`

---

## File Map

### New Files

```
src/riszotto/
  api/
    __init__.py           # FastAPI app factory, static file mounting
    routes.py             # API endpoint handlers (search, neighbors, item, status)

frontend/
  package.json            # bun project, dependencies
  tsconfig.json           # TypeScript config
  vite.config.ts          # Vite config with API proxy
  index.html              # SPA entry
  src/
    main.tsx              # React root mount
    App.tsx               # Layout shell, state management
    theme.ts              # MUI createTheme (light + dark Warm Parchment)
    api.ts                # Typed fetch wrappers for /api/*
    types.ts              # Shared TypeScript types
    components/
      TopBar.tsx          # Logo, stats, dark mode toggle
      SearchBar.tsx       # MUI Autocomplete with debounced semantic search
      DetailPanel.tsx     # Selected paper metadata + action buttons
      GraphView.tsx       # ReactFlow canvas + d3-force layout engine
      PaperNode.tsx       # Custom ReactFlow node component
      GraphControls.tsx   # Cutoff/depth sliders overlay

tests/
  test_api.py             # FastAPI endpoint tests
```

### Modified Files

```
src/riszotto/semantic.py    # Add get_neighbors(), enrich metadata in build_index()
src/riszotto/client.py      # Extract discover_libraries() from cli.py
src/riszotto/cli.py         # Add `web` command, refactor to use client.discover_libraries()
pyproject.toml              # Add [web] extras, hatch build config for static/
.gitignore                  # Add src/riszotto/static/, node_modules, frontend/dist
tests/test_semantic.py      # Update tests for enriched metadata
```

---

## Phase 1: Backend Prerequisites

### Task 1: Enrich ChromaDB Metadata

Currently `build_index()` only stores `title` and `itemType` in ChromaDB metadata. The API needs `authors` and `year` without per-query Zotero lookups.

**Files:**
- Modify: `src/riszotto/semantic.py:126-131`
- Modify: `tests/test_semantic.py`

- [ ] **Step 1: Write failing test for enriched metadata**

In `tests/test_semantic.py`, add a test to `TestBuildIndex` that verifies upsert includes `creators` and `date`:

```python
def test_build_index_stores_enriched_metadata(self):
    """Verify build_index stores creators and date in ChromaDB metadata."""
    mock_collection = MagicMock()
    mock_collection.get.return_value = {"ids": []}

    items = [
        {
            "key": "ABC123",
            "data": {
                "title": "Test Paper",
                "itemType": "journalArticle",
                "creators": [
                    {"creatorType": "author", "lastName": "Smith", "firstName": "John"},
                    {"creatorType": "author", "lastName": "Doe", "firstName": "Jane"},
                ],
                "date": "2023-06-15",
                "abstractNote": "Abstract text.",
                "tags": [],
            },
        }
    ]

    with (
        patch("riszotto.semantic._get_collection", return_value=mock_collection),
        patch.object(mock_collection, "count", return_value=0),
    ):
        from riszotto.semantic import build_index

        mock_zot = MagicMock()
        # build_index uses zot.everything(zot.top()) when limit is None
        mock_zot.top.return_value = items
        mock_zot.everything.return_value = items
        build_index(mock_zot, rebuild=True)

    call_args = mock_collection.upsert.call_args
    metadatas = call_args[1]["metadatas"] if "metadatas" in call_args[1] else call_args[0][2]
    assert metadatas[0]["creators"] == "Smith, John; Doe, Jane"
    assert metadatas[0]["date"] == "2023-06-15"
    assert metadatas[0]["title"] == "Test Paper"
    assert metadatas[0]["itemType"] == "journalArticle"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_semantic.py::TestBuildIndex::test_build_index_stores_enriched_metadata -v`
Expected: FAIL — `creators` key not in metadata

- [ ] **Step 3: Implement enriched metadata in build_index()**

In `src/riszotto/semantic.py`, modify the metadata dict in `build_index()` (around line 126-131). Reuse `format_creator` from `formatting.py` (already exists — do NOT duplicate):

```python
from riszotto.formatting import format_creator
```

Then update the metadata dict in `build_index()`:

```python
metadatas.append(
    {
        "title": data.get("title", ""),
        "itemType": data.get("itemType", ""),
        "creators": "; ".join(
            format_creator(c) for c in data.get("creators", [])
        ),
        "date": data.get("date", ""),
    }
)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_semantic.py::TestBuildIndex::test_build_index_stores_enriched_metadata -v`
Expected: PASS

- [ ] **Step 5: Update existing tests that assert metadata**

Check existing tests in `TestBuildIndex` that assert on upsert call args — they may need to include the new `creators` and `date` fields. Run the full test suite:

Run: `uv run pytest tests/test_semantic.py -v`
Expected: All PASS

- [ ] **Step 6: Update semantic_search() to return enriched fields**

In `semantic_search()` (around line 170), the result dict currently returns `key`, `title`, `itemType`, `score`. Add `creators` and `date`:

```python
results.append(
    {
        "key": id_,
        "title": meta.get("title", ""),
        "itemType": meta.get("itemType", ""),
        "creators": meta.get("creators", ""),
        "date": meta.get("date", ""),
        "score": round(1 - dist, 4),
    }
)
```

- [ ] **Step 7: Write test for enriched search results**

```python
def test_semantic_search_returns_enriched_fields(self):
    """Verify search results include creators and date."""
    mock_collection = MagicMock()
    mock_collection.query.return_value = {
        "ids": [["key1"]],
        "distances": [[0.2]],
        "metadatas": [[{
            "title": "Test",
            "itemType": "journalArticle",
            "creators": "Smith, John",
            "date": "2023",
        }]],
    }

    with patch("riszotto.semantic._get_collection", return_value=mock_collection):
        from riszotto.semantic import semantic_search
        results = semantic_search("test query")

    assert results[0]["creators"] == "Smith, John"
    assert results[0]["date"] == "2023"
```

- [ ] **Step 8: Run all semantic tests**

Run: `uv run pytest tests/test_semantic.py -v`
Expected: All PASS

- [ ] **Step 9: Commit**

```bash
git add src/riszotto/semantic.py tests/test_semantic.py
git commit -m "feat: enrich ChromaDB metadata with creators and date"
```

---

### Task 2: Extract Library Discovery to client.py

`_discover_libraries()` in `cli.py` (lines 153-226) is coupled to Typer/CLI. Extract a shared version to `client.py` so the API can use it.

**Files:**
- Modify: `src/riszotto/client.py`
- Modify: `src/riszotto/cli.py:153-226`
- Modify: `tests/test_client.py`

- [ ] **Step 1: Write failing test for discover_libraries()**

In `tests/test_client.py`:

```python
class TestDiscoverLibraries:
    """Tests for discover_libraries()."""

    def test_returns_personal_library(self):
        """Personal library is always included."""
        mock_config = MagicMock()
        mock_config.has_remote_credentials = False

        with (
            patch("riszotto.client.get_client") as mock_get,
            patch("riszotto.client.load_config", return_value=mock_config),
        ):
            mock_zot = MagicMock()
            mock_zot.groups.return_value = []
            mock_get.return_value = mock_zot

            from riszotto.client import discover_libraries
            libs = discover_libraries()

        assert len(libs) >= 1
        assert libs[0]["name"] == "My Library"
        assert libs[0]["type"] == "user"

    def test_includes_local_groups(self):
        """Local groups from Zotero are discovered."""
        mock_zot = MagicMock()
        mock_config = MagicMock()
        mock_config.has_remote_credentials = False

        mock_group = {
            "id": 12345,
            "data": {"name": "Lab Papers", "id": 12345},
        }
        mock_zot.groups.return_value = [mock_group]

        with (
            patch("riszotto.client.get_client", return_value=mock_zot),
            patch("riszotto.client.load_config", return_value=mock_config),
        ):
            from riszotto.client import discover_libraries
            libs = discover_libraries()

        group_libs = [l for l in libs if l["type"] == "group"]
        assert len(group_libs) == 1
        assert group_libs[0]["name"] == "Lab Papers"
        assert group_libs[0]["id"] == "12345"  # stored as string for consistency
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_client.py::TestDiscoverLibraries -v`
Expected: FAIL — `discover_libraries` not importable

- [ ] **Step 3: Extract discover_libraries() into client.py**

Add to `src/riszotto/client.py`:

```python
from riszotto.config import load_config


def _discover_remote_groups(config: "Config") -> list[dict[str, Any]]:
    """Discover groups via remote Zotero API if credentials are available."""
    if not config.has_remote_credentials:
        return []
    try:
        remote_zot = zotero.Zotero(config.user_id, "user", config.api_key)
        return remote_zot.groups() or []
    except Exception:
        return []


def discover_libraries() -> list[dict[str, Any]]:
    """Discover all accessible Zotero libraries (personal + groups).

    Returns
    -------
    list[dict[str, Any]]
        Each dict has keys: name, id, type ("user" or "group"), source ("local" or "remote"),
        and collection_name (ChromaDB collection name for semantic indexing).
    """
    config = load_config()
    libraries: list[dict[str, Any]] = []
    seen_group_ids: set[int] = set()

    # Personal library is always present
    libraries.append({
        "name": "My Library",
        "id": "0",
        "type": "user",
        "source": "local",
        "collection_name": "user_0",
    })

    # Local groups
    try:
        zot = get_client()
        for group in zot.groups() or []:
            gid = group.get("id") or group.get("data", {}).get("id")
            gname = group.get("data", {}).get("name", f"Group {gid}")
            if gid and gid not in seen_group_ids:
                seen_group_ids.add(gid)
                libraries.append({
                    "name": gname,
                    "id": str(gid),  # always string for consistency
                    "type": "group",
                    "source": "local",
                    "collection_name": f"group_{gid}",
                })
    except Exception:
        pass  # Local API may not be running

    # Remote groups (deduplicated)
    for group in _discover_remote_groups(config):
        gid = group.get("id") or group.get("data", {}).get("id")
        gname = group.get("data", {}).get("name", f"Group {gid}")
        if gid and gid not in seen_group_ids:
            seen_group_ids.add(gid)
            libraries.append({
                "name": gname,
                "id": str(gid),  # always string for consistency
                "type": "group",
                "source": "remote",
                "collection_name": f"group_{gid}",
            })

    return libraries
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_client.py::TestDiscoverLibraries -v`
Expected: PASS

- [ ] **Step 5: Refactor cli.py to use client.discover_libraries()**

Replace `_discover_libraries()` in `cli.py` (lines 153-226) with a wrapper that calls `client.discover_libraries()` and adds the Typer-specific `client` object to each entry:

```python
def _discover_libraries() -> list[dict]:
    """Discover libraries and attach live client objects for CLI use."""
    from riszotto.client import discover_libraries

    libs = discover_libraries()
    for lib in libs:
        try:
            lib_arg = None if lib["type"] == "user" else str(lib["id"])
            lib["client"] = get_client(lib_arg)
        except Exception:
            lib["client"] = None
    return libs
```

- [ ] **Step 6: Run full test suite to verify no regressions**

Run: `uv run pytest -v`
Expected: All PASS

- [ ] **Step 7: Commit**

```bash
git add src/riszotto/client.py src/riszotto/cli.py tests/test_client.py
git commit -m "refactor: extract discover_libraries() to client.py"
```

---

### Task 3: Add get_neighbors() to semantic.py

**Files:**
- Modify: `src/riszotto/semantic.py`
- Modify: `tests/test_semantic.py`

- [ ] **Step 1: Write failing test for get_neighbors()**

```python
class TestGetNeighbors:
    """Tests for get_neighbors()."""

    def test_returns_center_node_and_neighbors(self):
        """Center node at depth 0, neighbors at depth 1."""
        mock_collection = MagicMock()

        # get() returns the center item's embedding
        mock_collection.get.return_value = {
            "ids": ["center_key"],
            "embeddings": [[0.1, 0.2, 0.3]],
            "metadatas": [{"title": "Center Paper", "itemType": "journalArticle", "creators": "Smith, J", "date": "2020"}],
        }

        # query() returns neighbors
        mock_collection.query.return_value = {
            "ids": [["neighbor1", "neighbor2"]],
            "distances": [[0.15, 0.4]],
            "metadatas": [[
                {"title": "Neighbor 1", "itemType": "journalArticle", "creators": "Doe, J", "date": "2021"},
                {"title": "Neighbor 2", "itemType": "conferencePaper", "creators": "Lee, A", "date": "2019"},
            ]],
            "embeddings": [[[0.2, 0.3, 0.4], [0.5, 0.6, 0.7]]],
        }

        with patch("riszotto.semantic._get_collection", return_value=mock_collection):
            from riszotto.semantic import get_neighbors
            result = get_neighbors("center_key", cutoff=0.5, depth=1)

        assert len(result["nodes"]) == 3  # center + 2 neighbors
        assert result["nodes"][0]["key"] == "center_key"
        assert result["nodes"][0]["depth"] == 0
        assert len(result["edges"]) == 2

    def test_respects_cutoff(self):
        """Neighbors below cutoff are excluded."""
        mock_collection = MagicMock()
        mock_collection.get.return_value = {
            "ids": ["center"],
            "embeddings": [[0.1, 0.2, 0.3]],
            "metadatas": [{"title": "Center", "itemType": "journalArticle", "creators": "", "date": ""}],
        }
        mock_collection.query.return_value = {
            "ids": [["n1", "n2"]],
            "distances": [[0.1, 0.8]],  # n2 has low similarity (1-0.8=0.2)
            "metadatas": [[
                {"title": "Close", "itemType": "journalArticle", "creators": "", "date": ""},
                {"title": "Far", "itemType": "journalArticle", "creators": "", "date": ""},
            ]],
            "embeddings": [[[0.2, 0.3, 0.4], [0.9, 0.8, 0.7]]],
        }

        with patch("riszotto.semantic._get_collection", return_value=mock_collection):
            from riszotto.semantic import get_neighbors
            result = get_neighbors("center", cutoff=0.5, depth=1)

        # Only n1 passes cutoff (similarity 0.9 > 0.5), n2 doesn't (0.2 < 0.5)
        assert len(result["nodes"]) == 2
        assert len(result["edges"]) == 1

    def test_max_nodes_cap(self):
        """Graph is capped at 50 nodes."""
        mock_collection = MagicMock()
        mock_collection.get.return_value = {
            "ids": ["center"],
            "embeddings": [[0.1]],
            "metadatas": [{"title": "Center", "itemType": "journalArticle", "creators": "", "date": ""}],
        }

        # Return 60 neighbors (all above cutoff)
        ids = [[f"n{i}" for i in range(60)]]
        distances = [[0.05] * 60]
        metadatas = [[{"title": f"Paper {i}", "itemType": "journalArticle", "creators": "", "date": ""} for i in range(60)]]
        embeddings = [[[0.1] for _ in range(60)]]

        mock_collection.query.return_value = {
            "ids": ids, "distances": distances,
            "metadatas": metadatas, "embeddings": embeddings,
        }

        with patch("riszotto.semantic._get_collection", return_value=mock_collection):
            from riszotto.semantic import get_neighbors
            result = get_neighbors("center", cutoff=0.0, depth=1)

        assert len(result["nodes"]) <= 50
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_semantic.py::TestGetNeighbors -v`
Expected: FAIL — `get_neighbors` not importable

- [ ] **Step 3: Implement get_neighbors()**

Add to `src/riszotto/semantic.py`:

```python
MAX_GRAPH_NODES = 50
MAX_NEIGHBORS_PER_NODE = 10


def get_neighbors(
    item_key: str,
    *,
    cutoff: float = 0.35,
    depth: int = 2,
    collection_name: str = "user_0",
) -> dict:
    """Build a similarity graph around a paper.

    Parameters
    ----------
    item_key : str
        Zotero item key to center the graph on.
    cutoff : float
        Minimum similarity score (0-1) for an edge.
    depth : int
        How many hops from the center node to expand.
    collection_name : str
        ChromaDB collection to query.

    Returns
    -------
    dict
        Graph with "nodes" and "edges" lists. Capped at MAX_GRAPH_NODES.
    """
    collection = _get_collection(collection_name=collection_name)

    nodes: list[dict] = []
    edges: list[dict] = []
    seen_keys: set[str] = set()

    # Get center node embedding
    center = collection.get(ids=[item_key], include=["embeddings", "metadatas"])
    if not center["ids"]:
        return {"nodes": [], "edges": []}

    center_meta = center["metadatas"][0]
    center_embedding = center["embeddings"][0]

    nodes.append({
        "key": item_key,
        "title": center_meta.get("title", ""),
        "itemType": center_meta.get("itemType", ""),
        "creators": center_meta.get("creators", ""),
        "date": center_meta.get("date", ""),
        "depth": 0,
        "score": 1.0,
    })
    seen_keys.add(item_key)

    # BFS expansion
    frontier = [(item_key, center_embedding, 0)]  # (key, embedding, current_depth)

    while frontier and len(nodes) < MAX_GRAPH_NODES:
        source_key, embedding, current_depth = frontier.pop(0)

        if current_depth >= depth:
            continue

        results = collection.query(
            query_embeddings=[embedding],
            n_results=MAX_NEIGHBORS_PER_NODE + 1,  # +1 to account for self
            include=["metadatas", "distances", "embeddings"],
        )

        for i, neighbor_key in enumerate(results["ids"][0]):
            if neighbor_key == source_key:
                continue
            if len(nodes) >= MAX_GRAPH_NODES:
                break

            distance = results["distances"][0][i]
            similarity = round(1 - distance, 4)

            if similarity < cutoff:
                continue

            meta = results["metadatas"][0][i]
            neighbor_embedding = results["embeddings"][0][i]

            edges.append({
                "source": source_key,
                "target": neighbor_key,
                "similarity": similarity,
            })

            if neighbor_key not in seen_keys:
                seen_keys.add(neighbor_key)
                nodes.append({
                    "key": neighbor_key,
                    "title": meta.get("title", ""),
                    "itemType": meta.get("itemType", ""),
                    "creators": meta.get("creators", ""),
                    "date": meta.get("date", ""),
                    "depth": current_depth + 1,
                    "score": similarity,
                })
                frontier.append((neighbor_key, neighbor_embedding, current_depth + 1))

    return {"nodes": nodes, "edges": edges}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_semantic.py::TestGetNeighbors -v`
Expected: All PASS

- [ ] **Step 5: Run full semantic test suite**

Run: `uv run pytest tests/test_semantic.py -v`
Expected: All PASS

- [ ] **Step 6: Commit**

```bash
git add src/riszotto/semantic.py tests/test_semantic.py
git commit -m "feat: add get_neighbors() for similarity graph expansion"
```

---

## Phase 2: FastAPI Backend

### Task 4: Create FastAPI App and API Endpoints

**Files:**
- Create: `src/riszotto/api/__init__.py`
- Create: `src/riszotto/api/routes.py`
- Create: `tests/test_api.py`

- [ ] **Step 1: Write failing tests for API endpoints**

Create `tests/test_api.py`:

```python
"""Tests for the FastAPI API endpoints."""

from unittest.mock import MagicMock, patch

import pytest


@pytest.fixture
def client():
    """Create a FastAPI test client."""
    from fastapi.testclient import TestClient
    from riszotto.api import create_app

    app = create_app()
    return TestClient(app)


class TestSearchEndpoint:
    def test_search_returns_results(self, client):
        mock_results = [
            {"key": "ABC", "title": "Test Paper", "itemType": "journalArticle",
             "creators": "Smith, J", "date": "2023", "score": 0.95},
        ]
        with patch("riszotto.api.routes.semantic_search", return_value=mock_results):
            response = client.get("/api/search?q=test&limit=10")
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["title"] == "Test Paper"

    def test_search_requires_query(self, client):
        response = client.get("/api/search")
        assert response.status_code == 422


class TestAutocompleteEndpoint:
    def test_autocomplete_returns_limited_results(self, client):
        mock_results = [
            {"key": "A", "title": "Paper A", "itemType": "journalArticle",
             "creators": "X", "date": "2023", "score": 0.9},
        ]
        with patch("riszotto.api.routes.semantic_search", return_value=mock_results):
            response = client.get("/api/autocomplete?q=test")
        assert response.status_code == 200


class TestNeighborsEndpoint:
    def test_neighbors_returns_graph(self, client):
        mock_graph = {
            "nodes": [{"key": "A", "title": "Paper A", "depth": 0, "score": 1.0,
                        "itemType": "journalArticle", "creators": "", "date": ""}],
            "edges": [],
        }
        with patch("riszotto.api.routes.get_neighbors", return_value=mock_graph):
            response = client.get("/api/neighbors/ABC123?cutoff=0.3&depth=2")
        assert response.status_code == 200
        data = response.json()
        assert "nodes" in data
        assert "edges" in data


class TestItemEndpoint:
    def test_item_returns_metadata(self, client):
        mock_item = {
            "key": "ABC123",
            "data": {
                "title": "Test Paper",
                "creators": [{"lastName": "Smith", "firstName": "J", "creatorType": "author"}],
                "abstractNote": "Abstract",
                "date": "2023",
                "itemType": "journalArticle",
                "tags": [{"tag": "ML"}],
            },
        }
        with (
            patch("riszotto.api.routes.get_client", return_value=MagicMock()),
            patch("riszotto.api.routes.get_item", return_value=mock_item),
        ):
            response = client.get("/api/item/ABC123")
        assert response.status_code == 200
        data = response.json()
        assert data["title"] == "Test Paper"
        assert data["authors"] == ["Smith, J"]
        assert data["zoteroLink"] == "zotero://select/items/ABC123"


class TestStatusEndpoint:
    def test_status_returns_index_info(self, client):
        mock_libs = [
            {"name": "My Library", "id": "0", "type": "user", "collection_name": "user_0"},
        ]
        with (
            patch("riszotto.api.routes.discover_libraries", return_value=mock_libs),
            patch("riszotto.api.routes.get_index_status", return_value={"count": 100, "path": "/tmp"}),
        ):
            response = client.get("/api/status")
        assert response.status_code == 200
        data = response.json()
        assert data["total_papers"] == 100
        assert len(data["libraries"]) == 1
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_api.py -v`
Expected: FAIL — cannot import `riszotto.api`

- [ ] **Step 3: Create the FastAPI app factory**

Create `src/riszotto/api/__init__.py`:

```python
"""FastAPI application for riszotto web UI."""

from __future__ import annotations

import importlib.resources
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from riszotto.api.routes import router


def create_app() -> FastAPI:
    """Create and configure the FastAPI application.

    Returns
    -------
    FastAPI
        Configured application with API routes and static file serving.
    """
    app = FastAPI(title="riszotto", docs_url="/api/docs", redoc_url=None)
    app.include_router(router, prefix="/api")

    # Serve built frontend assets if available
    static_dir = Path(__file__).parent.parent / "static"
    if static_dir.is_dir():
        app.mount("/", StaticFiles(directory=str(static_dir), html=True), name="static")

    return app
```

- [ ] **Step 4: Create API routes**

Create `src/riszotto/api/routes.py`:

```python
"""API endpoint handlers."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query

from riszotto.client import discover_libraries, get_client, get_item
from riszotto.semantic import get_index_status, get_neighbors, semantic_search

router = APIRouter()


@router.get("/search")
def search(q: str = Query(..., min_length=1), limit: int = Query(10, ge=1, le=100)):
    """Semantic search for papers.

    Parameters
    ----------
    q : str
        Search query.
    limit : int
        Maximum results to return.
    """
    return semantic_search(q, limit=limit)


@router.get("/autocomplete")
def autocomplete(q: str = Query(..., min_length=1), limit: int = Query(5, ge=1, le=20)):
    """Autocomplete suggestions from semantic search.

    Parameters
    ----------
    q : str
        Partial search query.
    limit : int
        Maximum suggestions.
    """
    return semantic_search(q, limit=limit)


@router.get("/neighbors/{item_key}")
def neighbors(
    item_key: str,
    cutoff: float = Query(0.35, ge=0.0, le=1.0),
    depth: int = Query(2, ge=1, le=4),
):
    """Get similarity graph around a paper.

    Parameters
    ----------
    item_key : str
        Zotero item key to center graph on.
    cutoff : float
        Minimum similarity score for edges.
    depth : int
        Number of hops from center.
    """
    result = get_neighbors(item_key, cutoff=cutoff, depth=depth)
    if not result["nodes"]:
        raise HTTPException(status_code=404, detail="Item not found in index")
    return result


@router.get("/item/{item_key}")
def item_detail(item_key: str):
    """Get full metadata for a single paper.

    Parameters
    ----------
    item_key : str
        Zotero item key.
    """
    try:
        zot = get_client()
        raw = get_item(zot, item_key)
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"Zotero unavailable: {e}")

    data = raw.get("data", raw)
    creators = data.get("creators", [])
    authors = []
    for c in creators:
        last = c.get("lastName", "")
        first = c.get("firstName", "")
        if last and first:
            authors.append(f"{last}, {first}")
        elif last:
            authors.append(last)
        elif c.get("name"):
            authors.append(c["name"])

    return {
        "key": raw.get("key", item_key),
        "title": data.get("title", ""),
        "authors": authors,
        "abstract": data.get("abstractNote", ""),
        "tags": [t.get("tag", "") for t in data.get("tags", [])],
        "date": data.get("date", ""),
        "itemType": data.get("itemType", ""),
        "zoteroLink": f"zotero://select/items/{item_key}",
    }


@router.get("/status")
def status():
    """Get index status across all libraries."""
    libraries = discover_libraries()
    total = 0
    lib_stats = []

    for lib in libraries:
        col_name = lib.get("collection_name", "user_0")
        try:
            info = get_index_status(collection_name=col_name)
            count = info.get("count", 0)
        except Exception:
            count = 0
        total += count
        lib_stats.append({"name": lib["name"], "count": count})

    return {"total_papers": total, "libraries": lib_stats}
```

- [ ] **Step 5: Add test dependencies**

Add `httpx` and `fastapi` to the dev dependency group in `pyproject.toml`:

```toml
[dependency-groups]
dev = [
    "pytest>=9.0.2",
    "httpx>=0.24.0",
    "fastapi>=0.100.0",
]
```

Then sync: `uv sync --group dev`

- [ ] **Step 6: Run API tests**

Run: `uv run pytest tests/test_api.py -v`
Expected: All PASS

- [ ] **Step 7: Run full test suite**

Run: `uv run pytest -v`
Expected: All PASS

- [ ] **Step 8: Commit**

```bash
git add src/riszotto/api/ tests/test_api.py pyproject.toml
git commit -m "feat: add FastAPI backend with search, neighbors, item, status endpoints"
```

---

### Task 5: Add `web` CLI Command and Update pyproject.toml

**Files:**
- Modify: `src/riszotto/cli.py`
- Modify: `pyproject.toml`
- Modify: `.gitignore`

- [ ] **Step 1: Add web extras to pyproject.toml**

Add under `[project.optional-dependencies]`:

```toml
web = [
    "fastapi>=0.100.0",
    "uvicorn>=0.20.0",
]
```

Add hatch build config to include static files:

```toml
[tool.hatch.build.targets.wheel]
packages = ["src/riszotto"]

[tool.hatch.build.targets.wheel.force-include]
"src/riszotto/static" = "riszotto/static"
```

- [ ] **Step 2: Add `web` command to cli.py**

Add to `src/riszotto/cli.py`:

```python
@app.command()
def web(
    port: int = typer.Option(8080, "--port", "-p", help="Port to serve on."),
    no_open: bool = typer.Option(False, "--no-open", help="Don't open browser automatically."),
) -> None:
    """Launch the web UI for interactive semantic search."""
    try:
        import uvicorn
    except ImportError:
        typer.echo("Web UI requires extra dependencies. Install with:")
        typer.echo("  pip install riszotto[web]")
        raise typer.Exit(1)

    from riszotto.api import create_app

    app_instance = create_app()

    if not no_open:
        import webbrowser
        import threading

        def open_browser():
            import time
            time.sleep(1)
            webbrowser.open(f"http://localhost:{port}")

        threading.Thread(target=open_browser, daemon=True).start()

    typer.echo(f"Starting riszotto web UI on http://localhost:{port}")
    uvicorn.run(app_instance, host="127.0.0.1", port=port, log_level="warning")
```

- [ ] **Step 3: Update .gitignore**

Append to `.gitignore`:

```
# Frontend
node_modules/
frontend/dist/
src/riszotto/static/

# Brainstorming
.superpowers/
```

- [ ] **Step 4: Run existing tests to verify no regressions**

Run: `uv run pytest -v`
Expected: All PASS

- [ ] **Step 5: Commit**

```bash
git add src/riszotto/cli.py pyproject.toml .gitignore
git commit -m "feat: add web command and web extras to pyproject.toml"
```

---

## Phase 3: Frontend

### Task 6: Scaffold Frontend Project

**Files:**
- Create: `frontend/package.json`
- Create: `frontend/tsconfig.json`
- Create: `frontend/vite.config.ts`
- Create: `frontend/index.html`
- Create: `frontend/src/main.tsx`
- Create: `frontend/src/vite-env.d.ts`

- [ ] **Step 1: Initialize bun project**

```bash
cd frontend
bun init -y
```

- [ ] **Step 2: Install dependencies**

```bash
cd frontend
bun add react react-dom @xyflow/react @mui/material @emotion/react @emotion/styled @mui/icons-material d3-force
bun add -d typescript @types/react @types/react-dom @types/d3-force @vitejs/plugin-react vite
```

- [ ] **Step 3: Create vite.config.ts**

```typescript
import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  build: {
    outDir: "../src/riszotto/static",
    emptyOutDir: true,
  },
  server: {
    proxy: {
      "/api": {
        target: "http://localhost:8080",
        changeOrigin: true,
      },
    },
  },
});
```

- [ ] **Step 4: Create tsconfig.json**

```json
{
  "compilerOptions": {
    "target": "ES2020",
    "useDefineForClassFields": true,
    "lib": ["ES2020", "DOM", "DOM.Iterable"],
    "module": "ESNext",
    "skipLibCheck": true,
    "moduleResolution": "bundler",
    "allowImportingTsExtensions": true,
    "isolatedModules": true,
    "moduleDetection": "force",
    "noEmit": true,
    "jsx": "react-jsx",
    "strict": true,
    "noUnusedLocals": true,
    "noUnusedParameters": true,
    "noFallthroughCasesInSwitch": true,
    "forceConsistentCasingInFileNames": true
  },
  "include": ["src"]
}
```

- [ ] **Step 5: Create index.html**

```html
<!DOCTYPE html>
<html lang="en">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <title>riszotto search</title>
  </head>
  <body>
    <div id="root"></div>
    <script type="module" src="/src/main.tsx"></script>
  </body>
</html>
```

- [ ] **Step 6: Create src/vite-env.d.ts**

```typescript
/// <reference types="vite/client" />
```

- [ ] **Step 7: Create src/main.tsx (minimal)**

```tsx
import React from "react";
import ReactDOM from "react-dom/client";
import App from "./App";

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>
);
```

- [ ] **Step 8: Create src/App.tsx (placeholder)**

```tsx
export default function App() {
  return <div>riszotto search — loading...</div>;
}
```

- [ ] **Step 9: Verify it builds**

```bash
cd frontend && bun run vite build
```

Expected: Build succeeds, output in `src/riszotto/static/`

- [ ] **Step 10: Commit**

```bash
git add frontend/
git commit -m "feat: scaffold frontend with Vite + React + TypeScript"
```

---

### Task 7: Theme and Types

**Files:**
- Create: `frontend/src/theme.ts`
- Create: `frontend/src/types.ts`
- Create: `frontend/src/api.ts`

- [ ] **Step 1: Create types.ts**

```typescript
export interface Paper {
  key: string;
  title: string;
  creators: string;
  date: string;
  score: number;
  itemType: string;
}

export interface PaperDetail {
  key: string;
  title: string;
  authors: string[];
  abstract: string;
  tags: string[];
  date: string;
  itemType: string;
  zoteroLink: string;
}

export interface GraphNode {
  key: string;
  title: string;
  creators: string;
  date: string;
  itemType: string;
  depth: number;
  score: number;
}

export interface GraphEdge {
  source: string;
  target: string;
  similarity: number;
}

export interface GraphData {
  nodes: GraphNode[];
  edges: GraphEdge[];
}

export interface LibraryStatus {
  name: string;
  count: number;
}

export interface IndexStatus {
  total_papers: number;
  libraries: LibraryStatus[];
}
```

- [ ] **Step 2: Create theme.ts**

```typescript
import { createTheme } from "@mui/material/styles";

const shared = {
  typography: {
    fontFamily: "'Source Sans 3', sans-serif",
    h1: { fontFamily: "'Cormorant Garamond', serif", fontWeight: 700 },
    h2: { fontFamily: "'Cormorant Garamond', serif", fontWeight: 700 },
    h3: { fontFamily: "'Cormorant Garamond', serif", fontWeight: 700 },
    h4: { fontFamily: "'Cormorant Garamond', serif", fontWeight: 600 },
  },
};

export const lightTheme = createTheme({
  ...shared,
  palette: {
    mode: "light",
    primary: { main: "#b8956a" },
    secondary: { main: "#3a3228" },
    background: { default: "#f8f4ec", paper: "#fff" },
    text: { primary: "#3a3228", secondary: "#8a7a62" },
    divider: "#e2d8c8",
  },
});

export const darkTheme = createTheme({
  ...shared,
  palette: {
    mode: "dark",
    primary: { main: "#d4a574" },
    secondary: { main: "#e8e0d4" },
    background: { default: "#1c1a16", paper: "#262220" },
    text: { primary: "#e8e0d4", secondary: "#9a8a72" },
    divider: "#3a3428",
  },
});
```

- [ ] **Step 3: Create api.ts**

```typescript
import type { Paper, PaperDetail, GraphData, IndexStatus } from "./types";

const BASE = "/api";

export async function searchPapers(query: string, limit = 10): Promise<Paper[]> {
  const res = await fetch(`${BASE}/search?q=${encodeURIComponent(query)}&limit=${limit}`);
  if (!res.ok) throw new Error(`Search failed: ${res.status}`);
  return res.json();
}

export async function autocompletePapers(query: string, limit = 5): Promise<Paper[]> {
  const res = await fetch(`${BASE}/autocomplete?q=${encodeURIComponent(query)}&limit=${limit}`);
  if (!res.ok) throw new Error(`Autocomplete failed: ${res.status}`);
  return res.json();
}

export async function getNeighbors(
  itemKey: string,
  cutoff = 0.35,
  depth = 2
): Promise<GraphData> {
  const res = await fetch(
    `${BASE}/neighbors/${itemKey}?cutoff=${cutoff}&depth=${depth}`
  );
  if (!res.ok) throw new Error(`Neighbors failed: ${res.status}`);
  return res.json();
}

export async function getItemDetail(itemKey: string): Promise<PaperDetail> {
  const res = await fetch(`${BASE}/item/${itemKey}`);
  if (!res.ok) throw new Error(`Item detail failed: ${res.status}`);
  return res.json();
}

export async function getStatus(): Promise<IndexStatus> {
  const res = await fetch(`${BASE}/status`);
  if (!res.ok) throw new Error(`Status failed: ${res.status}`);
  return res.json();
}
```

- [ ] **Step 4: Verify build**

```bash
cd frontend && bun run vite build
```

- [ ] **Step 5: Commit**

```bash
git add frontend/src/types.ts frontend/src/theme.ts frontend/src/api.ts
git commit -m "feat: add theme, types, and API client"
```

---

### Task 8: TopBar Component

**Files:**
- Create: `frontend/src/components/TopBar.tsx`

- [ ] **Step 1: Create TopBar.tsx**

```tsx
import AppBar from "@mui/material/AppBar";
import Toolbar from "@mui/material/Toolbar";
import Typography from "@mui/material/Typography";
import IconButton from "@mui/material/IconButton";
import Box from "@mui/material/Box";
import Brightness4Icon from "@mui/icons-material/Brightness4";
import Brightness7Icon from "@mui/icons-material/Brightness7";
import type { IndexStatus } from "../types";

interface TopBarProps {
  status: IndexStatus | null;
  darkMode: boolean;
  onToggleDarkMode: () => void;
}

export default function TopBar({ status, darkMode, onToggleDarkMode }: TopBarProps) {
  return (
    <AppBar
      position="static"
      elevation={0}
      sx={{
        bgcolor: "background.paper",
        borderBottom: 1,
        borderColor: "divider",
      }}
    >
      <Toolbar variant="dense" sx={{ gap: 2 }}>
        <Typography
          variant="h6"
          sx={{
            fontFamily: "'Cormorant Garamond', serif",
            fontWeight: 700,
            color: "text.primary",
          }}
        >
          riszotto
          <Box component="span" sx={{ color: "primary.main", fontWeight: 400, ml: 0.5 }}>
            search
          </Box>
        </Typography>

        {status && (
          <Box sx={{ display: "flex", gap: 2, ml: 2 }}>
            <Typography variant="caption" color="text.secondary">
              <Box component="span" sx={{ fontFamily: "'JetBrains Mono', monospace", color: "text.primary" }}>
                {status.total_papers.toLocaleString()}
              </Box>{" "}
              papers
            </Typography>
            <Typography variant="caption" color="text.secondary">
              <Box component="span" sx={{ fontFamily: "'JetBrains Mono', monospace", color: "text.primary" }}>
                {status.libraries.length}
              </Box>{" "}
              {status.libraries.length === 1 ? "library" : "libraries"}
            </Typography>
          </Box>
        )}

        <Box sx={{ flexGrow: 1 }} />

        <IconButton onClick={onToggleDarkMode} size="small" color="inherit" sx={{ color: "text.secondary" }}>
          {darkMode ? <Brightness7Icon fontSize="small" /> : <Brightness4Icon fontSize="small" />}
        </IconButton>
      </Toolbar>
    </AppBar>
  );
}
```

- [ ] **Step 2: Verify build**

```bash
cd frontend && bun run vite build
```

- [ ] **Step 3: Commit**

```bash
git add frontend/src/components/TopBar.tsx
git commit -m "feat: add TopBar component with stats and dark mode toggle"
```

---

### Task 9: SearchBar Component

**Files:**
- Create: `frontend/src/components/SearchBar.tsx`

- [ ] **Step 1: Create SearchBar.tsx**

```tsx
import { useState, useCallback, useRef } from "react";
import Autocomplete from "@mui/material/Autocomplete";
import TextField from "@mui/material/TextField";
import Box from "@mui/material/Box";
import Typography from "@mui/material/Typography";
import SearchIcon from "@mui/icons-material/Search";
import InputAdornment from "@mui/material/InputAdornment";
import type { Paper } from "../types";
import { autocompletePapers } from "../api";

interface SearchBarProps {
  onSelect: (paper: Paper) => void;
}

export default function SearchBar({ onSelect }: SearchBarProps) {
  const [options, setOptions] = useState<Paper[]>([]);
  const [loading, setLoading] = useState(false);
  const [inputValue, setInputValue] = useState("");

  const debounceTimer = useRef<ReturnType<typeof setTimeout> | null>(null);

  const handleInputChange = useCallback(
    (_: unknown, value: string) => {
      setInputValue(value);
      if (debounceTimer.current) clearTimeout(debounceTimer.current);

      if (value.length < 2) {
        setOptions([]);
        return;
      }

      debounceTimer.current = setTimeout(async () => {
        setLoading(true);
        try {
          const results = await autocompletePapers(value);
          setOptions(results);
        } catch {
          setOptions([]);
        } finally {
          setLoading(false);
        }
      }, 300);
    },
    []
  );

  return (
    <Autocomplete
      freeSolo
      options={options}
      loading={loading}
      inputValue={inputValue}
      onInputChange={handleInputChange}
      getOptionLabel={(option) =>
        typeof option === "string" ? option : option.title
      }
      onChange={(_, value) => {
        if (value && typeof value !== "string") {
          onSelect(value);
        }
      }}
      renderOption={({ key, ...props }, option) => (
        <Box component="li" key={key} {...props} sx={{ display: "flex", justifyContent: "space-between", gap: 1 }}>
          <Box sx={{ minWidth: 0 }}>
            <Typography variant="body2" noWrap sx={{ fontWeight: 500 }}>
              {option.title}
            </Typography>
            <Typography variant="caption" color="text.secondary" noWrap>
              {option.creators} &middot; {option.date}
            </Typography>
          </Box>
          <Typography
            variant="caption"
            sx={{
              fontFamily: "'JetBrains Mono', monospace",
              color: "primary.main",
              flexShrink: 0,
            }}
          >
            {option.score.toFixed(2)}
          </Typography>
        </Box>
      )}
      renderInput={(params) => (
        <TextField
          {...params}
          placeholder="Search papers semantically..."
          size="small"
          slotProps={{
            input: {
              ...params.InputProps,
              startAdornment: (
                <InputAdornment position="start">
                  <SearchIcon sx={{ color: "primary.main", fontSize: 20 }} />
                </InputAdornment>
              ),
            },
          }}
        />
      )}
      sx={{ width: "100%" }}
    />
  );
}
```

- [ ] **Step 2: Verify build**

```bash
cd frontend && bun run vite build
```

- [ ] **Step 3: Commit**

```bash
git add frontend/src/components/SearchBar.tsx
git commit -m "feat: add SearchBar with debounced autocomplete"
```

---

### Task 10: DetailPanel Component

**Files:**
- Create: `frontend/src/components/DetailPanel.tsx`

- [ ] **Step 1: Create DetailPanel.tsx**

```tsx
import { useEffect, useState } from "react";
import Box from "@mui/material/Box";
import Card from "@mui/material/Card";
import Typography from "@mui/material/Typography";
import Chip from "@mui/material/Chip";
import Button from "@mui/material/Button";
import LinearProgress from "@mui/material/LinearProgress";
import Tooltip from "@mui/material/Tooltip";
import Skeleton from "@mui/material/Skeleton";
import MenuBookIcon from "@mui/icons-material/MenuBook";
import PictureAsPdfIcon from "@mui/icons-material/PictureAsPdf";
import ContentCopyIcon from "@mui/icons-material/ContentCopy";
import type { Paper, PaperDetail } from "../types";
import { getItemDetail } from "../api";

interface DetailPanelProps {
  paper: Paper | null;
}

export default function DetailPanel({ paper }: DetailPanelProps) {
  const [detail, setDetail] = useState<PaperDetail | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!paper) {
      setDetail(null);
      return;
    }
    setLoading(true);
    setError(null);
    getItemDetail(paper.key)
      .then(setDetail)
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }, [paper?.key]);

  if (!paper) return null;

  return (
    <Card
      variant="outlined"
      sx={{ p: 2.5, borderColor: "divider", bgcolor: "background.paper" }}
    >
      <Typography
        variant="caption"
        sx={{
          fontWeight: 600,
          textTransform: "uppercase",
          letterSpacing: 1.2,
          color: "primary.main",
          mb: 0.5,
          display: "block",
        }}
      >
        Selected Paper
      </Typography>

      <Typography
        variant="h6"
        sx={{
          fontFamily: "'Cormorant Garamond', serif",
          fontWeight: 700,
          lineHeight: 1.3,
          mb: 1,
        }}
      >
        {paper.title}
      </Typography>

      {loading ? (
        <Skeleton variant="text" width="80%" />
      ) : detail ? (
        <Typography variant="body2" color="text.secondary" sx={{ mb: 1 }}>
          {detail.authors.join(", ")}
        </Typography>
      ) : (
        <Typography variant="body2" color="text.secondary" sx={{ mb: 1 }}>
          {paper.creators}
        </Typography>
      )}

      <Box sx={{ display: "flex", gap: 1, mb: 1.5, flexWrap: "wrap" }}>
        <Chip label={paper.date || "n.d."} size="small" variant="outlined" />
        <Chip label={paper.itemType} size="small" variant="outlined" />
      </Box>

      <Box sx={{ display: "flex", alignItems: "center", gap: 1, mb: 1.5 }}>
        <Typography variant="caption" color="text.secondary">
          Similarity
        </Typography>
        <LinearProgress
          variant="determinate"
          value={paper.score * 100}
          sx={{ flex: 1, height: 6, borderRadius: 3 }}
        />
        <Typography
          variant="caption"
          sx={{ fontFamily: "'JetBrains Mono', monospace", fontWeight: 500 }}
        >
          {paper.score.toFixed(2)}
        </Typography>
      </Box>

      {detail?.abstract && (
        <>
          <Typography
            variant="caption"
            sx={{
              fontWeight: 600,
              textTransform: "uppercase",
              letterSpacing: 1,
              color: "text.secondary",
              display: "block",
              mb: 0.5,
            }}
          >
            Abstract
          </Typography>
          <Typography
            variant="body2"
            color="text.secondary"
            sx={{ lineHeight: 1.6, mb: 1.5 }}
          >
            {detail.abstract.length > 300
              ? detail.abstract.slice(0, 300) + "..."
              : detail.abstract}
          </Typography>
        </>
      )}

      {detail?.tags && detail.tags.length > 0 && (
        <Box sx={{ display: "flex", gap: 0.5, flexWrap: "wrap", mb: 2 }}>
          {detail.tags.map((tag) => (
            <Chip key={tag} label={tag} size="small" variant="outlined" sx={{ fontSize: 11 }} />
          ))}
        </Box>
      )}

      {error && (
        <Typography variant="caption" color="error" sx={{ mb: 1, display: "block" }}>
          Zotero unavailable — showing basic info
        </Typography>
      )}

      <Box sx={{ display: "flex", gap: 1, borderTop: 1, borderColor: "divider", pt: 1.5 }}>
        {detail && (
          <Tooltip title="Open in Zotero desktop" arrow>
            <Button
              size="small"
              variant="contained"
              startIcon={<MenuBookIcon />}
              href={detail.zoteroLink}
              sx={{ textTransform: "none", fontSize: 12 }}
            >
              Zotero
            </Button>
          </Tooltip>
        )}
        <Tooltip title="Copy BibTeX to clipboard" arrow>
          <Button
            size="small"
            variant="outlined"
            startIcon={<ContentCopyIcon />}
            onClick={() => navigator.clipboard.writeText(`@article{${paper.key}}`)}
            sx={{ textTransform: "none", fontSize: 12 }}
          >
            BibTeX
          </Button>
        </Tooltip>
      </Box>
    </Card>
  );
}
```

- [ ] **Step 2: Verify build**

```bash
cd frontend && bun run vite build
```

- [ ] **Step 3: Commit**

```bash
git add frontend/src/components/DetailPanel.tsx
git commit -m "feat: add DetailPanel with metadata, actions, and Zotero link"
```

---

### Task 11: PaperNode Component

**Files:**
- Create: `frontend/src/components/PaperNode.tsx`

- [ ] **Step 1: Create PaperNode.tsx**

```tsx
import { memo } from "react";
import { Handle, Position, type NodeProps } from "@xyflow/react";
import Box from "@mui/material/Box";
import Typography from "@mui/material/Typography";
import Tooltip from "@mui/material/Tooltip";

interface PaperNodeData {
  title: string;
  creators: string;
  date: string;
  score: number;
  depth: number;
  onNodeClick: (key: string) => void;
  [key: string]: unknown;
}

function PaperNode({ id, data }: NodeProps & { data: PaperNodeData }) {
  const { title, creators, date, score, depth, onNodeClick } = data;
  const isCenter = depth === 0;
  const isFar = depth >= 2;

  return (
    <Tooltip
      title={
        <Box>
          <Typography variant="body2" sx={{ fontWeight: 600 }}>{title}</Typography>
          <Typography variant="caption" sx={{ opacity: 0.7 }}>{creators} &middot; {date}</Typography>
          <Typography variant="caption" sx={{ display: "block", color: "primary.main", fontFamily: "'JetBrains Mono', monospace", mt: 0.5 }}>
            Similarity: {score.toFixed(2)}
          </Typography>
          {!isCenter && (
            <Typography variant="caption" sx={{ display: "block", opacity: 0.5, fontStyle: "italic", mt: 0.5 }}>
              Click to re-center
            </Typography>
          )}
        </Box>
      }
      arrow
      placement="top"
    >
      <Box
        onClick={() => !isCenter && onNodeClick(id)}
        sx={{
          px: 1.5,
          py: 1,
          borderRadius: 2,
          cursor: isCenter ? "default" : "pointer",
          maxWidth: 180,
          bgcolor: isCenter ? "secondary.main" : "background.paper",
          color: isCenter ? "background.default" : "text.primary",
          border: 2,
          borderColor: isCenter ? "primary.main" : "divider",
          opacity: isFar ? 0.7 : 1,
          fontSize: isFar ? 11 : isCenter ? 13 : 12,
          fontWeight: isCenter ? 600 : 500,
          boxShadow: 1,
          transition: "transform 0.2s, box-shadow 0.2s",
          "&:hover": isCenter
            ? {}
            : { transform: "scale(1.05)", boxShadow: 3 },
        }}
      >
        <Typography
          variant="body2"
          noWrap
          sx={{ fontSize: "inherit", fontWeight: "inherit" }}
        >
          {title}
        </Typography>
        <Typography
          variant="caption"
          sx={{
            fontFamily: "'JetBrains Mono', monospace",
            fontSize: 10,
            color: isCenter ? "divider" : "primary.main",
            display: "block",
          }}
        >
          {isCenter ? "center" : score.toFixed(2)}
        </Typography>
        <Handle type="source" position={Position.Right} style={{ visibility: "hidden" }} />
        <Handle type="target" position={Position.Left} style={{ visibility: "hidden" }} />
      </Box>
    </Tooltip>
  );
}

export default memo(PaperNode);
```

- [ ] **Step 2: Verify build**

```bash
cd frontend && bun run vite build
```

- [ ] **Step 3: Commit**

```bash
git add frontend/src/components/PaperNode.tsx
git commit -m "feat: add PaperNode custom ReactFlow node component"
```

---

### Task 12: GraphControls Component

**Files:**
- Create: `frontend/src/components/GraphControls.tsx`

- [ ] **Step 1: Create GraphControls.tsx**

```tsx
import Box from "@mui/material/Box";
import Slider from "@mui/material/Slider";
import Typography from "@mui/material/Typography";
import Paper from "@mui/material/Paper";

interface GraphControlsProps {
  cutoff: number;
  depth: number;
  onCutoffChange: (value: number) => void;
  onDepthChange: (value: number) => void;
}

export default function GraphControls({
  cutoff,
  depth,
  onCutoffChange,
  onDepthChange,
}: GraphControlsProps) {
  return (
    <Paper
      elevation={0}
      sx={(theme) => ({
        position: "absolute",
        top: 16,
        right: 16,
        zIndex: 10,
        p: 2,
        width: 200,
        bgcolor: theme.palette.mode === "dark"
          ? "rgba(38,34,32,0.92)"
          : "rgba(255,255,255,0.92)",
        backdropFilter: "blur(8px)",
        border: 1,
        borderColor: "divider",
        borderRadius: 2,
      })}
    >
      <Box sx={{ mb: 1.5 }}>
        <Typography
          variant="caption"
          sx={{
            fontWeight: 600,
            textTransform: "uppercase",
            letterSpacing: 1,
            color: "text.secondary",
            display: "flex",
            justifyContent: "space-between",
          }}
        >
          Similarity cutoff
          <Box
            component="span"
            sx={{ fontFamily: "'JetBrains Mono', monospace" }}
          >
            {cutoff.toFixed(2)}
          </Box>
        </Typography>
        <Slider
          value={cutoff}
          onChange={(_, v) => onCutoffChange(v as number)}
          min={0}
          max={1}
          step={0.05}
          size="small"
        />
      </Box>
      <Box>
        <Typography
          variant="caption"
          sx={{
            fontWeight: 600,
            textTransform: "uppercase",
            letterSpacing: 1,
            color: "text.secondary",
            display: "flex",
            justifyContent: "space-between",
          }}
        >
          Depth
          <Box
            component="span"
            sx={{ fontFamily: "'JetBrains Mono', monospace" }}
          >
            {depth}
          </Box>
        </Typography>
        <Slider
          value={depth}
          onChange={(_, v) => onDepthChange(v as number)}
          min={1}
          max={4}
          step={1}
          marks
          size="small"
        />
      </Box>
    </Paper>
  );
}
```

- [ ] **Step 2: Verify build**

```bash
cd frontend && bun run vite build
```

- [ ] **Step 3: Commit**

```bash
git add frontend/src/components/GraphControls.tsx
git commit -m "feat: add GraphControls with cutoff and depth sliders"
```

---

### Task 13: GraphView Component (ReactFlow + d3-force)

**Files:**
- Create: `frontend/src/components/GraphView.tsx`

- [ ] **Step 1: Create GraphView.tsx**

This is the most complex component — it converts API graph data into ReactFlow nodes/edges and runs d3-force for layout.

```tsx
import { useEffect, useMemo, useCallback, useRef } from "react";
import {
  ReactFlow,
  Controls,
  MiniMap,
  Background,
  useNodesState,
  useEdgesState,
  ReactFlowProvider,
  type Node,
  type Edge,
} from "@xyflow/react";
import { forceSimulation, forceLink, forceManyBody, forceCenter, forceCollide } from "d3-force";
import "@xyflow/react/dist/style.css";
import Box from "@mui/material/Box";
import Typography from "@mui/material/Typography";
import PaperNode from "./PaperNode";
import GraphControls from "./GraphControls";
import type { GraphData } from "../types";

const nodeTypes = { paper: PaperNode };

interface GraphViewProps {
  graphData: GraphData | null;
  cutoff: number;
  depth: number;
  onCutoffChange: (v: number) => void;
  onDepthChange: (v: number) => void;
  onNodeClick: (key: string) => void;
  loading: boolean;
}

interface SimNode {
  id: string;
  x: number;
  y: number;
}

interface SimLink {
  source: string;
  target: string;
  similarity: number;
}

function computeLayout(graphData: GraphData): { nodes: Node[]; edges: Edge[] } {
  if (!graphData.nodes.length) return { nodes: [], edges: [] };

  const simNodes: SimNode[] = graphData.nodes.map((n, i) => ({
    id: n.key,
    x: i === 0 ? 0 : (Math.random() - 0.5) * 600,
    y: i === 0 ? 0 : (Math.random() - 0.5) * 400,
  }));

  const simLinks: SimLink[] = graphData.edges.map((e) => ({
    source: e.source,
    target: e.target,
    similarity: e.similarity,
  }));

  const sim = forceSimulation(simNodes as any)
    .force(
      "link",
      forceLink(simLinks as any)
        .id((d: any) => d.id)
        .distance((d: any) => 150 * (1 - d.similarity + 0.2))
    )
    .force("charge", forceManyBody().strength(-300))
    .force("center", forceCenter(0, 0))
    .force("collide", forceCollide(60))
    .stop();

  // Run simulation synchronously
  for (let i = 0; i < 150; i++) sim.tick();

  const posMap = new Map<string, { x: number; y: number }>();
  simNodes.forEach((n: any) => posMap.set(n.id, { x: n.x, y: n.y }));

  const nodes: Node[] = graphData.nodes.map((n) => {
    const pos = posMap.get(n.key) || { x: 0, y: 0 };
    return {
      id: n.key,
      type: "paper",
      position: { x: pos.x, y: pos.y },
      data: {
        title: n.title,
        creators: n.creators,
        date: n.date,
        score: n.score,
        depth: n.depth,
        onNodeClick: () => {},  // will be set via props
      },
    };
  });

  const edges: Edge[] = graphData.edges.map((e, i) => ({
    id: `e-${i}`,
    source: e.source,
    target: e.target,
    style: {
      strokeWidth: Math.max(1, e.similarity * 3),
      opacity: 0.2 + e.similarity * 0.5,
    },
    animated: false,
  }));

  return { nodes, edges };
}

function GraphViewInner({
  graphData,
  cutoff,
  depth,
  onCutoffChange,
  onDepthChange,
  onNodeClick,
  loading,
}: GraphViewProps) {
  const [nodes, setNodes, onNodesChange] = useNodesState([]);
  const [edges, setEdges, onEdgesChange] = useEdgesState([]);

  useEffect(() => {
    if (!graphData) {
      setNodes([]);
      setEdges([]);
      return;
    }

    const { nodes: layoutNodes, edges: layoutEdges } = computeLayout(graphData);

    // Inject onNodeClick into each node's data
    const nodesWithClick = layoutNodes.map((n) => ({
      ...n,
      data: { ...n.data, onNodeClick },
    }));

    setNodes(nodesWithClick);
    setEdges(layoutEdges);
  }, [graphData, onNodeClick]);

  if (!graphData) {
    return (
      <Box
        sx={{
          display: "flex",
          flexDirection: "column",
          alignItems: "center",
          justifyContent: "center",
          height: "100%",
          color: "text.secondary",
        }}
      >
        <Typography variant="h5" sx={{ fontFamily: "'Cormorant Garamond', serif", mb: 1 }}>
          {loading ? "Loading..." : "Search to explore"}
        </Typography>
        <Typography variant="body2" color="text.secondary">
          Select a paper to see its similarity graph
        </Typography>
      </Box>
    );
  }

  return (
    <Box sx={{ height: "100%", position: "relative" }}>
      <GraphControls
        cutoff={cutoff}
        depth={depth}
        onCutoffChange={onCutoffChange}
        onDepthChange={onDepthChange}
      />
      <ReactFlow
        nodes={nodes}
        edges={edges}
        onNodesChange={onNodesChange}
        onEdgesChange={onEdgesChange}
        nodeTypes={nodeTypes}
        fitView
        fitViewOptions={{ padding: 0.3 }}
        minZoom={0.2}
        maxZoom={3}
        proOptions={{ hideAttribution: true }}
      >
        <Background />
        <Controls position="bottom-left" />
        <MiniMap
          position="bottom-right"
          nodeStrokeWidth={3}
          pannable
          zoomable
        />
      </ReactFlow>
    </Box>
  );
}

export default function GraphView(props: GraphViewProps) {
  return (
    <ReactFlowProvider>
      <GraphViewInner {...props} />
    </ReactFlowProvider>
  );
}
```

- [ ] **Step 2: Verify build**

```bash
cd frontend && bun run vite build
```

- [ ] **Step 3: Commit**

```bash
git add frontend/src/components/GraphView.tsx
git commit -m "feat: add GraphView with ReactFlow and d3-force spring layout"
```

---

### Task 14: Wire Everything Together in App.tsx

**Files:**
- Modify: `frontend/src/App.tsx`
- Modify: `frontend/src/main.tsx`

- [ ] **Step 1: Update main.tsx with theme provider**

```tsx
import React from "react";
import ReactDOM from "react-dom/client";
import App from "./App";

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>
);
```

- [ ] **Step 2: Implement App.tsx**

```tsx
import { useState, useEffect, useCallback, useMemo } from "react";
import { ThemeProvider } from "@mui/material/styles";
import CssBaseline from "@mui/material/CssBaseline";
import Box from "@mui/material/Box";
import { lightTheme, darkTheme } from "./theme";
import TopBar from "./components/TopBar";
import SearchBar from "./components/SearchBar";
import DetailPanel from "./components/DetailPanel";
import GraphView from "./components/GraphView";
import { getStatus, getNeighbors } from "./api";
import type { Paper, GraphData, IndexStatus } from "./types";

export default function App() {
  const [darkMode, setDarkMode] = useState(() => {
    return localStorage.getItem("riszotto-dark-mode") === "true";
  });
  const [status, setStatus] = useState<IndexStatus | null>(null);
  const [selectedPaper, setSelectedPaper] = useState<Paper | null>(null);
  const [graphData, setGraphData] = useState<GraphData | null>(null);
  const [graphLoading, setGraphLoading] = useState(false);
  const [cutoff, setCutoff] = useState(0.35);
  const [depth, setDepth] = useState(2);

  const theme = useMemo(() => (darkMode ? darkTheme : lightTheme), [darkMode]);

  const toggleDarkMode = useCallback(() => {
    setDarkMode((prev) => {
      const next = !prev;
      localStorage.setItem("riszotto-dark-mode", String(next));
      return next;
    });
  }, []);

  // Fetch status on mount
  useEffect(() => {
    getStatus().then(setStatus).catch(() => {});
  }, []);

  // Fetch graph when paper, cutoff, or depth changes
  const fetchGraph = useCallback(
    async (paperKey: string) => {
      setGraphLoading(true);
      try {
        const data = await getNeighbors(paperKey, cutoff, depth);
        setGraphData(data);
      } catch {
        setGraphData(null);
      } finally {
        setGraphLoading(false);
      }
    },
    [cutoff, depth]
  );

  useEffect(() => {
    if (selectedPaper) {
      fetchGraph(selectedPaper.key);
    }
  }, [selectedPaper?.key, cutoff, depth, fetchGraph]);

  const handlePaperSelect = useCallback((paper: Paper) => {
    setSelectedPaper(paper);
  }, []);

  const handleNodeClick = useCallback(
    (key: string) => {
      // Re-center: find the node in current graph data to build a Paper object
      const node = graphData?.nodes.find((n) => n.key === key);
      if (node) {
        setSelectedPaper({
          key: node.key,
          title: node.title,
          creators: node.creators,
          date: node.date,
          score: node.score,
          itemType: node.itemType,
        });
      }
    },
    [graphData]
  );

  return (
    <ThemeProvider theme={theme}>
      <CssBaseline />
      <Box sx={{ display: "flex", flexDirection: "column", height: "100vh" }}>
        <TopBar
          status={status}
          darkMode={darkMode}
          onToggleDarkMode={toggleDarkMode}
        />
        <Box sx={{ display: "flex", flex: 1, overflow: "hidden" }}>
          {/* Left Panel */}
          <Box
            sx={{
              width: 300,
              minWidth: 300,
              borderRight: 1,
              borderColor: "divider",
              display: "flex",
              flexDirection: "column",
              bgcolor: "background.default",
            }}
          >
            <Box sx={{ p: 2, pb: 0 }}>
              <SearchBar onSelect={handlePaperSelect} />
            </Box>
            <Box sx={{ flex: 1, overflow: "auto", p: 2 }}>
              <DetailPanel paper={selectedPaper} />
            </Box>
          </Box>

          {/* Right Panel — Graph */}
          <Box sx={{ flex: 1, position: "relative" }}>
            <GraphView
              graphData={graphData}
              cutoff={cutoff}
              depth={depth}
              onCutoffChange={setCutoff}
              onDepthChange={setDepth}
              onNodeClick={handleNodeClick}
              loading={graphLoading}
            />
          </Box>
        </Box>
      </Box>
    </ThemeProvider>
  );
}
```

- [ ] **Step 3: Add Google Fonts link to index.html**

Update `frontend/index.html` `<head>`:

```html
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Cormorant+Garamond:wght@400;600;700&family=Source+Sans+3:wght@300;400;500;600&family=JetBrains+Mono:wght@400;500&display=swap" rel="stylesheet">
```

- [ ] **Step 4: Verify full build**

```bash
cd frontend && bun run vite build
```

Expected: Build succeeds, all assets in `src/riszotto/static/`

- [ ] **Step 5: Commit**

```bash
git add frontend/
git commit -m "feat: wire up App with all components, theme, and state management"
```

---

## Phase 4: Integration and Polish

### Task 15: End-to-End Smoke Test

- [ ] **Step 1: Install web extras**

```bash
uv add fastapi uvicorn --optional web
uv sync --all-extras
```

- [ ] **Step 2: Build frontend**

```bash
cd frontend && bun run build
```

- [ ] **Step 3: Start the web UI**

```bash
uv run riszotto web --no-open --port 8080
```

Visit http://localhost:8080 and verify:
- Page loads with Warm Parchment theme
- Top bar shows "riszotto search"
- Search bar accepts input
- Dark mode toggle works
- If index exists: search returns results, clicking a result shows graph

- [ ] **Step 4: Run full test suite**

```bash
uv run pytest -v
```

Expected: All PASS

- [ ] **Step 5: Final commit**

```bash
git add -A
git commit -m "feat: complete semantic search web UI"
```
