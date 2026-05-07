import os
from unittest.mock import patch

import pytest
from pydantic import ValidationError

from riszotto.config import Config, load_config


class TestConfig:
    @pytest.fixture(autouse=True)
    def _clear_riszotto_env(self, monkeypatch):
        """Remove inherited RISZOTTO_ZOTERO_* env vars so each test starts clean.

        CI and developer shells may have these set (e.g. for integration tests),
        which would otherwise leak into the unit-level config tests.
        """
        for var in (
            "RISZOTTO_ZOTERO_API_KEY",
            "RISZOTTO_ZOTERO_USER_ID",
            "RISZOTTO_ZOTERO_MODE",
        ):
            monkeypatch.delenv(var, raising=False)

    def test_defaults_when_no_file_no_env(self, tmp_path):
        with patch("riszotto.config.CONFIG_PATH", tmp_path / "config.toml"):
            config = load_config()
        assert config.api_key is None
        assert config.user_id is None
        assert config.mode == "auto"

    def test_reads_toml_file(self, tmp_path):
        config_file = tmp_path / "config.toml"
        config_file.write_text(
            '[zotero]\napi_key = "KEY123"\nuser_id = "456"\nmode = "web"\n'
        )
        with patch("riszotto.config.CONFIG_PATH", config_file):
            config = load_config()
        assert config.api_key == "KEY123"
        assert config.user_id == "456"
        assert config.mode == "web"

    def test_env_vars_override_file(self, tmp_path):
        config_file = tmp_path / "config.toml"
        config_file.write_text(
            '[zotero]\napi_key = "file_key"\nuser_id = "file_id"\nmode = "local"\n'
        )
        with (
            patch("riszotto.config.CONFIG_PATH", config_file),
            patch.dict(
                os.environ,
                {
                    "RISZOTTO_ZOTERO_API_KEY": "env_key",
                    "RISZOTTO_ZOTERO_USER_ID": "env_id",
                    "RISZOTTO_ZOTERO_MODE": "web",
                },
                clear=False,
            ),
        ):
            config = load_config()
        assert config.api_key == "env_key"
        assert config.user_id == "env_id"
        assert config.mode == "web"

    def test_env_vars_without_file(self, tmp_path):
        with (
            patch("riszotto.config.CONFIG_PATH", tmp_path / "config.toml"),
            patch.dict(
                os.environ, {"RISZOTTO_ZOTERO_API_KEY": "env_only"}, clear=False
            ),
        ):
            config = load_config()
        assert config.api_key == "env_only"
        assert config.user_id is None
        assert config.mode == "auto"

    def test_partial_toml(self, tmp_path):
        config_file = tmp_path / "config.toml"
        config_file.write_text('[zotero]\napi_key = "KEY123"\n')
        with patch("riszotto.config.CONFIG_PATH", config_file):
            config = load_config()
        assert config.api_key == "KEY123"
        assert config.user_id is None
        assert config.mode == "auto"

    def test_empty_toml(self, tmp_path):
        config_file = tmp_path / "config.toml"
        config_file.write_text("")
        with patch("riszotto.config.CONFIG_PATH", config_file):
            config = load_config()
        assert config.api_key is None
        assert config.user_id is None
        assert config.mode == "auto"

    def test_invalid_mode_raises(self, tmp_path):
        config_file = tmp_path / "config.toml"
        config_file.write_text('[zotero]\nmode = "bogus"\n')
        with patch("riszotto.config.CONFIG_PATH", config_file):
            with pytest.raises(ValidationError):
                load_config()

    def test_old_env_vars_are_ignored(self, tmp_path):
        """ZOTERO_API_KEY (no RISZOTTO_ prefix) must NOT be read."""
        with (
            patch("riszotto.config.CONFIG_PATH", tmp_path / "config.toml"),
            patch.dict(
                os.environ,
                {"ZOTERO_API_KEY": "old_name", "ZOTERO_USER_ID": "old_id"},
                clear=False,
            ),
        ):
            config = load_config()
        assert config.api_key is None
        assert config.user_id is None

    def test_has_remote_credentials(self):
        c = Config(api_key="k", user_id="u")
        assert c.has_remote_credentials is True
        assert Config(api_key="k").has_remote_credentials is False
        assert Config(user_id="u").has_remote_credentials is False
        assert Config().has_remote_credentials is False
