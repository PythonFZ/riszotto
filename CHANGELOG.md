# Changelog

## Unreleased

### Added
- `mode` config field (`auto` | `local` | `web`) selects between the local
  Zotero desktop and the Zotero Web API for both personal and group libraries.
- `show` works against the Web API by downloading attachment PDFs into a
  content-addressed cache (`~/.cache/riszotto/pdfs/{md5}.pdf`).
- `cache show` reports the new PDF cache. `cache clear` clears it; new
  `--only conversions|pdfs` flag for selective clearing.

### Changed (breaking)
- Environment variables are renamed to use the `RISZOTTO_` prefix:
  `ZOTERO_API_KEY` → `RISZOTTO_ZOTERO_API_KEY`,
  `ZOTERO_USER_ID` → `RISZOTTO_ZOTERO_USER_ID`. The old names are no
  longer read. Update your shell config; TOML config is unchanged.
- With credentials configured, the personal library now uses the Web API
  (previous behavior: local-only for personal, Web for groups).
  Set `mode = "local"` to keep the previous personal-library behavior.
