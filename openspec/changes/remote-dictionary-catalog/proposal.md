## Why

Importing a dictionary today requires the user to already have the file on the
phone: build or download it on a computer, move it across, then pick the folder
in Aurelex. That is a real barrier for the dictionaries this project can
already produce at scale — `kaikki-to-dsl` outputs multi-GB per language pair,
which nobody wants to sideload by hand. A curated, hand-maintained online
catalog lets the user install those dictionaries from inside the app, while
keeping the project itself a consumer of somebody else's hosting rather than the
host of dictionary data.

## What Changes

- **A curated catalog surface** in the Dictionaries pane: "Add from remote"
  opens the catalog in place over the pane (no new navigation tab), listing
  entries with name, language pair, total download size, and an *installed*
  badge.
- **The catalog is a single static, hand-authored JSON document** fetched over
  HTTPS from a URL compiled into the app and persisted into `settings.json`.
  There is no discovery, no scraping, no per-user feed, no account, and no
  entry versioning or update checking.
- **Multi-select download.** The user picks one or more entries and downloads
  them as a batch, with byte-level progress (fraction, transferred/total,
  speed, current entry) surfaced in the UI and in the foreground-service
  notification.
- **Cancellation is download-only and batch-wide.** Cancelling aborts the
  transfer, discards partial files, and reports *cancelled* (distinct from
  *failed*). It never disturbs the scan/index chain, and never clears the
  existing continuous processing indication while that chain is still running.
- **Downloads land in the same app-private staged tree** as a folder import, via
  an atomic rename out of a scratch directory, so the existing
  scan → auto-index → refresh chain consumes them unchanged. Downloaded
  dictionaries are permanent, removable by the existing multi-select Remove
  path, and need no storage permission.
- **Optional pronunciation audio.** Audio bundles are a separate opt-in part of
  an entry and are never fetched unless asked for, because they dominate total
  size. Audio can be added to an already-installed dictionary later.
- **Free-space preflight.** A download is refused when the device cannot hold
  the bundle, and warned about when headroom is thin.
- **Integrity verification is best-effort:** a per-file checksum is verified
  when the catalog supplies one and skipped when it does not, because the
  catalog is hand-maintained.
- **No engine/carve changes.** The `gd_*` boundary, `patches/`, and the CI
  smoke test are untouched.

## Capabilities

### New Capabilities

- `remote-dictionary-catalog`: browsing a curated remote catalog of installable
  dictionaries, batch selection and download with progress and cancellation,
  optional audio bundles, integrity verification, free-space preflight, and
  landing the result in the app's dictionary set.

### Modified Capabilities

- `dictionary-management`: add the remote catalog as a second way to populate
  the staged dictionary tree, and define how a late-arriving audio bundle is
  picked up by an already-loaded dictionary.
- `storage-folder-access`: clarify that a curated catalog is a discovery
  surface, not a registered source — installing from it is still a one-off copy
  with no source list, no Rescan, and no persisted grant.

## Impact

- **App/Android:** new `DictionaryDownloadService` foreground service (resume
  via HTTP `Range`, foreground notification, progress, cancel); new catalog
  fetch/parse; new `staging-tmp/<contentHash>/` → `staged/<contentHash>/`
  hand-off; new SharedPreferences marker read by the existing 500 ms poller
  (`app/EngineController.cpp`).
- **App/QML:** a catalog sheet over the Dictionaries pane; a new
  "Add from remote" action; new download progress properties and a cancel
  action; new `Accessible.name` element IDs for every interactive element added
  (see `AGENTS.md`).
- **Settings:** new `remoteCatalogUrl` key in `settings.json`, defaulted from a
  compiled-in constant; not user-editable in this change.
- **Docs that become false and must be amended:** the `README.md` privacy claim
  ("no network permission other than what the WebView needs") and the
  `docs/DESIGN-v2.md` "Search in online dictionaries" non-goal. The
  `network_security_config.xml` stays as-is: the catalog is HTTPS-only, so no
  cleartext exception is needed.
- **Localization:** this adds a substantial set of user-visible strings; per
  `AGENTS.md` the RU and JA catalogs, `values-ru/`, `values-ja/`, and the
  recompiled `.qm` files land in the same change.
- **Network:** `INTERNET` permission and `Qt6::Network` are already present, so
  no new dependency is introduced; the app gains its first outbound network use.
- **Known limitation (not addressed here):** a multi-GB dictionary's automatic
  full-text build holds the engine's global mutex for its whole duration, so
  the app is unsearchable while it runs. That is owned by the separate
  `fts-indexing-performance` change and is deliberately not bundled here.
