"""Thin wrapper around pyzotero for local Zotero API access."""

from __future__ import annotations

from typing import Any
from urllib.parse import unquote, urlparse

from pyzotero import zotero


def get_client() -> zotero.Zotero:
    """Create a pyzotero client connected to the local Zotero instance."""
    return zotero.Zotero(
        library_id="0",
        library_type="user",
        api_key=None,
        local=True,
    )


_CHILD_ITEM_TYPES = {"attachment", "note", "annotation"}


def search_items(
    zot: zotero.Zotero,
    query: str,
    *,
    full_text: bool = False,
    limit: int = 25,
    start: int = 0,
    tag: list[str] | None = None,
    item_type: str | None = None,
    since: str | None = None,
    sort: str | None = None,
    direction: str | None = None,
) -> list[dict[str, Any]]:
    """Search the Zotero library, resolving child items to their parents."""
    qmode = "everything" if full_text else "titleCreatorYear"
    kwargs: dict[str, Any] = {"q": query, "qmode": qmode, "limit": limit, "start": start}
    if tag is not None:
        kwargs["tag"] = tag if len(tag) > 1 else tag[0]
    if item_type is not None:
        kwargs["itemType"] = item_type
    if since is not None:
        kwargs["since"] = since
    if sort is not None:
        kwargs["sort"] = sort
    if direction is not None:
        kwargs["direction"] = direction
    raw = zot.items(**kwargs)

    results: list[dict[str, Any]] = []
    seen_keys: set[str] = set()

    for item in raw:
        data = item.get("data", {})
        if data.get("itemType") in _CHILD_ITEM_TYPES:
            parent_key = data.get("parentItem")
            if not parent_key or parent_key in seen_keys:
                continue
            seen_keys.add(parent_key)
            results.append(zot.item(parent_key))
        else:
            key = data.get("key", "")
            if key in seen_keys:
                continue
            seen_keys.add(key)
            results.append(item)

    return results


def get_item(zot: zotero.Zotero, key: str) -> dict[str, Any]:
    """Get a single item by key."""
    return zot.item(key)


def get_pdf_attachments(zot: zotero.Zotero, key: str) -> list[dict[str, Any]]:
    """Get PDF attachments for an item."""
    children = zot.children(key)
    return [
        child
        for child in children
        if child.get("data", {}).get("contentType") == "application/pdf"
    ]


def list_collections(zot: zotero.Zotero) -> list[dict[str, Any]]:
    """Get all collections in the library."""
    return zot.collections()


def collection_items(
    zot: zotero.Zotero,
    collection_key: str,
    *,
    limit: int = 25,
    start: int = 0,
) -> list[dict[str, Any]]:
    """Get items in a specific collection."""
    return zot.collection_items(collection_key, limit=limit, start=start)


def get_pdf_path(attachment: dict[str, Any]) -> str | None:
    """Extract the local file path from an attachment's enclosure link."""
    href = attachment.get("links", {}).get("enclosure", {}).get("href")
    if not href:
        return None
    parsed = urlparse(href)
    if parsed.scheme == "file":
        return unquote(parsed.path)
    return None
