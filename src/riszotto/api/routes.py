"""API endpoint handlers."""

from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, HTTPException, Query

from riszotto.client import (
    discover_libraries,
    get_client,
    get_item,
    get_item_bibtex,
    get_pdf_attachments,
    search_items,
)
from riszotto.formatting import format_creator
from riszotto.semantic import get_index_status, get_neighbors, semantic_search

router = APIRouter()


@router.get("/search")
def search(
    q: str = Query(..., min_length=1),
    limit: int = Query(10, ge=1, le=100),
    mode: Literal["semantic", "fulltext", "title"] = Query("semantic"),
    library: str = Query("user_0"),
):
    """Search for papers.

    Parameters
    ----------
    q : str
        Search query.
    limit : int
        Maximum results.
    mode : str
        Search mode: "semantic" (embedding similarity), "fulltext" (all fields),
        or "title" (title/creator/year only).
    library : str
        ChromaDB collection name (e.g. "user_0", "group_12345").
    """
    if mode == "semantic":
        return semantic_search(q, limit=limit, collection_name=library)

    # For fulltext/title modes, use the Zotero search API
    try:
        zot = get_client()
        results = search_items(
            zot, q, full_text=(mode == "fulltext"), limit=limit
        )
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"Zotero unavailable: {e}")

    return [
        {
            "key": item.get("key", ""),
            "title": item.get("data", {}).get("title", ""),
            "creators": "; ".join(
                format_creator(c) for c in item.get("data", {}).get("creators", [])
            ),
            "date": item.get("data", {}).get("date", ""),
            "itemType": item.get("data", {}).get("itemType", ""),
            "score": 0,
        }
        for item in results
    ]


@router.get("/autocomplete")
def autocomplete(
    q: str = Query(..., min_length=1),
    limit: int = Query(5, ge=1, le=20),
    library: str = Query("user_0"),
):
    """Autocomplete suggestions from semantic search."""
    return semantic_search(q, limit=limit, collection_name=library)


@router.get("/neighbors/{item_key}")
def neighbors(
    item_key: str,
    cutoff: float = Query(0.35, ge=0.0, le=1.0),
    depth: int = Query(2, ge=1, le=4),
    library: str = Query("user_0"),
):
    """Get similarity graph around a paper."""
    result = get_neighbors(
        item_key, cutoff=cutoff, depth=depth, collection_name=library
    )
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
    authors = [format_creator(c) for c in data.get("creators", [])]

    pdf_attachments = []
    try:
        attachments = get_pdf_attachments(zot, item_key)
        for att in attachments:
            att_key = att.get("key", "")
            pdf_attachments.append({
                "key": att_key,
                "title": att.get("data", {}).get("title", "PDF"),
                "zoteroLink": f"zotero://open-pdf/library/items/{att_key}",
            })
    except Exception:
        pass

    return {
        "key": raw.get("key", item_key),
        "title": data.get("title", ""),
        "authors": authors,
        "abstract": data.get("abstractNote", ""),
        "tags": [t.get("tag", "") for t in data.get("tags", [])],
        "date": data.get("date", ""),
        "itemType": data.get("itemType", ""),
        "zoteroLink": f"zotero://select/library/items/{item_key}",
        "attachments": pdf_attachments,
    }


@router.get("/item/{item_key}/bibtex")
def item_bibtex(item_key: str):
    """Get BibTeX entry for a paper."""
    try:
        zot = get_client()
        bibtex = get_item_bibtex(zot, item_key)
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"Zotero unavailable: {e}")
    return {"bibtex": bibtex}


@router.get("/libraries")
def libraries():
    """List all accessible Zotero libraries."""
    return discover_libraries()


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
