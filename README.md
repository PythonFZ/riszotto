# riszotto

CLI tool for searching and reading papers from your local Zotero library.

Requires Zotero desktop to be running with the local API enabled.

## Install

```
uvx riszotto --help
```

## Usage

```bash
# Search your library
riszotto search machine learning transformers

# Search full-text content
riszotto search --full-text "attention mechanism"

# View paper metadata as JSON
riszotto info ABC12345

# Read a paper's PDF as markdown
riszotto show ABC12345

# Select a specific PDF attachment (1-indexed)
riszotto show --attachment 2 ABC12345
```
