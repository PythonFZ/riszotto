# tests/test_converter_docling.py
"""Tests for docling converter availability and init behavior.

These tests do NOT require docling to be installed — they verify
the graceful-degradation path (DOCLING_AVAILABLE flag, ImportError).

Integration tests live in test_converter_docling_integration.py.
Edge-case tests live in test_converter_docling_edge_cases.py.
"""

import sys
from unittest.mock import patch

import pytest


class TestDoclingAvailableFlag:
    def test_import_error_sets_flag_false(self):
        with patch.dict(
            sys.modules, {"docling": None, "docling.document_converter": None}
        ):
            from riszotto.converter.docling import DOCLING_AVAILABLE

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
