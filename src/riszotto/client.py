"""Thin wrapper around pyzotero for local Zotero API access."""

from __future__ import annotations

import re
from typing import Any
from urllib.parse import unquote, urlparse

from pyzotero import zotero
from pyzotero.zotero_errors import PyZoteroError

from riszotto.config import load_config
from riszotto.formatting import CHILD_ITEM_TYPES

DEFAULT_BIBTEX_EXCLUDE: set[str] = {
    "file",
    "abstract",
    "note",
    "keywords",
    "urldate",
    "annote",
}


class LibraryNotFoundError(Exception):
    """Raised when a requested library/group cannot be found."""


class AmbiguousLibraryError(Exception):
    """Raised when a library name matches multiple groups."""


def find_group(groups: list[dict[str, Any]], library: str) -> dict[str, Any] | None:
    """Match a library name or ID against a list of Zotero groups.

    Resolution order (first match wins):
    1. Case-insensitive exact name match
    2. Case-insensitive substring name match (unique only)
    3. Numeric group ID match

    Parameters
    ----------
    groups : list[dict[str, Any]]
        List of group dicts from pyzotero's ``groups()`` method.
    library : str
        User-provided library name or numeric ID.

    Returns
    -------
    dict[str, Any] or None
        The matched group dict, or None if no match found.

    Raises
    ------
    AmbiguousLibraryError
        If substring matching yields multiple results.
    """
    needle = library.lower()

    # 1. Exact name match
    for group in groups:
        if group["data"]["name"].lower() == needle:
            return group

    # 2. Substring name match
    substring_matches = [g for g in groups if needle in g["data"]["name"].lower()]
    if len(substring_matches) == 1:
        return substring_matches[0]
    if len(substring_matches) > 1:
        names = [g["data"]["name"] for g in substring_matches]
        raise AmbiguousLibraryError(
            f"'{library}' matches multiple groups: {names}. "
            "Use a more specific name or the group ID."
        )

    # 3. Numeric ID match
    try:
        numeric_id = int(library)
        for group in groups:
            if group["id"] == numeric_id:
                return group
    except ValueError:
        pass

    return None


def get_client(library: str | None = None) -> zotero.Zotero:
    """Create a pyzotero client, optionally targeting a group library.

    Parameters
    ----------
    library : str or None
        Group name or numeric ID. If None, returns the personal library client.

    Returns
    -------
    zotero.Zotero
        A configured pyzotero client.

    Raises
    ------
    LibraryNotFoundError
        If the requested group cannot be found locally or remotely.
    AmbiguousLibraryError
        If the name matches multiple groups.
    """
    if library is None:
        return zotero.Zotero(
            library_id="0",
            library_type="user",
            api_key=None,
            local=True,
        )

    config = load_config()

    # Try local first
    local_client = zotero.Zotero(library_id="0", library_type="user", local=True)
    try:
        local_groups = local_client.groups()
        match = find_group(local_groups, library)
        if match:
            return zotero.Zotero(
                library_id=str(match["id"]),
                library_type="group",
                local=True,
            )
    except (ConnectionError, OSError, PyZoteroError):
        pass  # local API not available

    # Fall back to remote
    if not config.has_remote_credentials:
        raise LibraryNotFoundError(
            f"Group '{library}' not found locally. "
            "Configure api_key and user_id in ~/.riszotto/config.toml "
            "for remote access."
        )

    remote_client = zotero.Zotero(
        library_id=config.user_id,
        library_type="user",
        api_key=config.api_key,
    )
    remote_groups = remote_client.groups()
    match = find_group(remote_groups, library)
    if match:
        return zotero.Zotero(
            library_id=str(match["id"]),
            library_type="group",
            api_key=config.api_key,
        )

    available = [g["data"]["name"] for g in remote_groups]
    raise LibraryNotFoundError(f"Group '{library}' not found. Available: {available}")


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
    kwargs: dict[str, Any] = {
        "q": query,
        "qmode": qmode,
        "limit": limit,
        "start": start,
    }
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
        if data.get("itemType") in CHILD_ITEM_TYPES:
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


def recent_items(
    zot: zotero.Zotero,
    *,
    limit: int = 10,
) -> list[dict[str, Any]]:
    """Get recently added items, excluding attachments."""
    return zot.items(
        sort="dateAdded", direction="desc", limit=limit, itemType="-attachment"
    )


def get_item_bibtex(
    zot: zotero.Zotero, key: str, *, exclude: set[str] | None = None
) -> str:
    """Get a single item's BibTeX entry, optionally stripping fields."""
    result = zot.item(key, format="bibtex")
    bibtex = result.decode("utf-8") if isinstance(result, bytes) else str(result)
    if exclude:
        bibtex = _filter_bibtex_fields(bibtex, exclude)
    return bibtex


def _filter_bibtex_fields(bibtex: str, exclude: set[str]) -> str:
    """Remove fields from a BibTeX entry string.

    Uses line-by-line brace counting to handle multi-line values (e.g. abstracts).
    """
    lines = bibtex.splitlines(keepends=True)
    result: list[str] = []
    skipping = False
    brace_depth = 0

    field_re = re.compile(r"^\s*(\w+)\s*=\s*")

    for line in lines:
        if skipping:
            brace_depth += line.count("{") - line.count("}")
            if brace_depth <= 0:
                skipping = False
                brace_depth = 0
            continue

        m = field_re.match(line)
        if m and m.group(1) in exclude:
            brace_depth = line.count("{") - line.count("}")
            if brace_depth > 0:
                skipping = True
            continue

        result.append(line)

    # Clean up trailing comma before closing brace
    text = "".join(result)
    text = re.sub(r",\s*\n(\s*})", r"\n\1", text)
    return text


def get_pdf_path(attachment: dict[str, Any]) -> str | None:
    """Extract the local file path from an attachment's enclosure link."""
    href = attachment.get("links", {}).get("enclosure", {}).get("href")
    if not href:
        return None
    parsed = urlparse(href)
    if parsed.scheme == "file":
        return unquote(parsed.path)
    return None
