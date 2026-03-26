# Table Output Default + Skill Update

## Problem

Agents using riszotto consistently pipe JSON through Python one-liners to get readable output:

```bash
uvx riszotto search "MLIP arena" -l 3 2>/dev/null | python3 -c "import sys,json; d=json.load(sys.stdin); [print(f'  {r[\"key\"]}: {r[\"title\"][:80]} ({r[\"date\"]})') for r in d.get('results',[])]"
```

This is ugly, fragile, and repeated across every agent session. The CLI should provide human-readable output by default.

## Design

### CLI: Table output as default

**Affected commands:** `search`, `recent`, `collections`

**Not affected:** `libraries` (already table), `show` (markdown), `export` (bibtex), `index` (text/JSON status)

#### `--format` / `-f` flag

Add `--format` / `-f` to `search`, `recent`, and `collections`. Accepts `table` (default) or `json`. This is consistent with `export` which already has `--format` / `-f` (defaulting to `bibtex`).

| Command | `--format` values | Default |
|---------|-------------------|---------|
| `search` | `table`, `json` | `table` |
| `recent` | `table`, `json` | `table` |
| `collections` | `table`, `json` | `table` |
| `export` | `bibtex` (existing) | `bibtex` |

#### Table format for item results

```
KEY        DATE   AUTHORS                  TITLE
ABC12345   2024   Smith, J; Doe, A         MLIP Arena: Benchmarking Machine Learning Inter...
DEF45678   2023   Lee, K                   Active Learning for MLIP Training Data Selectio...
```

- Columns: `KEY`, `DATE`, `AUTHORS`, `TITLE`
- `DATE`: extract year only (first 4 digits from Zotero's date string; empty string if no date)
- `AUTHORS`: join list with `; `, truncate to column width with `...`
- `TITLE`: fills remaining width, truncated with `...`
- No abstract, tags, or itemType in table view (available via `--format json`)
- Semantic search adds a `SCORE` column between `AUTHORS` and `TITLE`
- **Empty results:** print `No results found.` (no header row)

#### Table format for `--all-libraries` search

Group results under library name headers. Each library gets its own header row:

```
── My Library ──
KEY        DATE   AUTHORS                  TITLE
ABC12345   2024   Smith, J; Doe, A         MLIP Arena: Benchmarking...

── Shared Group ──
KEY        DATE   AUTHORS                  TITLE
GHI78901   2023   Zhang, W                 Foundation Models for...
```

No per-library pagination — `--all-libraries` mode does not support `--page`. When `--format json` is used with `--all-libraries`, output the current grouped dict unchanged.

#### Table format for collections listing

```
KEY        NAME
COL123     Machine Learning
COL456     Thermodynamics
```

When listing items within a collection (key provided), use the same item table as search.

Collections listing (`collections` without a key) has no pagination.

#### Pagination footer

For commands with `--page` support (`search`, `collections` with key):

```
Page 1/3. Next: uvx riszotto search "query" --page 2
```

No footer when results fit in one page. `recent` has no `--page` parameter, so no pagination footer.

### Implementation details

#### Table formatting in `formatting.py`

Add two public functions:

- `format_items_table(results: list[dict], *, semantic: bool = False) -> str`
- `format_collections_table(collections: list[dict]) -> str`

Input: the dicts already produced by `_format_result` / `_format_collection`. The table formatter joins `authors` lists with `; `.

Column widths (fixed, no terminal detection): `KEY` 10, `DATE` 6, `AUTHORS` 25, `SCORE` 6 (semantic only), `TITLE` fills remainder up to 120 chars total width. Truncate with `...` when content exceeds column width. Year extraction (`date[:4]`) happens in the table formatter, not in `_format_result`.

#### CLI changes in `cli.py`

- Define a shared `FormatOption` (like `LibraryOption` on line 32) using a plain string with default `"table"` — matching how `export` defines its `--format` (plain string, not `Choice`)
- Add `--format` / `-f` to `search`, `recent`, `collections`
- Thread `format` param into `_search_all_libraries` helper (it currently outputs JSON directly on line 314)
- When `--format json`: use existing `json.dumps(envelope, indent=2)` path unchanged
- When table (default): call `_format_result` with `max_value_size=0` (no truncation — table handles its own), then pass results to `format_items_table()`
- `max_value_size` option: keep on all commands for `--format json` backward compat, ignored in table mode

#### Existing test migration

21 tests in `tests/test_cli.py` call `json.loads(result.output)` on command output. All must add `"--format", "json"` to their invocation args. Affected test classes: `TestSearch` (7), `TestSearchSemantic` (3), `TestCollections` (3), `TestRecent` (2), `TestFuzzyAuthorMatching` (4), `TestAllLibrariesSearch` (2).

New table-formatting unit tests should go in `tests/test_formatting.py`.

### Skill update

Update the skill file:
- `skills/using-riszotto/SKILL.md`

#### Dos and Don'ts section

Add a prominent section near the top of each skill:

```markdown
## Dos and Don'ts

**Do:**
- Run `uvx riszotto search "query"` directly — output is a readable table
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
```

#### Other skill changes

- Remove any mention of JSON as the default output format for search/recent/collections
- Remove "Output: JSON with `results` array..." from search command details
- Add note that default output is a human-readable table
- Add `--format json` flag to the quick reference table where relevant

### Files to modify

| File | Change |
|------|--------|
| `src/riszotto/formatting.py` | Add `format_items_table()`, `format_collections_table()` |
| `src/riszotto/cli.py` | Add `--format json` flag to `search`, `recent`, `collections`; default to table output |
| `skills/using-riszotto/SKILL.md` | Update output docs, add Dos and Don'ts |
| `tests/` | New tests for table formatting; migrate existing JSON-parsing tests to use `--format json` |

### Not in scope

- Changing `index --status` output (low frequency, JSON is fine)
- Changing `libraries` (already table)
- Changing `show` or `export` (already non-JSON)
- Color/styling in table output (keep it plain text for agent consumption)
- Adding `--page` to `recent` (out of scope, simple list command)
- `--no-header` flag (not needed for agent use case)
