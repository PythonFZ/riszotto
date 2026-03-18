import json
from unittest.mock import MagicMock, patch

from typer.testing import CliRunner

from riszotto.cli import app

runner = CliRunner()


class TestSearch:
    @patch("riszotto.cli.get_client")
    def test_search_outputs_json_envelope(self, mock_get_client):
        mock_zot = MagicMock()
        mock_get_client.return_value = mock_zot
        mock_zot.items.return_value = [
            {
                "data": {
                    "key": "ABC12345",
                    "title": "Attention Is All You Need",
                    "itemType": "journalArticle",
                    "date": "2017-06-12",
                    "abstractNote": "We propose a new architecture.",
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
                    "tags": [{"tag": "transformers"}, {"tag": "NLP"}],
                },
                "meta": {"creatorSummary": "Vaswani et al."},
            }
        ]
        result = runner.invoke(app, ["search", "attention"])
        assert result.exit_code == 0
        parsed = json.loads(result.output)
        assert parsed["page"] == 1
        assert parsed["limit"] == 25
        assert parsed["start"] == 0
        assert len(parsed["results"]) == 1
        item = parsed["results"][0]
        assert item["key"] == "ABC12345"
        assert item["title"] == "Attention Is All You Need"
        assert item["itemType"] == "journalArticle"
        assert item["date"] == "2017-06-12"
        assert item["authors"] == ["Vaswani, Ashish", "Shazeer, Noam"]
        assert item["abstract"] == "We propose a new architecture."
        assert item["tags"] == ["transformers", "NLP"]

    @patch("riszotto.cli.get_client")
    def test_search_no_results(self, mock_get_client):
        mock_zot = MagicMock()
        mock_get_client.return_value = mock_zot
        mock_zot.items.return_value = []
        result = runner.invoke(app, ["search", "nonexistent"])
        assert result.exit_code == 0
        parsed = json.loads(result.output)
        assert parsed["results"] == []

    @patch("riszotto.cli.get_client")
    def test_search_full_text_flag(self, mock_get_client):
        mock_zot = MagicMock()
        mock_get_client.return_value = mock_zot
        mock_zot.items.return_value = []
        runner.invoke(app, ["search", "--full-text", "deep learning"])
        mock_zot.items.assert_called_once_with(
            q="deep learning", qmode="everything", limit=25, start=0
        )

    @patch("riszotto.cli.get_client")
    def test_search_limit_flag(self, mock_get_client):
        mock_zot = MagicMock()
        mock_get_client.return_value = mock_zot
        mock_zot.items.return_value = []
        runner.invoke(app, ["search", "--limit", "5", "test"])
        mock_zot.items.assert_called_once_with(
            q="test", qmode="titleCreatorYear", limit=5, start=0
        )

    @patch("riszotto.cli.get_client")
    def test_search_zotero_not_running(self, mock_get_client):
        mock_get_client.side_effect = ConnectionError("connection refused")
        result = runner.invoke(app, ["search", "test"])
        assert result.exit_code == 1
        assert "Zotero desktop is not running" in result.output

    @patch("riszotto.cli.get_client")
    def test_search_page_flag(self, mock_get_client):
        mock_zot = MagicMock()
        mock_get_client.return_value = mock_zot
        mock_zot.items.return_value = []
        runner.invoke(app, ["search", "--page", "3", "test"])
        mock_zot.items.assert_called_once_with(
            q="test", qmode="titleCreatorYear", limit=25, start=50
        )

    @patch("riszotto.cli.get_client")
    def test_search_page_in_envelope(self, mock_get_client):
        mock_zot = MagicMock()
        mock_get_client.return_value = mock_zot
        mock_zot.items.return_value = []
        result = runner.invoke(app, ["search", "--page", "2", "--limit", "10", "test"])
        assert result.exit_code == 0
        parsed = json.loads(result.output)
        assert parsed["page"] == 2
        assert parsed["limit"] == 10
        assert parsed["start"] == 10

    @patch("riszotto.cli.get_client")
    def test_search_max_value_size_truncates(self, mock_get_client):
        mock_zot = MagicMock()
        mock_get_client.return_value = mock_zot
        long_abstract = "A" * 300
        mock_zot.items.return_value = [
            {
                "data": {
                    "key": "ABC12345",
                    "title": "Short",
                    "itemType": "journalArticle",
                    "date": "2024",
                    "abstractNote": long_abstract,
                    "creators": [],
                    "tags": [],
                },
                "meta": {},
            }
        ]
        result = runner.invoke(app, ["search", "test"])
        assert result.exit_code == 0
        parsed = json.loads(result.output)
        assert parsed["results"][0]["abstract"] == "<hidden (300 chars)>"

    @patch("riszotto.cli.get_client")
    def test_search_max_value_size_zero_shows_all(self, mock_get_client):
        mock_zot = MagicMock()
        mock_get_client.return_value = mock_zot
        long_abstract = "A" * 300
        mock_zot.items.return_value = [
            {
                "data": {
                    "key": "ABC12345",
                    "title": "Short",
                    "itemType": "journalArticle",
                    "date": "2024",
                    "abstractNote": long_abstract,
                    "creators": [],
                    "tags": [],
                },
                "meta": {},
            }
        ]
        result = runner.invoke(app, ["search", "--max-value-size", "0", "test"])
        assert result.exit_code == 0
        parsed = json.loads(result.output)
        assert parsed["results"][0]["abstract"] == long_abstract

    @patch("riszotto.cli.get_client")
    def test_search_creator_name_field(self, mock_get_client):
        """Creators with 'name' instead of firstName/lastName (e.g. institutions)."""
        mock_zot = MagicMock()
        mock_get_client.return_value = mock_zot
        mock_zot.items.return_value = [
            {
                "data": {
                    "key": "X1",
                    "title": "T",
                    "itemType": "journalArticle",
                    "date": "2024",
                    "abstractNote": "",
                    "creators": [{"name": "WHO", "creatorType": "author"}],
                    "tags": [],
                },
                "meta": {},
            }
        ]
        result = runner.invoke(app, ["search", "test"])
        parsed = json.loads(result.output)
        assert parsed["results"][0]["authors"] == ["WHO"]

    @patch("riszotto.cli.search_items")
    @patch("riszotto.cli.get_client")
    def test_search_tag_flag(self, mock_get_client, mock_search_items):
        mock_get_client.return_value = MagicMock()
        mock_search_items.return_value = []
        runner.invoke(app, ["search", "--tag", "physics", "test"])
        _, kwargs = mock_search_items.call_args
        assert kwargs["tag"] == ["physics"]

    @patch("riszotto.cli.search_items")
    @patch("riszotto.cli.get_client")
    def test_search_multiple_tags(self, mock_get_client, mock_search_items):
        mock_get_client.return_value = MagicMock()
        mock_search_items.return_value = []
        runner.invoke(app, ["search", "--tag", "ml", "--tag", "physics", "test"])
        _, kwargs = mock_search_items.call_args
        assert kwargs["tag"] == ["ml", "physics"]

    @patch("riszotto.cli.search_items")
    @patch("riszotto.cli.get_client")
    def test_search_item_type_flag(self, mock_get_client, mock_search_items):
        mock_get_client.return_value = MagicMock()
        mock_search_items.return_value = []
        runner.invoke(app, ["search", "--item-type", "book", "test"])
        _, kwargs = mock_search_items.call_args
        assert kwargs["item_type"] == "book"

    @patch("riszotto.cli.search_items")
    @patch("riszotto.cli.get_client")
    def test_search_sort_flags(self, mock_get_client, mock_search_items):
        mock_get_client.return_value = MagicMock()
        mock_search_items.return_value = []
        runner.invoke(
            app, ["search", "--sort", "dateModified", "--direction", "asc", "test"]
        )
        _, kwargs = mock_search_items.call_args
        assert kwargs["sort"] == "dateModified"
        assert kwargs["direction"] == "asc"

    @patch("riszotto.cli.get_client")
    def test_search_author_filters_results(self, mock_get_client):
        mock_zot = MagicMock()
        mock_get_client.return_value = mock_zot
        mock_zot.items.return_value = [
            {
                "data": {
                    "key": "K1",
                    "title": "Paper A",
                    "itemType": "journalArticle",
                    "date": "2024",
                    "abstractNote": "",
                    "tags": [],
                    "creators": [
                        {
                            "firstName": "Alice",
                            "lastName": "Smith",
                            "creatorType": "author",
                        }
                    ],
                },
            },
            {
                "data": {
                    "key": "K2",
                    "title": "Paper B",
                    "itemType": "journalArticle",
                    "date": "2024",
                    "abstractNote": "",
                    "tags": [],
                    "creators": [
                        {
                            "firstName": "Bob",
                            "lastName": "Jones",
                            "creatorType": "author",
                        }
                    ],
                },
            },
        ]
        result = runner.invoke(app, ["search", "--author", "smith", "test"])
        assert result.exit_code == 0
        parsed = json.loads(result.output)
        assert len(parsed["results"]) == 1
        assert parsed["results"][0]["key"] == "K1"


class TestSearchSemantic:
    @patch("riszotto.cli.get_client")
    @patch("riszotto.cli._import_semantic")
    def test_semantic_search_outputs_envelope(
        self, mock_import_semantic, mock_get_client
    ):
        mock_zot = MagicMock()
        mock_zot.library_type = "users"
        mock_get_client.return_value = mock_zot
        mock_semantic = MagicMock()
        mock_import_semantic.return_value = mock_semantic
        mock_semantic.semantic_search.return_value = [
            {
                "key": "P1",
                "title": "Paper One",
                "itemType": "journalArticle",
                "score": 0.95,
            },
            {"key": "P2", "title": "Paper Two", "itemType": "book", "score": 0.80},
        ]
        mock_zot.item.side_effect = lambda key: {
            "P1": {
                "data": {
                    "key": "P1",
                    "title": "Paper One",
                    "itemType": "journalArticle",
                    "date": "2024",
                    "abstractNote": "Abstract 1.",
                    "creators": [],
                    "tags": [],
                },
            },
            "P2": {
                "data": {
                    "key": "P2",
                    "title": "Paper Two",
                    "itemType": "book",
                    "date": "2023",
                    "abstractNote": "Abstract 2.",
                    "creators": [],
                    "tags": [],
                },
            },
        }[key]

        result = runner.invoke(app, ["search", "--semantic", "attention mechanisms"])
        assert result.exit_code == 0
        parsed = json.loads(result.output)
        assert len(parsed["results"]) == 2
        assert parsed["results"][0]["key"] == "P1"
        assert parsed["results"][0]["score"] == 0.95
        assert parsed["results"][0]["title"] == "Paper One"
        assert parsed["results"][1]["key"] == "P2"
        assert parsed["results"][1]["score"] == 0.80

    @patch("riszotto.cli.get_client")
    @patch("riszotto.cli._import_semantic")
    def test_semantic_search_no_results(self, mock_import_semantic, mock_get_client):
        mock_get_client.return_value = MagicMock(library_type="users")
        mock_semantic = MagicMock()
        mock_import_semantic.return_value = mock_semantic
        mock_semantic.semantic_search.return_value = []

        result = runner.invoke(app, ["search", "--semantic", "nonexistent"])
        assert result.exit_code == 0
        parsed = json.loads(result.output)
        assert parsed["results"] == []

    @patch("riszotto.cli._import_semantic")
    def test_semantic_search_missing_extras(self, mock_import_semantic):
        mock_import_semantic.return_value = None

        result = runner.invoke(app, ["search", "--semantic", "test"])
        assert result.exit_code == 1
        assert "semantic" in result.output.lower()

    @patch("riszotto.cli.get_client")
    @patch("riszotto.cli._import_semantic")
    def test_semantic_search_author_filters(
        self, mock_import_semantic, mock_get_client
    ):
        mock_zot = MagicMock()
        mock_zot.library_type = "users"
        mock_get_client.return_value = mock_zot
        mock_semantic = MagicMock()
        mock_import_semantic.return_value = mock_semantic
        mock_semantic.semantic_search.return_value = [
            {
                "key": "P1",
                "title": "Paper One",
                "itemType": "journalArticle",
                "score": 0.95,
            },
            {"key": "P2", "title": "Paper Two", "itemType": "book", "score": 0.80},
        ]
        mock_zot.item.side_effect = lambda key: {
            "P1": {
                "data": {
                    "key": "P1",
                    "title": "Paper One",
                    "itemType": "journalArticle",
                    "date": "2024",
                    "abstractNote": "",
                    "tags": [],
                    "creators": [
                        {
                            "firstName": "Alice",
                            "lastName": "Smith",
                            "creatorType": "author",
                        }
                    ],
                },
            },
            "P2": {
                "data": {
                    "key": "P2",
                    "title": "Paper Two",
                    "itemType": "book",
                    "date": "2023",
                    "abstractNote": "",
                    "tags": [],
                    "creators": [
                        {
                            "firstName": "Bob",
                            "lastName": "Jones",
                            "creatorType": "author",
                        }
                    ],
                },
            },
        }[key]

        result = runner.invoke(
            app, ["search", "--semantic", "--author", "jones", "test"]
        )
        assert result.exit_code == 0
        parsed = json.loads(result.output)
        assert len(parsed["results"]) == 1
        assert parsed["results"][0]["key"] == "P2"

    @patch("riszotto.cli.get_client")
    @patch("riszotto.cli._import_semantic")
    def test_semantic_search_respects_limit(
        self, mock_import_semantic, mock_get_client
    ):
        mock_get_client.return_value = MagicMock(library_type="users")
        mock_semantic = MagicMock()
        mock_import_semantic.return_value = mock_semantic
        mock_semantic.semantic_search.return_value = []

        runner.invoke(app, ["search", "--semantic", "--limit", "5", "test"])
        mock_semantic.semantic_search.assert_called_once_with(
            "test", limit=5, collection_name="user_0"
        )


class TestConnectionError:
    @patch("riszotto.cli.get_client")
    def test_collections_zotero_not_running(self, mock_get_client):
        mock_get_client.side_effect = ConnectionError("connection refused")
        result = runner.invoke(app, ["collections"])
        assert result.exit_code == 1
        assert "Zotero desktop is not running" in result.output


class TestShow:
    @patch("riszotto.cli.MarkItDown")
    @patch("riszotto.cli.get_client")
    def test_show_converts_pdf(self, mock_get_client, mock_markitdown_cls):
        mock_zot = MagicMock()
        mock_get_client.return_value = mock_zot
        mock_zot.children.return_value = [
            {
                "data": {
                    "key": "ATT1",
                    "itemType": "attachment",
                    "contentType": "application/pdf",
                    "filename": "paper.pdf",
                },
                "links": {
                    "enclosure": {
                        "href": "file:///Users/me/Zotero/storage/ATT1/paper.pdf"
                    }
                },
            }
        ]
        mock_md = MagicMock()
        mock_markitdown_cls.return_value = mock_md
        mock_result = MagicMock()
        mock_result.markdown = "# Paper Title\n\nSome content here."
        mock_md.convert.return_value = mock_result

        result = runner.invoke(app, ["show", "PARENT1"])
        assert result.exit_code == 0
        assert "# Paper Title" in result.output
        mock_md.convert.assert_called_once_with(
            "/Users/me/Zotero/storage/ATT1/paper.pdf"
        )

    @patch("riszotto.cli.get_client")
    def test_show_no_pdf_attachment(self, mock_get_client):
        mock_zot = MagicMock()
        mock_get_client.return_value = mock_zot
        mock_zot.children.return_value = [
            {"data": {"key": "NOTE1", "itemType": "note"}, "links": {}},
        ]
        result = runner.invoke(app, ["show", "PARENT1"])
        assert result.exit_code == 1
        assert "No PDF attachment" in result.output

    @patch("riszotto.cli.MarkItDown")
    @patch("riszotto.cli.get_client")
    def test_show_attachment_flag(self, mock_get_client, mock_markitdown_cls):
        mock_zot = MagicMock()
        mock_get_client.return_value = mock_zot
        mock_zot.children.return_value = [
            {
                "data": {
                    "key": "ATT1",
                    "itemType": "attachment",
                    "contentType": "application/pdf",
                    "filename": "paper1.pdf",
                },
                "links": {"enclosure": {"href": "file:///path/to/paper1.pdf"}},
            },
            {
                "data": {
                    "key": "ATT2",
                    "itemType": "attachment",
                    "contentType": "application/pdf",
                    "filename": "paper2.pdf",
                },
                "links": {"enclosure": {"href": "file:///path/to/paper2.pdf"}},
            },
        ]
        mock_md = MagicMock()
        mock_markitdown_cls.return_value = mock_md
        mock_result = MagicMock()
        mock_result.markdown = "Second PDF content"
        mock_md.convert.return_value = mock_result

        result = runner.invoke(app, ["show", "--attachment", "2", "PARENT1"])
        assert result.exit_code == 0
        mock_md.convert.assert_called_once_with("/path/to/paper2.pdf")

    @patch("riszotto.cli.MarkItDown")
    @patch("riszotto.cli.get_client")
    def test_show_page_default_paginates(self, mock_get_client, mock_markitdown_cls):
        mock_zot = MagicMock()
        mock_get_client.return_value = mock_zot
        mock_zot.children.return_value = [
            {
                "data": {
                    "key": "ATT1",
                    "itemType": "attachment",
                    "contentType": "application/pdf",
                    "filename": "paper.pdf",
                },
                "links": {"enclosure": {"href": "file:///path/to/paper.pdf"}},
            }
        ]
        mock_md = MagicMock()
        mock_markitdown_cls.return_value = mock_md
        mock_result = MagicMock()
        # 10 lines of content, page_size=5
        mock_result.markdown = "\n".join(f"Line {i}" for i in range(1, 11))
        mock_md.convert.return_value = mock_result

        result = runner.invoke(app, ["show", "--page-size", "5", "PARENT1"])
        assert result.exit_code == 0
        assert "Line 1" in result.output
        assert "Line 5" in result.output
        assert "Line 6" not in result.output
        assert "Page 1/2" in result.output

    @patch("riszotto.cli.MarkItDown")
    @patch("riszotto.cli.get_client")
    def test_show_page_2(self, mock_get_client, mock_markitdown_cls):
        mock_zot = MagicMock()
        mock_get_client.return_value = mock_zot
        mock_zot.children.return_value = [
            {
                "data": {
                    "key": "ATT1",
                    "itemType": "attachment",
                    "contentType": "application/pdf",
                    "filename": "paper.pdf",
                },
                "links": {"enclosure": {"href": "file:///path/to/paper.pdf"}},
            }
        ]
        mock_md = MagicMock()
        mock_markitdown_cls.return_value = mock_md
        mock_result = MagicMock()
        mock_result.markdown = "\n".join(f"Line {i}" for i in range(1, 11))
        mock_md.convert.return_value = mock_result

        result = runner.invoke(
            app, ["show", "--page", "2", "--page-size", "5", "PARENT1"]
        )
        assert result.exit_code == 0
        assert "Line 6" in result.output
        assert "Line 10" in result.output
        assert "Line 5" not in result.output

    @patch("riszotto.cli.MarkItDown")
    @patch("riszotto.cli.get_client")
    def test_show_page_zero_dumps_all(self, mock_get_client, mock_markitdown_cls):
        mock_zot = MagicMock()
        mock_get_client.return_value = mock_zot
        mock_zot.children.return_value = [
            {
                "data": {
                    "key": "ATT1",
                    "itemType": "attachment",
                    "contentType": "application/pdf",
                    "filename": "paper.pdf",
                },
                "links": {"enclosure": {"href": "file:///path/to/paper.pdf"}},
            }
        ]
        mock_md = MagicMock()
        mock_markitdown_cls.return_value = mock_md
        mock_result = MagicMock()
        mock_result.markdown = "\n".join(f"Line {i}" for i in range(1, 11))
        mock_md.convert.return_value = mock_result

        result = runner.invoke(
            app, ["show", "--page", "0", "--page-size", "5", "PARENT1"]
        )
        assert result.exit_code == 0
        assert "Line 1" in result.output
        assert "Line 10" in result.output

    @patch("riszotto.cli.MarkItDown")
    @patch("riszotto.cli.get_client")
    def test_show_page_out_of_range(self, mock_get_client, mock_markitdown_cls):
        mock_zot = MagicMock()
        mock_get_client.return_value = mock_zot
        mock_zot.children.return_value = [
            {
                "data": {
                    "key": "ATT1",
                    "itemType": "attachment",
                    "contentType": "application/pdf",
                    "filename": "paper.pdf",
                },
                "links": {"enclosure": {"href": "file:///path/to/paper.pdf"}},
            }
        ]
        mock_md = MagicMock()
        mock_markitdown_cls.return_value = mock_md
        mock_result = MagicMock()
        mock_result.markdown = "Short doc"
        mock_md.convert.return_value = mock_result

        result = runner.invoke(
            app, ["show", "--page", "99", "--page-size", "5", "PARENT1"]
        )
        assert result.exit_code == 1
        assert "out of range" in result.output.lower()

    @patch("riszotto.cli.MarkItDown")
    @patch("riszotto.cli.get_client")
    def test_show_search_finds_lines(self, mock_get_client, mock_markitdown_cls):
        mock_zot = MagicMock()
        mock_get_client.return_value = mock_zot
        mock_zot.children.return_value = [
            {
                "data": {
                    "key": "ATT1",
                    "itemType": "attachment",
                    "contentType": "application/pdf",
                    "filename": "paper.pdf",
                },
                "links": {"enclosure": {"href": "file:///path/to/paper.pdf"}},
            }
        ]
        mock_md = MagicMock()
        mock_markitdown_cls.return_value = mock_md
        mock_result = MagicMock()
        # 20 filler lines, then a match, then 20 more filler lines
        lines = [f"filler line {i}" for i in range(20)]
        lines.append("This paper studies regression.")
        lines.extend(f"filler line {i}" for i in range(20, 40))
        mock_result.markdown = "\n".join(lines)
        mock_md.convert.return_value = mock_result

        result = runner.invoke(
            app, ["show", "--search", "regression", "-C", "1", "PARENT1"]
        )
        assert result.exit_code == 0
        assert "This paper studies regression." in result.output
        assert "filler line 19" in result.output  # 1 line before
        assert "filler line 20" in result.output  # 1 line after
        assert "filler line 0" not in result.output  # far away

    @patch("riszotto.cli.MarkItDown")
    @patch("riszotto.cli.get_client")
    def test_show_search_no_match(self, mock_get_client, mock_markitdown_cls):
        mock_zot = MagicMock()
        mock_get_client.return_value = mock_zot
        mock_zot.children.return_value = [
            {
                "data": {
                    "key": "ATT1",
                    "itemType": "attachment",
                    "contentType": "application/pdf",
                    "filename": "paper.pdf",
                },
                "links": {"enclosure": {"href": "file:///path/to/paper.pdf"}},
            }
        ]
        mock_md = MagicMock()
        mock_markitdown_cls.return_value = mock_md
        mock_result = MagicMock()
        mock_result.markdown = (
            "# Introduction\n\nSome content.\n\n## Methods\n\nMore content."
        )
        mock_md.convert.return_value = mock_result

        result = runner.invoke(app, ["show", "--search", "nonexistent", "PARENT1"])
        assert result.exit_code == 0
        assert "No lines matching" in result.output

    @patch("riszotto.cli.MarkItDown")
    @patch("riszotto.cli.get_client")
    def test_show_search_multiple_terms(self, mock_get_client, mock_markitdown_cls):
        mock_zot = MagicMock()
        mock_get_client.return_value = mock_zot
        mock_zot.children.return_value = [
            {
                "data": {
                    "key": "ATT1",
                    "itemType": "attachment",
                    "contentType": "application/pdf",
                    "filename": "paper.pdf",
                },
                "links": {"enclosure": {"href": "file:///path/to/paper.pdf"}},
            }
        ]
        mock_md = MagicMock()
        mock_markitdown_cls.return_value = mock_md
        mock_result = MagicMock()
        # 20 filler lines between each content line to avoid context overlap
        filler_a = "\n".join(f"padding {i}" for i in range(20))
        mock_result.markdown = (
            f"DFT and BMIM were studied.\n{filler_a}\n"
            f"We used DFT calculations.\n{filler_a}\n"
            f"BMIM showed interesting properties.\n{filler_a}\n"
            f"DFT confirms BMIM stability."
        )
        mock_md.convert.return_value = mock_result

        result = runner.invoke(
            app, ["show", "--search", "DFT BMIM", "-C", "0", "PARENT1"]
        )
        assert result.exit_code == 0
        # Lines containing BOTH terms match
        assert "DFT and BMIM were studied." in result.output
        assert "DFT confirms BMIM stability." in result.output
        # Lines with only one term do not
        assert "We used DFT calculations." not in result.output
        assert "BMIM showed interesting properties." not in result.output

    @patch("riszotto.cli.MarkItDown")
    @patch("riszotto.cli.get_client")
    def test_show_search_case_insensitive(self, mock_get_client, mock_markitdown_cls):
        mock_zot = MagicMock()
        mock_get_client.return_value = mock_zot
        mock_zot.children.return_value = [
            {
                "data": {
                    "key": "ATT1",
                    "itemType": "attachment",
                    "contentType": "application/pdf",
                    "filename": "paper.pdf",
                },
                "links": {"enclosure": {"href": "file:///path/to/paper.pdf"}},
            }
        ]
        mock_md = MagicMock()
        mock_markitdown_cls.return_value = mock_md
        mock_result = MagicMock()
        mock_result.markdown = "Machine Learning is great."
        mock_md.convert.return_value = mock_result

        result = runner.invoke(app, ["show", "--search", "MACHINE LEARNING", "PARENT1"])
        assert result.exit_code == 0
        assert "Machine Learning is great." in result.output

    @patch("riszotto.cli.MarkItDown")
    @patch("riszotto.cli.get_client")
    def test_show_search_separator_between_blocks(
        self, mock_get_client, mock_markitdown_cls
    ):
        mock_zot = MagicMock()
        mock_get_client.return_value = mock_zot
        mock_zot.children.return_value = [
            {
                "data": {
                    "key": "ATT1",
                    "itemType": "attachment",
                    "contentType": "application/pdf",
                    "filename": "paper.pdf",
                },
                "links": {"enclosure": {"href": "file:///path/to/paper.pdf"}},
            }
        ]
        mock_md = MagicMock()
        mock_markitdown_cls.return_value = mock_md
        mock_result = MagicMock()
        lines = [f"filler {i}" for i in range(20)]
        lines[3] = "match alpha here"
        lines[15] = "match alpha there"
        mock_result.markdown = "\n".join(lines)
        mock_md.convert.return_value = mock_result

        result = runner.invoke(app, ["show", "--search", "alpha", "-C", "1", "PARENT1"])
        assert result.exit_code == 0
        assert "\n--\n" in result.output


class TestExport:
    @patch("riszotto.cli.get_item_bibtex")
    @patch("riszotto.cli.get_client")
    def test_export_default_bibtex(self, mock_get_client, mock_get_bibtex):
        mock_zot = MagicMock()
        mock_get_client.return_value = mock_zot
        mock_get_bibtex.return_value = "@article{doe2024, title={Test Paper}}"

        result = runner.invoke(app, ["export", "ABC123"])
        assert result.exit_code == 0
        assert "@article{doe2024, title={Test Paper}}" in result.output
        from riszotto.client import DEFAULT_BIBTEX_EXCLUDE

        mock_get_bibtex.assert_called_once_with(
            mock_zot, "ABC123", exclude=DEFAULT_BIBTEX_EXCLUDE
        )

    @patch("riszotto.cli.get_item_bibtex")
    @patch("riszotto.cli.get_client")
    def test_export_include_all(self, mock_get_client, mock_get_bibtex):
        mock_zot = MagicMock()
        mock_get_client.return_value = mock_zot
        mock_get_bibtex.return_value = "@article{doe2024, title={Test}}"

        result = runner.invoke(app, ["export", "ABC123", "--include-all"])
        assert result.exit_code == 0
        mock_get_bibtex.assert_called_once_with(mock_zot, "ABC123", exclude=set())

    @patch("riszotto.cli.get_item_bibtex")
    @patch("riszotto.cli.get_client")
    def test_export_custom_exclude(self, mock_get_client, mock_get_bibtex):
        mock_zot = MagicMock()
        mock_get_client.return_value = mock_zot
        mock_get_bibtex.return_value = "@article{doe2024, title={Test}}"

        result = runner.invoke(
            app, ["export", "ABC123", "--exclude", "file", "--exclude", "note"]
        )
        assert result.exit_code == 0
        mock_get_bibtex.assert_called_once_with(
            mock_zot, "ABC123", exclude={"file", "note"}
        )

    @patch("riszotto.cli.get_client")
    def test_export_unknown_format(self, mock_get_client):
        mock_get_client.return_value = MagicMock()

        result = runner.invoke(app, ["export", "ABC123", "--format", "csv"])
        assert result.exit_code == 1
        assert "Unknown format" in result.output


class TestCollections:
    @patch("riszotto.cli.list_collections")
    @patch("riszotto.cli.get_client")
    def test_list_collections(self, mock_get_client, mock_list_collections):
        mock_get_client.return_value = MagicMock()
        mock_list_collections.return_value = [
            {"data": {"key": "COL1", "name": "Physics", "parentCollection": False}},
            {"data": {"key": "COL2", "name": "ML", "parentCollection": "COL1"}},
        ]
        result = runner.invoke(app, ["collections"])
        assert result.exit_code == 0
        parsed = json.loads(result.output)
        assert len(parsed["results"]) == 2
        assert parsed["results"][0]["key"] == "COL1"
        assert parsed["results"][0]["name"] == "Physics"
        assert parsed["results"][1]["parentCollection"] == "COL1"

    @patch("riszotto.cli.collection_items")
    @patch("riszotto.cli.get_client")
    def test_collection_items(self, mock_get_client, mock_collection_items):
        mock_get_client.return_value = MagicMock()
        mock_collection_items.return_value = [
            {
                "data": {
                    "key": "P1",
                    "title": "Paper 1",
                    "itemType": "journalArticle",
                    "date": "2024",
                    "abstractNote": "",
                    "creators": [],
                    "tags": [],
                },
            }
        ]
        result = runner.invoke(app, ["collections", "COL1"])
        assert result.exit_code == 0
        parsed = json.loads(result.output)
        assert parsed["page"] == 1
        assert parsed["limit"] == 25
        assert parsed["start"] == 0
        assert len(parsed["results"]) == 1
        assert parsed["results"][0]["key"] == "P1"

    @patch("riszotto.cli.collection_items")
    @patch("riszotto.cli.get_client")
    def test_collection_items_pagination(self, mock_get_client, mock_collection_items):
        mock_get_client.return_value = MagicMock()
        mock_collection_items.return_value = []
        result = runner.invoke(
            app, ["collections", "COL1", "--page", "3", "--limit", "10"]
        )
        assert result.exit_code == 0
        parsed = json.loads(result.output)
        assert parsed["page"] == 3
        assert parsed["limit"] == 10
        assert parsed["start"] == 20
        call_args = mock_collection_items.call_args
        assert call_args[0][1] == "COL1"
        assert call_args[1] == {"limit": 10, "start": 20}


class TestRecent:
    @patch("riszotto.cli.recent_items")
    @patch("riszotto.cli.get_client")
    def test_recent_outputs_json(self, mock_get_client, mock_recent_items):
        mock_get_client.return_value = MagicMock()
        mock_recent_items.return_value = [
            {
                "data": {
                    "key": "P1",
                    "title": "Recent Paper",
                    "itemType": "journalArticle",
                    "date": "2024",
                    "abstractNote": "",
                    "creators": [],
                    "tags": [],
                },
            }
        ]
        result = runner.invoke(app, ["recent"])
        assert result.exit_code == 0
        parsed = json.loads(result.output)
        assert parsed["limit"] == 10
        assert len(parsed["results"]) == 1
        assert parsed["results"][0]["key"] == "P1"

    @patch("riszotto.cli.recent_items")
    @patch("riszotto.cli.get_client")
    def test_recent_custom_limit(self, mock_get_client, mock_recent_items):
        mock_get_client.return_value = MagicMock()
        mock_recent_items.return_value = []
        result = runner.invoke(app, ["recent", "--limit", "5"])
        assert result.exit_code == 0
        parsed = json.loads(result.output)
        assert parsed["limit"] == 5
        mock_recent_items.assert_called_once()
        _, kwargs = mock_recent_items.call_args
        assert kwargs["limit"] == 5

    @patch("riszotto.cli.get_client")
    def test_recent_zotero_not_running(self, mock_get_client):
        mock_get_client.side_effect = ConnectionError("connection refused")
        result = runner.invoke(app, ["recent"])
        assert result.exit_code == 1
        assert "Zotero desktop is not running" in result.output


class TestIndex:
    @patch("riszotto.cli.get_client")
    @patch("riszotto.cli._import_semantic")
    def test_index_builds(self, mock_import_semantic, mock_get_client):
        mock_zot = MagicMock()
        mock_zot.library_type = "users"
        mock_get_client.return_value = mock_zot
        mock_semantic = MagicMock()
        mock_import_semantic.return_value = mock_semantic
        mock_semantic.build_index.return_value = {"indexed": 10, "skipped": 2}

        result = runner.invoke(app, ["index"])
        assert result.exit_code == 0
        assert "10" in result.output
        mock_semantic.build_index.assert_called_once_with(
            mock_zot, rebuild=False, limit=None, collection_name="user_0"
        )

    @patch("riszotto.cli.get_client")
    @patch("riszotto.cli._import_semantic")
    def test_index_rebuild(self, mock_import_semantic, mock_get_client):
        mock_zot = MagicMock()
        mock_zot.library_type = "users"
        mock_get_client.return_value = mock_zot
        mock_semantic = MagicMock()
        mock_import_semantic.return_value = mock_semantic
        mock_semantic.build_index.return_value = {"indexed": 5, "skipped": 0}

        result = runner.invoke(app, ["index", "--rebuild"])
        assert result.exit_code == 0
        mock_semantic.build_index.assert_called_once_with(
            mock_zot, rebuild=True, limit=None, collection_name="user_0"
        )

    @patch("riszotto.cli.get_client")
    @patch("riszotto.cli._import_semantic")
    def test_index_status(self, mock_import_semantic, mock_get_client):
        mock_get_client.return_value = MagicMock(library_type="users")
        mock_semantic = MagicMock()
        mock_import_semantic.return_value = mock_semantic
        mock_semantic.get_index_status.return_value = {
            "count": 42,
            "path": "/home/user/.riszotto/chroma_db",
        }

        result = runner.invoke(app, ["index", "--status"])
        assert result.exit_code == 0
        parsed = json.loads(result.output)
        assert parsed["count"] == 42
        assert parsed["path"] == "/home/user/.riszotto/chroma_db"

    @patch("riszotto.cli._import_semantic")
    def test_index_missing_extras(self, mock_import_semantic):
        mock_import_semantic.return_value = None

        result = runner.invoke(app, ["index"])
        assert result.exit_code == 1
        assert "semantic" in result.output.lower()


class TestLibraries:
    @patch("riszotto.cli.zotero.Zotero")
    @patch("riszotto.cli.load_config")
    @patch("riszotto.cli.get_client")
    def test_lists_local_groups(self, mock_get_client, mock_config, mock_zotero_cls):
        from riszotto.config import Config

        mock_config.return_value = Config()
        mock_zot = MagicMock()
        mock_get_client.return_value = mock_zot
        mock_zot.groups.return_value = [
            {"id": 111, "data": {"name": "Lab Group"}},
            {"id": 222, "data": {"name": "Dept. Reading"}},
        ]
        mock_group_zot = MagicMock()
        mock_group_zot.num_items.return_value = 5
        mock_zotero_cls.return_value = mock_group_zot

        result = runner.invoke(app, ["libraries"])
        assert result.exit_code == 0
        assert "My Library" in result.output
        assert "Lab Group" in result.output
        assert "Dept. Reading" in result.output
        assert "111" in result.output
        assert "222" in result.output

    @patch("riszotto.cli.load_config")
    @patch("riszotto.cli.get_client")
    def test_no_libraries_local_only(self, mock_get_client, mock_config):
        from riszotto.config import Config

        mock_config.return_value = Config()
        mock_zot = MagicMock()
        mock_get_client.return_value = mock_zot
        mock_zot.groups.return_value = []

        result = runner.invoke(app, ["libraries"])
        assert result.exit_code == 0
        assert "My Library" in result.output

    @patch("riszotto.cli.zotero.Zotero")
    @patch("riszotto.cli.load_config")
    @patch("riszotto.cli.get_client")
    def test_lists_remote_groups(self, mock_get_client, mock_config, mock_zotero_cls):
        from riszotto.config import Config

        mock_config.return_value = Config(api_key="k", user_id="u")
        mock_local = MagicMock()
        mock_get_client.return_value = mock_local
        mock_local.groups.return_value = [
            {"id": 111, "data": {"name": "Local Group"}},
        ]
        mock_remote = MagicMock()
        mock_zotero_cls.return_value = mock_remote
        mock_remote.groups.return_value = [
            {"id": 111, "data": {"name": "Local Group"}},
            {"id": 222, "data": {"name": "Remote Only"}},
        ]

        result = runner.invoke(app, ["libraries"])
        assert result.exit_code == 0
        assert "Local Group" in result.output
        assert "Remote Only" in result.output
        lines = result.output.strip().split("\n")
        local_line = [line for line in lines if "Local Group" in line][0]
        assert "local" in local_line


class TestLibraryFlag:
    @patch("riszotto.cli.get_client")
    def test_search_with_library_flag(self, mock_get_client):
        mock_zot = MagicMock()
        mock_get_client.return_value = mock_zot
        mock_zot.items.return_value = []

        result = runner.invoke(app, ["search", "--library", "Lab Group", "test"])
        assert result.exit_code == 0
        mock_get_client.assert_called_once_with(library="Lab Group")

    @patch("riszotto.cli.get_client")
    def test_search_with_short_flag(self, mock_get_client):
        mock_zot = MagicMock()
        mock_get_client.return_value = mock_zot
        mock_zot.items.return_value = []

        result = runner.invoke(app, ["search", "-L", "999", "test"])
        assert result.exit_code == 0
        mock_get_client.assert_called_once_with(library="999")

    @patch("riszotto.cli.get_client")
    def test_search_default_no_library(self, mock_get_client):
        mock_zot = MagicMock()
        mock_get_client.return_value = mock_zot
        mock_zot.items.return_value = []

        runner.invoke(app, ["search", "test"])
        mock_get_client.assert_called_once_with(library=None)

    @patch("riszotto.cli.get_client")
    def test_collections_with_library_flag(self, mock_get_client):
        mock_zot = MagicMock()
        mock_get_client.return_value = mock_zot
        mock_zot.collections.return_value = []

        result = runner.invoke(app, ["collections", "--library", "Lab Group"])
        assert result.exit_code == 0
        mock_get_client.assert_called_once_with(library="Lab Group")

    @patch("riszotto.cli.get_client")
    def test_recent_with_library_flag(self, mock_get_client):
        mock_zot = MagicMock()
        mock_get_client.return_value = mock_zot
        mock_zot.items.return_value = []

        result = runner.invoke(app, ["recent", "--library", "Lab Group"])
        assert result.exit_code == 0
        mock_get_client.assert_called_once_with(library="Lab Group")

    @patch("riszotto.cli.get_item_bibtex")
    @patch("riszotto.cli.get_client")
    def test_export_with_library_flag(self, mock_get_client, mock_bibtex):
        mock_zot = MagicMock()
        mock_get_client.return_value = mock_zot
        mock_bibtex.return_value = "@article{x, title={T}}"

        result = runner.invoke(app, ["export", "--library", "Lab Group", "KEY1"])
        assert result.exit_code == 0
        mock_get_client.assert_called_once_with(library="Lab Group")

    @patch("riszotto.cli.get_client")
    def test_library_not_found_error(self, mock_get_client):
        from riszotto.client import LibraryNotFoundError

        mock_get_client.side_effect = LibraryNotFoundError("Group 'X' not found")
        result = runner.invoke(app, ["search", "--library", "X", "test"])
        assert result.exit_code == 1
        assert "not found" in result.output.lower()

    @patch("riszotto.cli.get_client")
    def test_ambiguous_library_error(self, mock_get_client):
        from riszotto.client import AmbiguousLibraryError

        mock_get_client.side_effect = AmbiguousLibraryError("matches multiple")
        result = runner.invoke(app, ["search", "--library", "Lab", "test"])
        assert result.exit_code == 1
        assert "multiple" in result.output.lower()

    @patch("riszotto.cli.get_client")
    def test_show_with_remote_library_no_local_pdf(self, mock_get_client):
        mock_zot = MagicMock()
        mock_get_client.return_value = mock_zot
        mock_zot.library_id = "999"
        mock_zot.children.return_value = [
            {
                "data": {
                    "key": "ATT1",
                    "itemType": "attachment",
                    "contentType": "application/pdf",
                },
                "links": {"enclosure": {"href": "https://api.zotero.org/..."}},
            }
        ]
        result = runner.invoke(app, ["show", "--library", "Remote Group", "ITEM1"])
        assert result.exit_code == 1
        assert "local" in result.output.lower()

    @patch("riszotto.cli._import_semantic")
    @patch("riszotto.cli.get_client")
    def test_semantic_search_with_library_uses_collection_name(
        self, mock_get_client, mock_import_semantic
    ):
        mock_zot = MagicMock()
        mock_zot.library_id = "987"
        mock_zot.library_type = "groups"
        mock_get_client.return_value = mock_zot
        mock_semantic = MagicMock()
        mock_import_semantic.return_value = mock_semantic
        mock_semantic.semantic_search.return_value = []

        result = runner.invoke(
            app, ["search", "--semantic", "--library", "Lab", "test"]
        )
        assert result.exit_code == 0
        mock_semantic.semantic_search.assert_called_once_with(
            "test", limit=25, collection_name="group_987"
        )

    @patch("riszotto.cli._import_semantic")
    @patch("riszotto.cli.get_client")
    def test_index_status_with_library(self, mock_get_client, mock_import_semantic):
        mock_zot = MagicMock()
        mock_zot.library_id = "987"
        mock_zot.library_type = "groups"
        mock_get_client.return_value = mock_zot
        mock_semantic = MagicMock()
        mock_import_semantic.return_value = mock_semantic
        mock_semantic.get_index_status.return_value = {"count": 5, "path": "/x"}

        result = runner.invoke(app, ["index", "--status", "--library", "Lab"])
        assert result.exit_code == 0
        mock_semantic.get_index_status.assert_called_once_with(
            collection_name="group_987"
        )
