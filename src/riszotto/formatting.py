"""Shared formatting helpers for riszotto."""

from __future__ import annotations

CHILD_ITEM_TYPES = {"attachment", "note", "annotation"}


def format_creator(creator: dict) -> str:
    """Format a single Zotero creator dict as a string."""
    last = creator.get("lastName", "")
    first = creator.get("firstName", "")
    if last and first:
        return f"{last}, {first}"
    return creator.get("name", last or first)


TABLE_WIDTH = 120
COL_KEY = 10
COL_DATE = 6
COL_AUTHORS = 25
COL_SCORE = 6


def _truncate(text: str, width: int) -> str:
    """Truncate text to width, adding '...' if needed.

    Parameters
    ----------
    text
        The string to truncate.
    width
        Maximum allowed character width.

    Returns
    -------
    str
        Original text if short enough, otherwise text truncated to width
        with trailing '...'.
    """
    if len(text) <= width:
        return text
    return text[: width - 3] + "..."


def _extract_year(date: str) -> str:
    """Extract first 4 digits as year from a Zotero date string.

    Parameters
    ----------
    date
        A Zotero date string such as ``"2024-01-15"`` or ``"2024"``.

    Returns
    -------
    str
        The first 4 characters of the date string, or the full string
        if it is shorter than 4 characters.
    """
    return date[:4] if len(date) >= 4 else date


def format_items_table(results: list[dict], *, semantic: bool = False) -> str:
    """Format item result dicts as a fixed-width table.

    Parameters
    ----------
    results
        List of dicts from ``_format_result``, each with keys:
        key, title, date, authors (list[str]), and optionally score.
    semantic
        If True, include a SCORE column.

    Returns
    -------
    str
        Formatted table string, or "No results found." if empty.
    """
    if not results:
        return "No results found."

    col_title = TABLE_WIDTH - COL_KEY - COL_DATE - COL_AUTHORS
    if semantic:
        col_title -= COL_SCORE

    header_parts = [f"{'KEY':<{COL_KEY}}", f"{'DATE':<{COL_DATE}}", f"{'AUTHORS':<{COL_AUTHORS}}"]
    if semantic:
        header_parts.append(f"{'SCORE':<{COL_SCORE}}")
    header_parts.append("TITLE")
    header = "".join(header_parts)

    lines = [header]
    for r in results:
        authors = "; ".join(r.get("authors", []))
        row_parts = [
            f"{_truncate(r.get('key', ''), COL_KEY - 1):<{COL_KEY}}",
            f"{_extract_year(r.get('date', '')):<{COL_DATE}}",
            f"{_truncate(authors, COL_AUTHORS - 1):<{COL_AUTHORS}}",
        ]
        if semantic:
            score = r.get("score", 0)
            row_parts.append(f"{score:<{COL_SCORE}.2f}")
        row_parts.append(_truncate(r.get("title", ""), col_title))
        lines.append("".join(row_parts))

    return "\n".join(lines)
