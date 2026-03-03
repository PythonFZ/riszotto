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
) -> list[dict[str, Any]]:
    """Search the Zotero library, resolving child items to their parents."""
    qmode = "everything" if full_text else "titleCreatorYear"
    raw = zot.items(q=query, qmode=qmode, limit=limit, start=start)

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


def get_pdf_path(attachment: dict[str, Any]) -> str | None:
    """Extract the local file path from an attachment's enclosure link."""
    href = attachment.get("links", {}).get("enclosure", {}).get("href")
    if not href:
        return None
    parsed = urlparse(href)
    if parsed.scheme == "file":
        return unquote(parsed.path)
    return None
