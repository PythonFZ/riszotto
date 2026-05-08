# `riszotto cache populate` — Bulk Library Conversion

## Summary

Add a `riszotto cache populate` command that, given a Zotero library, walks every parent item, downloads each item's first PDF attachment to the PDF cache, and converts it to markdown via the configured converter backend. Both caches are reused as-is, so the command is idempotent and resumable: re-running skips already-cached items in milliseconds.

The command is the natural batch counterpart to `riszotto show`, which does the same pipeline for one item at a time.

## Motivation

Users currently warm caches one paper at a time by running `riszotto show <key>`. For a library of thousands of items this is impractical: there is no way to say "make sure every paper in this library is locally converted and ready to read offline." Long-running docling conversions (~30 s/paper) need to happen overnight, but today they only happen interactively.

Concretely, this blocks:

1. Pre-warming a laptop's cache before an offline trip.
2. Bulk-prepping a group library for an LLM-augmented search workflow that expects markdown to already exist on disk.
3. Idempotent re-runs that incrementally pick up newly added papers without re-converting old ones.

## Design Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Command placement | `riszotto cache populate` (subcommand of existing `cache_app`) | Mental model: cache-warming. Discoverable next to `cache show` / `cache clear`. |
| Scope filters | `--library`, `--collection`, `--limit` | The minimum useful set; `--tag` / `--since` deferred until requested. |
| Outputs | Both PDF and markdown, always | Matches the user's stated goal ("all PDFs and all markdowns ready"). PDF-only / markdown-only flags are YAGNI. |
| Concurrency | Sequential (single loop) | docling is CPU/memory-heavy; multiple workers risk OOM and contention. Existing caches make resume cheap, so wall-clock is rarely the binding constraint. Parallelism deferred. |
| Failure handling | Continue, summarize at end | Single network blip should not abort an 8-hour run. Per-item failures logged to stderr; summary on stdout. |
| Code placement | New module `src/riszotto/bulk.py` | `cli.py` is already 1176 lines; extracting the loop body keeps the CLI thin and lets `populate_library()` be unit-tested without Typer's CliRunner. |
| Item discovery | New `client.all_items()` helper | No existing helper returns "every parent item in a library". `recent_items` is bounded; `search_items` requires a query. |
| Multi-PDF items | First attachment only (default `--attachment 1`, same as `show`) | Consistent with single-item behavior. Multi-attachment support is a future enhancement. |
| Out of scope | Parallelism, `--tag`, `--since`, `--ocr`, `--all-attachments`, retry-on-failure | Each is plausibly useful but not part of the v1 minimum. The cache shape supports adding any of them later without migration. |

## Command Surface

```
riszotto cache populate
    [--library, -L NAME]              # forwarded to _get_zot, same semantics as elsewhere
    [--collection, -c NAME]           # restrict to one collection (partial-name match)
    [--limit, -n N]                   # cap items processed (after filtering)
    [--backend {markitdown,docling}]  # default: configured backend
    [--dry-run]                       # list items that would be processed; exit
    [--no-cache]                      # forwarded to converter to force re-conversion
```

`--no-cache` only affects the markdown (converter) cache. The PDF cache is content-addressed by Zotero's md5, so re-downloading would be wasted bandwidth — it stays a hit. This matches `riszotto show --no-cache`.

Registered as `@cache_app.command("populate")` in `src/riszotto/cli.py`. Reuses the existing `LibraryOption` annotated alias.

## Architecture

### New module: `src/riszotto/bulk.py`

```python
@dataclass
class PopulateResult:
    ok: int
    skipped: dict[str, int]      # reason -> count
    failed: dict[str, list[str]] # reason -> list of "KEY: msg"
    elapsed_seconds: float
    interrupted: bool = False


def populate_library(
    zot: zotero.Zotero,
    *,
    collection_key: str | None = None,
    limit: int | None = None,
    backend: str | None = None,
    no_cache: bool = False,
    dry_run: bool = False,
    progress: ProgressReporter | None = None,
) -> PopulateResult:
    """Walk a library and warm both caches for every item with a PDF."""
```

`ProgressReporter` is a small protocol (`start(total)`, `advance(label)`, `finish()`) so tests can pass a no-op reporter and the CLI can pass a `rich.progress`-backed one.

### New helper: `src/riszotto/client.py`

```python
def all_items(
    zot: zotero.Zotero,
    *,
    collection_key: str | None = None,
    limit: int | None = None,
) -> list[dict[str, Any]]:
    """Return all parent (top-level) items in the library or a collection."""
```

- Calls `zot.collection_items_top(collection_key)` if a collection is given, else `zot.top()`.
- Wraps in `zot.everything(...)` when `limit is None`, so libraries larger than the 100-item API page work transparently.
- When `limit` is set, paginates manually with `start=...` to avoid fetching past the cap.

### CLI wrapper: `src/riszotto/cli.py:cache_populate`

Thin: parse flags, resolve library + collection, instantiate progress, call `populate_library`, print summary, choose exit code. The existing `_get_zot(library=...)` and `_match_library` patterns are reused.

A small `_resolve_collection_key(zot, name) -> str` mirrors the partial-match behavior of `_match_library`: single match wins, ambiguous matches list candidates and exit 1, no match exits 1.

## Per-Item Pipeline

For each parent item from `all_items(...)`:

1. `attachments = get_pdf_attachments(zot, item["key"])`
   - Empty → counted as `skipped["no_pdf"] += 1`.
   - Otherwise take `attachments[0]` (matches `show`'s default `--attachment 1`).

2. `pdf_path = resolve_pdf_path(zot, attachment)` (existing in `client.py`)
   - `PdfNotOnStorageError` → `skipped["not_on_storage"] += 1`.
   - `ZoteroPermissionError` → `skipped["permission"] += 1`.
   - Other `Exception` → `failed["download_failed"].append("KEY: msg")`.
   - Side effect: PDF is now in the PDF cache (md5-keyed).

3. `converter.convert(pdf_path, zotero_key=key, no_cache=no_cache)`
   - `ImportError` → re-raise; the run aborts (e.g. docling extras not installed).
   - Other `Exception` → `failed["convert_failed"].append("KEY: msg")`.
   - On success: markdown + figures are written to the converter cache by `Converter.convert`.

4. Counted as `ok`.

`--dry-run` skips steps 2–3 and prints `[N/M] KEY  TITLE  pdf=Y/N` per item.

## Progress and Output

- **stderr**: progress bar (TTY) or one-line-per-item logs (non-TTY). Matches existing CLI conventions where progress and warnings go to stderr.
- **stdout**: end-of-run summary, dry-run listing.

TTY example:

```
Populating cache for "PotentialSciences" (1247 items, collection: ML papers)
Converting [████████████░░░░░░░░] 612/1247  Smith et al. (2024) Attention is...  ETA 03:42:11
```

Non-TTY example (CI, piped to file):

```
[612/1247] ABC12345  ok
[613/1247] DEF67890  skip:no_pdf
[614/1247] GHI23456  fail:convert_failed: docling timeout
```

End-of-run summary on stdout:

```
Done. 1180 ok, 42 skipped, 25 failed in 4h 12m.
  skipped: 38 no_pdf, 4 not_on_storage
  failed:  21 convert_failed, 4 download_failed
Re-run the same command to retry — cached items are skipped instantly.
```

## Interrupt Handling

`KeyboardInterrupt` is caught at the loop boundary in `populate_library`. The partial `PopulateResult` is returned with `interrupted=True`. The CLI prints `Interrupted at N/M.` plus the partial summary and exits 130.

## Exit Codes

| Outcome | Code |
|---------|------|
| At least one item ok | 0 |
| Zero ok, ≥1 failure or skip | 1 |
| No accessible library, ambiguous collection, missing backend extras | 1 |
| `KeyboardInterrupt` | 130 |

## Testing

### `tests/test_bulk.py` (new)

Pure logic with mocked Zotero client + monkeypatched converter:

- Happy path: 3 items in, 3 ok out.
- Items with no PDF attachment counted as `skipped["no_pdf"]`.
- `PdfNotOnStorageError` and `ZoteroPermissionError` route to `skipped[...]`.
- Generic conversion exception routes to `failed["convert_failed"]` with key + message.
- `ImportError` from converter aborts and re-raises (so the CLI can exit 1).
- `--limit` truncates after discovery, before processing.
- `--dry-run` calls neither `resolve_pdf_path` nor `convert`.
- `KeyboardInterrupt` mid-loop returns a partial `PopulateResult` with `interrupted=True`.
- Cache hits still count as `ok` (idempotent re-runs).

### `tests/test_cli.py` (additions)

Typer integration with existing fixtures:

- `riszotto cache populate --library X` resolves the library and invokes `populate_library`.
- `--collection NAME` resolves to a key.
- Ambiguous collection name exits 1 with candidate list.
- Unknown library exits 1.
- Summary text format on stdout.
- Exit codes: 0 when ok > 0; 1 when ok == 0 and failed > 0; 130 on `KeyboardInterrupt`.

No new live-Zotero integration test — `test_integration_web_api.py` already covers the underlying `download_to_pdf_cache` + `resolve_pdf_path` paths.

## Out of Scope

- **Parallelism** (process pool or thread-per-stage). Adds complexity (memory contention, cache write locking) for unclear win on docling-heavy workloads. Deferred until the sequential version proves to be a real bottleneck.
- **`--tag` / `--since` / `--item-type` filters.** Mirror `search` but not part of the v1 minimum. Easy to add later by widening `all_items()`.
- **`--all-attachments`.** Currently skipped; v1 follows `show`'s "first attachment only" default.
- **`--ocr` / `--table-mode` / `--equation-style` passthrough.** Power users can re-run `riszotto show <key> --ocr` for individual edge cases.
- **Failure log file.** `populate-errors.log` was considered; for now stderr is enough. Easy to add when someone needs it.
- **Retry of failed items only.** Out of scope; could be added later as `riszotto cache populate --retry-failures` reading the (then-existing) failure log.
