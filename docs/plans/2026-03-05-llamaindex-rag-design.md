# LlamaIndex RAG Upgrade Design

## Problem

riszotto's semantic search embeds only metadata (title + authors + abstract + tags) per paper. The embedding model's 256-token limit truncates even abstracts. Results for specific queries surface irrelevant papers because the embeddings lack full-text content. For example, searching "BMIM BF4" returns a Zone 2 cardio training paper at rank 6.

## Solution

Replace the DIY ChromaDB approach in `semantic.py` with LlamaIndex's ingestion pipeline. Full PDF text is chunked, embedded, and stored — enabling semantic search over the actual paper content, not just metadata.

## Architecture

```
pyzotero (fetch items) → markitdown (PDF→text) → LlamaIndex (chunk→embed→store)
                                                      │
                                                      ├── SentenceSplitter (chunking)
                                                      ├── HuggingFaceEmbedding (bge-small-en-v1.5)
                                                      └── ChromaVectorStore (persistent storage)
```

### Indexing flow

1. Fetch all top-level items from Zotero via pyzotero
2. For each item: find PDF attachment via `get_pdf_attachments()` + `get_pdf_path()`
3. PDF found → `markitdown.convert(path)` → full text as Document
4. No PDF → title + abstract + tags + authors as Document
5. Each Document gets `doc_id=zotero_key` and `metadata={title, itemType, zotero_key}`
6. `VectorStoreIndex.from_documents()` → SentenceSplitter chunks → bge-small embeds → ChromaDB stores

### Search flow

1. Load index from persisted ChromaDB via `VectorStoreIndex.from_vector_store()`
2. `index.as_retriever(similarity_top_k=limit).retrieve(query)`
3. Deduplicate chunks: group by `zotero_key`, keep best score per paper
4. Return one result per paper with score

## Changes

### 1. Dependencies

```toml
[project.optional-dependencies]
semantic = [
    "llama-index-core>=0.14.0",
    "llama-index-vector-stores-chroma>=0.4.0",
    "llama-index-embeddings-huggingface>=0.5.0",
    "tqdm>=4.0.0",
]
```

ChromaDB and sentence-transformers come transitively. markitdown is already a base dependency.

### 2. Module: `src/riszotto/semantic.py` (rewrite)

Same public API, new internals:

- `build_index(zot, *, rebuild=False, limit=None)` — builds LlamaIndex Documents from Zotero items + PDFs, uses `VectorStoreIndex.from_documents()`. Incremental: checks existing `zotero_key`s in ChromaDB, skips them.
- `semantic_search(query, *, limit=10)` — loads index from ChromaDB, retrieves via `as_retriever()`, deduplicates chunks to unique papers, returns same result format.
- `get_index_status()` — same (count + path).

### 3. PDF handling

Uses existing `client.py` functions (`get_pdf_attachments`, `get_pdf_path`) to find PDFs. markitdown converts to text. Items without PDFs fall back to metadata-only documents.

### 4. Embedding model

`BAAI/bge-small-en-v1.5` via `llama-index-embeddings-huggingface`. 384-dim, outperforms all-MiniLM-L6-v2 on MTEB benchmarks.

### 5. Chunking

LlamaIndex's `SentenceSplitter` with default `chunk_size=1024`, `chunk_overlap=20`. Respects sentence boundaries.

### 6. CLI

No changes needed — `cli.py` already calls `semantic.build_index()` and `semantic.semantic_search()` with the same signatures.

### 7. Chunk deduplication

Multiple chunks from the same paper can match. `semantic_search()` groups by `zotero_key`, keeps the highest-scoring chunk per paper, returns one result per paper.

### 8. Incremental indexing

Check existing `zotero_key`s in ChromaDB collection metadata, skip items already indexed. Changed PDFs require `--rebuild`. Acceptable since PDF content rarely changes in Zotero.

### 9. Migration

Switching from the old metadata-only index requires a one-time `riszotto index --rebuild`.

## Storage

- Path: `~/.riszotto/chroma_db/` (unchanged)
- Size: ~50-200MB for 500 papers with full text (up from ~5MB metadata-only)
- Delete with `rm -rf ~/.riszotto/`

## Testing

- Unit tests mock LlamaIndex's `VectorStoreIndex` and `ChromaVectorStore`
- Test chunk deduplication (multiple chunks → one result per paper)
- Existing CLI tests pass unchanged (same public API)
