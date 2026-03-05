# Search Improvements Design

## Problem

1. **Result quality**: Full-text search (`qmode="everything"`) is now the default, returning papers that merely cite search terms in references/body text, burying the actual relevant papers.
2. **Display truncation**: The compact table format truncates authors (18 chars) and titles (60 chars), losing useful information.
3. **Redundant command**: `info` command overlaps with search if search returns full metadata.

## Changes

### 1. Default search mode: revert to metadata-only

- Change `full_text` default back to `False` (`qmode="titleCreatorYear"`)
- `--full-text` remains available as opt-in flag

### 2. JSON output instead of table

- Replace compact table with JSON envelope:
  ```json
  {
    "page": 1,
    "limit": 25,
    "start": 0,
    "results": [
      {
        "key": "CE4EZTKL",
        "title": "Effect of the damping function in ...",
        "itemType": "journalArticle",
        "date": "2011",
        "authors": ["Grimme, Stefan", "Ehrlich, Stephan", "Goerigk, Lars"],
        "abstract": "<hidden (1234 chars)>",
        "tags": ["density functional theory", "dispersion energy"]
      }
    ]
  }
  ```
- Add `--max-value-size` option (default 200) to truncate long string values (reuse `_filter_long_values` from current `info` command)
- Keep `--limit` and `--page` for pagination

### 3. Remove `info` command

- Redundant now that `search` returns full metadata as JSON
- Remove the command; keep `_filter_long_values` helper (reused by search)
