# Pagination & Filtering Design

**Goal:** Add pagination to `search` and `show`, value-size filtering to `info`, and section search to `show`.

---

## 1. Search: `--page` flag

Add `--page` / `-p` (default 1). Pyzotero supports `start` + `limit` natively.

- Compute `start = (page - 1) * limit`
- Print footer: `Page 1 (results 1-25). Next: riszotto search --page 2 "query"`
- `--limit` stays as-is (default 25)

```
riszotto search machine learning           # page 1
riszotto search --page 2 machine learning  # results 26-50
```

## 2. Info: `--max-value-size` flag

Default 200 chars. Any JSON value (string) exceeding the threshold gets replaced with `"<hidden (N chars)>"`. The JSON structure stays complete — every key is present.

- `--max-value-size 0` disables filtering (show everything)
- Only applies to string values; numbers, booleans, arrays, nested objects are untouched

```
riszotto info ABC12345                      # abstractNote: "<hidden (1543 chars)>"
riszotto info --max-value-size 0 ABC12345   # full output
riszotto info --max-value-size 500 ABC12345 # more lenient
```

## 3. Show: `--page` with line-based chunking

No cache — re-convert each invocation (markitdown is fast, KISS).

- `--page` / `-p` (default 1): show lines `(page-1)*page_size + 1` through `page*page_size`
- `--page-size` (default 500 lines): chunk size. 500 lines fits small papers in one page, chunks large ones into manageable pieces for agentic LLM context windows.
- `--page 0`: override to dump everything
- Footer: `Page 1/N. Next: riszotto show --page 2 ABC12345`

```
riszotto show ABC12345              # page 1, first 500 lines
riszotto show --page 2 ABC12345     # lines 501-1000
riszotto show --page 0 ABC12345     # all
```

## 4. Show: `--search` with heading-based sections

- `--search` / `-s` flag. Convert PDF, split markdown on `^#{1,6} ` headings.
- Print only sections where the search term appears (case-insensitive substring match).
- Each matching section includes its heading + full content up to the next heading.
- If no sections match: `No sections matching 'X' found.`
- `--search` and `--page` are mutually exclusive (search returns all matching sections).

```
riszotto show --search "regression" ABC12345
```

---

## Files to modify

- `src/riszotto/client.py` — add `start` param to `search_items`
- `src/riszotto/cli.py` — all three commands get new flags
- `tests/test_client.py` — test `start` param
- `tests/test_cli.py` — tests for all new flags
