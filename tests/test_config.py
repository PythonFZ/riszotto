import os
from unittest.mock import patch

from riszotto.config import Config, load_config


class TestConfig:
    def test_defaults_when_no_file_no_env(self, tmp_path):
        with patch("riszotto.config.CONFIG_PATH", tmp_path / "config.toml"):
            config = load_config()
        assert config.api_key is None
        assert config.user_id is None

    def test_reads_toml_file(self, tmp_path):
        config_file = tmp_path / "config.toml"
        config_file.write_text('[zotero]\napi_key = "KEY123"\nuser_id = "456"\n')
        with patch("riszotto.config.CONFIG_PATH", config_file):
            config = load_config()
        assert config.api_key == "KEY123"
        assert config.user_id == "456"

    def test_env_vars_override_file(self, tmp_path):
        config_file = tmp_path / "config.toml"
        config_file.write_text('[zotero]\napi_key = "file_key"\nuser_id = "file_id"\n')
        with (
            patch("riszotto.config.CONFIG_PATH", config_file),
            patch.dict(
                os.environ,
                {"ZOTERO_API_KEY": "env_key", "ZOTERO_USER_ID": "env_id"},
            ),
        ):
            config = load_config()
        assert config.api_key == "env_key"
        assert config.user_id == "env_id"

    def test_env_vars_without_file(self, tmp_path):
        with (
            patch("riszotto.config.CONFIG_PATH", tmp_path / "config.toml"),
            patch.dict(os.environ, {"ZOTERO_API_KEY": "env_only"}),
        ):
            config = load_config()
        assert config.api_key == "env_only"
        assert config.user_id is None

    def test_partial_toml(self, tmp_path):
        config_file = tmp_path / "config.toml"
        config_file.write_text('[zotero]\napi_key = "KEY123"\n')
        with patch("riszotto.config.CONFIG_PATH", config_file):
            config = load_config()
        assert config.api_key == "KEY123"
        assert config.user_id is None

    def test_empty_toml(self, tmp_path):
        config_file = tmp_path / "config.toml"
        config_file.write_text("")
        with patch("riszotto.config.CONFIG_PATH", config_file):
            config = load_config()
        assert config.api_key is None
        assert config.user_id is None

    def test_has_remote_credentials(self):
        assert Config(api_key="k", user_id="u").has_remote_credentials
        assert not Config(api_key="k", user_id=None).has_remote_credentials
        assert not Config().has_remote_credentials
