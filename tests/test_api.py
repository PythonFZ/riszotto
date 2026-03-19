"""Tests for the FastAPI API endpoints."""

from unittest.mock import MagicMock, patch

import pytest


@pytest.fixture
def client():
    """Create a FastAPI test client."""
    from fastapi.testclient import TestClient
    from riszotto.api import create_app

    app = create_app()
    return TestClient(app)


class TestSearchEndpoint:
    def test_search_returns_results(self, client):
        mock_results = [
            {"key": "ABC", "title": "Test Paper", "itemType": "journalArticle",
             "creators": "Smith, J", "date": "2023", "score": 0.95},
        ]
        with patch("riszotto.api.routes.semantic_search", return_value=mock_results):
            response = client.get("/api/search?q=test&limit=10")
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["title"] == "Test Paper"

    def test_search_requires_query(self, client):
        response = client.get("/api/search")
        assert response.status_code == 422


class TestAutocompleteEndpoint:
    def test_autocomplete_returns_limited_results(self, client):
        mock_results = [
            {"key": "A", "title": "Paper A", "itemType": "journalArticle",
             "creators": "X", "date": "2023", "score": 0.9},
        ]
        with patch("riszotto.api.routes.semantic_search", return_value=mock_results):
            response = client.get("/api/autocomplete?q=test")
        assert response.status_code == 200


class TestNeighborsEndpoint:
    def test_neighbors_returns_graph(self, client):
        mock_graph = {
            "nodes": [{"key": "A", "title": "Paper A", "depth": 0, "score": 1.0,
                        "itemType": "journalArticle", "creators": "", "date": ""}],
            "edges": [],
        }
        with patch("riszotto.api.routes.get_neighbors", return_value=mock_graph):
            response = client.get("/api/neighbors/ABC123?cutoff=0.3&depth=2")
        assert response.status_code == 200
        data = response.json()
        assert "nodes" in data
        assert "edges" in data


class TestItemEndpoint:
    def test_item_returns_metadata(self, client):
        mock_item = {
            "key": "ABC123",
            "data": {
                "title": "Test Paper",
                "creators": [{"lastName": "Smith", "firstName": "J", "creatorType": "author"}],
                "abstractNote": "Abstract",
                "date": "2023",
                "itemType": "journalArticle",
                "tags": [{"tag": "ML"}],
            },
        }
        with (
            patch("riszotto.api.routes.get_client", return_value=MagicMock()),
            patch("riszotto.api.routes.get_item", return_value=mock_item),
        ):
            response = client.get("/api/item/ABC123")
        assert response.status_code == 200
        data = response.json()
        assert data["title"] == "Test Paper"
        assert data["authors"] == ["Smith, J"]
        assert data["zoteroLink"] == "zotero://select/items/ABC123"


class TestStatusEndpoint:
    def test_status_returns_index_info(self, client):
        mock_libs = [
            {"name": "My Library", "id": "0", "type": "user", "collection_name": "user_0"},
        ]
        with (
            patch("riszotto.api.routes.discover_libraries", return_value=mock_libs),
            patch("riszotto.api.routes.get_index_status", return_value={"count": 100, "path": "/tmp"}),
        ):
            response = client.get("/api/status")
        assert response.status_code == 200
        data = response.json()
        assert data["total_papers"] == 100
        assert len(data["libraries"]) == 1
