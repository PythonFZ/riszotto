"""Shared formatting helpers for riszotto."""

from __future__ import annotations


def format_creator(creator: dict) -> str:
    """Format a single Zotero creator dict as a string."""
    last = creator.get("lastName", "")
    first = creator.get("firstName", "")
    if last and first:
        return f"{last}, {first}"
    return creator.get("name", last or first)
