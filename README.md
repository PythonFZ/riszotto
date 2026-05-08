# Research Zotero - riszotto

![riszotto](assets/riszotto.png)

[![PyPI version](https://badge.fury.io/py/riszotto.svg)](https://badge.fury.io/py/riszotto)
[![Spec-Driven Development](https://img.shields.io/badge/Spec--Driven_Development-blue)](https://github.blog/ai-and-ml/generative-ai/spec-driven-development-with-ai-get-started-with-a-new-open-source-toolkit/)
[![Skills Enabled](https://img.shields.io/badge/Skills-Enabled-green)](https://agentskills.io/)

CLI tool for searching, reading, and exporting papers from your Zotero libraries — personal and group.

Requires Zotero desktop to be running with the local API enabled.

## Getting Started

Requires [uv](https://docs.astral.sh/uv/getting-started/installation/).

```bash
uv tool install riszotto
riszotto --help
```

For semantic search:

```bash
uv tool install "riszotto[semantic]"
riszotto search --semantic "query"
```

## Usage

```bash
# List available libraries (personal + groups)
riszotto libraries

# Search your library
riszotto search machine learning transformers

# Search a group library
riszotto search -L "My Group" "neural networks"

# Full-text search
riszotto search --full-text "attention mechanism"

# Semantic search (requires index)
riszotto search --semantic "how do transformers work"

# Filter by author or tag
riszotto search "deep learning" --author "Hinton"
riszotto search "ML" --tag "papers" --tag "2024"

# Read a paper's PDF as markdown
riszotto show ABC12345
riszotto show ABC12345 --page 2
riszotto show ABC12345 --search "methodology"

# Export BibTeX
riszotto export ABC12345

# Browse collections and recent papers
riszotto collections
riszotto recent

# Build semantic search index (per library)
riszotto index
riszotto index -L "My Group"

# Bulk-populate the cache

Download every PDF and convert each to markdown for an entire library.
Re-runs are idempotent: cached items are skipped instantly.

```bash
# Whole library
riszotto cache populate --library "potentialsciences"

# Just one collection, limited to the first 50 items (useful for testing)
riszotto cache populate --library "potentialsciences" \
    --collection "ML papers" --limit 50

# Dry-run: list items that would be processed
riszotto cache populate --dry-run
```

The command prints a progress bar to stderr and an end-of-run summary
to stdout. Per-item failures are logged but do not abort the run.
```

## Group Libraries

All commands support `--library` / `-L` to target a group library by name or ID. Without it, commands default to the personal library.

## Configuration

The config file path follows OS conventions (via `platformdirs`). Run
`riszotto config` to print the resolved path and the currently-loaded
values on your machine. Typical locations:

| OS | Path |
|----|------|
| macOS | `~/Library/Application Support/riszotto/config.toml` |
| Linux | `$XDG_CONFIG_HOME/riszotto/config.toml` (defaults to `~/.config/riszotto/config.toml`) |
| Windows | `%APPDATA%\riszotto\config.toml` |

Contents:

```toml
[zotero]
api_key = "..."   # from zotero.org/settings/keys
user_id = "..."   # numeric user ID
mode = "auto"     # "auto" (default) | "local" | "web"
```

Mode resolution:

| `mode` | creds set | result |
|--------|-----------|--------|
| `auto` (default) | yes | use the Zotero Web API |
| `auto` | no | use the local Zotero desktop |
| `local` | — | always local |
| `web` | yes | always web |
| `web` | no | error: web mode requires creds |

Environment variables (override the TOML file):

- `RISZOTTO_ZOTERO_API_KEY`
- `RISZOTTO_ZOTERO_USER_ID`
- `RISZOTTO_ZOTERO_MODE`

In web mode, `show` downloads attachment PDFs into a content-addressed
cache (path varies by OS — see `riszotto cache show`) under `pdfs/{md5}.pdf`,
deduplicated across libraries. The PDF must be on Zotero storage —
attachments with `md5 = null` (file sync disabled, metadata-only
attachments) cannot be retrieved over the web API.

## Claude Code Skill

Install the skill to help Claude Code agents use riszotto:

```bash
npx skills add https://github.com/pythonfz/riszotto
```

## Acknowledgments

Inspired by [zotero-mcp](https://github.com/54yyyu/zotero-mcp).
