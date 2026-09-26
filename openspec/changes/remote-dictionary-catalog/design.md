## Context

The import chain today is a *producer → tail* pipeline, even though only one
producer exists:

```
  SAF folder pick
       |
       v
  StagingService (foreground)  -- copies into files/staging-tmp/<sourceId>/
       |                          -- atomic rename to files/staged/<sourceId>/
       |                          -- writes shared_prefs/staging.xml
       v
  500 ms poller (EngineController.cpp:2104) sees the marker clear
       |
       v
  runScan()  ->  gd_scan_dicts(files/staged)  [recursive, whole tree]
       |
       v
  autoIndexMissing()  ->  FTS worker  ->  refreshDictionaries()
       |
       v
  processingActive = false
```

Constraints that shape the approach:

- `runScan()` scans `files/staged` recursively and is **completely agnostic**
  about how bytes arrived. Anything that lands in that tree is picked up.
- `processingActive` is a **single** flag covering the whole chain
  (`EngineController.hpp:58-64`), and it currently **disables the Dicts Remove
  button** (`main.qml:1327-1336`). Spec
  `dictionary-management` / "Continuous processing indication" requires it never
  blink off mid-chain.
- `StagingService.stageOne` derives `sourceId` from the tree URI
  (`AurelexActivity.java:136`) and **unconditionally wipes**
  `staging-tmp/<sourceId>` before copying (`:144-145`) — there is no resume.
- The Qt process is killed on activity destroy
  (`AurelexActivity.java:774-787`, `Process.killProcess`), so long work must
  live in a Java foreground service to survive backgrounding — the same reason
  `StagingService` and `IndexingService` exist.
- A dictionary's source file is **permanent**. The index is an offset table, not
  a content store: at query time `dict_data_read_( dz, articleOffset, articleSize, … )`
  reads the article body out of the `.dsl.dz` (`engine/src/dict/dsl.cc:499`), and
  mdict memory-maps the file for the dictionary's lifetime
  (`engine/src/dict/mdictparser.hh:38-39`, `ScopedMemMap`). Deleting a
  downloaded file after indexing yields a dictionary that scans and indexes but
  returns nothing on every lookup.
- `INTERNET` (`app/android/AndroidManifest.xml:8`) and `Qt6::Network`
  (`app/CMakeLists.txt:50,83`) are already present, but the app has **zero**
  outbound network code today.
- `network_security_config.xml` permits cleartext only on `127.0.0.1`.
- `settings.json` (`EngineController.cpp:1887-1921`) is the only settings
  store; `saveSettings()` rewrites the whole object, so a new key needs no
  migration and an absent key cleanly means "use the default".

## Goals / Non-Goals

**Goals:**

- Install a dictionary from a curated catalog with no sideloading and no
  computer round-trip.
- Reuse the existing scan → auto-index → refresh chain **unchanged**, so no
  engine/carve work and no new `processingActive` phase.
- Survive backgrounding, show real byte-level progress, and allow cancelling
  the transfer.
- Land in the same app-private tree, be removable by the existing Remove path,
  and need no storage permission.
- Keep the download cancellable **without** giving the user a way to abort an
  index build (that remains `fts-indexing-performance`'s business).

**Non-Goals:**

- Any catalog publishing, generation, or CI pipeline. The catalog is a
  hand-authored file. (A `scripts/build-catalog.py` helper is a plausible later
  maintainer convenience, deliberately not in this change.)
- Entry versioning, update checks, "update my installed dictionary", catalog-side
  uninstall, discovery/scraping, accounts, per-user feeds, telemetry.
- Pre-built index bundles. See "Dict ids are path-dependent" below.
- Bounding or making interruptible the automatic full-text build
  (`fts-indexing-performance`).
- Letting the user point the app at their own catalog URL. The URL is compiled
  in; making it editable is a later, additive settings change.

## Decisions

### 1. Downloads are a second producer, not a new phase

The download is modelled as an *acquire* step that feeds the same staging tree
the SAF producer feeds. It is deliberately **not** folded into the
`processingActive` chain.

```
  +-- SAF pick --------> StagingService ----+
                                            |  atomic rename
  QUEUE (acquire)                          v
                                 files/staged/<contentHash>/
                                            |
                                            v
                            runScan -> autoIndexMissing -> refresh
                                            |        (the SHARED tail,
  +-- catalog pick -> DictionaryDownloadService+         unchanged)
       cancel: abort, purge scratch, never touch the tail
```

Rationale: `processingActive` doubles as a **lock** on the Dicts pane. A 3 GB
download inside that flag would freeze removal and the FTS UI for an hour, and
would make the existing "continuous processing indication" requirement apply to
a phase that has no natural end the user can wait for. Splitting the queues
means the tail's requirements — including the no-blink rule — are **untouched**,
and a download can sit in the background while the user goes back to searching.

*Alternative considered:* one chain with a `downloading` phase. Rejected: it
converts a bounded, user-visible operation into an unbounded one that disables
deletion, and it would force amendments to the continuous-indication
requirement.

### 2. Cancel is batch-wide, download-only, and never clears `processingActive`

One cancel aborts the entire batch in flight. It reports *cancelled*, which is
distinct from *failed*, and leaves any running scan/index tail alone.

The load-bearing invariant: **cancelling must not clear `processingActive` if
the tail is still live.** Cancel means "stop the transfer, delete
`staging-tmp/<id>`, re-evaluate" — never "set the flag false". Getting this
wrong would break the no-blink guarantee mid-build.

*Alternative considered:* per-entry cancel. Rejected for v1 — a batch is chosen
in one action, so batch-wide cancel matches the mental model and needs no
per-file state in the UI.

### 3. `sourceId` is a content hash, not a URL or URI hash

Staging identifiers are `staging-tmp/<id>` / `staged/<id>`. For downloads the id
is derived from the entry's content identity (the catalog `entry.id` plus the
required-file names), not from the URL.

Rationale: the engine's dictionary id is an MD5 over the **absolute source
paths** (`engine/src/dict/dictionary.cc:562-598`, via
`Dictionary::makeDictionaryId`, non-portable branch). So re-downloading the same
dictionary to a *different* path yields a *different* engine id and therefore a
**duplicate row** in the dictionary list — `gd_scan_dicts` dedups by id
(`carve/gd_boundary.cc:440-447`) and would not catch it. A deterministic
content-derived id makes a repeat install a clean no-op, and keeps the folder
import's existing `hasStagedCopy` dedup meaningful across both producers.

### 4. Integrity verification is best-effort; `sizeBytes` is mandatory, `sha256` is not

The catalog is hand-maintained. Requiring a checksum per file makes the first
maintainer mistake a download that fails verification with no way to tell a
corrupt transfer from a wrong hash.

```
  file.sha256 present -> verify, reject the file on mismatch,
                         naming the entry in the error
  file.sha256 absent  -> skip verification, proceed
  file.sizeBytes      -> always required (free-space preflight, progress total)
```

### 5. Free-space preflight: refuse below 512 MiB headroom, warn below 2 GiB

```
  free < bundleBytes + 512 MiB  ->  REFUSE, name the entry and the shortfall
  free < bundleBytes + 2 GiB    ->  WARN, then proceed on confirmation
  otherwise                     ->  proceed
```

The rename is same-volume, so there is no 2x doubling penalty to reserve. The
2 GiB tier exists because the full-text build that follows needs room we cannot
predict for a multi-GB dictionary. Both constants live in one place, to be
tuned from real devices.

### 6. Audio is opt-in, and adding it later is a *reload*, not a reindex

Audio dominates total size (the kaikki audio archive is ~20 GB versus a
multi-GB dictionary), so it is never fetched unless asked for, and can be added
to an already-installed entry later.

The late-add path is cheap, and the mechanism is worth stating precisely so
nobody later "helpfully" queues a full rebuild:

- The engine computes the dictionary id **before** appending the resource zip
  (`engine/src/dict/dsl.cc:1739` vs `:1749`), so the id is **unchanged** by
  adding audio.
- The lookup index's staleness check keys on the `hasZipFile` flag stored in the
  index header (`engine/src/dict/dsl.cc:110-119`, used at `:1755`), so the
  lookup index **rebuilds itself** on the next load.
- The full-text index is keyed on the dictionary id and short-circuits when
  present (`engine/src/ftshelpers.cc:56-69`), and article text lives in the
  `.dsl.dz`, which did not change — so the FTS index is **reused as-is**.
- `gd_scan_dicts` would rebuild the correct dictionary and then **discard** it,
  because the id is already loaded (`carve/gd_boundary.cc:440-447`). The
  in-memory dictionary keeps its empty `resourceZip` until reloaded.

Hence: download the audio bundle, then `gd_remove_dict(id)` + `runScan()`.
`gd_remove_dict` already exists (`carve/goldendict.h:127`) — this is app-side
only, no `patches/` change. The user is not asked to restart the app.

### 7. Two network stacks, two jobs

| Job | Stack | Rationale |
|---|---|---|
| Fetch + parse the catalog JSON | `QNetworkAccessManager` in `EngineController` | Small, quick, in-process; already linked; parsed as JSON in C++ anyway. If it fails the button simply stays disabled — no need for survival. |
| Download dictionary files | `HttpURLConnection` in a new `DictionaryDownloadService` foreground service | Must survive backgrounding and be cancellable; must write into `getFilesDir()`; the Qt process is killed on activity destroy (`AurelexActivity.java:774-787`). |

*Alternatives considered:* all-Qt (a `QNetworkReply` dies with the process, and
re-implements the foreground-service pattern that already exists twice); Android
`DownloadManager` (gives resume and notifications free, but cannot place files
in app-private **internal** storage and cannot do the
`staging-tmp/ → staged/` atomic rename that the whole safety story rests on).

### 8. Partial-file resume, and a scratch directory that survives a kill

`StagingService.stageOne` wipes `staging-tmp/<sourceId>` unconditionally
(`AurelexActivity.java:144-145`) because a SAF copy has no meaningful resume
point. Downloads do, so the download path keeps its partial and resumes.

- Resume uses HTTP `Range` with `If-Range` (ETag/Last-Modified) so a changed
  remote file restarts cleanly instead of corrupting.
- If the server answers `200` instead of `206`, or the validator changed, the
  file restarts from zero.
- On service start, an orphaned `staging-tmp/<id>` from a previous run is
  **resumed** if its entry is still in the current catalog, and **purged**
  otherwise. Existing `purgeStagingTmp()` (`EngineController.cpp:797-807`)
  still runs at the end of the scan/index chain, but must not race an active
  download — it is scoped to that chain today, and download scratch is keyed by
  content hash so the two cannot collide.
- A partial file is never visible to the engine: it lives in `staging-tmp/` and
  only becomes visible via the atomic rename on completion. This is the same
  invariant `StagingService` already documents, and it is why a killed or
  cancelled download can never produce a `scanFailures` entry.

### 9. Java → C++ hand-off via a SharedPreferences marker

The download service writes `shared_prefs/download.xml` (active, entry name,
files done/total, bytes done/total, speed, outcome) and the existing 500 ms
poller reads it, mirroring `staging.xml` and `indexing.xml`. Preferred over a
JNI callback because polling cannot miss a state transition, and it matches the
established idiom exactly. The marker is cleared on terminal outcome
(success / cancelled / failed), which is the poller's cue to re-evaluate.

### 10. Manifest: a static, hand-authored document

```json
{
  "schemaVersion": 1,
  "updated": "2026-09-26",
  "entries": [
    {
      "id": "kaikki-en-ru",
      "name": "Wiktionary (English - Russian)",
      "langFrom": "en",
      "langTo": "ru",
      "attribution": "Wiktionary contributors, CC BY-SA 4.0",
      "license": "CC-BY-SA-4.0",
      "files": [
        { "role": "dictionary", "required": true,
          "name": "kaikki-en-ru.dsl.dz",
          "url": "https://…", "sizeBytes": 123456789, "sha256": "…" },
        { "role": "resources", "required": false,
          "name": "kaikki-en-ru.dsl.dz.files.zip",
          "url": "https://…", "sizeBytes": 9876543210, "sha256": "…" }
      ]
    }
  ]
}
```

`role` is open (`dictionary`, `resources`, and later `index`) so the shape does
not have to change when a future bundle type appears. Entry download size is
**derived** (sum of files) rather than stored, so it cannot drift. `required:
false` is what makes audio opt-in.

**Installed detection:** an entry is installed when *every* file with
`role: "dictionary"` has its basename present in the set of basenames of
`dictionaries[].source`. Using the file list rather than a single
`primaryFile` field is what makes mdict pairs (`.mdx` + `.mdd`) work. This is
also the only dedup the app needs — a re-install of the same entry is a no-op
scan by engine-id.

### 11. Probing the catalog

"Add from remote" is disabled when the catalog is not reachable. The probe runs
when the Dictionaries pane is entered (and on explicit refresh), **not** at app
start — probing at startup would add network latency to launch for a surface
most sessions never open. The last good manifest and its reachability are cached
in `settings.json`, so a previously-seen catalog still renders (read-only) while
offline, with download attempts failing individually.

### 12. HTTPS only; no cleartext exception

`network_security_config.xml` stays untouched. The compiled-in URL is HTTPS, and
`Qt6::Network` plus the `INTERNET` permission are already present, so no
dependency and no manifest permission change is needed. Accepting a
user-supplied URL later would force a decision about LAN cleartext; deferring
the user-supplied URL is what keeps that decision out of this change.

### 13. Settings key

`remoteCatalogUrl` in `settings.json`, written on first run from a compiled-in
constant, read thereafter. `loadSettings()` already tolerates an absent key, and
`saveSettings()` rewrites the object wholesale, so there is no migration path
and no schema version to bump.

## Risks / Trade-offs

- **A multi-GB dictionary's automatic full-text build blocks the engine.**
  `gd_fts_index` holds the global `g_engineMutex` for the whole `makeFTSIndex()`
  run, so lookups, scans, group edits, and removal all block for its duration
  and the app is unsearchable meanwhile. This is the first thing users will hit
  with a large entry. → **Not mitigated here, by agreement**: it is owned by
  `fts-indexing-performance`, and bundling them would make this change neither
  isolated nor reviewable. Recorded here so it is a known cost, not a surprise.
- **Auto-indexing is unbounded, so a multi-GB entry can make the app unusable
  for a long time.** → Same owner. The catalog is expected to lead with
  small-to-medium entries; the first real multi-GB install will quantify it.
- **The catalog is a single point of failure for discovery.** If the hand-curated
  file is malformed or unreachable, the feature is simply unavailable; folder
  import is untouched. → The button is disabled rather than erroring, and the
  last good manifest is cached for offline reading.
- **Hand-maintained `sizeBytes` can be wrong**, which would make the free-space
  preflight lie and the progress bar wrong. → `sizeBytes` is mandatory but
  unverified; the download loop treats a mismatch as a non-fatal warning, and
  the transfer itself is bounded by the HTTP `Content-Length`.
- **Entry ids and file names must stay stable.** A renamed file breaks
  installed-detection for anyone who already installed the old name. → Entries
  are append-only by convention; the change does not enforce it.
- **The `Range`/`If-Range` resume path depends on server behaviour** that
  differs between hosts. → Falls back to a clean full re-fetch on any
  `200`-for-`Range`, validator change, or short read. Worst case is re-download,
  never a corrupt install.
- **The scratch dir survives a kill, so a killed download can leak disk.**
  → Orphaned scratch is reconciled on the next service start (resume or purge),
  and the content-hash keying keeps it from colliding with the SAF producer.
- **The download service is a new long-lived Java component** with a cancel path
  that nothing else in the app has. → Cancel is one idempotent flag check in the
  transfer loop; terminal outcomes are funnelled through a single place so
  success/cancel/fail cannot be confused.

## Migration Plan

None required. No stored state is reinterpreted, no spec'd behavior is removed,
and `remoteCatalogUrl` is additive with a compiled-in default. Rollback is
removing the "Add from remote" action; already-installed dictionaries are
indistinguishable from folder-imported ones and keep working.

## Open Questions

- Whether the catalog is served from `raw.githubusercontent.com` or GitHub Pages
  — affects caching headers and how often the app should re-probe, but not the
  schema, the approach, or the task breakdown.
- Whether to add a maintainer-side `scripts/build-catalog.py` that computes
  `sizeBytes`/`sha256` and emits the manifest, removing the manual step. Purely a
  repo-tooling question with no effect on the app.
- Whether "Add from remote" should also be reachable from the onboarding flow.
