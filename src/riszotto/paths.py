"""Centralized platform-specific directory resolution."""

from __future__ import annotations

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
