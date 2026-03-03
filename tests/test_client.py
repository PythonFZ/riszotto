from unittest.mock import MagicMock, patch

from riszotto.client import get_client, search_items, get_item, get_pdf_attachments, get_pdf_path


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
