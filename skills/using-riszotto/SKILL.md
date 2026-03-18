---
name: using-riszotto
description: Use when the user asks to search, read, or export papers from their Zotero library, including group libraries. Use when working with Zotero references, citations, PDFs, or bibliographies. Triggers on "find papers", "search Zotero", "read paper", "export BibTeX", "recent papers", "group library", "shared library".
---

# Using riszotto

## Overview

**riszotto** is a CLI tool for searching, reading, and exporting papers from all Zotero libraries. Run commands via `uvx riszotto <command>` — no install needed.

**Prerequisite:** Zotero desktop must be running with the local API enabled (default port 23119).

## When to Use

- User wants to search, read, or export papers from their Zotero library
- User needs BibTeX citations with field control
- User wants to browse collections or recent additions
- User needs semantic (natural language) search

Commands default to the personal library. Use `--library` / `-L` to target a different library (discover with `uvx riszotto libraries`).

## Quick Reference

| Task | Command |
|------|---------|
| List available libraries | `uvx riszotto libraries` |
| Search by keywords | `uvx riszotto search "query terms"` |
| Search a group library | `uvx riszotto search -L "My Group" "query"` |
| Search all fields | `uvx riszotto search --full-text "query"` |
| Semantic search | `uvx riszotto search --semantic "natural language query"` |
| Filter by author | `uvx riszotto search "topic" --author "LastName"` |
| Filter by tag | `uvx riszotto search "topic" --tag "tagname"` |
| Read a paper | `uvx riszotto show <KEY>` |
| Search within PDF | `uvx riszotto show <KEY> --search "term"` |
| Export BibTeX | `uvx riszotto export <KEY>` |
| List collections | `uvx riszotto collections` |
| Recent papers | `uvx riszotto recent` |
| Build semantic index | `uvx riszotto index` |

## Group Libraries

All commands accept `--library` / `-L` with a group name or numeric ID. Matching: exact name > substring > ID. Without `-L`, commands use the personal library.

```bash
uvx riszotto libraries                              # discover groups
uvx riszotto search -L "My Group" "neural networks"  # search a group
uvx riszotto index -L "My Group"                     # build semantic index for group
```

For groups not synced locally, configure `~/.riszotto/config.toml` with `api_key` and `user_id` from zotero.org/settings/keys.

## Common Workflows

### Search and Read

```bash
# 1. Search for papers
uvx riszotto search "attention mechanisms"

# 2. Copy the key from results (e.g., ABC12345)
# 3. Read the paper
uvx riszotto show ABC12345

# 4. Navigate pages or search within
uvx riszotto show ABC12345 --page 2
uvx riszotto show ABC12345 --search "methodology" --context 5
```

### Export Citations

```bash
# Clean BibTeX (strips file, abstract, note, keywords, urldate, annote)
uvx riszotto export ABC12345

# All fields
uvx riszotto export ABC12345 --include-all

# Custom exclusions
uvx riszotto export ABC12345 --exclude file --exclude abstract
```

### Semantic Search (requires one-time index build per library)

```bash
# Build index first (once per library)
uvx riszotto index
uvx riszotto index -L "My Group"  # for group libraries

# Then search naturally
uvx riszotto search --semantic "how do transformers handle long sequences"
```

## Command Details

### libraries
`uvx riszotto libraries`

Lists all accessible libraries with name, ID, type, item count, and source (local/remote).

### search
`uvx riszotto search [OPTIONS] TERMS...`

Key options: `--full-text`, `--semantic`, `--author NAME`, `--tag TAG` (repeatable, AND logic), `--item-type TYPE`, `--since DATE`, `--sort FIELD`, `--direction asc|desc`, `--limit N`, `--page N`, `--library NAME_OR_ID`

Output: JSON with `results` array containing `key`, `title`, `authors`, `abstract`, `tags`, and pagination metadata.

### show
`uvx riszotto show KEY [OPTIONS]`

Key options: `--attachment N` (1-indexed), `--page N` (0=all), `--page-size N` (default 500), `--search TERM`, `--context N` (default 3), `--library NAME_OR_ID`

Output: Markdown-converted PDF content.

### export
`uvx riszotto export KEY [OPTIONS]`

Key options: `--format bibtex` (default), `--exclude FIELD` (repeatable), `--include-all`, `--library NAME_OR_ID`

### collections
`uvx riszotto collections [COLLECTION_KEY] [--library NAME_OR_ID]`

Without key: lists all collections. With key: lists items in that collection.

### recent
`uvx riszotto recent [--limit N] [--library NAME_OR_ID]`

Shows recently added papers (default 10).

### index
`uvx riszotto index [OPTIONS]`

Key options: `--rebuild` (full rebuild), `--status` (show stats), `--limit N`, `--library NAME_OR_ID`

Each library has its own separate semantic index.

## Common Mistakes

- **Zotero not running:** All commands fail with a connection error. Remind the user to start Zotero desktop.
- **Semantic search without index:** `--semantic` requires `uvx riszotto index` first (per library). A clear error shows the exact command needed.
- **Using item key vs attachment key:** `show` expects the parent item key, not the PDF attachment key.
- **show with remote-only groups:** `show` requires locally synced PDFs. Sync the group in Zotero desktop first.
- **Short flag conflict:** `-L` is `--library`, `-l` is `--limit`.
