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
```

## Group Libraries

All commands support `--library` / `-L` to target a group library by name or ID. Without it, commands default to the personal library.

For groups not synced locally, configure `~/.riszotto/config.toml` for remote API access:

```toml
[zotero]
api_key = "..."   # from zotero.org/settings/keys
user_id = "..."   # from zotero.org/settings/keys
```

## Claude Code Skill

Install the skill to help Claude Code agents use riszotto:

```bash
npx skills add https://github.com/pythonfz/riszotto
```

## Acknowledgments

Inspired by [zotero-mcp](https://github.com/54yyyu/zotero-mcp).
