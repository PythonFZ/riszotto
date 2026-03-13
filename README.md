# Research Zotero - riszotto

![riszotto](assets/riszotto.png)

[![PyPI version](https://badge.fury.io/py/riszotto.svg)](https://badge.fury.io/py/riszotto)
[![Spec-Driven Development](https://img.shields.io/badge/Spec--Driven_Development-blue)](https://github.blog/ai-and-ml/generative-ai/spec-driven-development-with-ai-get-started-with-a-new-open-source-toolkit/)
[![Skills Enabled](https://img.shields.io/badge/Skills-Enabled-green)](https://agentskills.io/)

CLI tool for searching, reading, and exporting papers from your local Zotero library.

Requires Zotero desktop to be running with the local API enabled.

## Getting Started

Requires [uv](https://docs.astral.sh/uv/getting-started/installation/).

```bash
uvx riszotto --help
```

For semantic search:

```bash
uvx --with "riszotto[semantic]" riszotto search --semantic "query"
```

## Usage

```bash
# Search your library
riszotto search machine learning transformers

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

# Build semantic search index
riszotto index
```

## Claude Code Skill

Install the skill to help Claude Code agents use riszotto:

```bash
npx skills add https://github.com/pythonfz/riszotto
```

## Acknowledgments

Inspired by [zotero-mcp](https://github.com/54yyyu/zotero-mcp).
