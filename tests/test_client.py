from unittest.mock import MagicMock, patch

from riszotto.client import (
    DEFAULT_BIBTEX_EXCLUDE,
    _filter_bibtex_fields,
    collection_items,
    get_client,
    get_item,
    get_item_bibtex,
    get_pdf_attachments,
    get_pdf_path,
    list_collections,
    recent_items,
    search_items,
)


class TestGetClient:
    def test_returns_zotero_instance(self):
        with patch("riszotto.client.zotero.Zotero") as mock_zotero:
            client = get_client()
            mock_zotero.assert_called_once_with(
                library_id="0",
                library_type="user",
                api_key=None,
                local=True,
            )


class TestSearchItems:
    def test_search_default_mode(self):
        mock_zot = MagicMock()
        mock_zot.items.return_value = [
            {
                "data": {
                    "key": "ABC123",
                    "title": "Test Paper",
                    "date": "2024-01-15",
                    "creators": [{"firstName": "John", "lastName": "Doe", "creatorType": "author"}],
                },
                "meta": {"creatorSummary": "Doe et al."},
            }
        ]
        results = search_items(mock_zot, "test query", full_text=False, limit=25)
        mock_zot.items.assert_called_once_with(q="test query", qmode="titleCreatorYear", limit=25, start=0)
        assert len(results) == 1
        assert results[0]["data"]["key"] == "ABC123"

    def test_search_full_text_mode(self):
        mock_zot = MagicMock()
        mock_zot.items.return_value = []
        search_items(mock_zot, "test query", full_text=True, limit=10)
        mock_zot.items.assert_called_once_with(q="test query", qmode="everything", limit=10, start=0)

    def test_search_with_start_offset(self):
        mock_zot = MagicMock()
        mock_zot.items.return_value = []
        search_items(mock_zot, "test", full_text=False, limit=25, start=50)
        mock_zot.items.assert_called_once_with(q="test", qmode="titleCreatorYear", limit=25, start=50)

    def test_search_default_start_is_zero(self):
        mock_zot = MagicMock()
        mock_zot.items.return_value = []
        search_items(mock_zot, "test", full_text=False, limit=25)
        mock_zot.items.assert_called_once_with(q="test", qmode="titleCreatorYear", limit=25, start=0)

    def test_search_resolves_attachments_to_parents(self):
        mock_zot = MagicMock()
        mock_zot.items.return_value = [
            {"data": {"key": "ATT1", "itemType": "attachment", "parentItem": "PAPER1"}},
            {"data": {"key": "PAPER2", "itemType": "journalArticle", "title": "Direct Hit"}},
            {"data": {"key": "ATT2", "itemType": "attachment", "parentItem": "PAPER1"}},
            {"data": {"key": "NOTE1", "itemType": "note", "parentItem": "PAPER3"}},
        ]
        mock_zot.item.side_effect = lambda key: {
            "PAPER1": {"data": {"key": "PAPER1", "itemType": "journalArticle", "title": "Resolved Paper"}},
            "PAPER3": {"data": {"key": "PAPER3", "itemType": "journalArticle", "title": "From Note"}},
        }[key]

        results = search_items(mock_zot, "test", full_text=True, limit=25)
        keys = [r["data"]["key"] for r in results]
        assert keys == ["PAPER1", "PAPER2", "PAPER3"]
        # PAPER1 fetched only once despite two attachments
        mock_zot.item.assert_any_call("PAPER1")
        mock_zot.item.assert_any_call("PAPER3")
        assert mock_zot.item.call_count == 2

    def test_search_keeps_parent_items_as_is(self):
        mock_zot = MagicMock()
        mock_zot.items.return_value = [
            {"data": {"key": "P1", "itemType": "journalArticle", "title": "Paper 1"}},
            {"data": {"key": "P2", "itemType": "conferencePaper", "title": "Paper 2"}},
        ]
        results = search_items(mock_zot, "test", full_text=False, limit=25)
        assert len(results) == 2
        assert results[0]["data"]["key"] == "P1"
        assert results[1]["data"]["key"] == "P2"
        mock_zot.item.assert_not_called()

    def test_search_with_tag_filter(self):
        mock_zot = MagicMock()
        mock_zot.items.return_value = []
        search_items(mock_zot, "test", full_text=False, limit=25, tag=["physics"])
        mock_zot.items.assert_called_once_with(
            q="test", qmode="titleCreatorYear", limit=25, start=0, tag="physics"
        )

    def test_search_with_multiple_tags(self):
        mock_zot = MagicMock()
        mock_zot.items.return_value = []
        search_items(mock_zot, "test", full_text=False, limit=25, tag=["ml", "physics"])
        mock_zot.items.assert_called_once_with(
            q="test", qmode="titleCreatorYear", limit=25, start=0, tag=["ml", "physics"]
        )

    def test_search_with_item_type(self):
        mock_zot = MagicMock()
        mock_zot.items.return_value = []
        search_items(mock_zot, "test", full_text=False, limit=25, item_type="book")
        mock_zot.items.assert_called_once_with(
            q="test", qmode="titleCreatorYear", limit=25, start=0, itemType="book"
        )

    def test_search_with_since(self):
        mock_zot = MagicMock()
        mock_zot.items.return_value = []
        search_items(mock_zot, "test", full_text=False, limit=25, since="2024-01-01")
        mock_zot.items.assert_called_once_with(
            q="test", qmode="titleCreatorYear", limit=25, start=0, since="2024-01-01"
        )

    def test_search_with_sort(self):
        mock_zot = MagicMock()
        mock_zot.items.return_value = []
        search_items(mock_zot, "test", full_text=False, limit=25, sort="dateModified", direction="asc")
        mock_zot.items.assert_called_once_with(
            q="test", qmode="titleCreatorYear", limit=25, start=0, sort="dateModified", direction="asc"
        )


class TestGetItem:
    def test_returns_item(self):
        mock_zot = MagicMock()
        mock_zot.item.return_value = {"data": {"key": "ABC123", "title": "Test"}}
        result = get_item(mock_zot, "ABC123")
        mock_zot.item.assert_called_once_with("ABC123")
        assert result["data"]["title"] == "Test"


class TestGetPdfAttachments:
    def test_filters_pdf_children(self):
        mock_zot = MagicMock()
        mock_zot.children.return_value = [
            {
                "data": {"key": "ATT1", "itemType": "attachment", "contentType": "application/pdf", "filename": "paper.pdf"},
                "links": {"enclosure": {"href": "file:///path/to/paper.pdf"}},
            },
            {
                "data": {"key": "NOTE1", "itemType": "note"},
                "links": {},
            },
        ]
        pdfs = get_pdf_attachments(mock_zot, "PARENT1")
        assert len(pdfs) == 1
        assert pdfs[0]["data"]["key"] == "ATT1"

    def test_no_attachments(self):
        mock_zot = MagicMock()
        mock_zot.children.return_value = []
        pdfs = get_pdf_attachments(mock_zot, "PARENT1")
        assert pdfs == []


class TestListCollections:
    def test_returns_collections(self):
        mock_zot = MagicMock()
        mock_zot.collections.return_value = [
            {"data": {"key": "COL1", "name": "Physics", "parentCollection": False}},
            {"data": {"key": "COL2", "name": "Subfield", "parentCollection": "COL1"}},
        ]
        result = list_collections(mock_zot)
        mock_zot.collections.assert_called_once()
        assert len(result) == 2
        assert result[0]["data"]["key"] == "COL1"

    def test_returns_empty_list(self):
        mock_zot = MagicMock()
        mock_zot.collections.return_value = []
        result = list_collections(mock_zot)
        assert result == []


class TestCollectionItems:
    def test_returns_items(self):
        mock_zot = MagicMock()
        mock_zot.collection_items.return_value = [
            {"data": {"key": "P1", "title": "Paper 1"}},
        ]
        result = collection_items(mock_zot, "COL1", limit=10, start=0)
        mock_zot.collection_items.assert_called_once_with("COL1", limit=10, start=0)
        assert len(result) == 1

    def test_default_pagination(self):
        mock_zot = MagicMock()
        mock_zot.collection_items.return_value = []
        collection_items(mock_zot, "COL1")
        mock_zot.collection_items.assert_called_once_with("COL1", limit=25, start=0)


class TestRecentItems:
    def test_returns_recent_items(self):
        mock_zot = MagicMock()
        mock_zot.items.return_value = [
            {"data": {"key": "P1", "title": "Recent Paper"}},
        ]
        result = recent_items(mock_zot, limit=5)
        mock_zot.items.assert_called_once_with(
            sort="dateAdded", direction="desc", limit=5, itemType="-attachment"
        )
        assert len(result) == 1

    def test_default_limit(self):
        mock_zot = MagicMock()
        mock_zot.items.return_value = []
        recent_items(mock_zot)
        mock_zot.items.assert_called_once_with(
            sort="dateAdded", direction="desc", limit=10, itemType="-attachment"
        )


class TestGetItemBibtex:
    def test_decodes_bytes(self):
        mock_zot = MagicMock()
        bibtex_bytes = b"@article{doe2024, title={Test}}"
        mock_zot.item.return_value = bibtex_bytes
        result = get_item_bibtex(mock_zot, "ABC123")
        mock_zot.item.assert_called_once_with("ABC123", format="bibtex")
        assert result == "@article{doe2024, title={Test}}"

    def test_handles_string(self):
        mock_zot = MagicMock()
        mock_zot.item.return_value = "@article{doe2024, title={Test}}"
        result = get_item_bibtex(mock_zot, "ABC123")
        assert result == "@article{doe2024, title={Test}}"

    def test_exclude_strips_fields(self):
        mock_zot = MagicMock()
        bibtex = (
            "@article{doe2024,\n"
            "  title = {Test},\n"
            "  abstract = {Long abstract text},\n"
            "  author = {Doe, John}\n"
            "}"
        )
        mock_zot.item.return_value = bibtex.encode()
        result = get_item_bibtex(mock_zot, "ABC123", exclude={"abstract"})
        assert "abstract" not in result
        assert "title = {Test}" in result
        assert "author = {Doe, John}" in result

    def test_exclude_empty_set_keeps_all(self):
        mock_zot = MagicMock()
        bibtex = "@article{doe2024,\n  title = {Test},\n  abstract = {Abs}\n}"
        mock_zot.item.return_value = bibtex.encode()
        result = get_item_bibtex(mock_zot, "ABC123", exclude=set())
        assert "abstract = {Abs}" in result

    def test_exclude_none_keeps_all(self):
        mock_zot = MagicMock()
        bibtex = "@article{doe2024,\n  title = {Test},\n  abstract = {Abs}\n}"
        mock_zot.item.return_value = bibtex.encode()
        result = get_item_bibtex(mock_zot, "ABC123")
        assert "abstract = {Abs}" in result


class TestFilterBibtexFields:
    def test_removes_single_line_field(self):
        bibtex = (
            "@article{doe2024,\n"
            "  title = {Test Paper},\n"
            "  file = {/path/to/file.pdf},\n"
            "  author = {Doe, John}\n"
            "}"
        )
        result = _filter_bibtex_fields(bibtex, {"file"})
        assert "file" not in result
        assert "title = {Test Paper}" in result
        assert "author = {Doe, John}" in result

    def test_removes_multiline_field(self):
        bibtex = (
            "@article{doe2024,\n"
            "  title = {Test},\n"
            "  abstract = {This is a long\n"
            "abstract that spans\n"
            "multiple lines},\n"
            "  author = {Doe, John}\n"
            "}"
        )
        result = _filter_bibtex_fields(bibtex, {"abstract"})
        assert "abstract" not in result
        assert "multiple lines" not in result
        assert "title = {Test}" in result
        assert "author = {Doe, John}" in result

    def test_removes_multiple_fields(self):
        bibtex = (
            "@article{doe2024,\n"
            "  title = {Test},\n"
            "  file = {/path.pdf},\n"
            "  abstract = {Abs},\n"
            "  note = {Some note},\n"
            "  author = {Doe}\n"
            "}"
        )
        result = _filter_bibtex_fields(bibtex, {"file", "abstract", "note"})
        assert "file" not in result
        assert "abstract" not in result
        assert "note" not in result
        assert "title = {Test}" in result
        assert "author = {Doe}" in result

    def test_default_exclude_set_has_expected_fields(self):
        assert "file" in DEFAULT_BIBTEX_EXCLUDE
        assert "abstract" in DEFAULT_BIBTEX_EXCLUDE
        assert "note" in DEFAULT_BIBTEX_EXCLUDE
        assert "keywords" in DEFAULT_BIBTEX_EXCLUDE
        assert "urldate" in DEFAULT_BIBTEX_EXCLUDE
        assert "annote" in DEFAULT_BIBTEX_EXCLUDE

    def test_no_trailing_comma_before_closing_brace(self):
        bibtex = (
            "@article{doe2024,\n"
            "  title = {Test},\n"
            "  file = {/path.pdf}\n"
            "}"
        )
        result = _filter_bibtex_fields(bibtex, {"file"})
        assert ",\n}" not in result


class TestGetPdfPath:
    def test_extracts_file_path(self):
        attachment = {
            "links": {
                "enclosure": {
                    "href": "file:///Users/me/Zotero/storage/ABC123/paper.pdf",
                }
            }
        }
        path = get_pdf_path(attachment)
        assert path == "/Users/me/Zotero/storage/ABC123/paper.pdf"

    def test_no_enclosure_returns_none(self):
        attachment = {"links": {}}
        path = get_pdf_path(attachment)
        assert path is None
