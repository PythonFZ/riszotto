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
