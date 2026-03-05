# New Commands Design

## Problem

riszotto only supports keyword search and PDF reading. The zotero-mcp server offers tag filtering, collection browsing, advanced search filters, and recent items — all useful for library navigation.

## Changes

### 1. Enhance `search` command with new flags

Add to existing `search` command:
- `--tag TAG` (repeatable, multiple `--tag` flags = AND logic) — filter by tags
- `--item-type TYPE` — filter by Zotero item type (e.g., `journalArticle`, `book`)
- `--since DATE` — only items modified after this date
- `--sort FIELD` — sort field (e.g., `dateModified`, `dateAdded`, `title`, `creator`)
- `--direction asc|desc` — sort direction (default `desc`)

These map directly to pyzotero's `.items()` parameters: `tag`, `itemType`, `since`, `sort`, `direction`.

### 2. New `collections` command

- `riszotto collections` — list all collections as JSON envelope:
  ```json
  {
    "results": [
      {"key": "ABC123", "name": "Machine Learning", "parentCollection": false}
    ]
  }
  ```
- `riszotto collections COLLECTION_KEY` — list items in that collection (same JSON envelope as search, using `_format_result`)

### 3. New `recent` command

- `riszotto recent` — recently added items
- `--limit` (default 10)
- `--max-value-size` (default 200)
- Same JSON envelope as search, using `_format_result`

### Output format

All commands use the same `{page, limit, start, results: [...]}` envelope for consistency.
