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
        mock_zot.items.assert_called_once_with(q="deep learning", qmode="everything", limit=25)

    @patch("riszotto.cli.get_client")
    def test_search_limit_flag(self, mock_get_client):
        mock_zot = MagicMock()
        mock_get_client.return_value = mock_zot
        mock_zot.items.return_value = []
        runner.invoke(app, ["search", "--limit", "5", "test"])
        mock_zot.items.assert_called_once_with(q="test", qmode="titleCreatorYear", limit=5)

    @patch("riszotto.cli.get_client")
    def test_search_zotero_not_running(self, mock_get_client):
        mock_get_client.side_effect = ConnectionError("connection refused")
        result = runner.invoke(app, ["search", "test"])
        assert result.exit_code == 1
        assert "Zotero desktop is not running" in result.output
