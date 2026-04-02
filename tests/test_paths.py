# tests/test_paths.py


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
