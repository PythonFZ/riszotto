"""Tests for table formatting functions."""

from riszotto.formatting import format_items_table


class TestFormatItemsTable:
    def test_basic_table(self):
        results = [
            {
                "key": "ABC12345",
                "title": "Attention Is All You Need",
                "date": "2017-06-12",
                "authors": ["Vaswani, Ashish", "Shazeer, Noam"],
            },
        ]
        output = format_items_table(results)
        lines = output.strip().splitlines()
        assert lines[0].startswith("KEY")
        assert "DATE" in lines[0]
        assert "AUTHORS" in lines[0]
        assert "TITLE" in lines[0]
        assert "ABC12345" in lines[1]
        assert "2017" in lines[1]
        assert "Vaswani, Ashish" in lines[1]
        assert "Attention Is All You Need" in lines[1]

    def test_empty_results(self):
        output = format_items_table([])
        assert output == "No results found."

    def test_year_extraction(self):
        results = [
            {"key": "K1", "title": "T", "date": "2024-01-15", "authors": []},
        ]
        output = format_items_table(results)
        assert "2024" in output
        assert "2024-01-15" not in output

    def test_year_extraction_short_date(self):
        results = [
            {"key": "K1", "title": "T", "date": "2024", "authors": []},
        ]
        output = format_items_table(results)
        assert "2024" in output

    def test_missing_date(self):
        results = [
            {"key": "K1", "title": "T", "date": "", "authors": []},
        ]
        output = format_items_table(results)
        lines = output.strip().splitlines()
        assert "K1" in lines[1]

    def test_authors_joined_with_semicolon(self):
        results = [
            {"key": "K1", "title": "T", "date": "2024", "authors": ["A", "B", "C"]},
        ]
        output = format_items_table(results)
        assert "A; B; C" in output or "A; B; ..." in output

    def test_long_title_truncated(self):
        results = [
            {"key": "K1", "title": "A" * 200, "date": "2024", "authors": []},
        ]
        output = format_items_table(results)
        lines = output.strip().splitlines()
        assert lines[1].endswith("...")
        assert len(lines[1]) <= 120

    def test_long_authors_truncated(self):
        results = [
            {
                "key": "K1",
                "title": "T",
                "date": "2024",
                "authors": ["Very Long Author Name"] * 5,
            },
        ]
        output = format_items_table(results)
        lines = output.strip().splitlines()
        assert "..." in lines[1]

    def test_semantic_score_column(self):
        results = [
            {
                "key": "K1",
                "title": "T",
                "date": "2024",
                "authors": [],
                "score": 0.95,
            },
        ]
        output = format_items_table(results, semantic=True)
        lines = output.strip().splitlines()
        assert "SCORE" in lines[0]
        assert "0.95" in lines[1]

    def test_multiple_rows(self):
        results = [
            {"key": "K1", "title": "First Paper", "date": "2024", "authors": ["A"]},
            {"key": "K2", "title": "Second Paper", "date": "2023", "authors": ["B"]},
        ]
        output = format_items_table(results)
        lines = output.strip().splitlines()
        assert len(lines) == 3  # header + 2 rows


from riszotto.formatting import format_collections_table


class TestFormatCollectionsTable:
    def test_basic_collections(self):
        collections = [
            {"key": "COL1", "name": "Physics"},
            {"key": "COL2", "name": "Machine Learning"},
        ]
        output = format_collections_table(collections)
        lines = output.strip().splitlines()
        assert "KEY" in lines[0]
        assert "NAME" in lines[0]
        assert "COL1" in lines[1]
        assert "Physics" in lines[1]
        assert "COL2" in lines[2]

    def test_empty_collections(self):
        output = format_collections_table([])
        assert output == "No results found."
