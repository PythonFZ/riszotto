from pathlib import Path
from unittest.mock import patch

import pytest


@pytest.fixture(autouse=True)
def _suppress_legacy_migration(tmp_path):
    """Prevent legacy migration warnings from polluting test output."""
    with patch("riszotto.paths.LEGACY_DIR", tmp_path / "nonexistent"):
        yield
