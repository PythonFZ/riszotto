"""riszotto CLI — search and read papers from your local Zotero library."""

from __future__ import annotations

import json
import unicodedata
from typing import Annotated, Optional

import typer
from markitdown import MarkItDown
from pyzotero import zotero
from pyzotero.zotero_errors import PyZoteroError

from riszotto.client import (
    DEFAULT_BIBTEX_EXCLUDE,
    AmbiguousLibraryError,
    LibraryNotFoundError,
    collection_items,
    get_client,
    get_item_bibtex,
    get_pdf_attachments,
    get_pdf_path,
    list_collections,
    recent_items,
    search_items,
)
from riszotto.config import load_config
from riszotto.formatting import (
    format_creator,
    format_items_table,
    format_collections_table,
)

app = typer.Typer(add_completion=False)

LibraryOption = Annotated[
    Optional[str],
    typer.Option(
        "--library",
        "-L",
        help="Group library name or ID (default: personal library)",
    ),
]

FormatOption = Annotated[
    str,
    typer.Option(
        "--format",
        "-f",
        help="Output format (table or json)",
    ),
]


def _import_semantic():
    """Import semantic module, returning None if extras not installed."""
    try:
        from riszotto import semantic

        return semantic
    except ImportError:
        return None


def _get_zot(library: str | None = None) -> zotero.Zotero:
    """Get Zotero client, raising typer.Exit on connection failure."""
    try:
        return get_client(library=library)
    except (LibraryNotFoundError, AmbiguousLibraryError) as e:
        typer.echo(str(e), err=True)
        raise typer.Exit(1)
    except ConnectionError:
        typer.echo(
            "Zotero desktop is not running. Start Zotero and ensure the local API is enabled.",
            err=True,
        )
        raise typer.Exit(1)


def _collection_name(zot: zotero.Zotero) -> str:
    """Derive ChromaDB collection name from the resolved Zotero client."""
    if zot.library_type in ("user", "users"):
        return "user_0"
    return f"group_{zot.library_id}"


def _strip_diacritics(text: str) -> str:
    """Normalize unicode and strip diacritical marks for comparison."""
    nfkd = unicodedata.normalize("NFKD", text)
    return "".join(
        c for c in nfkd if not unicodedata.category(c).startswith("M")
    ).lower()


def _levenshtein(s: str, t: str) -> int:
    """Compute Levenshtein edit distance between two strings."""
    if len(s) < len(t):
        return _levenshtein(t, s)
    if not t:
        return len(s)
    prev = list(range(len(t) + 1))
    for i, sc in enumerate(s):
        curr = [i + 1]
        for j, tc in enumerate(t):
            cost = 0 if sc == tc else 1
            curr.append(min(prev[j + 1] + 1, curr[j] + 1, prev[j] + cost))
        prev = curr
    return prev[-1]


def _fuzzy_substring_match(needle: str, haystack: str, max_distance: int = 2) -> bool:
    """Check if needle appears as a fuzzy substring in haystack."""
    if len(needle) > len(haystack):
        return _levenshtein(needle, haystack) <= max_distance
    for i in range(len(haystack) - len(needle) + 1):
        window = haystack[i : i + len(needle)]
        if _levenshtein(needle, window) <= max_distance:
            return True
    return False


def _matches_author(item: dict, author: str, *, fuzzy: bool = False) -> bool:
    """Check if any creator name matches the author query.

    Default: diacritic-insensitive substring match.
    With fuzzy=True: also allows Levenshtein distance <= 2.
    """
    needle = _strip_diacritics(author)
    for creator in item.get("data", {}).get("creators", []):
        name = _strip_diacritics(format_creator(creator))
        if needle in name:
            return True
        if fuzzy and _fuzzy_substring_match(needle, name):
            return True
    return False


def _filter_long_values(data: dict, max_size: int) -> dict:
    """Replace string values longer than max_size with a placeholder."""
    if max_size <= 0:
        return data
    filtered = {}
    for k, v in data.items():
        if isinstance(v, str) and len(v) > max_size:
            filtered[k] = f"<hidden ({len(v)} chars)>"
        else:
            filtered[k] = v
    return filtered


def _format_result(item: dict, max_value_size: int) -> dict:
    """Extract display fields from a Zotero item."""
    data = item.get("data", {})
    result = {
        "key": data.get("key", ""),
        "title": data.get("title", ""),
        "itemType": data.get("itemType", ""),
        "date": data.get("date", ""),
        "authors": [format_creator(c) for c in data.get("creators", [])],
        "abstract": data.get("abstractNote", ""),
        "tags": [t["tag"] for t in data.get("tags", [])],
    }
    return _filter_long_values(result, max_value_size)


def _discover_libraries() -> list[dict]:
    """Discover all accessible libraries and return metadata with clients.

    Returns
    -------
    list[dict]
        Each dict has keys: name, id, type, source, client.
        Remote group entries also include ``meta_items``.
    """
    config = load_config()
    libs: list[dict] = []
    seen_ids: set[int] = set()

    try:
        local_zot = get_client()
        libs.append(
            {
                "name": "My Library",
                "id": "0",
                "type": "user",
                "source": "local",
                "client": local_zot,
            }
        )
        for group in local_zot.groups():
            seen_ids.add(group["id"])
            try:
                group_zot = zotero.Zotero(
                    library_id=str(group["id"]),
                    library_type="group",
                    local=True,
                )
                libs.append(
                    {
                        "name": group["data"]["name"],
                        "id": str(group["id"]),
                        "type": "group",
                        "source": "local",
                        "client": group_zot,
                    }
                )
            except (ConnectionError, OSError, PyZoteroError):
                pass
    except (ConnectionError, OSError, PyZoteroError):
        pass

    if config.has_remote_credentials:
        try:
            remote = zotero.Zotero(
                library_id=config.user_id,
                library_type="user",
                api_key=config.api_key,
            )
            for group in remote.groups():
                if group["id"] not in seen_ids:
                    group_zot = zotero.Zotero(
                        library_id=str(group["id"]),
                        library_type="group",
                        api_key=config.api_key,
                    )
                    libs.append(
                        {
                            "name": group["data"]["name"],
                            "id": str(group["id"]),
                            "type": "group",
                            "source": "remote",
                            "client": group_zot,
                            "meta_items": group.get("meta", {}).get("numItems", "?"),
                        }
                    )
        except (ConnectionError, OSError, PyZoteroError) as e:
            typer.echo(f"Warning: remote group discovery failed: {e}", err=True)

    return libs


def _search_all_libraries(
    *,
    terms: list[str],
    full_text: bool,
    semantic: bool,
    limit: int,
    page: int,
    max_value_size: int,
    tag: list[str] | None,
    item_type: str | None,
    since: str | None,
    sort: str | None,
    direction: str | None,
    author: str | None,
    fuzzy: bool,
    format: str,
) -> None:
    """Search across all libraries and output grouped results."""
    query = " ".join(terms)
    libs = _discover_libraries()

    if not libs:
        typer.echo("No accessible libraries found.", err=True)
        raise typer.Exit(1)

    sem = None
    if semantic:
        sem = _import_semantic()
        if sem is None:
            typer.echo(
                "Semantic search extras not installed. Run: uv pip install riszotto[semantic]",
                err=True,
            )
            raise typer.Exit(1)

    grouped: dict[str, dict] = {}

    for lib in libs:
        lib_name, zot = lib["name"], lib["client"]
        if semantic:
            col = _collection_name(zot)
            try:
                status = sem.get_index_status(collection_name=col)
                if status["count"] == 0:
                    continue
            except Exception as e:
                typer.echo(f"Warning: skipping {lib_name}: {e}", err=True)
                continue
            hits = sem.semantic_search(query, limit=limit, collection_name=col)
            results = []
            for hit in hits:
                item = zot.item(hit["key"])
                if author and not _matches_author(item, author, fuzzy=fuzzy):
                    continue
                formatted = _format_result(
                    item, 0 if format == "table" else max_value_size
                )
                formatted["score"] = hit["score"]
                results.append(formatted)
        else:
            start = (page - 1) * limit
            raw = search_items(
                zot,
                query,
                full_text=full_text,
                limit=limit,
                start=start,
                tag=tag,
                item_type=item_type,
                since=since,
                sort=sort,
                direction=direction,
            )
            if author:
                raw = [
                    item for item in raw if _matches_author(item, author, fuzzy=fuzzy)
                ]
            results = [
                _format_result(item, 0 if format == "table" else max_value_size)
                for item in raw
            ]

        if results:
            envelope = {
                "page": page if not semantic else 1,
                "limit": limit,
                "start": (page - 1) * limit if not semantic else 0,
                "results": results,
            }
            grouped[lib_name] = envelope

    if format == "json":
        typer.echo(json.dumps(grouped, indent=2))
    else:
        parts = []
        for lib_name, envelope in grouped.items():
            parts.append(f"── {lib_name} ──")
            parts.append(format_items_table(envelope["results"], semantic=semantic))
        typer.echo("\n\n".join(parts) if parts else "No results found.")


@app.command()
def search(
    terms: Annotated[list[str], typer.Argument(help="Search terms")],
    full_text: Annotated[
        bool,
        typer.Option(
            "--full-text/--no-full-text", help="Search all fields including full-text"
        ),
    ] = False,
    semantic: Annotated[
        bool, typer.Option("--semantic", help="Use semantic similarity search")
    ] = False,
    limit: Annotated[
        int, typer.Option("--limit", "-l", help="Maximum number of results")
    ] = 25,
    page: Annotated[
        int, typer.Option("--page", "-p", help="Page number (1-indexed)")
    ] = 1,
    max_value_size: Annotated[
        int,
        typer.Option(
            "--max-value-size",
            help="Hide string values longer than this (0 = show all)",
        ),
    ] = 200,
    tag: Annotated[
        Optional[list[str]],
        typer.Option("--tag", "-t", help="Filter by tag (repeatable, AND logic)"),
    ] = None,
    item_type: Annotated[
        Optional[str],
        typer.Option(
            "--item-type", help="Filter by item type (e.g. journalArticle, book)"
        ),
    ] = None,
    since: Annotated[
        Optional[str],
        typer.Option("--since", help="Only items modified after this date"),
    ] = None,
    sort: Annotated[
        Optional[str],
        typer.Option("--sort", help="Sort field (e.g. dateModified, title, creator)"),
    ] = None,
    direction: Annotated[
        Optional[str], typer.Option("--direction", help="Sort direction (asc or desc)")
    ] = None,
    author: Annotated[
        Optional[str],
        typer.Option(
            "--author",
            help="Filter by author name (diacritic-insensitive substring match)",
        ),
    ] = None,
    fuzzy: Annotated[
        bool,
        typer.Option(
            "--fuzzy",
            help="Use fuzzy matching for --author (Levenshtein distance <= 2)",
        ),
    ] = False,
    library: LibraryOption = None,
    all_libraries: Annotated[
        bool,
        typer.Option(
            "--all-libraries",
            "-A",
            help="Search across all accessible libraries",
        ),
    ] = False,
    format: FormatOption = "table",
) -> None:
    """Search for papers in your Zotero library."""
    if format not in ("table", "json"):
        typer.echo(f"Unknown format: {format}. Use 'table' or 'json'.", err=True)
        raise typer.Exit(1)

    if all_libraries and library:
        typer.echo("--all-libraries and --library are mutually exclusive.", err=True)
        raise typer.Exit(1)

    if all_libraries:
        _search_all_libraries(
            terms=terms,
            full_text=full_text,
            semantic=semantic,
            limit=limit,
            page=page,
            max_value_size=max_value_size,
            tag=tag,
            item_type=item_type,
            since=since,
            sort=sort,
            direction=direction,
            author=author,
            fuzzy=fuzzy,
            format=format,
        )
        return

    query = " ".join(terms)

    if semantic:
        sem = _import_semantic()
        if sem is None:
            typer.echo(
                "Semantic search extras not installed. Run: uv pip install riszotto[semantic]",
                err=True,
            )
            raise typer.Exit(1)

        zot = _get_zot(library=library)
        col = _collection_name(zot)
        status = sem.get_index_status(collection_name=col)
        if status["count"] == 0:
            lib_hint = f' --library "{library}"' if library else ""
            typer.echo(
                f"No semantic index found. Build one first: riszotto index{lib_hint}",
                err=True,
            )
            raise typer.Exit(1)
        hits = sem.semantic_search(query, limit=limit, collection_name=col)
        results = []
        for hit in hits:
            item = zot.item(hit["key"])
            if author and not _matches_author(item, author, fuzzy=fuzzy):
                continue
            formatted = _format_result(item, 0 if format == "table" else max_value_size)
            formatted["score"] = hit["score"]
            results.append(formatted)

        envelope = {
            "page": 1,
            "limit": limit,
            "start": 0,
            "results": results,
        }
        if format == "json":
            typer.echo(json.dumps(envelope, indent=2))
        else:
            typer.echo(format_items_table(envelope["results"], semantic=True))
        return

    start = (page - 1) * limit
    zot = _get_zot(library=library)
    results = search_items(
        zot,
        query,
        full_text=full_text,
        limit=limit,
        start=start,
        tag=tag,
        item_type=item_type,
        since=since,
        sort=sort,
        direction=direction,
    )

    if author:
        results = [
            item for item in results if _matches_author(item, author, fuzzy=fuzzy)
        ]

    envelope = {
        "page": page,
        "limit": limit,
        "start": start,
        "results": [
            _format_result(item, 0 if format == "table" else max_value_size)
            for item in results
        ],
    }
    if format == "json":
        typer.echo(json.dumps(envelope, indent=2))
    else:
        output = format_items_table(envelope["results"])
        typer.echo(output)
        if envelope["results"] and len(envelope["results"]) == limit:
            typer.echo(
                f"\nPage {page}. Next: riszotto search {' '.join(terms)} --page {page + 1}"
            )


@app.command()
def show(
    key: Annotated[str, typer.Argument(help="Zotero item key")],
    attachment: Annotated[
        int, typer.Option("--attachment", "-a", help="PDF attachment index (1-indexed)")
    ] = 1,
    page: Annotated[
        int, typer.Option("--page", "-p", help="Page number (1-indexed, 0 = show all)")
    ] = 1,
    page_size: Annotated[int, typer.Option("--page-size", help="Lines per page")] = 500,
    search: Annotated[
        Optional[str],
        typer.Option("--search", "-s", help="Show only lines matching all terms"),
    ] = None,
    context: Annotated[
        int,
        typer.Option("--context", "-C", help="Context lines around each search match"),
    ] = 3,
    library: LibraryOption = None,
) -> None:
    """Convert a paper's PDF attachment to markdown."""
    zot = _get_zot(library=library)

    pdfs = get_pdf_attachments(zot, key)
    if not pdfs:
        typer.echo(f"No PDF attachment found for item {key}.", err=True)
        raise typer.Exit(1)

    if attachment < 1 or attachment > len(pdfs):
        typer.echo(
            f"Attachment index {attachment} out of range. Item has {len(pdfs)} PDF(s).",
            err=True,
        )
        raise typer.Exit(1)

    selected = pdfs[attachment - 1]
    file_path = get_pdf_path(selected)
    if not file_path:
        if library:
            typer.echo(
                "PDF not available locally. The group is accessed via remote API "
                "and show requires local files. Sync this group in Zotero desktop "
                "for PDF access.",
                err=True,
            )
        else:
            typer.echo("Could not determine local file path for attachment.", err=True)
        raise typer.Exit(1)

    try:
        import logging

        logging.disable(logging.CRITICAL)
        try:
            md = MarkItDown()
            result = md.convert(file_path)
            markdown = result.markdown
        finally:
            logging.disable(logging.NOTSET)
    except Exception as e:
        typer.echo(f"Failed to convert PDF to markdown: {e}", err=True)
        raise typer.Exit(1)

    if search is not None:
        output = _grep_lines(markdown, search.split(), context)
        if output is None:
            typer.echo(f"No lines matching '{search}' found.")
            return
        typer.echo(output)
        return

    _show_paginated(markdown, page, page_size, key, library=library)


@app.command()
def export(
    key: Annotated[str, typer.Argument(help="Zotero item key")],
    format: Annotated[
        str, typer.Option("--format", "-f", help="Export format")
    ] = "bibtex",
    exclude: Annotated[
        Optional[list[str]],
        typer.Option("--exclude", "-e", help="BibTeX fields to exclude (repeatable)"),
    ] = None,
    include_all: Annotated[
        bool, typer.Option("--include-all", help="Don't exclude any fields")
    ] = False,
    library: LibraryOption = None,
) -> None:
    """Export an item in the specified format."""
    zot = _get_zot(library=library)
    if format == "bibtex":
        excluded = (
            set()
            if include_all
            else (set(exclude) if exclude else DEFAULT_BIBTEX_EXCLUDE)
        )
        typer.echo(get_item_bibtex(zot, key, exclude=excluded))
    else:
        typer.echo(f"Unknown format: {format}", err=True)
        raise typer.Exit(1)


def _show_paginated(
    markdown: str,
    page: int,
    page_size: int,
    key: str,
    *,
    library: str | None = None,
) -> None:
    """Print a page of markdown lines."""
    lines = markdown.splitlines()
    total_lines = len(lines)

    if page == 0:
        typer.echo(markdown)
        return

    total_pages = max(1, -(-total_lines // page_size))  # ceil division
    if page > total_pages:
        typer.echo(
            f"Page {page} out of range. Document has {total_pages} page(s).", err=True
        )
        raise typer.Exit(1)

    start = (page - 1) * page_size
    end = start + page_size
    typer.echo("\n".join(lines[start:end]))

    if total_pages > 1:
        lib_flag = f' --library "{library}"' if library else ""
        typer.echo(
            f"\nPage {page}/{total_pages}. Next: riszotto show{lib_flag} --page {page + 1} {key}"
        )


def _grep_lines(markdown: str, terms: list[str], context: int = 3) -> str | None:
    """Return lines matching all search terms with surrounding context, grep-style."""
    lines = markdown.splitlines()
    terms_lower = [t.lower() for t in terms]
    match_indices = {
        i for i, line in enumerate(lines) if all(t in line.lower() for t in terms_lower)
    }

    if not match_indices:
        return None

    # Expand to include context lines
    visible: set[int] = set()
    for i in match_indices:
        for j in range(max(0, i - context), min(len(lines), i + context + 1)):
            visible.add(j)

    # Build output with "--" separators between non-contiguous blocks
    output: list[str] = []
    prev = -2
    for i in sorted(visible):
        if i > prev + 1 and output:
            output.append("--")
        output.append(lines[i])
        prev = i

    return "\n".join(output)


def _format_collection(col: dict) -> dict:
    """Extract display fields from a Zotero collection."""
    data = col.get("data", {})
    return {
        "key": data.get("key", ""),
        "name": data.get("name", ""),
        "parentCollection": data.get("parentCollection", False),
    }


@app.command()
def collections(
    key: Annotated[
        Optional[str], typer.Argument(help="Collection key (omit to list all)")
    ] = None,
    limit: Annotated[
        int, typer.Option("--limit", "-l", help="Maximum number of results")
    ] = 25,
    page: Annotated[
        int, typer.Option("--page", "-p", help="Page number (1-indexed)")
    ] = 1,
    max_value_size: Annotated[
        int,
        typer.Option(
            "--max-value-size",
            help="Hide string values longer than this (0 = show all)",
        ),
    ] = 200,
    library: LibraryOption = None,
    format: FormatOption = "table",
) -> None:
    """List collections or items in a collection."""
    if format not in ("table", "json"):
        typer.echo(f"Unknown format: {format}. Use 'table' or 'json'.", err=True)
        raise typer.Exit(1)

    zot = _get_zot(library=library)
    if key is None:
        cols = list_collections(zot)
        envelope = {
            "results": [_format_collection(c) for c in cols],
        }
    else:
        start = (page - 1) * limit
        items = collection_items(zot, key, limit=limit, start=start)
        envelope = {
            "page": page,
            "limit": limit,
            "start": start,
            "results": [
                _format_result(item, 0 if format == "table" else max_value_size)
                for item in items
            ],
        }
    if format == "json":
        typer.echo(json.dumps(envelope, indent=2))
    elif key is None:
        typer.echo(format_collections_table(envelope["results"]))
    else:
        output = format_items_table(envelope["results"])
        typer.echo(output)
        if envelope["results"] and len(envelope["results"]) == limit:
            typer.echo(
                f"\nPage {page}. Next: riszotto collections {key} --page {page + 1}"
            )


@app.command()
def recent(
    limit: Annotated[
        int, typer.Option("--limit", "-l", help="Maximum number of results")
    ] = 10,
    max_value_size: Annotated[
        int,
        typer.Option(
            "--max-value-size",
            help="Hide string values longer than this (0 = show all)",
        ),
    ] = 200,
    library: LibraryOption = None,
    format: FormatOption = "table",
) -> None:
    """Show recently added papers."""
    if format not in ("table", "json"):
        typer.echo(f"Unknown format: {format}. Use 'table' or 'json'.", err=True)
        raise typer.Exit(1)

    zot = _get_zot(library=library)
    items = recent_items(zot, limit=limit)
    envelope = {
        "limit": limit,
        "results": [
            _format_result(item, 0 if format == "table" else max_value_size)
            for item in items
        ],
    }
    if format == "json":
        typer.echo(json.dumps(envelope, indent=2))
    else:
        typer.echo(format_items_table(envelope["results"]))


@app.command()
def index(
    rebuild: Annotated[
        bool, typer.Option("--rebuild", help="Drop and rebuild the entire index")
    ] = False,
    status: Annotated[
        bool, typer.Option("--status", help="Show index statistics")
    ] = False,
    limit: Annotated[
        Optional[int],
        typer.Option("--limit", "-l", help="Maximum items to fetch from Zotero"),
    ] = None,
    library: LibraryOption = None,
) -> None:
    """Build or update the semantic search index."""
    semantic = _import_semantic()
    if semantic is None:
        typer.echo(
            "Semantic search extras not installed. Run: uv pip install riszotto[semantic]",
            err=True,
        )
        raise typer.Exit(1)

    zot = _get_zot(library=library)
    col = _collection_name(zot)

    if status:
        info = semantic.get_index_status(collection_name=col)
        typer.echo(json.dumps(info, indent=2))
        return

    stats = semantic.build_index(zot, rebuild=rebuild, limit=limit, collection_name=col)
    typer.echo(f"Indexed {stats['indexed']} items ({stats['skipped']} skipped).")


@app.command()
def libraries() -> None:
    """List available Zotero libraries."""
    config = load_config()
    discovered = _discover_libraries()

    if not discovered:
        if not config.has_remote_credentials:
            typer.echo(
                "Zotero desktop is not running and no remote config found. "
                "Start Zotero or configure api_key and user_id in "
                "~/.riszotto/config.toml.",
                err=True,
            )
            raise typer.Exit(1)
        discovered = [
            {
                "name": "My Library",
                "id": "0",
                "type": "user",
                "source": "local",
                "client": None,
            }
        ]

    # Build display list with items count
    libs: list[dict] = []
    for lib_info in discovered:
        entry = {
            "name": lib_info["name"],
            "id": lib_info["id"],
            "type": lib_info["type"],
            "source": lib_info["source"],
        }
        if "meta_items" in lib_info:
            entry["items"] = lib_info["meta_items"]
        elif lib_info.get("client"):
            try:
                entry["items"] = lib_info["client"].num_items()
            except (ConnectionError, OSError, PyZoteroError):
                entry["items"] = "?"
        else:
            entry["items"] = "?"
        libs.append(entry)

    # Add index status
    sem = _import_semantic()
    for lib in libs:
        if sem is None:
            lib["indexed"] = "-"
        else:
            col = "user_0" if lib["type"] == "user" else f"group_{lib['id']}"
            try:
                status = sem.get_index_status(collection_name=col)
                lib["indexed"] = status["count"] if status["count"] > 0 else "-"
            except Exception as e:
                typer.echo(
                    f"Warning: index check failed for {lib['name']}: {e}",
                    err=True,
                )
                lib["indexed"] = "-"

    # Format as markdown table
    header = (
        f"{'Name':<30} {'ID':<10} {'Type':<8} {'Items':<8} {'Indexed':<8} {'Source'}"
    )
    lines = [header, "-" * len(header)]
    for lib in libs:
        lines.append(
            f"{lib['name']:<30} {lib['id']:<10} {lib['type']:<8} {str(lib['items']):<8} {str(lib['indexed']):<8} {lib['source']}"
        )
    typer.echo("\n".join(lines))
