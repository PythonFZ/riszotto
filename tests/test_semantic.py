from unittest.mock import MagicMock, patch

from riszotto.semantic import (
    _build_document_text,
    build_index,
    get_index_status,
    semantic_search,
    INDEX_DIR,
)


class TestBuildDocumentText:
    def test_full_item(self):
        item = {
            "data": {
                "title": "Attention Is All You Need",
                "creators": [
                    {
                        "firstName": "Ashish",
                        "lastName": "Vaswani",
                        "creatorType": "author",
                    },
                    {
                        "firstName": "Noam",
                        "lastName": "Shazeer",
                        "creatorType": "author",
                    },
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
        assert text == ""

    def test_institution_creator(self):
        item = {
            "data": {
                "title": "Report",
                "creators": [
                    {"name": "World Health Organization", "creatorType": "author"}
                ],
            }
        }
        text = _build_document_text(item)
        assert "World Health Organization" in text


class TestBuildIndex:
    @patch("riszotto.semantic._get_collection")
    def test_indexes_items(self, mock_get_col):
        mock_collection = MagicMock()
        mock_get_col.return_value = mock_collection
        mock_collection.count.return_value = 0

        mock_zot = MagicMock()
        mock_zot.top.return_value = []
        mock_zot.everything.return_value = [
            {
                "data": {
                    "key": "KEY1",
                    "title": "Paper One",
                    "itemType": "journalArticle",
                    "creators": [],
                    "abstractNote": "Abstract one.",
                    "tags": [],
                }
            },
            {
                "data": {
                    "key": "KEY2",
                    "title": "Paper Two",
                    "itemType": "journalArticle",
                    "creators": [],
                    "abstractNote": "Abstract two.",
                    "tags": [],
                }
            },
        ]

        result = build_index(mock_zot)
        assert result["indexed"] == 2
        mock_collection.upsert.assert_called_once()
        call_kwargs = mock_collection.upsert.call_args
        assert "KEY1" in call_kwargs[1]["ids"]
        assert "KEY2" in call_kwargs[1]["ids"]
        assert len(call_kwargs[1]["documents"]) == 2

    @patch("riszotto.semantic._get_collection")
    def test_skips_child_items(self, mock_get_col):
        mock_collection = MagicMock()
        mock_get_col.return_value = mock_collection
        mock_collection.count.return_value = 0

        mock_zot = MagicMock()
        mock_zot.top.return_value = []
        mock_zot.everything.return_value = [
            {
                "data": {
                    "key": "PARENT1",
                    "title": "Parent Paper",
                    "itemType": "journalArticle",
                    "creators": [],
                    "abstractNote": "Content.",
                    "tags": [],
                }
            },
            {
                "data": {
                    "key": "CHILD1",
                    "title": "",
                    "itemType": "attachment",
                    "parentItem": "PARENT1",
                }
            },
            {
                "data": {
                    "key": "CHILD2",
                    "title": "",
                    "itemType": "note",
                    "parentItem": "PARENT1",
                }
            },
            {
                "data": {
                    "key": "CHILD3",
                    "title": "",
                    "itemType": "annotation",
                    "parentItem": "PARENT1",
                }
            },
        ]

        result = build_index(mock_zot)
        assert result["indexed"] == 1
        call_kwargs = mock_collection.upsert.call_args
        assert call_kwargs[1]["ids"] == ["PARENT1"]

    @patch("riszotto.semantic._get_collection")
    def test_incremental_skips_existing(self, mock_get_col):
        mock_collection = MagicMock()
        mock_get_col.return_value = mock_collection
        mock_collection.count.return_value = 1
        mock_collection.get.return_value = {"ids": ["KEY1"]}

        mock_zot = MagicMock()
        mock_zot.top.return_value = []
        mock_zot.everything.return_value = [
            {
                "data": {
                    "key": "KEY1",
                    "title": "Already Indexed",
                    "itemType": "journalArticle",
                    "creators": [],
                    "abstractNote": "Old.",
                    "tags": [],
                }
            },
            {
                "data": {
                    "key": "KEY2",
                    "title": "New Paper",
                    "itemType": "journalArticle",
                    "creators": [],
                    "abstractNote": "New.",
                    "tags": [],
                }
            },
        ]

        result = build_index(mock_zot)
        assert result["indexed"] == 1
        assert result["skipped"] == 1
        call_kwargs = mock_collection.upsert.call_args
        assert call_kwargs[1]["ids"] == ["KEY2"]

    @patch("riszotto.semantic._get_collection")
    def test_rebuild_indexes_all(self, mock_get_col):
        mock_collection = MagicMock()
        mock_get_col.return_value = mock_collection

        mock_zot = MagicMock()
        mock_zot.top.return_value = []
        mock_zot.everything.return_value = [
            {
                "data": {
                    "key": "KEY1",
                    "title": "Paper One",
                    "itemType": "journalArticle",
                    "creators": [],
                    "abstractNote": "Content.",
                    "tags": [],
                }
            },
            {
                "data": {
                    "key": "KEY2",
                    "title": "Paper Two",
                    "itemType": "journalArticle",
                    "creators": [],
                    "abstractNote": "Content.",
                    "tags": [],
                }
            },
        ]

        result = build_index(mock_zot, rebuild=True)
        assert result["indexed"] == 2
        # rebuild=True is passed to _get_collection
        mock_get_col.assert_called_once_with(rebuild=True, collection_name="user_0")

    @patch("riszotto.semantic._get_collection")
    def test_no_items_to_index(self, mock_get_col):
        mock_collection = MagicMock()
        mock_get_col.return_value = mock_collection
        mock_collection.count.return_value = 0

        mock_zot = MagicMock()
        mock_zot.top.return_value = []
        mock_zot.everything.return_value = []

        result = build_index(mock_zot)
        assert result["indexed"] == 0
        mock_collection.upsert.assert_not_called()

    @patch("riszotto.semantic._get_collection")
    def test_limit_caps_fetch(self, mock_get_col):
        mock_collection = MagicMock()
        mock_get_col.return_value = mock_collection
        mock_collection.count.return_value = 0

        mock_zot = MagicMock()
        mock_zot.items.return_value = []

        build_index(mock_zot, limit=100)
        mock_zot.top.assert_called_once_with(limit=100)


class TestSemanticSearch:
    @patch("riszotto.semantic._get_collection")
    def test_returns_results_with_scores(self, mock_get_col):
        mock_collection = MagicMock()
        mock_get_col.return_value = mock_collection
        mock_collection.count.return_value = 2
        mock_collection.query.return_value = {
            "ids": [["KEY1", "KEY2"]],
            "distances": [[0.2, 0.5]],
            "metadatas": [
                [
                    {"title": "Paper One", "itemType": "journalArticle"},
                    {"title": "Paper Two", "itemType": "book"},
                ]
            ],
        }

        results = semantic_search("deep learning")
        assert len(results) == 2
        assert results[0]["key"] == "KEY1"
        assert results[0]["title"] == "Paper One"
        assert results[0]["itemType"] == "journalArticle"
        assert results[0]["score"] == 0.8
        assert results[1]["key"] == "KEY2"
        assert results[1]["score"] == 0.5

    @patch("riszotto.semantic._get_collection")
    def test_empty_results(self, mock_get_col):
        mock_collection = MagicMock()
        mock_get_col.return_value = mock_collection
        mock_collection.count.return_value = 1
        mock_collection.query.return_value = {
            "ids": [[]],
            "distances": [[]],
            "metadatas": [[]],
        }

        results = semantic_search("nonexistent topic")
        assert results == []

    @patch("riszotto.semantic._get_collection")
    def test_empty_index_returns_early(self, mock_get_col):
        mock_collection = MagicMock()
        mock_get_col.return_value = mock_collection
        mock_collection.count.return_value = 0

        results = semantic_search("anything")
        assert results == []
        mock_collection.query.assert_not_called()


class TestGetIndexStatus:
    @patch("riszotto.semantic._get_collection")
    def test_returns_count_and_path(self, mock_get_col):
        mock_collection = MagicMock()
        mock_get_col.return_value = mock_collection
        mock_collection.count.return_value = 42

        status = get_index_status()
        assert status["count"] == 42
        assert status["path"] == str(INDEX_DIR)

    @patch("riszotto.semantic._get_collection")
    def test_empty_index(self, mock_get_col):
        mock_collection = MagicMock()
        mock_get_col.return_value = mock_collection
        mock_collection.count.return_value = 0

        status = get_index_status()
        assert status["count"] == 0
        assert status["path"] == str(INDEX_DIR)


class TestCollectionNaming:
    @patch("riszotto.semantic._get_collection")
    def test_build_index_uses_collection_name(self, mock_get_col):
        mock_collection = MagicMock()
        mock_get_col.return_value = mock_collection
        mock_collection.count.return_value = 0

        mock_zot = MagicMock()
        mock_zot.top.return_value = []
        mock_zot.everything.return_value = []

        build_index(mock_zot, collection_name="group_999")
        mock_get_col.assert_called_once_with(rebuild=False, collection_name="group_999")

    @patch("riszotto.semantic._get_collection")
    def test_semantic_search_uses_collection_name(self, mock_get_col):
        mock_collection = MagicMock()
        mock_get_col.return_value = mock_collection
        mock_collection.count.return_value = 0

        semantic_search("query", collection_name="group_999")
        mock_get_col.assert_called_once_with(collection_name="group_999")

    @patch("riszotto.semantic._get_collection")
    def test_get_index_status_uses_collection_name(self, mock_get_col):
        mock_collection = MagicMock()
        mock_get_col.return_value = mock_collection
        mock_collection.count.return_value = 5

        get_index_status(collection_name="group_999")
        mock_get_col.assert_called_once_with(collection_name="group_999")

    @patch("riszotto.semantic._get_collection")
    def test_default_collection_name_is_user_0(self, mock_get_col):
        mock_collection = MagicMock()
        mock_get_col.return_value = mock_collection
        mock_collection.count.return_value = 0

        mock_zot = MagicMock()
        mock_zot.top.return_value = []
        mock_zot.everything.return_value = []

        build_index(mock_zot)
        mock_get_col.assert_called_once_with(rebuild=False, collection_name="user_0")


