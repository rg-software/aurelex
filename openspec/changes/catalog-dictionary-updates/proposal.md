## Why

Two related gaps in the shipped catalog surface, now that the catalog is public
and maintained over time:

1. **The status line misstates its own datum.** The catalog header shows
   "Updated &lt;time&gt;", but that value is when the app last *fetched* the
   manifest, not when the catalog changed. Worse, the surrounding strings say
   "Checking for updates:" and "Update check failed", although the app performs
   no update check at all — the current specification forbids it. The wording
   promises a lifecycle action that does not exist and describes the fetch time
   as a content date, so a user cannot tell "is this list fresh?" from "did a
   dictionary change?".
2. **An installed catalog dictionary can never be updated.** The catalog is a
   one-shot installer: once an entry is installed, the app never notices that the
   dictionary's content changed upstream, and the only refresh path is remove and
   reinstall. For a public catalog this is a real gap — and skipping it is
   wasteful, because the baseline is already recorded on device: since
   `public-catalog-hosting`, the app stores each installed entry's required-file
   SHA-256 (`catalogInstalledDigests`), explicitly so staleness can be detected
   without re-reading multi-GB files.

Deferring nothing further: the recorded digests are inert today (nothing consumes
them), so this change gives them their purpose.

## What Changes

- **Correct the catalog status wording.** Replace the "update"-flavoured strings
  with what the app actually does — a *check* of the catalog — and relabel the
  fetch-time line so it reads as when the catalog was last checked, not when it
  changed. Surface catalog-content staleness/availability only where it is true.
- **Detect updates for catalog-installed entries.** On a probe, compare each
  installed entry's recorded required-file SHA-256 against the manifest's. A
  difference marks that entry as having an update available. Detection is
  **catalog-installed entries only**; folder-imported dictionaries have no
  recorded digest and are never offered an update.
- **Apply an update — user-confirmed.** An entry with an update available offers
  an update affordance; the user taps it to apply. The system downloads the
  changed files and replaces the installed copies **in place** (same staging
  directory), so the dictionary keeps its name, position and group membership,
  then reloads it. Unlike adding optional audio, an update changes article text,
  so the dictionary's **full-text index is rebuilt** as part of the update.
- **BREAKING (specification):** the `remote-dictionary-catalog` requirement that
  says the system "SHALL NOT offer entry version comparison, update checks, or
  any other catalog-side lifecycle action" is contradicted by the above and is
  replaced by the update lifecycle.
- **Not in scope:** silent/automatic updates (the action is always user-
  confirmed), updating folder-imported dictionaries, any user-editable catalog
  URL, and pre-built index bundles.

## Capabilities

### New Capabilities

None. This change extends an existing capability; the catalog is the same
surface, now with a lifecycle for installed entries.

### Modified Capabilities

- `remote-dictionary-catalog`: replaces the read-only installed-entry rule with a
  digest-based, user-confirmed update lifecycle (detect via recorded SHA-256,
  download and replace in place, reload with a forced full-text rebuild, preserve
  identity/position/groups, leave folder-imported entries untouched), and
  specifies that the catalog status communicates the **last-checked** time rather
  than implying a catalog or entry change.

## Impact

- `app/EngineController.*` — digest comparison in `refreshCatalogEntries()`, a
  per-entry `updateAvailable` flag, and an update action that reuses the existing
  download path with an FTS rebuild (the audio-reload path in
  `reloadDictionariesForResources` is the nearest model, but it deliberately
  skips the rebuild).
- `app/main.qml` — the status/error strings and an update affordance on the
  installed row.
- The Android `DictionaryDownloadService` — no new transfer logic: an update is a
  normal download of the same file names. The already-installed re-download path
  (today only optional bundles) must be verified to overwrite the staged copies
  for an update.
- The engine's FTS index for the updated dictionary id must be invalidated and
  rebuilt; no `carve/` or `patches/` change is expected.
- No manifest schema change: the digests this relies on are already published and
  recorded.
- OpenSpec: a delta to the `remote-dictionary-catalog` spec.
