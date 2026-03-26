# tests/test_converter_base.py
from pathlib import Path

from riszotto.converter.base import ConversionResult, StyleOption, BackendName


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
