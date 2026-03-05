"""riszotto CLI — search and read papers from your local Zotero library."""

from __future__ import annotations

import json
from typing import Annotated, Optional

import typer
from markitdown import MarkItDown
from pyzotero import zotero

from riszotto.client import get_client, get_pdf_attachments, get_pdf_path, search_items

app = typer.Typer(add_completion=False)


def _get_zot() -> zotero.Zotero:
    """Get Zotero client, raising typer.Exit on connection failure."""
    try:
        return get_client()
    except (ConnectionError, Exception) as e:
        if "connection" in str(e).lower() or "refused" in str(e).lower():
            typer.echo(
                "Zotero desktop is not running. Start Zotero and ensure the local API is enabled.",
                err=True,
            )
            raise typer.Exit(1)
        raise


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


def _format_creator(creator: dict) -> str:
    """Format a single Zotero creator dict as a string."""
    last = creator.get("lastName", "")
    first = creator.get("firstName", "")
    if last and first:
        return f"{last}, {first}"
    return creator.get("name", last or first)


def _format_result(item: dict, max_value_size: int) -> dict:
    """Extract display fields from a Zotero item."""
    data = item.get("data", {})
    result = {
        "key": data.get("key", ""),
        "title": data.get("title", ""),
        "itemType": data.get("itemType", ""),
        "date": data.get("date", ""),
        "authors": [_format_creator(c) for c in data.get("creators", [])],
        "abstract": data.get("abstractNote", ""),
        "tags": [t["tag"] for t in data.get("tags", [])],
    }
    return _filter_long_values(result, max_value_size)


@app.command()
def search(
    terms: Annotated[list[str], typer.Argument(help="Search terms")],
    full_text: Annotated[bool, typer.Option("--full-text/--no-full-text", help="Search all fields including full-text")] = False,
    limit: Annotated[int, typer.Option("--limit", "-l", help="Maximum number of results")] = 25,
    page: Annotated[int, typer.Option("--page", "-p", help="Page number (1-indexed)")] = 1,
    max_value_size: Annotated[int, typer.Option("--max-value-size", help="Hide string values longer than this (0 = show all)")] = 200,
) -> None:
    """Search for papers in your Zotero library."""
    query = " ".join(terms)
    start = (page - 1) * limit
    zot = _get_zot()
    results = search_items(zot, query, full_text=full_text, limit=limit, start=start)

    envelope = {
        "page": page,
        "limit": limit,
        "start": start,
        "results": [_format_result(item, max_value_size) for item in results],
    }
    typer.echo(json.dumps(envelope, indent=2))



@app.command()
def show(
    key: Annotated[str, typer.Argument(help="Zotero item key")],
    attachment: Annotated[int, typer.Option("--attachment", "-a", help="PDF attachment index (1-indexed)")] = 1,
    page: Annotated[int, typer.Option("--page", "-p", help="Page number (1-indexed, 0 = show all)")] = 1,
    page_size: Annotated[int, typer.Option("--page-size", help="Lines per page")] = 500,
    search: Annotated[Optional[str], typer.Option("--search", "-s", help="Show only lines matching all terms")] = None,
    context: Annotated[int, typer.Option("--context", "-C", help="Context lines around each search match")] = 3,
) -> None:
    """Convert a paper's PDF attachment to markdown."""
    zot = _get_zot()

    pdfs = get_pdf_attachments(zot, key)
    if not pdfs:
        typer.echo(f"No PDF attachment found for item {key}.", err=True)
        raise typer.Exit(1)

    if attachment < 1 or attachment > len(pdfs):
        typer.echo(f"Attachment index {attachment} out of range. Item has {len(pdfs)} PDF(s).", err=True)
        raise typer.Exit(1)

    selected = pdfs[attachment - 1]
    file_path = get_pdf_path(selected)
    if not file_path:
        typer.echo("Could not determine local file path for attachment.", err=True)
        raise typer.Exit(1)

    try:
        md = MarkItDown()
        result = md.convert(file_path)
        markdown = result.markdown
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

    _show_paginated(markdown, page, page_size, key)


def _show_paginated(markdown: str, page: int, page_size: int, key: str) -> None:
    """Print a page of markdown lines."""
    lines = markdown.splitlines()
    total_lines = len(lines)

    if page == 0:
        typer.echo(markdown)
        return

    total_pages = max(1, -(-total_lines // page_size))  # ceil division
    if page > total_pages:
        typer.echo(f"Page {page} out of range. Document has {total_pages} page(s).", err=True)
        raise typer.Exit(1)

    start = (page - 1) * page_size
    end = start + page_size
    typer.echo("\n".join(lines[start:end]))

    if total_pages > 1:
        typer.echo(f"\nPage {page}/{total_pages}. Next: riszotto show --page {page + 1} {key}")


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


@app.command()
def collections(
    key: Annotated[Optional[str], typer.Argument(help="Collection key (omit to list all)")] = None,
) -> None:
    """List collections or items in a collection."""
    zot = _get_zot()
    typer.echo(json.dumps({"results": []}, indent=2))
