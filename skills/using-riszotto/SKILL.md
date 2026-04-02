---
name: using-riszotto
description: Use when the user asks to search, read, or export papers from their Zotero library, including group libraries. Use when working with Zotero references, citations, PDFs, or bibliographies. Triggers on "find papers", "search Zotero", "read paper", "export BibTeX", "recent papers", "group library", "shared library".
---

# Using riszotto

CLI for searching, reading, and exporting papers from Zotero. Run via `riszotto <command>`. Requires Zotero desktop running with local API enabled.

If `riszotto` is not found, instruct the user to install it: `uv tool install riszotto` (or `uv tool install "riszotto[semantic]"` for semantic search support).

Default: personal library. Use `-L "Name"` for groups, `-A` for all libraries. Discover with `riszotto libraries`.

## Dos and Don'ts

**Do:**
- Run `riszotto search "query"` directly — output is a readable table
- Read the table output as-is — keys, dates, authors, and titles are all there
- Use `-l` / `--limit` to control result count
- Combine filters: `--author`, `--tag`, `--full-text` to narrow results
- Run multiple searches as separate commands

**Don't:**
- Pipe riszotto output through `python3 -c "import sys,json; ..."` — the table is already human-readable
- Use `--format json` unless you have a specific programmatic need (you almost never do)
- Use `2>/dev/null` to suppress stderr — let errors surface so you can act on them
- Truncate titles manually with `[:80]` — the table already truncates
- Parse table output with scripts — if you truly need structured data, use `--format json`, but question why first
- Chain multiple searches in a single shell command with `echo "---"` separators

## Quick Reference

| Task | Command |
|------|---------|
| List libraries | `riszotto libraries` |
| Search keywords | `riszotto search "query"` |
| Search all libraries | `riszotto search -A "query"` |
| Search group library | `riszotto search -L "Group" "query"` |
| Search all fields | `riszotto search --full-text "query"` |
| Semantic search | `riszotto search --semantic "query"` |
| Filter by author | `riszotto search "topic" --author "Name"` |
| Fuzzy author match | `riszotto search "topic" --author "Name" --fuzzy` |
| Filter by tag | `riszotto search "topic" --tag "tag"` |
| Read paper | `riszotto show <KEY>` |
| Search within PDF | `riszotto show <KEY> --search "term"` |
| Export BibTeX | `riszotto export <KEY>` |
| Collections | `riszotto collections` |
| Recent papers | `riszotto recent` |
| Build semantic index | `riszotto index` |
| JSON output | `riszotto search "query" --format json` |

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
- Check `libraries` output for `Indexed` column before using `--semantic`

## Common Mistakes

- **Zotero not running:** Start Zotero desktop with local API enabled
- **Semantic without index:** Run `riszotto index` first (per library)
- **`show` needs parent key**, not attachment key; requires locally synced PDFs for group libraries
- **Flag conflict:** `-L` = `--library`, `-l` = `--limit`, `-f` = `--format`

Run `riszotto <command> --help` for full options.
