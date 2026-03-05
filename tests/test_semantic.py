from unittest.mock import MagicMock, patch

from riszotto.semantic import (
    _build_document_text,
)


class TestBuildDocumentText:
    def test_full_item(self):
        item = {
            "data": {
                "title": "Attention Is All You Need",
                "creators": [
                    {"firstName": "Ashish", "lastName": "Vaswani", "creatorType": "author"},
                    {"firstName": "Noam", "lastName": "Shazeer", "creatorType": "author"},
                ],
                "abstractNote": "We propose a new architecture.",
                "tags": [{"tag": "transformers"}, {"tag": "NLP"}],
            }
        }
        text = _build_document_text(item)
        assert "Attention Is All You Need" in text
        assert "Vaswani, Ashish" in text
        assert "Shazeer, Noam" in text
        assert "We propose a new architecture." in text
        assert "transformers" in text
        assert "NLP" in text

    def test_missing_fields(self):
        item = {"data": {"title": "Sparse Title"}}
        text = _build_document_text(item)
        assert "Sparse Title" in text

    def test_empty_item(self):
        item = {"data": {}}
        text = _build_document_text(item)
        assert isinstance(text, str)

    def test_institution_creator(self):
        item = {
            "data": {
                "title": "Report",
                "creators": [{"name": "World Health Organization", "creatorType": "author"}],
            }
        }
        text = _build_document_text(item)
        assert "World Health Organization" in text
