import json
from unittest.mock import MagicMock, patch

from typer.testing import CliRunner

from riszotto.cli import app

runner = CliRunner()


class TestSearch:
    @patch("riszotto.cli.get_client")
    def test_search_shows_table(self, mock_get_client):
        mock_zot = MagicMock()
        mock_get_client.return_value = mock_zot
        mock_zot.items.return_value = [
            {
                "data": {
                    "key": "ABC12345",
                    "title": "Attention Is All You Need",
                    "date": "2017-06-12",
                    "creators": [
                        {"firstName": "Ashish", "lastName": "Vaswani", "creatorType": "author"},
                        {"firstName": "Noam", "lastName": "Shazeer", "creatorType": "author"},
                    ],
                },
                "meta": {"creatorSummary": "Vaswani et al."},
            }
        ]
        result = runner.invoke(app, ["search", "attention"])
        assert result.exit_code == 0
        assert "ABC12345" in result.output
        assert "2017" in result.output
        assert "Vaswani" in result.output
        assert "Attention Is All You Need" in result.output

    @patch("riszotto.cli.get_client")
    def test_search_no_results(self, mock_get_client):
        mock_zot = MagicMock()
        mock_get_client.return_value = mock_zot
        mock_zot.items.return_value = []
        result = runner.invoke(app, ["search", "nonexistent"])
        assert result.exit_code == 0
        assert "KEY" in result.output  # header still present

    @patch("riszotto.cli.get_client")
    def test_search_full_text_flag(self, mock_get_client):
        mock_zot = MagicMock()
        mock_get_client.return_value = mock_zot
        mock_zot.items.return_value = []
        runner.invoke(app, ["search", "--full-text", "deep learning"])
        mock_zot.items.assert_called_once_with(q="deep learning", qmode="everything", limit=25, start=0)

    @patch("riszotto.cli.get_client")
    def test_search_limit_flag(self, mock_get_client):
        mock_zot = MagicMock()
        mock_get_client.return_value = mock_zot
        mock_zot.items.return_value = []
        runner.invoke(app, ["search", "--limit", "5", "test"])
        mock_zot.items.assert_called_once_with(q="test", qmode="titleCreatorYear", limit=5, start=0)

    @patch("riszotto.cli.get_client")
    def test_search_zotero_not_running(self, mock_get_client):
        mock_get_client.side_effect = ConnectionError("connection refused")
        result = runner.invoke(app, ["search", "test"])
        assert result.exit_code == 1
        assert "Zotero desktop is not running" in result.output

    @patch("riszotto.cli.get_client")
    def test_search_page_flag(self, mock_get_client):
        mock_zot = MagicMock()
        mock_get_client.return_value = mock_zot
        mock_zot.items.return_value = []
        runner.invoke(app, ["search", "--page", "3", "test"])
        mock_zot.items.assert_called_once_with(q="test", qmode="titleCreatorYear", limit=25, start=50)

    @patch("riszotto.cli.get_client")
    def test_search_page_footer(self, mock_get_client):
        mock_zot = MagicMock()
        mock_get_client.return_value = mock_zot
        mock_zot.items.return_value = [
            {
                "data": {"key": "ABC12345", "title": "Paper", "date": "2024", "creators": []},
                "meta": {},
            }
        ]
        result = runner.invoke(app, ["search", "test"])
        assert result.exit_code == 0
        assert "Page 1" in result.output
        assert "--page 2" in result.output


class TestInfo:
    @patch("riszotto.cli.get_client")
    def test_info_outputs_json(self, mock_get_client):
        mock_zot = MagicMock()
        mock_get_client.return_value = mock_zot
        mock_zot.item.return_value = {
            "data": {
                "key": "ABC12345",
                "title": "Test Paper",
                "DOI": "10.1234/test",
                "itemType": "journalArticle",
            }
        }
        result = runner.invoke(app, ["info", "ABC12345"])
        assert result.exit_code == 0
        parsed = json.loads(result.output)
        assert parsed["title"] == "Test Paper"
        assert parsed["DOI"] == "10.1234/test"

    @patch("riszotto.cli.get_client")
    def test_info_invalid_key(self, mock_get_client):
        mock_zot = MagicMock()
        mock_get_client.return_value = mock_zot
        mock_zot.item.side_effect = Exception("Item not found")
        result = runner.invoke(app, ["info", "BADKEY"])
        assert result.exit_code == 1
        assert "not found" in result.output.lower()


class TestShow:
    @patch("riszotto.cli.MarkItDown")
    @patch("riszotto.cli.get_client")
    def test_show_converts_pdf(self, mock_get_client, mock_markitdown_cls):
        mock_zot = MagicMock()
        mock_get_client.return_value = mock_zot
        mock_zot.children.return_value = [
            {
                "data": {"key": "ATT1", "itemType": "attachment", "contentType": "application/pdf", "filename": "paper.pdf"},
                "links": {"enclosure": {"href": "file:///Users/me/Zotero/storage/ATT1/paper.pdf"}},
            }
        ]
        mock_md = MagicMock()
        mock_markitdown_cls.return_value = mock_md
        mock_result = MagicMock()
        mock_result.markdown = "# Paper Title\n\nSome content here."
        mock_md.convert.return_value = mock_result

        result = runner.invoke(app, ["show", "PARENT1"])
        assert result.exit_code == 0
        assert "# Paper Title" in result.output
        mock_md.convert.assert_called_once_with("/Users/me/Zotero/storage/ATT1/paper.pdf")

    @patch("riszotto.cli.get_client")
    def test_show_no_pdf_attachment(self, mock_get_client):
        mock_zot = MagicMock()
        mock_get_client.return_value = mock_zot
        mock_zot.children.return_value = [
            {"data": {"key": "NOTE1", "itemType": "note"}, "links": {}},
        ]
        result = runner.invoke(app, ["show", "PARENT1"])
        assert result.exit_code == 1
        assert "No PDF attachment" in result.output

    @patch("riszotto.cli.MarkItDown")
    @patch("riszotto.cli.get_client")
    def test_show_attachment_flag(self, mock_get_client, mock_markitdown_cls):
        mock_zot = MagicMock()
        mock_get_client.return_value = mock_zot
        mock_zot.children.return_value = [
            {
                "data": {"key": "ATT1", "itemType": "attachment", "contentType": "application/pdf", "filename": "paper1.pdf"},
                "links": {"enclosure": {"href": "file:///path/to/paper1.pdf"}},
            },
            {
                "data": {"key": "ATT2", "itemType": "attachment", "contentType": "application/pdf", "filename": "paper2.pdf"},
                "links": {"enclosure": {"href": "file:///path/to/paper2.pdf"}},
            },
        ]
        mock_md = MagicMock()
        mock_markitdown_cls.return_value = mock_md
        mock_result = MagicMock()
        mock_result.markdown = "Second PDF content"
        mock_md.convert.return_value = mock_result

        result = runner.invoke(app, ["show", "--attachment", "2", "PARENT1"])
        assert result.exit_code == 0
        mock_md.convert.assert_called_once_with("/path/to/paper2.pdf")


class TestInfoMaxValueSize:
    @patch("riszotto.cli.get_client")
    def test_info_hides_long_values(self, mock_get_client):
        mock_zot = MagicMock()
        mock_get_client.return_value = mock_zot
        mock_zot.item.return_value = {
            "data": {
                "key": "ABC12345",
                "title": "Short",
                "abstractNote": "A" * 300,
            }
        }
        result = runner.invoke(app, ["info", "ABC12345"])
        assert result.exit_code == 0
        parsed = json.loads(result.output)
        assert parsed["title"] == "Short"
        assert parsed["abstractNote"] == "<hidden (300 chars)>"

    @patch("riszotto.cli.get_client")
    def test_info_max_value_size_zero_shows_all(self, mock_get_client):
        mock_zot = MagicMock()
        mock_get_client.return_value = mock_zot
        long_abstract = "A" * 300
        mock_zot.item.return_value = {
            "data": {
                "key": "ABC12345",
                "title": "Short",
                "abstractNote": long_abstract,
            }
        }
        result = runner.invoke(app, ["info", "--max-value-size", "0", "ABC12345"])
        assert result.exit_code == 0
        parsed = json.loads(result.output)
        assert parsed["abstractNote"] == long_abstract

    @patch("riszotto.cli.get_client")
    def test_info_max_value_size_custom(self, mock_get_client):
        mock_zot = MagicMock()
        mock_get_client.return_value = mock_zot
        mock_zot.item.return_value = {
            "data": {
                "key": "ABC12345",
                "title": "Short title",
                "abstractNote": "A" * 100,
            }
        }
        result = runner.invoke(app, ["info", "--max-value-size", "50", "ABC12345"])
        assert result.exit_code == 0
        parsed = json.loads(result.output)
        assert parsed["title"] == "Short title"  # 11 chars, under 50
        assert parsed["abstractNote"] == "<hidden (100 chars)>"
