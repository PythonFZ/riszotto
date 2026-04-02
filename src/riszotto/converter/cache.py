"""SHA256-keyed conversion cache for docling results."""

from __future__ import annotations

import hashlib
import shutil
from datetime import datetime, timezone
from pathlib import Path

from pydantic import BaseModel

from riszotto.converter.base import BackendName, ConversionResult, StyleOption
from riszotto.paths import CONVERSION_CACHE_DIR


class CacheMeta(BaseModel):
    """Metadata for a cached conversion result."""

    created: datetime
    backend: BackendName
    table_style: StyleOption
    equation_style: StyleOption
    pdf_hash: str


def compute_pdf_hash(pdf_path: Path) -> str:
    """Return first 12 hex chars of the SHA256 hash of a PDF file."""
    h = hashlib.sha256(pdf_path.read_bytes()).hexdigest()
    return h[:12]


def cache_dir_for(zotero_key: str, pdf_hash: str) -> Path:
    """Return the cache directory for a specific paper + hash."""
    return CONVERSION_CACHE_DIR / zotero_key / pdf_hash


def read_cache(
    *,
    zotero_key: str,
    pdf_hash: str,
    table_style: StyleOption,
    equation_style: StyleOption,
) -> ConversionResult | None:
    """Read a cached conversion result, or None if not found/mismatched."""
    cache_path = cache_dir_for(zotero_key, pdf_hash)
    meta_file = cache_path / "meta.json"
    content_file = cache_path / "content.md"

    if not meta_file.exists() or not content_file.exists():
        return None

    meta = CacheMeta.model_validate_json(meta_file.read_text())

    if meta.table_style != table_style or meta.equation_style != equation_style:
        return None

    markdown = content_file.read_text()
    figures = {
        f.name: f
        for f in cache_path.iterdir()
        if f.suffix in (".png", ".jpg", ".jpeg") and f.name != "meta.json"
    }

    return ConversionResult(markdown=markdown, figures=figures)


def write_cache(
    *,
    zotero_key: str,
    pdf_hash: str,
    markdown: str,
    figures: dict[str, Path],
    backend: BackendName,
    table_style: StyleOption,
    equation_style: StyleOption,
) -> Path:
    """Write a conversion result to cache. Returns the cache directory.

    Removes any existing hash directories for this zotero_key
    (only one hash per key is kept).
    """
    key_dir = CONVERSION_CACHE_DIR / zotero_key

    # Remove old hash directories for this key
    if key_dir.exists():
        for child in key_dir.iterdir():
            if child.is_dir() and child.name != pdf_hash:
                shutil.rmtree(child)

    cache_path = cache_dir_for(zotero_key, pdf_hash)
    cache_path.mkdir(parents=True, exist_ok=True)

    (cache_path / "content.md").write_text(markdown)

    for name, src in figures.items():
        dest = cache_path / name
        if src != dest:
            shutil.copy2(src, dest)

    meta = CacheMeta(
        created=datetime.now(timezone.utc),
        backend=backend,
        table_style=table_style,
        equation_style=equation_style,
        pdf_hash=pdf_hash,
    )
    (cache_path / "meta.json").write_text(meta.model_dump_json(indent=2))

    return cache_path


def clear_cache(
    *,
    key: str | None = None,
    older_than_days: int | None = None,
) -> int:
    """Clear cached conversions. Returns number of papers cleared."""
    if not CONVERSION_CACHE_DIR.exists():
        return 0

    cleared = 0

    if key is not None:
        key_dir = CONVERSION_CACHE_DIR / key
        if key_dir.exists():
            shutil.rmtree(key_dir)
            cleared = 1
        return cleared

    for key_dir in CONVERSION_CACHE_DIR.iterdir():
        if not key_dir.is_dir():
            continue
        if older_than_days is not None:
            meta_files = list(key_dir.rglob("meta.json"))
            if meta_files:
                meta = CacheMeta.model_validate_json(meta_files[0].read_text())
                age_days = (datetime.now(timezone.utc) - meta.created).days
                if age_days < older_than_days:
                    continue
        shutil.rmtree(key_dir)
        cleared += 1

    return cleared


def get_cache_stats(*, key: str | None = None) -> dict:
    """Return cache statistics."""
    if not CONVERSION_CACHE_DIR.exists():
        return {"paper_count": 0, "total_bytes": 0, "path": str(CONVERSION_CACHE_DIR)}

    total_bytes = 0
    paper_count = 0
    papers: list[dict] = []

    dirs = [CONVERSION_CACHE_DIR / key] if key else CONVERSION_CACHE_DIR.iterdir()

    for key_dir in dirs:
        if not isinstance(key_dir, Path):
            continue
        if not key_dir.is_dir():
            continue
        paper_count += 1
        paper_bytes = sum(f.stat().st_size for f in key_dir.rglob("*") if f.is_file())
        total_bytes += paper_bytes
        papers.append({"key": key_dir.name, "bytes": paper_bytes})

    return {
        "paper_count": paper_count,
        "total_bytes": total_bytes,
        "path": str(CONVERSION_CACHE_DIR),
        "papers": papers,
    }
