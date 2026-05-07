"""Content-addressed cache of PDF attachments downloaded from the Zotero web API.

Files are stored at ``PDF_CACHE_DIR / {md5}.pdf`` where md5 is the value
exposed by the Zotero API on synced storage attachments.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from riszotto.paths import PDF_CACHE_DIR


def pdf_cache_path(md5: str) -> Path:
    """Return the on-disk path for a given content hash."""
    return PDF_CACHE_DIR / f"{md5}.pdf"


def read_pdf_cache(md5: str) -> Path | None:
    """Return the cached PDF path if it exists, else ``None``."""
    p = pdf_cache_path(md5)
    return p if p.is_file() else None


def download_to_pdf_cache(zot: Any, attachment: dict[str, Any]) -> Path:
    """Ensure the attachment's PDF is in the cache; return the path.

    Parameters
    ----------
    zot : pyzotero.zotero.Zotero
        Configured pyzotero client (web mode).
    attachment : dict
        Zotero attachment item (must have ``data.md5`` and ``data.filename``).

    Returns
    -------
    Path
        Path to the cached PDF.

    Raises
    ------
    ValueError
        If ``attachment.data.md5`` is missing.
    """
    data = attachment.get("data", {})
    md5 = data.get("md5")
    if not md5:
        raise ValueError("attachment has no md5; file is not on Zotero storage")

    cached = read_pdf_cache(md5)
    if cached is not None:
        return cached

    PDF_CACHE_DIR.mkdir(parents=True, exist_ok=True)

    item_key = attachment["key"]
    cache_filename = f"{md5}.pdf"
    zot.dump(item_key, cache_filename, str(PDF_CACHE_DIR))

    return pdf_cache_path(md5)


def clear_pdf_cache() -> int:
    """Remove all cached PDFs. Return the count of files removed."""
    if not PDF_CACHE_DIR.exists():
        return 0
    n = 0
    for p in PDF_CACHE_DIR.iterdir():
        if p.is_file() and p.suffix == ".pdf":
            p.unlink()
            n += 1
    return n


def pdf_cache_stats() -> dict[str, Any]:
    """Return ``{count, total_bytes, path}`` for the PDF cache."""
    if not PDF_CACHE_DIR.exists():
        return {"count": 0, "total_bytes": 0, "path": str(PDF_CACHE_DIR)}
    count = 0
    total = 0
    for p in PDF_CACHE_DIR.iterdir():
        if p.is_file() and p.suffix == ".pdf":
            count += 1
            total += p.stat().st_size
    return {"count": count, "total_bytes": total, "path": str(PDF_CACHE_DIR)}
