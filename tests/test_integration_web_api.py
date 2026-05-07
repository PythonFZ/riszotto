"""End-to-end tests against the real Zotero Web API.

Skipped unless ``RISZOTTO_ZOTERO_API_KEY`` and ``RISZOTTO_ZOTERO_USER_ID`` are
set. The default unit-test run does not collect these (filtered by the
``integration`` marker in ``pyproject.toml``). The integration CI workflow
runs them with ``pytest -m integration``.
"""

from __future__ import annotations

import os

import pytest

from riszotto.client import (
    PdfNotOnStorageError,
    get_client,
    get_pdf_attachments,
    resolve_pdf_path,
    search_items,
)
from riszotto.config import load_config

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(
        not os.environ.get("RISZOTTO_ZOTERO_API_KEY")
        or not os.environ.get("RISZOTTO_ZOTERO_USER_ID"),
        reason="requires RISZOTTO_ZOTERO_API_KEY and RISZOTTO_ZOTERO_USER_ID",
    ),
]


def _require(env: str) -> str:
    val = os.environ.get(env)
    if not val:
        pytest.skip(f"requires {env}")
    return val


def test_personal_library_search_hits_web_api():
    """Auto + creds → personal library uses the Web API and returns results."""
    config = load_config()
    assert config.has_remote_credentials
    zot = get_client()
    results = search_items(zot, "the", limit=1)
    assert isinstance(results, list)


def test_group_library_search_hits_web_api():
    group_id = _require("RISZOTTO_TEST_GROUP_ID")
    zot = get_client(library=group_id)
    results = search_items(zot, "the", limit=1)
    assert isinstance(results, list)


def test_show_downloads_pdf_and_caches_it(tmp_path, monkeypatch):
    """First call downloads from Zotero storage; second hits the PDF cache."""
    monkeypatch.setattr("riszotto.pdf_cache.PDF_CACHE_DIR", tmp_path)

    group_id = _require("RISZOTTO_TEST_GROUP_ID")
    item_key = _require("RISZOTTO_TEST_GROUP_ITEM_KEY")
    zot = get_client(library=group_id)
    attachments = get_pdf_attachments(zot, item_key)
    assert attachments, f"no PDF children on {item_key}"
    att = attachments[0]
    md5 = att["data"].get("md5")
    assert md5, "test fixture must point at a synced (md5-populated) attachment"

    path1 = resolve_pdf_path(zot, att)
    assert path1.is_file()
    assert path1.name == f"{md5}.pdf"
    size_after_download = path1.stat().st_size

    def _fail(*args, **kwargs):
        raise AssertionError("zot.dump must not be called on cache hit")

    monkeypatch.setattr(zot, "dump", _fail)
    path2 = resolve_pdf_path(zot, att)
    assert path2 == path1
    assert path2.stat().st_size == size_after_download


def test_libraries_command_works_without_local_zotero():
    """`riszotto libraries` returns 0 when Zotero desktop is unreachable.

    On CI runners there is no Zotero desktop; the command must enumerate
    libraries via the Web API and not surface an httpx.ConnectError to the
    user. Regression for the bug where _discover_libraries hardcoded
    local=True for group clients regardless of the active mode.
    """
    from typer.testing import CliRunner

    from riszotto.cli import app

    result = CliRunner().invoke(app, ["libraries"])
    assert result.exit_code == 0, (
        f"libraries exit {result.exit_code}\n--- output ---\n{result.output}"
    )
    assert "My Library" in result.output
    # The "Connection refused" httpx error must never reach the user.
    assert "Connection refused" not in result.output
    assert "Traceback" not in result.output


def test_personal_md5_null_raises_clean_error(tmp_path, monkeypatch):
    """Personal-library items with md5=None surface PdfNotOnStorageError."""
    monkeypatch.setattr("riszotto.pdf_cache.PDF_CACHE_DIR", tmp_path)

    item_key = _require("RISZOTTO_TEST_PERSONAL_ITEM_KEY")
    zot = get_client()
    attachments = get_pdf_attachments(zot, item_key)
    assert attachments, f"no PDF children on {item_key}"
    att = attachments[0]
    assert att["data"].get("md5") is None, (
        "fixture must be a non-synced (md5=None) attachment"
    )

    with pytest.raises(PdfNotOnStorageError) as exc_info:
        resolve_pdf_path(zot, att)
    assert att["key"] in str(exc_info.value)
