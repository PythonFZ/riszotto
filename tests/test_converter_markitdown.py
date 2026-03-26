# tests/test_converter_markitdown.py
from pathlib import Path
from unittest.mock import MagicMock, patch

from riszotto.converter.markitdown import MarkItDownConverter


class TestMarkItDownConverter:
    @patch("riszotto.converter.markitdown.MarkItDown")
    def test_convert_returns_markdown(self, mock_markitdown_cls):
        mock_md = MagicMock()
        mock_markitdown_cls.return_value = mock_md
        mock_result = MagicMock()
        mock_result.markdown = "# Title\n\nContent here."
        mock_md.convert.return_value = mock_result

        converter = MarkItDownConverter()
        result = converter.convert(Path("/fake/paper.pdf"), zotero_key="ABC123")

        assert result.markdown == "# Title\n\nContent here."
        assert result.figures == {}
        mock_md.convert.assert_called_once_with(Path("/fake/paper.pdf"))

    @patch("riszotto.converter.markitdown.MarkItDown")
    def test_ignores_style_flags(self, mock_markitdown_cls):
        mock_md = MagicMock()
        mock_markitdown_cls.return_value = mock_md
        mock_result = MagicMock()
        mock_result.markdown = "text"
        mock_md.convert.return_value = mock_result

        converter = MarkItDownConverter()
        result = converter.convert(
            Path("/fake/paper.pdf"),
            table_style="image",
            equation_style="image",
            zotero_key="ABC123",
            no_cache=True,
        )
        assert result.markdown == "text"
        assert result.figures == {}

    @patch("riszotto.converter.markitdown.MarkItDown")
    def test_suppresses_logging(self, mock_markitdown_cls):
        import logging

        mock_md = MagicMock()
        mock_markitdown_cls.return_value = mock_md
        mock_result = MagicMock()
        mock_result.markdown = "text"
        mock_md.convert.return_value = mock_result

        converter = MarkItDownConverter()
        converter.convert(Path("/fake/paper.pdf"), zotero_key="KEY1")

        # After convert, logging should be re-enabled
        assert logging.root.manager.disable < logging.CRITICAL
