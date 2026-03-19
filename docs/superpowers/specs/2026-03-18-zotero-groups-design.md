# Zotero Group Libraries Support

## Summary

Add support for searching, browsing, and exporting from Zotero group/shared libraries in addition to the personal library. Includes a new `libraries` command for discovery, a `--library` flag on all existing commands, a configuration system for remote API access, and per-library semantic search indexes.

All riszotto operations are **read-only** — no write access to any Zotero library is required, so group permission levels (owner/admin/member/viewer) do not affect functionality.

## Motivation

riszotto currently only accesses the local personal Zotero library (hardcoded `library_id="0"`, `library_type="user"`). Users with shared/group libraries cannot search or export from them.

## Design Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Library selection | Per-command `--library` flag | Avoids `cmd <args> search <args>` pattern; explicit and self-contained |
| Library targeting | One library at a time (default: personal) | Simpler UX; covers primary use case |
| Library identifier | Name or ID, auto-detected | Try case-insensitive name match first, fall back to numeric ID |
| Connection strategy | Local first, remote fallback | Zero-config for local users; remote only when needed |
| Configuration | `tomllib` + `os.environ` (zero dependencies) | Python 3.11+ has `tomllib` in stdlib; avoids adding pydantic |
| Semantic index | Namespaced per library (ChromaDB collection per library ID) | Keeps indexes isolated; no cross-contamination |
| Short flag | `-L` for `--library` | `-l` is already used by `--limit` on `search`, `collections`, `recent`, `index` |

## Configuration

### File: `~/.riszotto/config.toml`

```toml
[zotero]
api_key = "ABC123XYZ789"   # from zotero.org/settings/keys
user_id = "123456"          # from zotero.org/settings/keys (numeric, not username)
```

Both fields are optional. Without them, riszotto operates in local-only mode (current behavior). With them, riszotto can fall back to the remote Zotero API when a group is not available locally.

### Environment variable overrides

| Config key | Env var | Purpose |
|-----------|---------|---------|
| `api_key` | `ZOTERO_API_KEY` | Zotero API key |
| `user_id` | `ZOTERO_USER_ID` | Zotero user ID |

### Precedence

defaults < config file < environment variables

### Implementation

A `Config` dataclass in `src/riszotto/config.py`:

```python
@dataclasses.dataclass
class Config:
    api_key: str | None = None
    user_id: str | None = None
```

Loaded by a `load_config()` function that:
1. Sets defaults (all `None`)
2. Reads `~/.riszotto/config.toml` if it exists (via `tomllib`)
3. Overrides with env vars if set

The `~/.riszotto/` directory is **not** created by `load_config()`. It only reads an existing file. The directory is created elsewhere (e.g., by the semantic index) or manually by the user.

## Client Resolution

`get_client()` in `client.py` gains a `library: str | None = None` parameter.

### Resolution logic

```
get_client(library=None):
    config = load_config()

    if library is None:
        # Personal library — same as current behavior
        return Zotero(library_id="0", library_type="user", local=True)

    # Try local first: discover groups via local API
    local_client = Zotero(library_id="0", library_type="user", local=True)
    try:
        local_groups = local_client.groups()
        match = find_group(local_groups, library)
        if match:
            return Zotero(
                library_id=str(match["id"]),
                library_type="group",
                local=True,
            )
    except Exception:
        pass  # local API not available

    # Fall back to remote API (requires config)
    if not config.api_key or not config.user_id:
        raise LibraryNotFoundError(
            f"Group '{library}' not found locally. "
            "Configure api_key and user_id in ~/.riszotto/config.toml "
            "for remote access."
        )

    remote_client = Zotero(
        library_id=config.user_id,
        library_type="user",
        api_key=config.api_key,
    )
    remote_groups = remote_client.groups()
    match = find_group(remote_groups, library)
    if match:
        return Zotero(
            library_id=str(match["id"]),
            library_type="group",
            api_key=config.api_key,
        )

    # No match found
    available = [g["data"]["name"] for g in remote_groups]
    raise LibraryNotFoundError(
        f"Group '{library}' not found. Available: {available}"
    )
```

`LibraryNotFoundError` is a custom exception defined in `client.py`, caught by the CLI layer in `_get_zot()` and surfaced as a `typer.Exit(code=1)` with a user-friendly message.

### Expected pyzotero group data structure

`zot.groups()` returns a list of dicts. Each group dict has:
- `group["id"]` — integer group ID (top-level key)
- `group["data"]["name"]` — string group name (nested under `"data"`)

Both local and remote API return the same structure via pyzotero.

### Group matching (`find_group`)

Applied in strict order — first match wins:

1. **Exact name match** (case-insensitive) — short-circuits, always preferred even if substring matches also exist
2. **Substring name match** (case-insensitive) — if exactly one result, return it; if multiple, raise `AmbiguousLibraryError` listing all matches
3. **Numeric ID match** — try parsing `library` as int, match against `group["id"]`
4. Return `None` if no match

### CLI helper: `_get_zot()`

The existing `_get_zot()` in `cli.py` is updated to accept a `library: str | None` parameter and pass it through to `get_client()`. Its error handling is extended to catch `LibraryNotFoundError` and `AmbiguousLibraryError` alongside the existing `ConnectionError` handling.

## CLI Changes

### New command: `libraries`

```
riszotto libraries
```

Lists the personal library and all accessible group libraries as a **markdown table** (human-friendly discovery command; internally represented as `list[dict]`):

```
Name                ID        Type    Source
My Library          0         user    local
Lab Group           987654    group   local
Dept. Reading       123456    group   remote
```

Discovery logic:
1. Try local API first (`zot.groups()` on local client)
2. If remote config available, also fetch remote groups
3. Merge and deduplicate (a group found both locally and remotely shows as "local")
4. Always include the personal library as the first entry

### Existing commands: `--library` / `-L` flag

Added to: `search`, `show`, `export`, `collections`, `recent`, `index`.

```
riszotto search --library "Lab Group" "neural networks"
riszotto search -L 987654 "neural networks"
riszotto export --library "Lab Group" ITEMKEY --format bibtex
riszotto collections --library "Lab Group"
riszotto recent --library "Lab Group"
riszotto index --library "Lab Group" --rebuild
```

Default: `None` (personal library). The flag accepts a group name or numeric group ID.

### `show` command limitation with remote groups

The `show` command reads PDFs via local file paths (`file://` URLs from Zotero attachments). When using a **remote-only** group library (not synced locally), no local file exists. In this case, `show` raises an error: `"PDF not available locally. The group '{name}' is accessed via remote API and show requires local files. Sync this group in Zotero desktop for PDF access."` Downloading remote PDFs to temp files is out of scope for this iteration.

## Semantic Search

### Per-library indexing

The ChromaDB store at `~/.riszotto/chroma_db/` currently uses a single collection named `"zotero"`. With multi-library support, each library gets its own ChromaDB collection, keyed by a stable identifier:

- Personal library: collection name `user_0`
- Group libraries: collection name `group_{group_id}`

### Migration from existing index

~~On first access, if a collection named `"zotero"` exists and no `user_0` collection exists, automatically rename `"zotero"` to `"user_0"`.~~ **Decision (2026-03-19):** Automatic migration was intentionally removed. Existing users with a `"zotero"` collection must rebuild their index via `riszotto index --rebuild`. The simplification avoids coupling to ChromaDB's internal rename semantics.

### Function signature changes

The following functions in `semantic.py` gain a `collection_name: str = "user_0"` parameter:

- `build_index(zot, collection_name="user_0", ...)` (currently takes only `zot`)
- `semantic_search(query, collection_name="user_0", ...)` (currently takes only `query`)
- `get_index_status(collection_name="user_0")` (currently takes no args)
- `_get_collection(collection_name="user_0")` (currently hardcoded to `"zotero"`)

The CLI layer derives `collection_name` from the resolved library: `"user_0"` when no `--library` flag, or `"group_{id}"` when a group is selected.

### Commands

```
riszotto index --library "Lab Group"           # build index for group
riszotto index --library "Lab Group" --rebuild  # rebuild index for group
riszotto index --library "Lab Group" --status   # show index status for group
riszotto search --library "Lab Group" --semantic "neural networks"
```

Without `--library`, index commands operate on the personal library (unchanged).

## Error Handling

| Scenario | Behavior |
|----------|----------|
| `--library` used, group not found locally, no remote config | `LibraryNotFoundError` with message to configure `api_key`/`user_id` |
| `--library` used, group not found anywhere | `LibraryNotFoundError` listing available groups |
| `--library` substring matches multiple groups | `AmbiguousLibraryError` listing ambiguous matches |
| `show --library` with remote-only group | Error: PDF not available locally |
| `libraries` command, local API unavailable, no remote config | Error: "Zotero desktop not running and no remote config" |
| Remote API call fails (bad key, network) | Error with the upstream message |

All custom exceptions (`LibraryNotFoundError`, `AmbiguousLibraryError`) are caught by `_get_zot()` and surfaced as user-friendly messages via `typer.echo()` + `raise typer.Exit(code=1)`.

## Files

| File | Change |
|------|--------|
| `src/riszotto/config.py` | **New.** `Config` dataclass, `load_config()` function |
| `src/riszotto/client.py` | Modify `get_client()` to accept `library` param; add `find_group()`, custom exceptions |
| `src/riszotto/cli.py` | Add `--library`/`-L` to all commands; update `_get_zot()`; add `libraries` command |
| `src/riszotto/semantic.py` | Add `collection_name` param to functions; migrate `"zotero"` -> `"user_0"` |
| `tests/test_config.py` | **New.** Tests for config loading (file, env vars, precedence) |
| `tests/test_client.py` | Tests for group resolution (name match, ID match, ambiguous, fallback, error cases) |
| `tests/test_cli.py` | Tests for `--library` flag on commands; tests for `libraries` command |
| `tests/test_semantic.py` | Tests for per-library collection namespacing; migration from `"zotero"` collection |
