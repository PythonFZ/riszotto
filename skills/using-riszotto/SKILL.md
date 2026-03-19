---
name: using-riszotto
description: Use when the user asks to search, read, or export papers from their Zotero library, including group libraries. Use when working with Zotero references, citations, PDFs, or bibliographies. Triggers on "find papers", "search Zotero", "read paper", "export BibTeX", "recent papers", "group library", "shared library".
---

# Using riszotto

CLI for searching, reading, and exporting papers from Zotero. Run via `uvx riszotto <command>`. Requires Zotero desktop running with local API enabled.

Default: personal library. Use `-L "Name"` for groups, `-A` for all libraries. Discover with `uvx riszotto libraries`.

## Quick Reference

| Task | Command |
|------|---------|
| List libraries | `uvx riszotto libraries` |
| Search keywords | `uvx riszotto search "query"` |
| Search all libraries | `uvx riszotto search -A "query"` |
| Search group library | `uvx riszotto search -L "Group" "query"` |
| Search all fields | `uvx riszotto search --full-text "query"` |
| Semantic search | `uvx riszotto search --semantic "query"` |
| Filter by author | `uvx riszotto search "topic" --author "Name"` |
| Fuzzy author match | `uvx riszotto search "topic" --author "Name" --fuzzy` |
| Filter by tag | `uvx riszotto search "topic" --tag "tag"` |
| Read paper | `uvx riszotto show <KEY>` |
| Search within PDF | `uvx riszotto show <KEY> --search "term"` |
| Export BibTeX | `uvx riszotto export <KEY>` |
| Collections | `uvx riszotto collections` |
| Recent papers | `uvx riszotto recent` |
| Build semantic index | `uvx riszotto index` |

## Search Strategy

Follow this cascade when searching:

1. **Keyword search** (default) — fast, precise for known titles/authors
2. **`--full-text`** — if 0 results, retry (searches all metadata fields)
3. **`--semantic`** — for natural language queries; requires `index` built first
4. **`-A`** — search across all libraries at once

Tips:
- Fewer terms = more hits (keyword mode uses AND logic)
- `--author "name"` handles diacritics automatically ("schafer" matches "Schäfer")
- `--fuzzy` with `--author` for uncertain spelling (Levenshtein distance <= 2)
- `--max-value-size 0` to see full abstracts
- Check `libraries` output for `Indexed` column before using `--semantic`

## Common Mistakes

- **Zotero not running:** Start Zotero desktop with local API enabled
- **Semantic without index:** Run `uvx riszotto index` first (per library)
- **`show` needs parent key**, not attachment key; requires locally synced PDFs for group libraries
- **Flag conflict:** `-L` = `--library`, `-l` = `--limit`

Run `uvx riszotto <command> --help` for full options.
