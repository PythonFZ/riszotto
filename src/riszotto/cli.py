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

    typer.echo(json.dumps(item.get("data", {}), indent=2))


@app.command()
def show(
    key: Annotated[str, typer.Argument(help="Zotero item key")],
    attachment: Annotated[int, typer.Option("--attachment", "-a", help="PDF attachment index (1-indexed)")] = 1,
) -> None:
    """Convert a paper's PDF attachment to markdown."""
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
        typer.echo(f"Could not determine local file path for attachment.", err=True)
        raise typer.Exit(1)

    try:
        md = MarkItDown()
        result = md.convert(file_path)
        typer.echo(result.markdown)
    except Exception as e:
        typer.echo(f"Failed to convert PDF to markdown: {e}", err=True)
        raise typer.Exit(1)
