"""riszotto CLI — search and read papers from your local Zotero library."""

from __future__ import annotations

import json
import sys
from typing import Annotated, Optional

import typer

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
) -> None:
    """Search for papers in your Zotero library."""
    query = " ".join(terms)
    try:
        zot = get_client()
        results = search_items(zot, query, full_text=full_text, limit=limit)
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
) -> None:
    """Convert a paper's PDF attachment to markdown."""
    typer.echo("show: not implemented")
