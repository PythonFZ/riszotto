# tests/test_paths.py
import os
from pathlib import Path
from unittest.mock import patch

import pytest


class TestPaths:
    def test_config_path_uses_platformdirs(self):
        from riszotto.paths import CONFIG_PATH

        assert CONFIG_PATH.name == "config.toml"
        assert "riszotto" in str(CONFIG_PATH)

    def test_chroma_dir_uses_platformdirs(self):
        from riszotto.paths import CHROMA_DIR

        assert CHROMA_DIR.name == "chroma_db"
        assert "riszotto" in str(CHROMA_DIR)

    def test_conversion_cache_dir_uses_platformdirs(self):
        from riszotto.paths import CONVERSION_CACHE_DIR

        assert CONVERSION_CACHE_DIR.name == "conversions"
        assert "riszotto" in str(CONVERSION_CACHE_DIR)


class TestLegacyMigration:
    def test_no_warning_when_no_legacy_dir(self, tmp_path, capsys):
        legacy = tmp_path / ".riszotto"
        # Don't create it — it doesn't exist
        with patch("riszotto.paths.LEGACY_DIR", legacy):
            from riszotto.paths import check_legacy_migration

            check_legacy_migration()
        assert capsys.readouterr().err == ""

    def test_warns_about_legacy_config(self, tmp_path, capsys):
        legacy = tmp_path / ".riszotto"
        legacy.mkdir()
        (legacy / "config.toml").write_text('[zotero]\napi_key = "x"\n')
        new_config = tmp_path / "new_config" / "config.toml"
        with (
            patch("riszotto.paths.LEGACY_DIR", legacy),
            patch("riszotto.paths.CONFIG_PATH", new_config),
            patch("riszotto.paths.config_dir", return_value=tmp_path / "new_config"),
        ):
            from riszotto.paths import check_legacy_migration

            check_legacy_migration()
        assert "legacy config" in capsys.readouterr().err.lower()

    def test_warns_about_legacy_chroma(self, tmp_path, capsys):
        legacy = tmp_path / ".riszotto"
        legacy.mkdir()
        (legacy / "chroma_db").mkdir()
        new_chroma = tmp_path / "new_data" / "chroma_db"
        with (
            patch("riszotto.paths.LEGACY_DIR", legacy),
            patch("riszotto.paths.CONFIG_PATH", tmp_path / "new_config" / "config.toml"),
            patch("riszotto.paths.CHROMA_DIR", new_chroma),
            patch("riszotto.paths.config_dir", return_value=tmp_path / "new_config"),
        ):
            from riszotto.paths import check_legacy_migration

            check_legacy_migration()
        assert "legacy index" in capsys.readouterr().err.lower()

    def test_no_warning_when_new_paths_already_exist(self, tmp_path, capsys):
        legacy = tmp_path / ".riszotto"
        legacy.mkdir()
        (legacy / "config.toml").write_text('[zotero]\napi_key = "x"\n')
        new_config = tmp_path / "new_config" / "config.toml"
        new_config.parent.mkdir(parents=True)
        new_config.write_text('[zotero]\napi_key = "y"\n')
        with (
            patch("riszotto.paths.LEGACY_DIR", legacy),
            patch("riszotto.paths.CONFIG_PATH", new_config),
            patch("riszotto.paths.config_dir", return_value=tmp_path / "new_config"),
        ):
            from riszotto.paths import check_legacy_migration

            check_legacy_migration()
        assert "legacy config" not in capsys.readouterr().err.lower()
