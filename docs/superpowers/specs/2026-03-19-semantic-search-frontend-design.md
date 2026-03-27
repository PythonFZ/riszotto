# Semantic Search Frontend — Design Spec

## Overview

An interactive web frontend for riszotto's semantic search, bundled as part of the Python package. Provides a search bar with autocomplete, a paper detail panel, and a ReactFlow-based similarity graph with spring/force layout. Launched via `riszotto web`.

## Architecture

```
┌──────────────────────────────────────────────────┐
│  Browser (React + MUI + ReactFlow)               │
│  ┌──────────┐  ┌──────────────────────────────┐  │
│  │ Search +  │  │  ReactFlow Graph             │  │
│  │ Detail    │  │  (d3-force spring layout)    │  │
│  │ Panel     │  │                              │  │
│  └──────────┘  └──────────────────────────────┘  │
└──────────────────┬───────────────────────────────┘
                   │ HTTP /api/*
┌──────────────────▼───────────────────────────────┐
│  FastAPI (thin wrapper)                          │
│  routes.py → semantic.py, client.py              │
└──────────────────────────────────────────────────┘
│  ChromaDB        │  Zotero Local API             │
└──────────────────┴───────────────────────────────┘
```

- **Backend**: FastAPI app in `src/riszotto/api/`, reusing existing `semantic.py` and `client.py` — zero logic duplication.
- **Frontend**: Vite + React + TypeScript in `frontend/`, built assets served from `src/riszotto/static/`.
- **CLI**: New `riszotto web [--port 8080] [--no-open]` command starts the server and opens the browser (unless `--no-open`).
- **Library scope**: The web UI targets the default personal library (`user_0`) initially. Multi-library selection is out of scope for v1.

## Hard Constraint: No Code Duplication

The API layer is a thin wrapper that calls existing modules. Before writing any new data-access or search logic, check if it already exists in `semantic.py`, `client.py`, or `config.py`. If two places need the same logic, extract it into a shared function first.

## UI Layout

Single-page app with two panels:

### Left Panel (300px, fixed width)

1. **Search bar** (top) — MUI `Autocomplete` with `freeSolo`, debounced semantic search. Shows ranked results with title, authors, year, similarity score. Keyboard shortcut: Cmd+K / Ctrl+K.

2. **Detail card** (below) — Appears when a paper is selected (from autocomplete or by clicking a graph node). Shows:
   - Title, authors, year, item type
   - Similarity score bar
   - Abstract (truncated with expand)
   - Tags
   - Action buttons:
     - **Open in Zotero** — `zotero://select/items/{key}` protocol link (MUI Tooltip: "Opens this item in Zotero desktop")
     - **PDF** — opens attached PDF via the API (MUI Tooltip: "View attached PDF")
     - **BibTeX** — copies citation to clipboard (MUI Tooltip: "Copy BibTeX to clipboard")

### Right Panel (flex, remaining width)

1. **ReactFlow canvas** — similarity graph with spring/force layout via d3-force.
   - **Center node**: Selected paper, highlighted with accent border, pinned to center.
   - **Depth-1 nodes**: Direct neighbors above similarity cutoff. White/surface background, solid border.
   - **Depth-2+ nodes**: Neighbors of neighbors. Smaller, more transparent.
   - **Edges**: Thickness and opacity scale with similarity score.
   - **Node tooltips** (MUI Tooltip): Full title, authors, year, score, "Click to re-center".
   - **Click a node**: Re-centers the graph on that paper (fetches its neighbors, rebuilds layout).

2. **Controls overlay** (top-right):
   - Similarity cutoff slider (MUI Slider, 0.0–1.0, default 0.35)
   - Depth slider (MUI Slider, 1–4, default 2)

3. **Zoom controls** (bottom-left): ReactFlow `<Controls />` component (+, -, Fit).

4. **Minimap** (bottom-right): ReactFlow `<MiniMap />`.

### Top Bar

- Logo: "riszotto search"
- Index stats: paper count, library count (from `/api/status`)
- Dark/light mode toggle: MUI IconButton (sun/moon), persisted to localStorage

## Theme: Warm Parchment

### Light Mode

| Token | Value | Usage |
|---|---|---|
| `background` | `#f8f4ec` | Page background |
| `surface` | `#fff` | Cards, dropdowns |
| `headerBg` | `#f2ece0` | Top bar, column headers |
| `border` | `#e2d8c8` | Dividers, card borders |
| `textPrimary` | `#3a3228` | Headings, titles |
| `textSecondary` | `#8a7a62` | Metadata, labels |
| `accent` | `#b8956a` | Active elements, scores, highlights |
| `accentLight` | `#d4c8b0` | Slider tracks, inactive borders |

### Dark Mode

| Token | Value | Usage |
|---|---|---|
| `background` | `#1c1a16` | Page background |
| `surface` | `#262220` | Cards, dropdowns |
| `headerBg` | `#201e1a` | Top bar |
| `border` | `#3a3428` | Dividers |
| `textPrimary` | `#e8e0d4` | Headings, titles |
| `textSecondary` | `#9a8a72` | Metadata |
| `accent` | `#d4a574` | Slightly brighter accent |
| `accentLight` | `#4a4238` | Slider tracks |

### Typography

- **Headers/Logo**: Cormorant Garamond (serif), 700
- **Body/UI**: Source Sans 3, 400/500/600
- **Monospace** (scores, stats): JetBrains Mono, 400/500

Implemented via MUI `createTheme` with custom palette and typography overrides. Dark mode toggled via `ThemeProvider` context.

## Force Layout (d3-force)

ReactFlow renders nodes and edges. d3-force computes positions:

- `forceLink()` — edge length inversely proportional to similarity (high similarity = close together)
- `forceManyBody()` — repulsion to prevent clustering
- `forceCenter()` — center node gravitates to viewport center
- `forceCollide()` — prevents node label overlap

Layout recalculates when:
- Center node changes (user clicks a node or selects from autocomplete)
- Cutoff or depth sliders change

Animated position transitions using ReactFlow's built-in node animation.

### Custom Node Component

Single `PaperNode` component renders all depth levels. Props determine visual treatment:
- `depth: 0` → center style (dark bg, accent border, larger text)
- `depth: 1` → direct neighbor (surface bg, solid border)
- `depth: 2+` → distant neighbor (surface bg, light border, smaller, reduced opacity)

MUI `Tooltip` wraps each node.

## API Endpoints

All in `src/riszotto/api/routes.py`. Thin wrappers around existing modules.

### `GET /api/search?q={query}&limit=10`

Calls `semantic.semantic_search()`.

**Metadata enrichment required**: The current `build_index()` only stores `title` and `itemType` in ChromaDB metadata. To return `authors` and `year` in search results without a per-query Zotero lookup, `build_index()` must be updated to also store `creators` (formatted as author string) and `date`/`year` in the ChromaDB metadata at index time. This is a one-time change to `semantic.py` and requires a re-index (`riszotto index --rebuild`).

Returns: `[{key, title, authors, year, score, itemType}]`

### `GET /api/autocomplete?q={query}&limit=5`

Same `semantic.semantic_search()` with smaller limit. Could be merged into `/api/search` with a `limit` parameter, but keeping it separate allows future optimization (e.g., prefix matching vs full semantic search).

Returns: `[{key, title, authors, year, score}]`

### `GET /api/neighbors/{item_key}?cutoff=0.35&depth=2`

**New function**: `semantic.get_neighbors(item_key, cutoff, depth)`.

Queries ChromaDB for the item's embedding via `collection.get(ids=[item_key], include=["embeddings"])`, then uses that embedding with `collection.query(query_embeddings=...)` to find similar items above cutoff. Recursively expands neighbors up to depth.

**Performance bounds**: Recursive expansion can fan out quickly. To prevent runaway queries:
- Hard cap of **50 nodes** total in the returned graph, regardless of depth/cutoff settings.
- Each depth level queries at most 10 neighbors per node.
- If the cap is reached, stop expansion and return what we have. The frontend should indicate truncation.

Returns graph structure:

```json
{
  "nodes": [
    {"key": "ABC123", "title": "...", "authors": [...], "year": "2017", "depth": 0, "score": 1.0},
    {"key": "DEF456", "title": "...", "authors": [...], "year": "2019", "depth": 1, "score": 0.87}
  ],
  "edges": [
    {"source": "ABC123", "target": "DEF456", "similarity": 0.87}
  ]
}
```

### `GET /api/item/{item_key}`

Calls `client.py` to fetch full metadata for the detail panel.

Returns: `{key, title, authors, abstract, tags, date, itemType, zoteroLink, attachments}`

### `GET /api/status`

Returns aggregated index status across all libraries.

**Prerequisite refactor**: The current `get_index_status()` returns `{count, path}` for a single collection. Multi-library discovery logic currently lives in `cli.py`'s `_discover_libraries()`, tightly coupled to Typer/CLI concerns. Before the API can use it, extract the library discovery logic into a shared function in `client.py` (e.g., `discover_libraries() -> list[dict]`) that both `cli.py` and `api/routes.py` can call. This extraction is required before implementing this endpoint.

Returns: `{total_papers, libraries: [{name, count}]}`

## Project Structure

```
frontend/                     # Vite + React + TypeScript
  package.json                # bun as package manager
  bun.lock
  vite.config.ts
  tsconfig.json
  index.html
  src/
    main.tsx
    App.tsx
    theme.ts                  # Warm Parchment light/dark MUI themes
    api.ts                    # fetch wrappers for /api/* endpoints
    components/
      TopBar.tsx              # logo, stats, dark mode toggle
      SearchBar.tsx           # MUI Autocomplete + debounced search
      DetailPanel.tsx         # selected paper metadata + actions
      GraphView.tsx           # ReactFlow canvas + d3-force layout
      PaperNode.tsx           # custom ReactFlow node component
      GraphControls.tsx       # cutoff/depth sliders overlay

src/riszotto/
  api/
    __init__.py               # FastAPI app factory
    routes.py                 # all endpoints
    deps.py                   # shared dependencies (semantic index, client)
  semantic.py                 # existing + new get_neighbors()
  client.py                   # existing, unchanged
  cli.py                      # existing + new `web` command
  static/                     # built frontend assets (gitignored)
```

## Build & Packaging

- `bun run build` in `frontend/` outputs to `src/riszotto/static/`
- FastAPI serves `static/` with `StaticFiles(directory="static", html=True)` for SPA fallback
- `pyproject.toml` adds optional dependency group:
  ```toml
  [project.optional-dependencies]
  web = ["fastapi>=0.100.0", "uvicorn>=0.20.0"]
  ```
- Install: `pip install riszotto[web]` or `uv add riszotto[web]`
- Run: `riszotto web [--port 8080]`
- **Hatch build config**: `pyproject.toml` needs `[tool.hatch.build.targets.wheel]` configuration to force-include `src/riszotto/static/` in the wheel, since it's gitignored and not picked up automatically

## Dev Workflow

There is one CLI command: `riszotto web [--port 8080]`. In development, run the backend and frontend separately:

- Frontend dev: `cd frontend && bun run dev` — Vite dev server with HMR, proxies `/api/*` to FastAPI
- Backend dev: `uv run riszotto web --no-open` — starts FastAPI on port 8000 (API only, no browser auto-open)
- Vite config proxies `/api/*` to `localhost:8000`
- Production: `bun run build` then `riszotto web` serves everything from one process

## Frontend Dependencies

- `react`, `react-dom`
- `@xyflow/react` (ReactFlow v12)
- `@mui/material`, `@emotion/react`, `@emotion/styled`
- `d3-force` (layout computation)
- `typescript`, `vite`, `@vitejs/plugin-react`

## Empty State

When no search query is active and no paper is selected:
- Left panel: search bar only, no detail card
- Right panel: empty graph area with index stats (paper count, libraries) centered as placeholder text
- Invites user to search

## Error Handling

- Index not built: show message "No index found. Run `riszotto index` to build one." with terminal command copyable.
- Zotero not running: graceful error on `/api/item/*` calls, detail panel shows "Zotero unavailable" with retry button. The graph (which uses only ChromaDB data) continues to work without Zotero — only the detail panel degrades.
- Empty search results: "No papers found for this query" in autocomplete dropdown.

## Out of Scope (Future)

- Full library cluster overview (precomputed cluster map)
- Saved searches / bookmarks
- Multi-library graph overlay
- Export graph as image
