"""Configuration loading from TOML file and environment variables."""

from __future__ import annotations

import dataclasses
import os
import tomllib

from riszotto.paths import CONFIG_PATH


@dataclasses.dataclass
class Config:
    """Zotero connection configuration."""

    api_key: str | None = None
    user_id: str | None = None

    @property
    def has_remote_credentials(self) -> bool:
        """Check if both API key and user ID are configured."""
        return self.api_key is not None and self.user_id is not None


def load_config() -> Config:
    """Load config from TOML file, then override with env vars.

    Precedence: defaults < config file < environment variables.
    """
    config = Config()

    # Read TOML file if it exists
    if CONFIG_PATH.is_file():
        with open(CONFIG_PATH, "rb") as f:
            data = tomllib.load(f)
        zotero = data.get("zotero", {})
        if "api_key" in zotero:
            config.api_key = zotero["api_key"]
        if "user_id" in zotero:
            config.user_id = zotero["user_id"]

    # Override with environment variables
    env_key = os.environ.get("ZOTERO_API_KEY")
    if env_key is not None:
        config.api_key = env_key
    env_id = os.environ.get("ZOTERO_USER_ID")
    if env_id is not None:
        config.user_id = env_id

    return config
