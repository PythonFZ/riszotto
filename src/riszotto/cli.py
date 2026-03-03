"""riszotto CLI — search and read papers from your local Zotero library."""

from __future__ import annotations

import json
import sys
from typing import Annotated, Optional

import typer
from markitdown import MarkItDown

from riszotto.client import get_client, get_item, get_pdf_attachments, get_pdf_path, search_items

app = typer.Typer(add_completion=False)


def _format_author(item: dict) -> str:
    """Extract a short author string from an item."""
    summary = item.get("meta", {}).get("creatorSummary", "")
    if summary:
        return summary
    creators = item.get("data", {}).get("creators", [])
    if not creators:
        return ""
    first = creators[0]
    name = first.get("lastName", first.get("name", ""))
    if len(creators) > 1:
        return f"{name} et al."
    return name


def _format_year(item: dict) -> str:
    """Extract year from an item's date field."""
    date = item.get("data", {}).get("date", "")
    return date[:4] if len(date) >= 4 else ""


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


@app.command()
def search(
    terms: Annotated[list[str], typer.Argument(help="Search terms")],
    full_text: Annotated[bool, typer.Option("--full-text", help="Search all fields including full-text")] = False,
    limit: Annotated[int, typer.Option("--limit", "-l", help="Maximum number of results")] = 25,
    page: Annotated[int, typer.Option("--page", "-p", help="Page number (1-indexed)")] = 1,
) -> None:
    """Search for papers in your Zotero library."""
    query = " ".join(terms)
    start = (page - 1) * limit
    try:
        zot = get_client()
        results = search_items(zot, query, full_text=full_text, limit=limit, start=start)
    except (ConnectionError, Exception) as e:
        if "connection" in str(e).lower() or "refused" in str(e).lower():
            typer.echo("Zotero desktop is not running. Start Zotero and ensure the local API is enabled.", err=True)
            raise typer.Exit(1)
        raise

    # Print compact table
    typer.echo(f"{'KEY':<11}{'YEAR':<6}{'AUTHOR':<20}{'TITLE'}")
    for item in results:
        data = item.get("data", {})
        key = data.get("key", "")
        year = _format_year(item)
        author = _format_author(item)
        title = data.get("title", "")
        # Truncate long values
        if len(author) > 18:
            author = author[:17] + "…"
        if len(title) > 60:
            title = title[:59] + "…"
        typer.echo(f"{key:<11}{year:<6}{author:<20}{title}")

    # Footer
    first = start + 1
    last = start + len(results)
    typer.echo(f"\nPage {page} (results {first}-{last}). Next: riszotto search --page {page + 1} \"{query}\"")


@app.command()
def info(
    key: Annotated[str, typer.Argument(help="Zotero item key")],
    max_value_size: Annotated[int, typer.Option("--max-value-size", help="Hide string values longer than this (0 = show all)")] = 200,
) -> None:
    """Show JSON metadata for a paper."""
    try:
        zot = get_client()
    except (ConnectionError, Exception) as e:
        if "connection" in str(e).lower() or "refused" in str(e).lower():
            typer.echo("Zotero desktop is not running. Start Zotero and ensure the local API is enabled.", err=True)
            raise typer.Exit(1)
        raise

    try:
        item = get_item(zot, key)
    except Exception:
        typer.echo(f"Item '{key}' not found in your library.", err=True)
        raise typer.Exit(1)

    data = item.get("data", {})
    data = _filter_long_values(data, max_value_size)
    typer.echo(json.dumps(data, indent=2))


@app.command()
def show(
    key: Annotated[str, typer.Argument(help="Zotero item key")],
    attachment: Annotated[int, typer.Option("--attachment", "-a", help="PDF attachment index (1-indexed)")] = 1,
    page: Annotated[int, typer.Option("--page", "-p", help="Page number (1-indexed, 0 = show all)")] = 1,
    page_size: Annotated[int, typer.Option("--page-size", help="Lines per page")] = 500,
    search: Annotated[Optional[str], typer.Option("--search", "-s", help="Show only sections matching this term")] = None,
) -> None:
    """Convert a paper's PDF attachment to markdown."""
    if search is not None and page != 1:
        typer.echo("--search and --page cannot be used together.", err=True)
        raise typer.Exit(1)

    try:
        zot = get_client()
    except (ConnectionError, Exception) as e:
        if "connection" in str(e).lower() or "refused" in str(e).lower():
            typer.echo("Zotero desktop is not running. Start Zotero and ensure the local API is enabled.", err=True)
            raise typer.Exit(1)
        raise

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
        _show_search(markdown, search)
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


def _show_search(markdown: str, term: str) -> None:
    """Print markdown sections matching a search term."""
    pass  # implemented in Task 5
