# Search Improvements Design

**Date:** 2026-03-19
**Branch:** feat/search-improvements
**Status:** Approved

## Context

Integration testing of the riszotto CLI with real-world prompts revealed several issues:

1. Semantic search crashes due to a ChromaDB API change (`NotFoundError` vs `ValueError`)
2. No way to search across all libraries at once — users must run 4 separate searches
3. Author matching fails on diacritics ("bogdau" won't find "Magdău")
4. The SKILL.md lacks search strategy guidance, so AI assistants don't know which search mode to use
5. No visibility into which libraries have a semantic index

## 1. Bug Fix: `_maybe_migrate` Crash

**File:** `src/riszotto/semantic.py`

The `_maybe_migrate` function catches `ValueError` when checking for a legacy `"zotero"` collection, but ChromaDB now raises `chromadb.errors.NotFoundError` for missing collections.

**Fix:** Change the except clause to catch both:

```python
from chromadb.errors import NotFoundError

try:
    old = client.get_collection(name="zotero")
    old.modify(name="user_0")
except (ValueError, NotFoundError):
    pass  # no legacy collection
```

## 2. Cross-Library Search

**Files:** `src/riszotto/cli.py`, `src/riszotto/client.py`

### New flag

Add `--all-libraries` / `-A` to the `search` command. Mutually exclusive with `--library`.

### Behavior

1. Discover all accessible libraries using the same logic as the `libraries` command (local personal + local groups + remote groups)
2. Run the search against each library
3. Return results grouped by library name
4. Omit libraries with 0 results
5. For `--semantic` mode, skip libraries without an index (no error, just skip)

### Output format

When `--all-libraries` is active, the JSON output changes to a grouped structure:

```json
{
  "My Library": {
    "page": 1,
    "limit": 25,
    "start": 0,
    "results": [
      {"key": "SM3VRDWP", "title": "Computer simulation of diffusion coefficients...", ...}
    ]
  },
  "ICP Bib": {
    "page": 1,
    "limit": 25,
    "start": 0,
    "results": [
      {"key": "FQ5QWHLH", "title": "Collaboration on machine-learned potentials...", ...}
    ]
  }
}
```

Each library's results use the same envelope format as single-library search. Libraries with zero results are omitted from the output.

### Implementation

Add a helper `_discover_libraries()` that returns a list of `(name, zot_client)` tuples, reusing the discovery logic from the `libraries` command. The search command loops over these clients when `-A` is set.

For semantic search with `-A`: attempt `get_index_status()` for each library's collection. If count is 0 or the collection doesn't exist, skip that library silently.

## 3. Fuzzy Author Matching

**Files:** `src/riszotto/cli.py`

### Default behavior change

The `--author` filter currently does case-insensitive substring matching. The new default adds **diacritic-insensitive matching** via Unicode normalization:

```python
import unicodedata

def _normalize(text: str) -> str:
    """Strip diacritics and lowercase for comparison."""
    nfkd = unicodedata.normalize("NFKD", text)
    return "".join(c for c in nfkd if not unicodedata.category(c).startswith("M")).lower()
```

This means `--author "bogdau"` matches "Magdău", `--author "schafer"` matches "Schäfer". No new dependencies.

### New `--fuzzy` flag

When `--fuzzy` is passed alongside `--author`, matching uses Levenshtein distance (threshold ≤ 2) on top of diacritic normalization. This catches typos and partial name recall.

Implementation: a simple Levenshtein function (stdlib-only, no external dependency). Applied as a sliding window over the normalized author name to find the best substring match distance.

```
--author "bogdan" --fuzzy  →  matches "Magdău" (normalized "magdau", distance 1 from "bogdan")
```

`--fuzzy` without `--author` is ignored (no error).

## 4. Libraries Command: Index Status

**Files:** `src/riszotto/cli.py`, `src/riszotto/semantic.py`

Add an `Indexed` column to `libraries` output showing whether a semantic index exists for each library and its document count.

```
Name                           ID         Type     Items    Indexed  Source
---------------------------------------------------------------------------
My Library                     0          user     624      573      local
gmnn_and_friends               4832688    group    8        -        local
ICP Bib                        5796833    group    11536    3000     local
potentialsciences              6448354    group    18       -        local
```

`-` means no index exists. A number means the index has that many documents.

Implementation: for each library, derive the collection name and call `get_index_status()`. If the collection doesn't exist, show `-`. Requires the semantic extras to be installed; if not installed, show `-` for all.

## 5. SKILL.md Search Strategy

**File:** `skills/using-riszotto/SKILL.md`

Add a "Search Strategy" section after the "Quick Reference" table:

```markdown
## Search Strategy

When searching for papers, follow this cascade:

1. **Keyword search** (default) — fast, precise for known titles/authors
2. **`--full-text`** — if 0 results from keyword search, retry with this flag (searches all metadata fields)
3. **`--semantic`** — for natural language queries ("how do transformers handle long sequences"); requires a built index
4. **`--all-libraries` / `-A`** — search across all accessible libraries at once

Tips for better results:
- Reduce search terms if getting 0 results — keyword mode uses AND logic, so more terms = fewer hits
- Use `--max-value-size 0` to see full abstracts when evaluating relevance
- Use `--author "name"` to filter by author; diacritics are handled automatically
- Add `--fuzzy` with `--author` if unsure about exact spelling
- Use `show <KEY> --search "term"` to find specific values within a paper's PDF
- Check `libraries` output for the `Indexed` column before using `--semantic`
```

## Testing

- **Bug fix:** Update `test_semantic.py` migration tests to verify both `ValueError` and `NotFoundError` are caught
- **Cross-library search:** Test with mock multi-library setup; test grouped output format; test `--all-libraries` mutual exclusivity with `--library`; test semantic skip for unindexed libraries
- **Fuzzy author:** Test diacritic normalization ("Magdău" via "magdau"); test Levenshtein matching with `--fuzzy`; test `--fuzzy` without `--author` is no-op
- **Index status in libraries:** Test with/without semantic extras installed; test mixed indexed/unindexed libraries

## Non-goals

- Query preprocessing (term splitting, abbreviation expansion) — handled by SKILL.md guidance instead
- Automatic search mode fallback — the AI assistant chains commands per SKILL.md strategy
- Changes to Zotero API query modes — we use what pyzotero provides
