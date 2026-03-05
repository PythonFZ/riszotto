"""Semantic search over Zotero items using ChromaDB embeddings."""

from __future__ import annotations

from pathlib import Path

from riszotto.formatting import format_creator

INDEX_DIR = Path.home() / ".riszotto" / "chroma_db"
BATCH_SIZE = 500

_CHILD_ITEM_TYPES = {"attachment", "note", "annotation"}


def _build_document_text(item: dict) -> str:
    """Concatenate item fields into a single string for embedding.

    Combines title, creators, abstract, and tags into one document.
    Handles missing fields gracefully and returns empty string if no content.
    """
    data = item.get("data", {})
    parts: list[str] = []

    title = data.get("title", "")
    if title:
        parts.append(title)

    creators = data.get("creators", [])
    for creator in creators:
        name = format_creator(creator)
        if name:
            parts.append(name)

    abstract = data.get("abstractNote", "")
    if abstract:
        parts.append(abstract)

    tags = data.get("tags", [])
    for tag_obj in tags:
        tag = tag_obj.get("tag", "")
        if tag:
            parts.append(tag)

    return " ".join(parts)


def _get_collection(*, rebuild: bool = False):
    """Get or create the ChromaDB collection.

    ChromaDB is imported inside this function so the base package
    works without the [semantic] extras installed.
    """
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
            pass

    return client.get_or_create_collection(name="zotero")


def build_index(zot, *, rebuild: bool = False, limit=None) -> dict[str, int]:
    """Build or update the semantic search index.

    Fetches items from Zotero and upserts their text into ChromaDB.
    In incremental mode (rebuild=False), skips items already in the index.
    """
    collection = _get_collection(rebuild=rebuild)

    fetch_limit = limit or 100
    items = zot.items(limit=fetch_limit, itemType="-attachment")

    # Filter out child items
    top_level = [
        item for item in items
        if item.get("data", {}).get("itemType", "").lower() not in _CHILD_ITEM_TYPES
    ]

    # In incremental mode, skip already-indexed items
    if not rebuild and collection.count() > 0:
        existing_ids = set(collection.get()["ids"])
    else:
        existing_ids = set()

    ids_to_upsert: list[str] = []
    docs_to_upsert: list[str] = []
    metas_to_upsert: list[dict] = []
    skipped = 0

    for item in top_level:
        data = item.get("data", {})
        key = data.get("key", "")

        if key in existing_ids:
            skipped += 1
            continue

        doc = _build_document_text(item)
        if not doc:
            skipped += 1
            continue

        ids_to_upsert.append(key)
        docs_to_upsert.append(doc)
        metas_to_upsert.append({
            "title": data.get("title", ""),
            "itemType": data.get("itemType", ""),
        })

    # Batch upsert in groups of BATCH_SIZE
    for i in range(0, len(ids_to_upsert), BATCH_SIZE):
        batch_end = i + BATCH_SIZE
        collection.upsert(
            ids=ids_to_upsert[i:batch_end],
            documents=docs_to_upsert[i:batch_end],
            metadatas=metas_to_upsert[i:batch_end],
        )

    return {"indexed": len(ids_to_upsert), "skipped": skipped}


def semantic_search(query: str, *, limit: int = 10) -> list[dict]:
    """Query the semantic index and return ranked results.

    Converts ChromaDB distances to similarity scores (1 - distance).
    """
    collection = _get_collection()
    results = collection.query(query_texts=[query], n_results=limit)

    ids = results.get("ids", [[]])[0]
    distances = results.get("distances", [[]])[0]
    metadatas = results.get("metadatas", [[]])[0]

    output: list[dict] = []
    for i, key in enumerate(ids):
        score = round(1 - distances[i], 4)
        meta = metadatas[i] if i < len(metadatas) else {}
        output.append({
            "key": key,
            "title": meta.get("title", ""),
            "itemType": meta.get("itemType", ""),
            "score": score,
        })

    return output


def get_index_status() -> dict:
    """Return the current state of the semantic index."""
    collection = _get_collection()
    return {
        "count": collection.count(),
        "path": str(INDEX_DIR),
    }
