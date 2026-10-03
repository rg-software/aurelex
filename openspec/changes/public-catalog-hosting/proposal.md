## Why

The curated dictionary catalog and the dictionary files it points at are hosted
on a maintainer's self-hosted Seafile share, and the repository is private. That
is adequate for internal testing but not for a public, open-source release: the
compiled-in URL leaks maintainer infrastructure and is not a stable, CDN-backed
location; the dictionary files carry hand-maintained, often-missing integrity
metadata; and the catalog itself has been hand-authored. Publishing the app
requires a stable, generated publication path that a release build can rely on
and that a future dictionary-update capability can build on.

## What Changes

- **Serve the catalog from GitHub Pages** at a stable URL and point the
  compiled-in default at it, replacing the Seafile share. The URL is decoupled
  from any branch or tag, so renaming or deleting a branch cannot break every
  installed app.
- **Host dictionary files as GitHub release assets** under **one permanent,
  never-deleted release tag** (not `releases/latest`), and point the catalog's
  file URLs there, so the URLs do not change when the app releases.
- **Generate the catalog** with `scripts/build-catalog.py`, which emits
  `catalog.json` from a maintained source and computes `sizeBytes` and a
  SHA-256 digest for every file, and enforces **stable, append-only entry ids
  and file names**. `sha256` becomes present on every published file, so
  integrity verification always applies and installed content is identifiable.
- **Record the installed content digest** per catalog entry when a catalog
  download completes, in `settings.json`. This is inert data (no UI, no update
  check reads it yet); it exists so the catalog's always-present digests identify
  what a user actually installed, and a future update capability can compare
  manifest and installed digests without re-hashing multi-gigabyte files.
- **Ready the repository for public access**: Aurelex's own license notice and a
  `THIRD-PARTY-NOTICES.md` (already added), an ignore for local agent/session
  state, a secret scan of history, repository metadata, and enabling Pages.

**Not in scope — deliberately:** entry version comparison, an "update available"
indication, or any update/upgrade action. The app stays a read-only list for
installed entries, exactly as the current `remote-dictionary-catalog`
specification requires. The digest recording above only makes that future work
clean; it adds no lifecycle behavior. A separate change will introduce dictionary
updates when we choose to build them.

Not a breaking change. No `schemaVersion` bump: the manifest parser already
tolerates the digests being present, and the app's "verify when supplied, accept
when absent" behavior is unchanged for older readers.

## Capabilities

### New Capabilities

None. This change hardens how an existing capability is delivered and published;
it introduces no new user-facing surface.

### Modified Capabilities

- `remote-dictionary-catalog`: adds a *Generated catalog publication* requirement
  (the catalog is generated from a maintained source, served from a stable HTTPS
  location, carries a computed size and SHA-256 digest for every file, keeps
  entry ids and file names stable and append-only, and references dictionary-file
  URLs that do not change when the app releases) and an *Installed catalog
  content is identifiable* requirement (the installed digests are recorded, with
  no update or version-comparison action added). The existing read-only catalog
  behavior is unchanged.

## Impact

- `app/EngineController.hpp` — the compiled-in default catalog URL.
- `app/EngineController.cpp` — persist the installed content digest per entry
  when a catalog download batch completes (`settings.json`).
- `app/RemoteCatalog.*` — parsing is unchanged; the digest field already exists
  and stays optional for backward compatibility.
- New `scripts/build-catalog.py` (with tests) and a `.github/workflows/pages.yml`
  that deploys the generated document; a release-asset upload path for the
  dictionary files.
- `docs/REMOTE-CATALOG.md`, `docs/DEVELOPMENT.md`, `README.md`, `.gitignore`.
- Repository settings (visibility, Pages), not code.
- No `engine/` or `patches/` change. No stored-state reinterpretation; rollback is
  restoring the previous URL.
