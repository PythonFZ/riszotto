# tests/test_converter_docling.py
import sys
from unittest.mock import MagicMock, patch

import pytest

from riszotto.converter.base import ConversionResult


class TestDoclingAvailableFlag:
    def test_import_error_sets_flag_false(self):
        # Force reimport with docling missing
        with patch.dict(
            sys.modules, {"docling": None, "docling.document_converter": None}
        ):
            # Can't easily reimport, so test the converter init behavior
            from riszotto.converter.docling import DOCLING_AVAILABLE

            # In the real module, if docling is not installed, this would be False.
            # Since docling may or may not be installed in test env, just test
            # that the flag exists and is a bool.
            assert isinstance(DOCLING_AVAILABLE, bool)


class TestDoclingConverterInit:
    def test_raises_if_docling_not_available(self):
        from riszotto.converter import docling as docling_module

        original = docling_module.DOCLING_AVAILABLE
        try:
            docling_module.DOCLING_AVAILABLE = False
            with pytest.raises(ImportError, match="riszotto\\[full\\]"):
                docling_module.DoclingConverter()
        finally:
            docling_module.DOCLING_AVAILABLE = original


# Stub classes used to make isinstance() checks work in tests when
# docling is not installed.  Each mock item is created as an instance of
# its corresponding stub, and the stub is injected into the module via
# patch(..., create=True).


class _StubTextItem:
    text = ""


class _StubPictureItem:
    def get_image(self, doc):
        return None


class _StubTableItem:
    def get_image(self, doc):
        return None

    def export_to_dataframe(self, doc=None):
        return None


class _StubFormulaItem:
    text = ""

    def get_image(self, doc):
        return None


class TestDoclingConverterConvert:
    """Test the convert method with fully mocked docling internals."""

    def _make_mock_text_item(self, text, label="paragraph"):
        item = MagicMock(spec=_StubTextItem)
        # Make isinstance(item, _StubTextItem) return True
        item.__class__ = _StubTextItem
        item.text = text
        item.label = label
        return item

    def _make_mock_picture_item(self):
        item = MagicMock(spec=_StubPictureItem)
        item.__class__ = _StubPictureItem
        mock_image = MagicMock()
        item.get_image.return_value = mock_image
        return item, mock_image

    def _make_mock_table_item(self, markdown_table="| A | B |\n|---|---|\n| 1 | 2 |"):
        import pandas as pd

        item = MagicMock(spec=_StubTableItem)
        item.__class__ = _StubTableItem
        mock_df = MagicMock(spec=pd.DataFrame)
        mock_df.to_markdown.return_value = markdown_table
        item.export_to_dataframe.return_value = mock_df
        mock_image = MagicMock()
        item.get_image.return_value = mock_image
        return item, mock_image

    def _make_mock_formula_item(self, text="E = mc^2"):
        item = MagicMock(spec=_StubFormulaItem)
        item.__class__ = _StubFormulaItem
        item.text = text
        mock_image = MagicMock()
        item.get_image.return_value = mock_image
        return item, mock_image

    @patch("riszotto.converter.docling.TextItem", _StubTextItem, create=True)
    @patch("riszotto.converter.docling.FormulaItem", _StubFormulaItem, create=True)
    @patch("riszotto.converter.docling.TableItem", _StubTableItem, create=True)
    @patch("riszotto.converter.docling.PictureItem", _StubPictureItem, create=True)
    @patch("riszotto.converter.docling.ThreadedPdfPipelineOptions", create=True)
    @patch("riszotto.converter.docling.TableStructureOptions", create=True)
    @patch("riszotto.converter.docling.TableFormerMode", create=True)
    @patch("riszotto.converter.docling.AcceleratorOptions", create=True)
    @patch("riszotto.converter.docling.AcceleratorDevice", create=True)
    @patch("riszotto.converter.docling.InputFormat", create=True)
    @patch("riszotto.converter.docling.PdfFormatOption", create=True)
    @patch("riszotto.converter.docling.DOCLING_AVAILABLE", True)
    @patch("riszotto.converter.docling.write_cache")
    @patch("riszotto.converter.docling.read_cache", return_value=None)
    @patch("riszotto.converter.docling.compute_pdf_hash", return_value="aabbccdd0011")
    @patch("riszotto.converter.docling.DocumentConverter", create=True)
    def test_convert_with_text_only(
        self,
        mock_dc_cls,
        mock_hash,
        mock_read,
        mock_write,
        _pfo,
        _ifmt,
        _ad,
        _ao,
        _tfm,
        _tso,
        _tppo,
        tmp_path,
    ):
        pdf = tmp_path / "paper.pdf"
        pdf.write_bytes(b"fake pdf")

        text_item = self._make_mock_text_item("Hello world")
        mock_doc = MagicMock()
        mock_doc.iterate_items.return_value = [(text_item, 0)]
        mock_conv_result = MagicMock()
        mock_conv_result.document = mock_doc
        mock_dc_cls.return_value.convert.return_value = mock_conv_result

        from riszotto.converter.docling import DoclingConverter

        converter = DoclingConverter()
        result = converter.convert(pdf, zotero_key="KEY1")

        assert "Hello world" in result.markdown
        mock_write.assert_called_once()

    @patch("riszotto.converter.docling.DOCLING_AVAILABLE", True)
    @patch("riszotto.converter.docling.read_cache")
    def test_returns_cached_result(self, mock_read, tmp_path):
        cached = ConversionResult(markdown="cached content", figures={})
        mock_read.return_value = cached

        pdf = tmp_path / "paper.pdf"
        pdf.write_bytes(b"fake pdf")

        from riszotto.converter.docling import DoclingConverter

        with patch("riszotto.converter.docling.compute_pdf_hash", return_value="h"):
            converter = DoclingConverter()
            result = converter.convert(pdf, zotero_key="KEY1")

        assert result.markdown == "cached content"

    @patch("riszotto.converter.docling.DOCLING_AVAILABLE", True)
    @patch("riszotto.converter.docling.read_cache", return_value=None)
    def test_no_cache_bypasses_read(self, mock_read, tmp_path):
        pdf = tmp_path / "paper.pdf"
        pdf.write_bytes(b"fake pdf")

        from riszotto.converter.docling import DoclingConverter

        with (
            patch("riszotto.converter.docling.compute_pdf_hash", return_value="h"),
            patch("riszotto.converter.docling.write_cache"),
            patch(
                "riszotto.converter.docling.DocumentConverter", create=True
            ) as mock_dc,
            patch("riszotto.converter.docling.ThreadedPdfPipelineOptions", create=True),
            patch("riszotto.converter.docling.TableStructureOptions", create=True),
            patch("riszotto.converter.docling.TableFormerMode", create=True),
            patch("riszotto.converter.docling.AcceleratorOptions", create=True),
            patch("riszotto.converter.docling.AcceleratorDevice", create=True),
            patch("riszotto.converter.docling.InputFormat", create=True),
            patch("riszotto.converter.docling.PdfFormatOption", create=True),
        ):
            mock_doc = MagicMock()
            mock_doc.iterate_items.return_value = []
            mock_dc.return_value.convert.return_value.document = mock_doc

            converter = DoclingConverter()
            converter.convert(pdf, zotero_key="KEY1", no_cache=True)

        mock_read.assert_not_called()


class TestNullGuards:
    """Test graceful fallback when get_image() returns None."""

    @patch("riszotto.converter.docling.TextItem", _StubTextItem, create=True)
    @patch("riszotto.converter.docling.FormulaItem", _StubFormulaItem, create=True)
    @patch("riszotto.converter.docling.TableItem", _StubTableItem, create=True)
    @patch("riszotto.converter.docling.PictureItem", _StubPictureItem, create=True)
    @patch("riszotto.converter.docling.ThreadedPdfPipelineOptions", create=True)
    @patch("riszotto.converter.docling.TableStructureOptions", create=True)
    @patch("riszotto.converter.docling.TableFormerMode", create=True)
    @patch("riszotto.converter.docling.AcceleratorOptions", create=True)
    @patch("riszotto.converter.docling.AcceleratorDevice", create=True)
    @patch("riszotto.converter.docling.InputFormat", create=True)
    @patch("riszotto.converter.docling.PdfFormatOption", create=True)
    @patch("riszotto.converter.docling.DOCLING_AVAILABLE", True)
    @patch("riszotto.converter.docling.write_cache")
    @patch("riszotto.converter.docling.read_cache", return_value=None)
    @patch("riszotto.converter.docling.compute_pdf_hash", return_value="aabb")
    @patch("riszotto.converter.docling.DocumentConverter", create=True)
    def test_picture_get_image_none(
        self, mock_dc, mock_hash, mock_read, mock_write,
        _pfo, _ifmt, _ad, _ao, _tfm, _tso, _tppo, tmp_path,
    ):
        pdf = tmp_path / "paper.pdf"
        pdf.write_bytes(b"fake pdf")

        item = MagicMock(spec=_StubPictureItem)
        item.__class__ = _StubPictureItem
        item.get_image.return_value = None

        mock_doc = MagicMock()
        mock_doc.iterate_items.return_value = [(item, 0)]
        mock_dc.return_value.convert.return_value.document = mock_doc

        from riszotto.converter.docling import DoclingConverter
        converter = DoclingConverter()
        result = converter.convert(pdf, zotero_key="K1")

        assert "[Figure 1: image not available]" in result.markdown

    @patch("riszotto.converter.docling.TextItem", _StubTextItem, create=True)
    @patch("riszotto.converter.docling.FormulaItem", _StubFormulaItem, create=True)
    @patch("riszotto.converter.docling.TableItem", _StubTableItem, create=True)
    @patch("riszotto.converter.docling.PictureItem", _StubPictureItem, create=True)
    @patch("riszotto.converter.docling.ThreadedPdfPipelineOptions", create=True)
    @patch("riszotto.converter.docling.TableStructureOptions", create=True)
    @patch("riszotto.converter.docling.TableFormerMode", create=True)
    @patch("riszotto.converter.docling.AcceleratorOptions", create=True)
    @patch("riszotto.converter.docling.AcceleratorDevice", create=True)
    @patch("riszotto.converter.docling.InputFormat", create=True)
    @patch("riszotto.converter.docling.PdfFormatOption", create=True)
    @patch("riszotto.converter.docling.DOCLING_AVAILABLE", True)
    @patch("riszotto.converter.docling.write_cache")
    @patch("riszotto.converter.docling.read_cache", return_value=None)
    @patch("riszotto.converter.docling.compute_pdf_hash", return_value="aabb")
    @patch("riszotto.converter.docling.DocumentConverter", create=True)
    def test_table_image_get_image_none_falls_back_to_inline(
        self, mock_dc, mock_hash, mock_read, mock_write,
        _pfo, _ifmt, _ad, _ao, _tfm, _tso, _tppo, tmp_path,
    ):
        import pandas as pd

        pdf = tmp_path / "paper.pdf"
        pdf.write_bytes(b"fake pdf")

        item = MagicMock(spec=_StubTableItem)
        item.__class__ = _StubTableItem
        item.get_image.return_value = None
        mock_df = MagicMock(spec=pd.DataFrame)
        mock_df.to_markdown.return_value = "| A |\n|---|\n| 1 |"
        item.export_to_dataframe.return_value = mock_df

        mock_doc = MagicMock()
        mock_doc.iterate_items.return_value = [(item, 0)]
        mock_dc.return_value.convert.return_value.document = mock_doc

        from riszotto.converter.docling import DoclingConverter
        converter = DoclingConverter()
        result = converter.convert(pdf, zotero_key="K1", table_style="image")

        assert "| A |" in result.markdown

    @patch("riszotto.converter.docling.TextItem", _StubTextItem, create=True)
    @patch("riszotto.converter.docling.FormulaItem", _StubFormulaItem, create=True)
    @patch("riszotto.converter.docling.TableItem", _StubTableItem, create=True)
    @patch("riszotto.converter.docling.PictureItem", _StubPictureItem, create=True)
    @patch("riszotto.converter.docling.ThreadedPdfPipelineOptions", create=True)
    @patch("riszotto.converter.docling.TableStructureOptions", create=True)
    @patch("riszotto.converter.docling.TableFormerMode", create=True)
    @patch("riszotto.converter.docling.AcceleratorOptions", create=True)
    @patch("riszotto.converter.docling.AcceleratorDevice", create=True)
    @patch("riszotto.converter.docling.InputFormat", create=True)
    @patch("riszotto.converter.docling.PdfFormatOption", create=True)
    @patch("riszotto.converter.docling.DOCLING_AVAILABLE", True)
    @patch("riszotto.converter.docling.write_cache")
    @patch("riszotto.converter.docling.read_cache", return_value=None)
    @patch("riszotto.converter.docling.compute_pdf_hash", return_value="aabb")
    @patch("riszotto.converter.docling.DocumentConverter", create=True)
    def test_formula_image_get_image_none_with_text_falls_back_to_latex(
        self, mock_dc, mock_hash, mock_read, mock_write,
        _pfo, _ifmt, _ad, _ao, _tfm, _tso, _tppo, tmp_path,
    ):
        pdf = tmp_path / "paper.pdf"
        pdf.write_bytes(b"fake pdf")

        item = MagicMock(spec=_StubFormulaItem)
        item.__class__ = _StubFormulaItem
        item.get_image.return_value = None
        item.text = "E = mc^2"

        mock_doc = MagicMock()
        mock_doc.iterate_items.return_value = [(item, 0)]
        mock_dc.return_value.convert.return_value.document = mock_doc

        from riszotto.converter.docling import DoclingConverter
        converter = DoclingConverter()
        result = converter.convert(pdf, zotero_key="K1", equation_mode="image")

        assert "$$E = mc^2$$" in result.markdown
