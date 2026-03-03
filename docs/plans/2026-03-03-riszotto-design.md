# riszotto - Zotero CLI Tool

## Overview

A focused CLI tool for searching and reading papers from a local Zotero library. Connects to the Zotero desktop app's local API (localhost:23119) via pyzotero. Converts PDF attachments to markdown via markitdown for terminal-friendly reading.

## Commands

### `riszotto search <terms...>`

Joins all positional args into a query string. Searches titles, creators, and year by default.

```
uvx riszotto search machine learning large language models
```

Output: compact table to stdout.

```
KEY        YEAR  AUTHOR              TITLE
NNCB6UAH   2018  Imbalzano et al.    Machine learning force fields...
ABC12345   2024  Smith et al.        Large language models for...
```

Flags:
- `--full-text` — search all fields including PDF full-text content
- `--limit N` — max results (default 25)

### `riszotto info <key>`

Returns the item's `data` dict as formatted JSON to stdout.

```
uvx riszotto info NNCB6UAH
```

Pipeable: `riszotto info NNCB6UAH | jq .DOI`

### `riszotto show <key>`

Finds the first PDF attachment, extracts the local file path from `links.enclosure.href`, converts via markitdown, prints markdown to stdout.

```
uvx riszotto show NNCB6UAH
```

Flags:
- `--attachment N` — select Nth PDF attachment (1-indexed, default 1)

## Architecture

```
src/riszotto/
    __init__.py
    cli.py        # Typer app with 3 commands
    client.py     # Thin wrapper around pyzotero (local=True)
```

### Data flow

```
CLI (Typer) --> Client (pyzotero local=True) --> Zotero desktop (localhost:23119)
                                                        |
show command --> extract file:// path from attachment --> markitdown --> stdout
```

### Client

Thin wrapper around pyzotero initialized with:

```python
zotero.Zotero(library_id="0", library_type="user", api_key=None, local=True)
```

No authentication needed. Requires Zotero desktop to be running.

Key patterns borrowed from [zotero-mcp](https://github.com/54yyyu/zotero-mcp):
- Local client initialization
- Attachment discovery via children endpoint, prioritizing PDFs
- Local file path extraction from `links.enclosure.href`
- markitdown conversion: `MarkItDown().convert(str(path)).text_content`

### No Pydantic

Dict access with type hints on helper functions. The 3 commands are simple enough that Pydantic models would be over-engineering. Can add later if scope grows.

## Dependencies

- `typer` — CLI framework
- `pyzotero` — Zotero API client (supports local=True)
- `markitdown` — PDF to markdown conversion

## Entry point

```toml
[project.scripts]
riszotto = "riszotto.cli:app"
```

Enables `uvx riszotto ...` usage.

## Error handling

Fail fast with clear messages, no retries:

- **Zotero not running:** "Zotero desktop is not running. Start Zotero and ensure the local API is enabled."
- **No results:** Empty table with header, exit 0
- **No PDF attachment:** "No PDF attachment found for item {key}."
- **Invalid key:** "Item '{key}' not found in your library."
- **markitdown failure:** "Failed to convert PDF to markdown: {error}"
