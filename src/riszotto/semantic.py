"""Semantic search over Zotero items using ChromaDB embeddings."""

from __future__ import annotations

from pathlib import Path

from riszotto.formatting import CHILD_ITEM_TYPES, format_creator

INDEX_DIR = Path.home() / ".riszotto" / "chroma_db"
BATCH_SIZE = 500


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


def _get_collection(*, rebuild: bool = False, collection_name: str = "user_0"):
    """Get or create a ChromaDB collection by name.

    ChromaDB is imported inside this function so the base package
    works without the [semantic] extras installed.
    """
    import chromadb
    from chromadb.config import Settings
    from chromadb.errors import NotFoundError

    client = chromadb.PersistentClient(
        path=str(INDEX_DIR),
        settings=Settings(anonymized_telemetry=False, allow_reset=True),
    )

    if rebuild:
        try:
            client.delete_collection(name=collection_name)
        except (ValueError, NotFoundError):
            pass

    return client.get_or_create_collection(
        name=collection_name,
        metadata={"hnsw:space": "cosine"},
    )


def build_index(
    zot,
    *,
    rebuild: bool = False,
    limit: int | None = None,
    collection_name: str = "user_0",
) -> dict[str, int]:
    """Build or update the semantic search index.

    Fetches items from Zotero and upserts their text into ChromaDB.
    In incremental mode (rebuild=False), skips items already in the index.
    """
    collection = _get_collection(rebuild=rebuild, collection_name=collection_name)

    if limit is not None:
        items = zot.top(limit=limit)
    else:
        items = zot.everything(zot.top())

    # Filter out child items
    top_level = [
        item
        for item in items
        if item.get("data", {}).get("itemType", "").lower() not in CHILD_ITEM_TYPES
    ]

    # In incremental mode, skip already-indexed items
    if not rebuild and collection.count() > 0:
        existing_ids = set(collection.get(include=[])["ids"])
    else:
        existing_ids = set()

    from tqdm import tqdm

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
        metas_to_upsert.append(
            {
                "title": data.get("title", ""),
                "itemType": data.get("itemType", ""),
                "creators": "; ".join(
                    format_creator(c) for c in data.get("creators", [])
                ),
                "date": data.get("date", ""),
            }
        )

    # Batch upsert in groups of BATCH_SIZE
    for i in tqdm(
        range(0, len(ids_to_upsert), BATCH_SIZE), desc="Upserting", unit="batch"
    ):
        batch_end = i + BATCH_SIZE
        collection.upsert(
            ids=ids_to_upsert[i:batch_end],
            documents=docs_to_upsert[i:batch_end],
            metadatas=metas_to_upsert[i:batch_end],
        )

    return {"indexed": len(ids_to_upsert), "skipped": skipped}


def semantic_search(
    query: str, *, limit: int = 10, collection_name: str = "user_0"
) -> list[dict]:
    """Query the semantic index and return ranked results.

    Converts ChromaDB distances to similarity scores (1 - distance).
    """
    collection = _get_collection(collection_name=collection_name)

    if collection.count() == 0:
        return []

    results = collection.query(query_texts=[query], n_results=limit)

    ids = results.get("ids", [[]])[0]
    distances = results.get("distances", [[]])[0]
    metadatas = results.get("metadatas", [[]])[0]

    output: list[dict] = []
    for i, key in enumerate(ids):
        score = round(1 - distances[i], 4)
        meta = metadatas[i] if i < len(metadatas) else {}
        output.append(
            {
                "key": key,
                "title": meta.get("title", ""),
                "itemType": meta.get("itemType", ""),
                "creators": meta.get("creators", ""),
                "date": meta.get("date", ""),
                "score": score,
            }
        )

    return output


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

    nodes.append(
        {
            "key": item_key,
            "title": center_meta.get("title", ""),
            "itemType": center_meta.get("itemType", ""),
            "creators": center_meta.get("creators", ""),
            "date": center_meta.get("date", ""),
            "depth": 0,
            "score": 1.0,
        }
    )
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

            edges.append(
                {
                    "source": source_key,
                    "target": neighbor_key,
                    "similarity": similarity,
                }
            )

            if neighbor_key not in seen_keys:
                seen_keys.add(neighbor_key)
                nodes.append(
                    {
                        "key": neighbor_key,
                        "title": meta.get("title", ""),
                        "itemType": meta.get("itemType", ""),
                        "creators": meta.get("creators", ""),
                        "date": meta.get("date", ""),
                        "depth": current_depth + 1,
                        "score": similarity,
                    }
                )
                frontier.append((neighbor_key, neighbor_embedding, current_depth + 1))

    return {"nodes": nodes, "edges": edges}


def get_index_status(*, collection_name: str = "user_0") -> dict:
    """Return the current state of the semantic index."""
    collection = _get_collection(collection_name=collection_name)
    return {
        "count": collection.count(),
        "path": str(INDEX_DIR),
    }
