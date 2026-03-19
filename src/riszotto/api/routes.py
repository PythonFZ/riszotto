"""API endpoint handlers."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query

from riszotto.client import discover_libraries, get_client, get_item
from riszotto.semantic import get_index_status, get_neighbors, semantic_search

router = APIRouter()


@router.get("/search")
def search(q: str = Query(..., min_length=1), limit: int = Query(10, ge=1, le=100)):
    """Semantic search for papers."""
    return semantic_search(q, limit=limit)


@router.get("/autocomplete")
def autocomplete(q: str = Query(..., min_length=1), limit: int = Query(5, ge=1, le=20)):
    """Autocomplete suggestions from semantic search."""
    return semantic_search(q, limit=limit)


@router.get("/neighbors/{item_key}")
def neighbors(
    item_key: str,
    cutoff: float = Query(0.35, ge=0.0, le=1.0),
    depth: int = Query(2, ge=1, le=4),
):
    """Get similarity graph around a paper."""
    result = get_neighbors(item_key, cutoff=cutoff, depth=depth)
    if not result["nodes"]:
        raise HTTPException(status_code=404, detail="Item not found in index")
    return result


@router.get("/item/{item_key}")
def item_detail(item_key: str):
    """Get full metadata for a single paper."""
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
