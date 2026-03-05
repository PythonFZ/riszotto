# Semantic Search Design

## Problem

riszotto only supports keyword search via Zotero's API. Users want to find related papers and search with natural language (e.g. "attention mechanisms in transformers" instead of exact terms).

## Changes

### 1. Optional dependency group

```toml
[project.optional-dependencies]
semantic = ["chromadb>=0.4.0", "sentence-transformers>=2.2.0"]
```

Install: `uv pip install riszotto[semantic]`

Base riszotto stays lightweight — semantic extras add ~500MB (ChromaDB + model).

### 2. New module: `src/riszotto/semantic.py`

- `build_index(zot, *, rebuild=False, limit=None)` — Fetches items from Zotero, constructs document text (title + authors + abstract + tags), upserts into ChromaDB. Incremental by default (skips existing keys). `rebuild=True` drops and recreates collection.
- `semantic_search(query, *, limit=10)` — Embeds query, finds nearest neighbors, returns list of result dicts with score.
- `get_index_status()` — Returns item count and DB path.
- ChromaDB persisted at `~/.riszotto/chroma_db/`
- Embedding: all-MiniLM-L6-v2 via ChromaDB's `DefaultEmbeddingFunction`
- Document IDs = Zotero item keys (enables upsert)

### 3. New CLI command: `riszotto index`

- `riszotto index` — Build/update index (incremental)
- `riszotto index --rebuild` — Full rebuild (drops and recreates)
- `riszotto index --status` — Show index stats (item count, DB path)
- Errors with helpful message if `[semantic]` extras not installed

### 4. New flag: `riszotto search --semantic`

- `riszotto search --semantic "attention mechanisms in transformers"`
- Same JSON envelope: `{page, limit, start, results: [...]}`
- Each result gets an extra `"score"` field (0-1, cosine similarity)
- Errors with helpful message if index doesn't exist or extras not installed
- `--semantic` is mutually exclusive with `--full-text`, `--tag`, `--item-type`, `--since`, `--sort`, `--direction` (semantic search has its own ranking)

### 5. Document text construction

```
{title} {author1}, {author2} {abstract} {tag1} {tag2}
```

Same approach as zotero-mcp but without fulltext — riszotto already has `show --search` for PDF content search.

### Storage

- Path: `~/.riszotto/chroma_db/`
- Size estimate: ~5-10MB for 500 papers, ~20-40MB for 2,000, ~100-200MB for 10,000
- Delete with `rm -rf ~/.riszotto/`
