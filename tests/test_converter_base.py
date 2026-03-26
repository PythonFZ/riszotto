# tests/test_converter_base.py
from unittest.mock import patch

import pytest

from riszotto.converter import get_converter
from riszotto.converter.base import BackendName, ConversionResult, StyleOption
from riszotto.converter.markitdown import MarkItDownConverter


class TestConversionResult:
    def test_creation_with_defaults(self):
        result = ConversionResult(markdown="# Hello")
        assert result.markdown == "# Hello"
        assert result.figures == {}

    def test_creation_with_figures(self, tmp_path):
        fig_path = tmp_path / "figure_1.png"
        fig_path.write_bytes(b"PNG")
        result = ConversionResult(
            markdown="![Figure 1](fig)",
            figures={"figure_1.png": fig_path},
        )
        assert result.figures["figure_1.png"] == fig_path


class TestTypeAliases:
    def test_style_option_values(self):
        inline: StyleOption = "inline"
        image: StyleOption = "image"
        assert inline == "inline"
        assert image == "image"

    def test_backend_name_values(self):
        mk: BackendName = "markitdown"
        dl: BackendName = "docling"
        assert mk == "markitdown"
        assert dl == "docling"


class TestGetConverter:
    def test_explicit_markitdown(self):
        converter = get_converter("markitdown")
        assert isinstance(converter, MarkItDownConverter)

    def test_explicit_docling_when_unavailable(self):
        with patch("riszotto.converter.docling.DOCLING_AVAILABLE", False):
            with pytest.raises(ImportError, match="riszotto\\[full\\]"):
                get_converter("docling")

    def test_auto_falls_back_to_markitdown(self):
        with patch("riszotto.converter.docling.DOCLING_AVAILABLE", False):
            converter = get_converter(None)
            assert isinstance(converter, MarkItDownConverter)

    def test_auto_returns_markitdown_when_no_docling_module(self):
        """When docling package isn't installed at all."""
        converter = get_converter("markitdown")
        assert isinstance(converter, MarkItDownConverter)
