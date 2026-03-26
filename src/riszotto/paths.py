"""Centralized platform-specific directory resolution."""

from __future__ import annotations

import sys
from pathlib import Path

from platformdirs import user_cache_dir, user_config_dir, user_data_dir


def config_dir() -> Path:
    """Return the platform-specific config directory for riszotto."""
    return Path(user_config_dir("riszotto"))


def data_dir() -> Path:
    """Return the platform-specific data directory for riszotto."""
    return Path(user_data_dir("riszotto"))


def cache_dir() -> Path:
    """Return the platform-specific cache directory for riszotto."""
    return Path(user_cache_dir("riszotto"))


CONFIG_PATH = config_dir() / "config.toml"
CHROMA_DIR = data_dir() / "chroma_db"
CONVERSION_CACHE_DIR = cache_dir() / "conversions"

LEGACY_DIR = Path.home() / ".riszotto"


def check_legacy_migration() -> None:
    """Warn if legacy ~/.riszotto/ exists and differs from platformdirs paths."""
    if not LEGACY_DIR.exists():
        return
    if LEGACY_DIR.resolve() == config_dir().resolve():
        return

    legacy_config = LEGACY_DIR / "config.toml"
    if legacy_config.exists() and not CONFIG_PATH.exists():
        print(
            f"Found legacy config at {legacy_config}. Please move it to {CONFIG_PATH}",
            file=sys.stderr,
        )

    legacy_chroma = LEGACY_DIR / "chroma_db"
    if legacy_chroma.exists() and not CHROMA_DIR.exists():
        print(
            f"Found legacy index at {legacy_chroma}. Please move it to {CHROMA_DIR}",
            file=sys.stderr,
        )
