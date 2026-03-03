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
        mock_zot.items.assert_called_once_with(q="test query", qmode="titleCreatorYear", limit=25)
        assert len(results) == 1
        assert results[0]["data"]["key"] == "ABC123"

    def test_search_full_text_mode(self):
        mock_zot = MagicMock()
        mock_zot.items.return_value = []
        search_items(mock_zot, "test query", full_text=True, limit=10)
        mock_zot.items.assert_called_once_with(q="test query", qmode="everything", limit=10)


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
