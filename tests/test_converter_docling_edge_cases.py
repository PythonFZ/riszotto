"""Edge-case tests for _process_items() with surgical mocks."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

docling = pytest.importorskip("docling")

from docling_core.types.doc import FormulaItem, PictureItem, TableItem  # noqa: E402

from riszotto.converter.docling import _process_items  # noqa: E402


class TestProcessItemsEdgeCases:
    def test_picture_get_image_none(self, tmp_path):
        item = MagicMock(spec=PictureItem)
        item.get_image.return_value = None

        parts, figures = _process_items(
            [(item, 0)],
            doc=MagicMock(),
            cache_path=tmp_path,
            table_style="inline",
            equation_mode="image",
        )

        assert len(parts) == 1
        assert "image not available" in parts[0]
        assert len(figures) == 0

    def test_table_image_fallback_to_inline(self, tmp_path):
        mock_df = MagicMock()
        mock_df.to_markdown.return_value = "| A |\n|---|\n| 1 |"

        item = MagicMock(spec=TableItem)
        item.get_image.return_value = None
        item.export_to_dataframe.return_value = mock_df

        parts, figures = _process_items(
            [(item, 0)],
            doc=MagicMock(),
            cache_path=tmp_path,
            table_style="image",
            equation_mode="image",
        )

        assert len(parts) == 1
        assert "| A |" in parts[0]
        assert len(figures) == 0

    def test_formula_image_fallback_to_latex(self, tmp_path):
        item = MagicMock(spec=FormulaItem)
        item.get_image.return_value = None
        item.text = "E = mc^2"

        parts, figures = _process_items(
            [(item, 0)],
            doc=MagicMock(),
            cache_path=tmp_path,
            table_style="inline",
            equation_mode="image",
        )

        assert len(parts) == 1
        assert "$$E = mc^2$$" in parts[0]
        assert len(figures) == 0

    def test_formula_no_image_no_text(self, tmp_path):
        item = MagicMock(spec=FormulaItem)
        item.get_image.return_value = None
        item.text = ""

        parts, figures = _process_items(
            [(item, 0)],
            doc=MagicMock(),
            cache_path=tmp_path,
            table_style="inline",
            equation_mode="image",
        )

        assert len(parts) == 1
        assert "not available" in parts[0]
        assert len(figures) == 0
