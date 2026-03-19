from unittest.mock import MagicMock, patch

import pytest

from riszotto.semantic import (
    _build_document_text,
    _get_collection,
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

    def test_build_index_stores_enriched_metadata(self):
        """Verify build_index stores creators and date in ChromaDB metadata."""
        mock_collection = MagicMock()
        mock_collection.get.return_value = {"ids": []}

        items = [
            {
                "key": "ABC123",
                "data": {
                    "title": "Test Paper",
                    "itemType": "journalArticle",
                    "creators": [
                        {"creatorType": "author", "lastName": "Smith", "firstName": "John"},
                        {"creatorType": "author", "lastName": "Doe", "firstName": "Jane"},
                    ],
                    "date": "2023-06-15",
                    "abstractNote": "Abstract text.",
                    "tags": [],
                },
            }
        ]

        with (
            patch("riszotto.semantic._get_collection", return_value=mock_collection),
            patch.object(mock_collection, "count", return_value=0),
        ):
            from riszotto.semantic import build_index

            mock_zot = MagicMock()
            # build_index uses zot.everything(zot.top()) when limit is None
            mock_zot.top.return_value = items
            mock_zot.everything.return_value = items
            build_index(mock_zot, rebuild=True)

        call_args = mock_collection.upsert.call_args
        metadatas = call_args[1]["metadatas"] if "metadatas" in call_args[1] else call_args[0][2]
        assert metadatas[0]["creators"] == "Smith, John; Doe, Jane"
        assert metadatas[0]["date"] == "2023-06-15"
        assert metadatas[0]["title"] == "Test Paper"
        assert metadatas[0]["itemType"] == "journalArticle"


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

    @patch("riszotto.semantic._get_collection")
    def test_semantic_search_returns_enriched_fields(self, mock_get_col):
        """Verify search results include creators and date."""
        mock_collection = MagicMock()
        mock_get_col.return_value = mock_collection
        mock_collection.count.return_value = 1
        mock_collection.query.return_value = {
            "ids": [["key1"]],
            "distances": [[0.2]],
            "metadatas": [[{
                "title": "Test",
                "itemType": "journalArticle",
                "creators": "Smith, John",
                "date": "2023",
            }]],
        }

        results = semantic_search("test query")
        assert results[0]["creators"] == "Smith, John"
        assert results[0]["date"] == "2023"


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


class TestGetCollectionErrorHandling:
    @patch("chromadb.PersistentClient")
    def test_rebuild_catches_value_error(self, mock_persistent_client):
        mock_client = mock_persistent_client.return_value
        mock_client.delete_collection.side_effect = ValueError("not found")
        mock_collection = MagicMock()
        mock_client.get_or_create_collection.return_value = mock_collection

        result = _get_collection(rebuild=True, collection_name="test")
        assert result == mock_collection

    @patch("chromadb.PersistentClient")
    def test_rebuild_catches_not_found_error(self, mock_persistent_client):
        from chromadb.errors import NotFoundError

        mock_client = mock_persistent_client.return_value
        mock_client.delete_collection.side_effect = NotFoundError("not found")
        mock_collection = MagicMock()
        mock_client.get_or_create_collection.return_value = mock_collection

        result = _get_collection(rebuild=True, collection_name="test")
        assert result == mock_collection

    @patch("chromadb.PersistentClient")
    def test_rebuild_propagates_other_errors(self, mock_persistent_client):
        mock_client = mock_persistent_client.return_value
        mock_client.delete_collection.side_effect = RuntimeError("unexpected")

        with pytest.raises(RuntimeError, match="unexpected"):
            _get_collection(rebuild=True, collection_name="test")


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


class TestGetNeighbors:
    """Tests for get_neighbors()."""

    def test_returns_center_node_and_neighbors(self):
        """Center node at depth 0, neighbors at depth 1."""
        mock_collection = MagicMock()

        # get() returns the center item's embedding
        mock_collection.get.return_value = {
            "ids": ["center_key"],
            "embeddings": [[0.1, 0.2, 0.3]],
            "metadatas": [{"title": "Center Paper", "itemType": "journalArticle", "creators": "Smith, J", "date": "2020"}],
        }

        # query() returns neighbors
        mock_collection.query.return_value = {
            "ids": [["neighbor1", "neighbor2"]],
            "distances": [[0.15, 0.4]],
            "metadatas": [[
                {"title": "Neighbor 1", "itemType": "journalArticle", "creators": "Doe, J", "date": "2021"},
                {"title": "Neighbor 2", "itemType": "conferencePaper", "creators": "Lee, A", "date": "2019"},
            ]],
            "embeddings": [[[0.2, 0.3, 0.4], [0.5, 0.6, 0.7]]],
        }

        with patch("riszotto.semantic._get_collection", return_value=mock_collection):
            from riszotto.semantic import get_neighbors
            result = get_neighbors("center_key", cutoff=0.5, depth=1)

        assert len(result["nodes"]) == 3  # center + 2 neighbors
        assert result["nodes"][0]["key"] == "center_key"
        assert result["nodes"][0]["depth"] == 0
        assert len(result["edges"]) == 2

    def test_respects_cutoff(self):
        """Neighbors below cutoff are excluded."""
        mock_collection = MagicMock()
        mock_collection.get.return_value = {
            "ids": ["center"],
            "embeddings": [[0.1, 0.2, 0.3]],
            "metadatas": [{"title": "Center", "itemType": "journalArticle", "creators": "", "date": ""}],
        }
        mock_collection.query.return_value = {
            "ids": [["n1", "n2"]],
            "distances": [[0.1, 0.8]],  # n2 has low similarity (1-0.8=0.2)
            "metadatas": [[
                {"title": "Close", "itemType": "journalArticle", "creators": "", "date": ""},
                {"title": "Far", "itemType": "journalArticle", "creators": "", "date": ""},
            ]],
            "embeddings": [[[0.2, 0.3, 0.4], [0.9, 0.8, 0.7]]],
        }

        with patch("riszotto.semantic._get_collection", return_value=mock_collection):
            from riszotto.semantic import get_neighbors
            result = get_neighbors("center", cutoff=0.5, depth=1)

        # Only n1 passes cutoff (similarity 0.9 > 0.5), n2 doesn't (0.2 < 0.5)
        assert len(result["nodes"]) == 2
        assert len(result["edges"]) == 1

    def test_max_nodes_cap(self):
        """Graph is capped at 50 nodes."""
        mock_collection = MagicMock()
        mock_collection.get.return_value = {
            "ids": ["center"],
            "embeddings": [[0.1]],
            "metadatas": [{"title": "Center", "itemType": "journalArticle", "creators": "", "date": ""}],
        }

        # Return 60 neighbors (all above cutoff)
        ids = [[f"n{i}" for i in range(60)]]
        distances = [[0.05] * 60]
        metadatas = [[{"title": f"Paper {i}", "itemType": "journalArticle", "creators": "", "date": ""} for i in range(60)]]
        embeddings = [[[0.1] for _ in range(60)]]

        mock_collection.query.return_value = {
            "ids": ids, "distances": distances,
            "metadatas": metadatas, "embeddings": embeddings,
        }

        with patch("riszotto.semantic._get_collection", return_value=mock_collection):
            from riszotto.semantic import get_neighbors
            result = get_neighbors("center", cutoff=0.0, depth=1)

        assert len(result["nodes"]) <= 50
