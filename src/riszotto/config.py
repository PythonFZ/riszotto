"""Configuration loading via pydantic-settings.

Reads from defaults, then ``~/.riszotto/config.toml`` ([zotero] section),
then environment variables prefixed with ``RISZOTTO_ZOTERO_``.
"""

from __future__ import annotations

import tomllib
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel
from pydantic_settings import (
    BaseSettings,
    PydanticBaseSettingsSource,
    SettingsConfigDict,
)

from riszotto.paths import CONFIG_PATH

Mode = Literal["auto", "local", "web"]


class Config(BaseModel):
    """Zotero connection configuration (public API consumed by client/cli)."""

    api_key: str | None = None
    user_id: str | None = None
    mode: Mode = "auto"

    @property
    def has_remote_credentials(self) -> bool:
        """Check if both API key and user ID are configured."""
        return self.api_key is not None and self.user_id is not None


class _ZoteroTomlSource(PydanticBaseSettingsSource):
    """Read the ``[zotero]`` section of CONFIG_PATH as a flat dict."""

    def __init__(self, settings_cls, toml_path: Path):
        super().__init__(settings_cls)
        self._toml_path = toml_path

    def get_field_value(self, field, field_name):  # required override
        data = self._load()
        if field_name in data:
            return data[field_name], field_name, False
        return None, field_name, False

    def __call__(self) -> dict[str, Any]:
        return self._load()

    def _load(self) -> dict[str, Any]:
        if not self._toml_path.is_file():
            return {}
        with open(self._toml_path, "rb") as f:
            data = tomllib.load(f)
        zotero = data.get("zotero", {})
        return {k: v for k, v in zotero.items() if k in {"api_key", "user_id", "mode"}}


class _Settings(BaseSettings):
    """Internal pydantic-settings model. Use ``load_config()`` instead."""

    api_key: str | None = None
    user_id: str | None = None
    mode: Mode = "auto"

    model_config = SettingsConfigDict(
        env_prefix="RISZOTTO_ZOTERO_",
        case_sensitive=False,
        extra="ignore",
    )

    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls,
        init_settings,
        env_settings,
        dotenv_settings,
        file_secret_settings,
    ):
        # Precedence (highest first): init kwargs, env vars, TOML file, defaults.
        return (
            init_settings,
            env_settings,
            _ZoteroTomlSource(settings_cls, CONFIG_PATH),
        )


def load_config() -> Config:
    """Load the active configuration.

    Precedence (lowest to highest): defaults < TOML file < environment variables.
    """
    s = _Settings()
    return Config(api_key=s.api_key, user_id=s.user_id, mode=s.mode)
