# Technical debt (internal backlog)

The **internal**, developer-facing technical-debt record. Debt found locally — by a
developer, a review, or a `he9_debt scan` — lands here. Entries are almost always
worked from here (`he9_start <TD-id>`), not filed as tracker issues. `he9_debt promote`
is the rare one-way escalation to the external tracker, and removes the entry.

**Priority** is the severity class of the deficiency on the review contract's `P` scale
(never `P0` — a P0 is fixed, not deferred):

- `P1` — will cause defects or block work soon
- `P2` — the maintainability / architecture / docs / tests class, no current behavioral impact
- `P3` — polish

**How an entry leaves this document:** the fixer removes it when the fix merges (an entry
whose fix already merged and lingers here is removed by the next scan's gardening pass).
A promoted entry is removed in the same change that files the public issue, with the
promotion noted in the commit message.

Each entry is self-contained: the review that produced it is not kept, so the evidence,
symptom, `file:line`, and rationale are inlined. `TD-###` ids are stable; the scan
candidate id (R-n) is provenance only.

---

## P1 — will cause defects or block work soon

### TD-039 — `apply-patches.ps1` reports success on a failed patch and keeps going (exit 0)

- **Priority:** P1
- **Location:** `scripts/apply-patches.ps1:16-28`
- **Symptom:** No `$LASTEXITCODE` check anywhere. Under `$ErrorActionPreference = "Stop"`, a native command's non-zero exit does not throw, so when `git apply --check` fails the script still runs `git apply`, moves to the next patch, and prints "patches applied to engine/" with exit 0 — on a partially-patched tree.
- **Evidence:** Lines 20-21 run check then apply with no exit-code handling; line 28 prints success unconditionally. The `.sh` twin (`scripts/apply-patches.sh:14-24`) normalizes CRLF, prints the engine HEAD on failure and `exit 1`; the `.ps1` does none of that and enumerates via `Get-ChildItem` without `Sort-Object`. CI only runs the `.sh` (`engine-smoke.yml:46`, `release-qt.yml:227`); the `.ps1` is the path AGENTS.md, README and ENGINE.md tell humans to use.
- **Why it matters:** A Windows build proceeds on a silently inconsistent engine tree; missing load-bearing patches reproduce exactly the on-device hangs the patch set exists to prevent, with no error pointing at the cause.
- **Direction:** Capture `$LASTEXITCODE` after `--check`, `throw`/`exit 1` on failure with the engine HEAD; add `Sort-Object Name`, CRLF normalization parity, and skip-already-applied detection (`git apply --reverse --check`).
- **Provenance:** he9-debt scan 2026-10-24 (`scripts/`), reviewer candidate R-1 (build-scripts track). Verified against the working tree.

### TD-040 — `backup-cache.py --compress` hard-fails: `gzip.open()` takes no `mtime` argument

- **Priority:** P1
- **Location:** `scripts/backup-cache.py:90`
- **Symptom:** The documented `--compress` path crashes with `TypeError: open() got an unexpected keyword argument 'mtime'` — `gzip.open` has no `mtime` parameter (it belongs to `gzip.GzipFile`).
- **Evidence:** Line 90 `gzip.open(tmp_out, "wb", mtime=0)`; `gzip.open` signature is `(filename, mode, compresslevel, encoding, errors, newline)`. Documented in `--help` (:53-54), `backup-cache.ps1:13`, and `docs/builds/cache.md:105`.
- **Why it matters:** The documented compressed-backup recipe fails for the first user who wants a smaller archive; the default plain-`.tar` path works, so the breakage waits silently.
- **Direction:** `gzip.GzipFile(fileobj=io.open(tmp_out, "wb"), mode="wb", mtime=0)` (keeps the deterministic-timestamp intent) or drop `mtime=0`; add a smoke check in `scripts/tests`.
- **Provenance:** he9-debt scan 2026-10-24 (`scripts/`), reviewer candidate R-2 (build-scripts track). Verified against the working tree.

### TD-041 — `bundle-audio` drop-dangling rewrite reuses stale text, clobbering the safe-name rewrite

- **Priority:** P1
- **Location:** `scripts/kaikki/prefetch.py:832-869`, specifically `:860`
- **Symptom:** The safe-name `rename` rewrite writes `rewrite_audio_refs(text, rename)`, but the missing-drop pass then rewrites from the **original** `text` (`rewritten = _AUDIO_REF_RE.sub(_drop, text)`) and overwrites the file. When both `rename` and `missing` are non-empty, the second write discards the first: present-but-renamed refs revert to unsafe names (dangling against a bundle holding safe names), and a missing-and-renamed ref is never dropped (`missing_set` holds safe names, the original text holds raw names).
- **Evidence:** `:832-843` (rename pass) vs `:853-869` (drop pass from stale `text`); `missing` holds safe names (`wanted` keyed by safe at :814, `extract_audio` at :820); no final `verify_bundle` runs before return 0.
- **Why it matters:** A recovery run over a dictionary with one quoted-name recording and one gone recording ships `[s]` links to files not in the bundle; audio silently breaks and the run's own "rewrote N reference(s)" message contradicts the file it wrote.
- **Direction:** Chain the rewrites on one variable, drop by both raw and safe names, then run `verify_bundle` before returning 0. ~5 lines + a test covering rename∧missing together.
- **Provenance:** he9-debt scan 2026-10-24 (`scripts/`), reviewer candidate R-1 (converter track). Verified against the working tree.

---

## P2 — maintainability / docs / tests class

### TD-001 — Host-test loop and target table omit `dict_identity_test`

- **Priority:** P2
- **Location:** `docs/DEVELOPMENT.md:112`, `docs/DEVELOPMENT.md:117-125`
- **Symptom:** The "run every host test" `foreach` loop lists 7 targets and the coverage
  table has 7 rows, but `app/tests/CMakeLists.txt:90` defines an 8th target,
  `dict_identity_test` (`DictIdentityTest.cpp`). A developer following DEVELOPMENT.md
  runs the "whole suite" and never executes the existing regression test for dictionary
  identity/dedup.
- **Evidence:** `app/tests/CMakeLists.txt:86-94` defines `dict_identity_test` (links Qt
  Core only; `DictIdentity.hpp` is header-only). `docs/TESTING.md:62-63` cites
  `app/tests/DictIdentityTest.cpp` as the host test for full-content dictionary-identity
  comparison. The loop at DEVELOPMENT.md:112 and the table at :117-125 both omit it.
- **Why it matters:** Silent test-coverage hole — identity/dedup logic can regress while
  the documented "whole suite" stays green.
- **Direction:** Add `dict_identity_test` to the loop and a table row (same recipe as the
  others — Qt Core only).
- **Provenance:** scan 2026-10-04, reviewer candidate R-1.

### TD-002 — Resolved FTS spec claims per-dictionary index-state UI that does not exist

- **Priority:** P2
- **Location:** `openspec/specs/full-text-search/spec.md:31-34`, `openspec/specs/full-text-search/spec.md:40-42`
- **Symptom:** Two resolved scenarios — "Index state is visible" (each loaded dictionary
  shows whether its full-text index is built, missing, or being built) and "Dictionary
  without FTS support" (the app documents it as not full-text-searchable) — describe UI
  that does not exist. The resolved spec is the record of what shipped; it overstates
  the product and misdirects verification.
- **Evidence:** No QML consumer of per-dictionary FTS state: a grep for
  `fts_enabled|fts_disabled|fts_build_state|fts_index_state` across `app/` matches only
  C++ (`EngineController.cpp:650,784,1049,2468,2478,2602` — banner/search-filter logic)
  and two orphaned assets `app/android/assets/icons/fts_enabled.svg` /
  `fts_disabled.svg` (referenced nowhere; only their internal sodipodi docname matches).
  The FTS pane (`app/main.qml:3715-3870`) has only the field, whole-words toggle, group
  scope, search button and results; dict rows show name + pair/size only. The only
  index-state UI is the global "Indexing (n of m)" banner (`app/main.qml:1875`). The
  boundary exposes the state (`carve/goldendict.h:187` `gd_fts_build_state`, `:193`
  `gd_fts_index_state`) but nothing surfaces it per dictionary.
- **Why it matters:** The spec overstates the product; TESTING.md has no recipe matching
  these scenarios; a future implementer cannot tell whether the missing UI is a
  regression or never shipped.
- **Direction:** Either amend the resolved spec to the shipped behavior (global progress
  only; unsupported formats silently absent from FTS) or file the missing UI as a
  backlog change. Do not leave the spec claiming unshipped UI. The orphaned SVG assets
  should be removed or wired up, whichever direction is chosen.
- **Provenance:** scan 2026-10-04, reviewer candidate R-2.

### TD-003 — Lookup spec's speex wording contradicts shipped behavior and the other records

- **Priority:** P2
- **Location:** `openspec/specs/lookup/spec.md:277`, `openspec/specs/lookup/spec.md:283-285`
- **Symptom:** The resolved spec says audio formats the player cannot decode "SHALL be
  gracefully indicated as unsupported", and the scenario says the app "signals that the
  format is unsupported". The shipped behavior is a logcat-only skip with no user-visible
  signal — and AGENTS.md and TESTING.md both record that weaker behavior as intended.
- **Evidence:** `app/android/src/org/aurelex/pocket/dictionary/AurelexActivity.java:47-49`
  — `.spx` URLs get `Log.w` + return, no UI signal. `AGENTS.md:74` — "speex (`.spx`) is
  unsupported-but-graceful (skipped without an error)". `docs/TESTING.md:95` row #20 —
  🔶 "silently skipped, not explicitly indicated".
- **Why it matters:** Spec, conventions file, and the verification record disagree about
  the same shipped behavior; a future implementer cannot tell whether the missing
  indication is a regression or a spec overstatement.
- **Direction:** Pick one authority — amend the lookup spec to "MUST NOT crash; MAY be
  skipped silently" (matching AGENTS.md/TESTING.md), or implement the user-visible
  indication to satisfy the spec.
- **Provenance:** scan 2026-10-04, reviewer candidate R-3. Re-confirmed by the
  2026-10-04 `app/` scan (reviewer candidate R-7) — same finding, no new entry.

### TD-004 — Build-requirements line hides the Android xapian build step and omits host libiconv

- **Priority:** P2
- **Location:** `docs/DEVELOPMENT.md:44-45`
- **Symptom:** The requirements line says "vcpkg deps (`zlib bzip2 liblzma lzo fmt
  xapian`)", implying a plain vcpkg install covers xapian. For the Android triplets it
  does not: xapian comes from `scripts/build-xapian-android.sh`, which no doc, AGENTS.md,
  or README mentions. The same line omits `libiconv`, which the host smoke triplet needs.
- **Evidence:** `carve/CMakeLists.txt:10-12` — "xapian for the android triplets is
  provided by `scripts/build-xapian-android.sh` (see design.md D2)"; that design.md lives
  only in the archived goldendict-mobile-port change. `.github/workflows/release-qt.yml:209-223`
  runs the script in CI (the "Build xapian for Android" step). `app/build.ps1` never
  mentions xapian (grep: no matches). Grep for `build-xapian-android` across `docs/`: no
  matches. libiconv: `.github/workflows/engine-smoke.yml:71` installs it for x64-windows;
  `carve/CMakeLists.txt:149-154` links `iconv` on Win32 host builds.
- **Why it matters:** A fresh clone following DEVELOPMENT.md installs the wrong thing (or
  fails) at configure/link time with no documented remedy; the requirement is
  discoverable only in workflow YAML and a code comment pointing into the archive.
- **Direction:** Add a short "Android xapian (and host libiconv)" note to DEVELOPMENT.md's
  build section naming `scripts/build-xapian-android.sh` and the cached-vcpkg CI step as
  the reference.
- **Provenance:** scan 2026-10-04, reviewer candidate R-4.

### TD-013 — Catalog re-probe: the 6-hour freshness gate is dead code, and four doc sites describe it as the design

- **Priority:** P2
- **Location:** `app/EngineController.cpp:3040-3050`, `app/EngineController.cpp:3148-3153`, `app/main.qml:1652-1659`
- **Symptom:** The "younger than 6 h → serve cache" gate in `fetchCatalog()` is unreachable:
  `refreshCatalog()` invalidates `m_manifestFetched` before delegating to it, and the
  catalog pane's `_openCatalog()` is the only caller of either function and always calls
  `refreshCatalog()`. Every pane open issues a real HTTPS fetch. Four doc/comment sites
  describe the gate as the live design.
- **Evidence:** `EngineController.cpp:3148-3153` — `refreshCatalog()` sets
  `m_manifestFetched = QDateTime()` then calls `fetchCatalog()`; the gate branch
  (:3040-3050) requires a valid, young timestamp. Grep over `app/main.qml`:
  `fetchCatalog` 0 hits, `refreshCatalog` 1 hit (:1658, inside `_openCatalog`). Contradicted
  by `EngineController.hpp:394-395` ("re-probing is deliberate, not on every visit"),
  `EngineController.hpp:869-871` (the `kCatalogRereprobeMs` comment), `RemoteCatalog.hpp:105-108`,
  and `docs/REMOTE-CATALOG.md:213-214` / `:270`.
- **Why it matters:** Docs and header comments describe network behavior that does not
  exist. A maintainer tuning network chatter or writing tests against the 6-h rule will
  be reasoning about a phantom.
- **Direction:** Pick one design. Either `_openCatalog` calls `fetchCatalog()` (restoring
  the gate — then the AGENTS.md "re-probes automatically" row stays true-ish), or delete
  the gate + `kCatalogRereprobeMs` and fix the three comment blocks and
  `REMOTE-CATALOG.md` § Hosting.
- **Provenance:** scan 2026-10-04 (`app/`), reviewer candidate R-1.

### TD-014 — TESTING.md "Known cosmetic difference" section contradicts the shipped code and the same doc's row 74

- **Priority:** P2
- **Location:** `docs/TESTING.md:455-465`
- **Symptom:** The "Known cosmetic difference (not a regression)" section claims the
  article canvas is **not** the same colour as the app background (`#FFFFFF` vs
  `#FFFBFE` light, `#242526` vs `#1C1B1F` dark) and references a `--gd-bg` CSS constant.
  The defect it describes was fixed (pin-article-canvas-against-dark-reader); the section
  now contradicts the same doc's newer rows.
- **Evidence:** `docs/TESTING.md:457-465` names the two pairs and `--gd-bg`; grep for
  `--gd-bg` across `app/android/assets`: no matches. `EngineController.cpp:1984-1985`
  pins `canvasBgLight`/`canvasBgDark` to `#fffbfe`/`#1c1b1f`; `main.qml:224-226`
  `uiBgHex()` returns the same pair; `docs/TESTING.md:642` (row 74, verified 2026-10-04)
  confirms canvas `#1C1B1F` dark / `#FFFBFE` light.
- **Why it matters:** It is the only section in the checklist asserting a since-fixed
  defect; anyone re-running the cutout/theme checklist will "fail" expectations or waste
  a device pass.
- **Direction:** Delete the section or rewrite it as a historical record.
- **Provenance:** scan 2026-10-04 (`app/`), reviewer candidate R-2.

### TD-015 — `build.ps1` `Write-QtLibResources`: dead first call block, and the live path contradicts its own `load_local_libs` comment

- **Priority:** P2
- **Location:** `app/build.ps1:82-88`, `app/build.ps1:116-122`
- **Symptom:** The function computes `$bundled`/`$qt`/`$loc` with explicit `-fullName`
  arguments at :116-118, then immediately overwrites all three at :120-122 with one-arg
  calls (`$fullName` defaults to `$false` → stem form). The first block's results are
  discarded — dead code. The block comment (:86-88) says `load_local_libs` entries are
  used **verbatim** (full filename), but the live path emits the **stem**; the kit's
  `QtLoader.java:289-296` does `libraryList.add(libsDir + lib)` verbatim, so code,
  comment, and the generated `libs.xml` disagree about the contract. The app demonstrably
  boots, so exactly one side is wrong and nothing in the repo says which.
- **Evidence:** `app/build.ps1:116-118` vs `:120-122` (overwrite); comment at `:86-88`;
  `QtLoader.java:289-296` (kit source).
- **Why it matters:** A reader who deletes the obviously-dead 116-118 block silently
  changes the shipped loader input; a reader who trusts the comment will "fix" it the
  other way. Either change is invisible until a device boot.
- **Direction:** Delete the dead block; then either restore `-fullName $true` for `$loc`
  (and re-verify boot) or correct the comment to describe the stem form that
  demonstrably works, noting which consumer normalizes it.
- **Provenance:** scan 2026-10-04 (`app/`), reviewer candidate R-3.

### TD-016 — `ftsIndexStates` reads the wrong model key ("index" vs "engineIndex") — latent

- **Priority:** P2
- **Location:** `app/EngineController.cpp:2481`, `:2485`, `:920`
- **Symptom:** `ftsIndexStates()` reads each dictionary's engine index from the model key
  `"index"`, but the dictionaries model carries it under `"engineIndex"`. The
  name-from-model fast path can never match, so every dictionary falls back to
  `gd_dict_info` with a fresh 4 KiB heap buffer — on the UI thread (const `Q_INVOKABLE`).
- **Evidence:** `EngineController.cpp:2481` — `m.insert("index", i)`; `:2485` —
  `mm.value("index", -1).toInt() == i`; the model is built at `:920` with
  `m.insert("engineIndex", i)`; QML consumes `engineIndex` (`main.qml:807`).
- **Why it matters:** Currently unreachable (nothing calls `ftsIndexStates` — see
  TD-017), so latent; the moment anything calls it, it silently takes the slow path on
  every tick caller.
- **Direction:** Fix the key, or remove with TD-017.
- **Provenance:** scan 2026-10-04 (`app/`), reviewer candidate R-4.

### TD-017 — Nine `Q_INVOKABLE`s unused from QML — dead public API on the engine controller

- **Priority:** P2
- **Location:** `app/EngineController.hpp:176-177`, `:183`, `:234`, `:238`, `:272-274`, `:302`, `:353`
- **Symptom:** Nine `Q_INVOKABLE`s on `EngineController` are never called from QML (the
  only QML file): `historyWords`, `favoritesWords`, `groupName`, `removeDictionary`,
  `moveDictionary`, `ftsIndex`, `ftsIndexState`, `ftsIndexStates`, `readPendingLookup`,
  `lookupInGroup`. `readPendingLookup`'s own comment says "kept for the QML invokable
  API" — an API that no longer exists; the Java docs still direct readers to it.
  `ftsIndex()` is the manual pre-auto-index path the specs replaced; `lookupInGroup` is
  superseded by `lookupInGroupWithSwitch`.
- **Evidence:** `engine.`-prefixed grep over `app/main.qml`: zero hits for all nine (the
  bare `groupName`/`ftsIndex`/`lookupInGroup` hits are QML-side properties or *different*
  members — `ftsIndexDone/Total/Fraction`, `lookupInGroupWithSwitch`).
  `EngineController.hpp:236-237` self-documents `moveDictionary` as "currently unused
  from QML"; `AurelexActivity.java:21` points at `EngineController.readPendingLookup`.
- **Why it matters:** Dead surface to keep compiling, documenting, and pointing Java
  comments at; `ftsIndex`/`ftsIndexStates` additionally carry the TD-016 bug and a
  UI-thread engine call.
- **Direction:** Delete them (git history preserves them) or mark them clearly; update
  the two Java doc references to `pollPendingLookup`.
- **Provenance:** scan 2026-10-04 (`app/`), reviewer candidate R-5.

### TD-018 — ArticleServer: unauthenticated loopback HTTP server exposes dictionary content to any co-installed app

- **Priority:** P2
- **Location:** `app/ArticleServer.cpp:162`, `:261-314`; `app/ArticleServer.hpp:17-32`
- **Symptom:** The article HTTP server binds `QHostAddress::LocalHost` with no
  authentication: any co-installed app can connect to `127.0.0.1:<port>` and read full
  dictionary payloads (`/bres/<dictId>/<path>`) and audio (`/gdau/…`). `rawHeaders` is
  deliberately unused; there is no token/Origin/Referer check. The 404/400/200 responses
  make port/content probing trivially distinguishable.
- **Evidence:** `ArticleServer.cpp:162` — `server->listen(QHostAddress::LocalHost)`;
  `:261-262` — `handle()` with `Q_UNUSED(rawHeaders)`; the route map in
  `ArticleServer.hpp:17-32` needs no knowledge beyond a port scan.
- **Why it matters:** Undercuts the app's local-only privacy posture against a local
  attacker (a hostile app already installed) — including commercial dictionary content.
  Not P0: exploitation requires a hostile app already on the device, and the data is the
  user's own imported dictionaries.
- **Direction:** Derive a per-process random secret, prefix all rewritten URLs with
  `/<secret>/`, and reject requests whose path does not carry it
  (`EngineController::rewriteArticleUrls` and the QML `gdlookup` prefix checks are the
  only places that build these URLs); or at minimum a required header checked in
  `handle()`. Alternatively document the accepted risk in the design doc.
- **Provenance:** scan 2026-10-04 (`app/`), reviewer candidate R-6.

### TD-028 — EngineController is a 4,180-line facade; ~1,500 lines across 6 clusters are extractable

- **Priority:** P2
- **Location:** `app/EngineController.cpp` (4,180 lines), `app/EngineController.hpp` (919 lines, 51 `Q_PROPERTY`s + 54 `Q_INVOKABLE`s)
- **Symptom:** EngineController is by far the largest file in `app/` (6× the
  next-largest `.cpp`, `RemoteCatalog.cpp` at ~700 lines) and carries at least six
  cohesive responsibility clusters on top of the QML facade. The facade size is partly
  forced (QML can only talk to QObjects; the carve is a C API), but the extractable
  residue is real and growing.
- **Evidence:** Function inventory of `EngineController.cpp`: diagnostic log capture
  (file:49-200, ~150 lines, self-contained statics, zero coupling); dictionary lifecycle
  (file:564-1630, ~1,000 lines — the `gd_*` orchestration, inherent); groups
  (file:1648-1870, ~220 lines); article rendering + `rewriteArticleUrls`
  (file:1870-2310, ~440 lines, of which `rewriteArticleUrls` is ~310); FTS
  (file:2464-2654, ~190 lines); history/favorites JSON persistence (file:2654-2820,
  ~170 lines); theme/device-state pollers (file:2844-3030, ~190 lines); catalog fetch
  (file:3033-3260, ~230 lines, QNetworkAccessManager); downloads client
  (file:3260-3685, ~425 lines); settings/onboarding (file:3685-3810, ~125 lines). The
  extraction pattern is already established: `RemoteCatalog`, `ArticleServer`,
  `StagedCleanup`, `StagingRules`, `DictIdentity`, `IndexMigration`, `IndexCleanup`,
  `DictionaryIndex` are all already separate modules — EngineController is the residue
  of an ongoing discipline, not a never-touched god object.
- **Why it matters:** A 4,180-line facade with delicate init-order/state coupling (the
  `gd_init` watcher, the serial `m_enginePool` dispatch, the display/engine index
  split) is increasingly expensive to change safely, and every new feature lands in the
  same file. No current behavioral impact — this is the maintainability/architecture
  class.
- **Direction:** No big-bang split (not cheap, real regression risk). Extract
  opportunistically when each area is next touched, cheapest first: (1) diagnostic log
  capture (~150 lines, zero coupling); (2) history/favorites persistence (~170 lines,
  self-contained JSON protocol); (3) catalog fetch (~230 lines, pairs with
  `RemoteCatalog` — also TD-013's neighborhood); (4) downloads client (~425 lines,
  pairs with the Java `DictionaryDownloadService`); (5) `rewriteArticleUrls` (~310
  lines, pure-ish HTML rewriting); (6) theme/device-state pollers (~190 lines — also
  TD-023's neighborhood). Groups (~220 lines) is cohesive but deeply tied to
  `gd_group_*` and active-group state; leave it unless a change forces the issue.
- **Provenance:** raised by the user 2026-10-04; sized and inventoried from the
  working tree.

### TD-030 — `gd_move_dict` corrupts user-group membership (no index remap) and its documented effect no longer exists

- **Priority:** P2
- **Location:** `carve/gd_boundary.cc:1026-1046`; `carve/goldendict.h:39-41`
- **Symptom:** `gd_move_dict` permutes `g_state->dictionaries` but, unlike
  `gd_remove_dict` (:1067-1074), never remaps `groupDefs[].dictIndices`. It then calls
  `rebuildGroups()`, which materializes user groups from those now-stale indices
  (:279-287) — after a move, every user group silently contains different dictionaries.
  Any later group mutation calls `saveGroupsLocked()`, which resolves the stale indices
  to IDs and **persists the corruption** to `groups.json`. Separately, the header
  contract is stale: since the `allOrder` model landed, `rebuildGroups()` materializes
  the "All" group from `allOrder`, which `gd_move_dict` never touches — so its reorder
  no longer affects article order at all.
- **Evidence:** `gd_boundary.cc:1026-1046` (no `groupDefs` remap) vs `:1067-1074`
  (`gd_remove_dict`'s remap); `goldendict.h:39-41` ("the combined article respects
  this order").
- **Why it matters:** Exported boundary API with a latent data-corruption bug and a
  contract that describes v1. Currently unreachable — `EngineController::moveDictionary`
  (:1632) is `Q_INVOKABLE` but no QML caller exists (TD-017) and the smoke tool doesn't
  call it — which is why this is P2, not P1. It becomes P1 the moment someone wires the
  "reorder the flat dict list" feature to the obvious API.
- **Direction:** Either delete `gd_move_dict` + `moveDictionary` (the dead v1 path), or
  fix it: remap `groupDefs` indices exactly as `gd_remove_dict` does, reorder
  `allOrder`, and re-document.
- **Provenance:** scan 2026-10-05 (`carve/` + `patches/`), reviewer candidate R-2.

### TD-031 — `gd_suggest` returns a count larger than the lines it wrote (hardcoded 16-cap, undocumented)

- **Priority:** P2
- **Location:** `carve/gd_boundary.cc:726-735`; `carve/goldendict.h:18-21`
- **Symptom:** `prefixMatch(..., 100)` is requested (:711), but only
  `min(16, results.size())` headwords are written (:726-727), while the return value is
  `results.size()` (up to ~100). The header says "Returns the number of results" with no
  cap.
- **Evidence:** `gd_boundary.cc:711`, `:726-727`, `:735`; `goldendict.h:18-21`.
- **Why it matters:** Today's only consumer ignores the count and splits the
  NUL-terminated buffer (`EngineController.cpp:2439`), so there is no live defect — but
  any count-trusting consumer (a second caller, a test, a future format change) walks
  past the terminator.
- **Direction:** Return the number of lines actually written, or make the cap a
  parameter and document it in `goldendict.h`.
- **Provenance:** scan 2026-10-05 (`carve/` + `patches/`), reviewer candidate R-3.

### TD-042 — `validate_catalog` skips the id-charset and `names` checks the deploy gate depends on

- **Priority:** P2
- **Location:** `scripts/catalogtool/core.py:136-186` (vs `:62-100`)
- **Symptom:** The CI deploy gate (`.github/workflows/pages.yml:47` runs `build-catalog.py validate`) checks id presence/uniqueness but never applies `_ID_RE` (defined at :23, applied only by `validate_source` at :81) and never inspects `names` — while the module docstring (:140-141) claims it checks "the shape the app's parser depends on".
- **Evidence:** `validate_catalog` :149-160 (no charset check, no `names` block) vs `validate_source` :81, :95-100. Companion to TD-026 (app-side `isValidToken` gap) — this is the generator-side twin, not a duplicate.
- **Why it matters:** A hand-edited `catalog/catalog.json` with `names: "str"` or a non-charset id deploys green while the app's parser rejects the whole manifest — the catalog feature goes dark for all users while CI stayed green.
- **Direction:** Apply `_ID_RE` and the `names`-object shape check in `validate_catalog`; add the two negative tests. Coordinate with TD-026's app-side fix.
- **Provenance:** he9-debt scan 2026-10-24 (`scripts/`), reviewer candidate R-1 (catalog track). Verified against the working tree.

### TD-043 — Publish identity guard silently bypassed when the live catalog is unreachable

- **Priority:** P2
- **Location:** `scripts/publish-catalog.ps1:60-65`, `:82-85`
- **Symptom:** On `Invoke-WebRequest` failure the script only warns ("treating all files as new") and takes the else branch that skips `diff` entirely and uploads every file with `--clobber` — no identity-violation check runs. `REMOTE-CATALOG.md:266-268` promises the tool "refuses to publish if `diff` reports an identity violation".
- **Evidence:** `:60-65` (fetch failure → warn) vs `:82-85` (upload all, no diff). The committed `catalog/catalog.json` is the last published snapshot (REMOTE-CATALOG.md:224) and could serve as the diff source when Pages is down.
- **Why it matters:** A rename published during a Pages outage breaks installed-detection/contentHash for existing users with no refusal — the append-only contract (REMOTE-CATALOG.md:272-276) loses its only enforcement exactly when the network is flaky.
- **Direction:** On live-fetch failure, diff against the committed `catalog/catalog.json` (refusing if absent/stale); only then fall back to treat-all-as-new for the upload set, never for the violation check.
- **Provenance:** he9-debt scan 2026-10-24 (`scripts/`), reviewer candidate R-2 (catalog track). Verified against the working tree.

### TD-044 — No cross-entry file-name uniqueness anywhere; `_index_files` silently collapses duplicates

- **Priority:** P2
- **Location:** `scripts/catalogtool/core.py:105-117`, `:164-173`, `:299-308`, `:352-354`
- **Symptom:** Both validators enforce file-name uniqueness per entry only; `build_catalog` never checks across entries; `_index_files` keys by name so two entries sharing a name overwrite each other, and `changed_entries` then reports only one affected entry.
- **Evidence:** `validate_source` :105-117, `validate_catalog` :164-173 (per-entry `seen_file_names` only); `_index_files` :303; `diff_catalogs` :352-354. REMOTE-CATALOG.md:124 / :274-276 make file `name` the installed-detection key with a stable, append-only contract.
- **Why it matters:** A new entry reusing an existing asset name passes build+validate, and updating "its" dictionary silently changes the other entry's payload (same URL, self-consistent manifest, but ambiguous detection and diff).
- **Direction:** Repo-level `seen_file_names` across entries in both validators (and assert in `diff`), mirroring the duplicate-entry-name rationale at :89-94.
- **Provenance:** he9-debt scan 2026-10-24 (`scripts/`), reviewer candidate R-3 (catalog track). Verified against the working tree.

### TD-045 — `file_url` does not percent-encode file names; `_is_basename` admits URL-hostile names

- **Priority:** P2
- **Location:** `scripts/catalogtool/core.py:39-46`, `:58-59`, `:175`
- **Symptom:** `file_url` concatenates `name` unencoded (:59) while `_is_basename` accepts spaces, `#`, `?`, `%`, non-ASCII (:39-46); `validate_catalog` checks only the `https://` prefix (:175). Latent — today's names are controlled ASCII.
- **Evidence:** `:39-46` vs `:59`; REMOTE-CATALOG.md:124 restricts only path separators/`..`.
- **Why it matters:** A manifest carrying `my dict.dsl.dz` (or `#frag`) validates and deploys, then the app-side download of that entry fails confusingly.
- **Direction:** `urllib.parse.quote(name)` in `file_url`, or restrict `_is_basename` to the release-asset charset and state it in REMOTE-CATALOG.md:124.
- **Provenance:** he9-debt scan 2026-10-24 (`scripts/`), reviewer candidate R-4 (catalog track). Verified against the working tree.

### TD-046 — CI-enforcing asset checker has zero tests while sibling validators have suites

- **Priority:** P2
- **Location:** `scripts/check-store-assets.py:1-298` (whole file); `scripts/tests/` (suites only for build-catalog, bilingual, kaikki)
- **Symptom:** The script gates releases (`release-qt.yml:326`, `check-store-assets.yml:44`) and contains non-trivial pure logic — `read_geometry` bounds (:67-83), ratio-tolerance (:155-159), duplicate detection (:170-185), NN-contiguity (:188-213) — with no coverage.
- **Evidence:** No `test_check_store_assets*` in `scripts/tests/`; CI pattern `-p "test_build_catalog.py"`.
- **Why it matters:** A checker regression green-lights bad store assets — the silent-pass failure class it exists to prevent.
- **Direction:** One unittest file over the pure functions (fixture PNG headers need only ~33 bytes).
- **Provenance:** he9-debt scan 2026-10-24 (`scripts/`), reviewer candidate R-5 (catalog track). Verified against the working tree.

### TD-047 — Example-dict generator never exercises the multi-chunk dictzip invariant it documents

- **Priority:** P2
- **Location:** `scripts/make-example-dicts.py:120`, `:128-149`
- **Symptom:** `chunk_length=16384` (:120) vs fixtures of 829/330/405 bytes — every generated `.dz` is one data chunk plus a 2-byte Z_FINISH epilogue appended as its own chunk (:147-149). The docstring's invariant (later-chunk back-references reaching into an earlier chunk) lives at boundaries where real data crosses; no fixture has one, and the trailing-epilogue-as-chunk deviates from real `dictzip`.
- **Evidence:** Module docstring :128-133; verified by generating to a temp dir (`chunk_len=16384, chunks=2`, compressed `(500, 2)` — chunk 2 is the flush epilogue, zero data). CI (`engine-smoke.yml:97-108`) asserts only lookups.
- **Why it matters:** The `.dsl.dz` reader's random-access path is regression-guarded vacuously; the next engine bump can reintroduce the unreadable-past-chunk-1 defect and CI stays green.
- **Direction:** Scale one fixture past `chunk_length` so chunk 2 carries data; fold the finish output into the final data chunk; assert the smoke tool resolves a headword whose article lives in chunk 2.
- **Provenance:** he9-debt scan 2026-10-24 (`scripts/`), reviewer candidate R-3 (build-scripts track). Verified against the working tree.

### TD-048 — `make-smoke-mdx.py --encoding` advertises a switch but only writes the header attribute

- **Priority:** P2
- **Location:** `scripts/make-smoke-mdx.py:40`, `:160-172`, `:231-237`
- **Symptom:** `enc` is threaded only into the header `('Encoding', encoding)` attribute (:166) while every body/key is `encode("utf-16-le")` (:72, :82, :101-114, :172). `--encoding UTF-8` emits a self-inconsistent file (declared UTF-8, encoded UTF-16LE). Argv parsing is also fragile (`--encoding` with no value → bare `IndexError` at :236; unknown flags silently ignored).
- **Evidence:** Usage at :40, :233; no caller uses the flag (`engine-smoke.yml:124` calls it without it). Latent.
- **Why it matters:** A trap for whoever tests the non-UTF-16 MDX path: a plausible fixture that fails confusingly or passes with garbage article text.
- **Direction:** Either implement the payload encodings for the advertised values or restrict via `argparse` `choices` (which also fixes the parsing fragility).
- **Provenance:** he9-debt scan 2026-10-24 (`scripts/`), reviewer candidate R-4 (build-scripts track). Verified against the working tree.

### TD-049 — Symbol-subset font regenerates from an unpinned upstream `master` URL

- **Priority:** P2
- **Location:** `scripts/build_symbol_subset.py:52-55`, `:61-67`
- **Symptom:** `VAR_SOURCE_URL` points at `raw.githubusercontent.com/.../master/...ttf` with no tag/commit and no checksum; `load_source` downloads it verbatim. A later re-run silently instances a different upstream font (the normalization pass at :84-96 exists because upstream metrics drift).
- **Evidence:** :52-55 (URL), :61-67 (unverified download); repo precedent is pinned inputs with recorded provenance (AGENTS.md `app/openssl/README.md`; `XAPIAN_SHA512` in `build-xapian-android.sh:32`).
- **Why it matters:** Non-reproducible asset regeneration; two rebuilds on different dates can ship visibly different icons with nothing recording which upstream revision produced the committed font.
- **Direction:** Pin a commit/tag in the URL, record it plus a sha256 in a provenance comment next to `GLYPHS`.
- **Provenance:** he9-debt scan 2026-10-24 (`scripts/`), reviewer candidate R-5 (build-scripts track). Verified against the working tree.

### TD-050 — Scripts still carry the Qt 6.6.3 / msvc2019_64 / NDK r23c generation; everything else moved on

- **Priority:** P2
- **Location:** `scripts/update-translations.ps1:27-29`; `scripts/build-xapian-android.sh:18`
- **Symptom:** `update-translations.ps1` defaults to `C:\Qt\6.6.3` + `msvc2019_64`; the current generation is Qt 6.9.3 + `msvc2022_64` (`app/build.ps1:42-43`) and NDK r30 (`app/build.ps1:45`, `release-qt.yml:44,106`); the xapian usage example still cites `android-ndk-r23c`.
- **Evidence:** Single-source-of-truth rule: `support-16kb-pages` design.md:7 ("pinned in three places that must move together"). The DEVELOPMENT.md sites are that change's task 1.2 scope (already-addressed there); the two script sites are named in no task of that change and would survive it.
- **Why it matters:** On a machine with only the 6.9.3 kit the script fails its own loud "lupdate not found" check until env vars are set; the r23c mention misleads a fresh reader about the expected NDK.
- **Direction:** Fold both script sites into `support-16kb-pages` task 1.2's blast radius (defaults to `C:\Qt\6.9.3` / `msvc2022_64`, updated usage string).
- **Provenance:** he9-debt scan 2026-10-24 (`scripts/`), reviewer candidate R-6 (build-scripts track). Verified against the working tree.

### TD-051 — Shard-name guard misses Windows drive-relative names (`C:evil.ogg`)

- **Priority:** P2
- **Location:** `scripts/kaikki/prefetch.py:628-651`
- **Symptom:** The guard consults `os.path.isabs(name)` only when `len(parts) > 1`; `C:evil.ogg` splits to one part, passes every check, and `os.path.join(into, "C:evil.ogg")` yields drive-relative `C:evil.ogg`, resolved against drive C's cwd — outside `--into`. Docstring promises "a list file from somewhere else cannot write outside `--into`".
- **Evidence:** :640-647 (guard); `open(..., "wb")` downstream writes the joined path.
- **Why it matters:** A crafted shard file can write outside the target directory on Windows. Exploit path is narrow (shards come from the operator's own machines) — hardening, not P0.
- **Direction:** Reject any name where `os.path.isabs(os.path.splitdrive(name)[0] + os.sep)`, or require `ntpath`-safe plain names (also allow one safe subdirectory for the `sub/gone.ogg` case).
- **Provenance:** he9-debt scan 2026-10-24 (`scripts/`), reviewer candidate R-2 (converter track). Verified against the working tree.

### TD-052 — `--reuse-bundle` repair crashes on a directory bundle (`IsADirectoryError` traceback)

- **Priority:** P2
- **Location:** `scripts/kaikki/build.py:376-399`
- **Symptom:** With a case-only mismatch and `--audio-layout dir`, `src_zf` is `None`; the repair loop skips every entry (`if src_zf is None: continue`), writes an empty zip to `bundle_dest + ".repair"`, then `os.replace(tmp_bundle, bundle_dest)` targets a directory → unhandled traceback instead of the designed "repaired N name(s)" outcome.
- **Evidence:** :376-399 (loop + replace); no `except` around the replace.
- **Why it matters:** Crash on a reachable (if narrow) path — reuse of a dir-layout bundle whose entry casing drifted. No data loss (replace fails before clobbering) but a raw traceback instead of recovery.
- **Direction:** For a dir bundle, copy the mismatched files under their required names inside the directory; or refuse `--reuse-bundle` with a case-mismatched dir bundle with a clear message.
- **Provenance:** he9-debt scan 2026-10-24 (`scripts/`), reviewer candidate R-3 (converter track). Verified against the working tree.

### TD-053 — `--audio-per-word` documented per headword but applied per record

- **Priority:** P2
- **Location:** `scripts/kaikki/cli.py:107`; `scripts/kaikki/render.py:484`; `scripts/kaikki/prefetch.py:87-94`
- **Symptom:** Help says "max audio files per headword (default 3)"; `render_card` calls `audio.plan(record)` for every record (:484), each with its own budget, and card-wide de-dup removes only identical names. A noun+verb headword with distinct recordings per record carries up to `per_word × records` links.
- **Evidence:** `:107` (help) vs `:484` + `_plan` (per-record planning); build and prefetcher agree with each other and both disagree with the help text.
- **Why it matters:** Bundles exceed the advertised cap for multi-POS headwords; disk/rate-limit budgets sized from the documented number undershoot.
- **Direction:** Cap card-wide in `render_card`/`_plan` (batch records before planning, as bilingual does), or reword the help to "per record of a headword".
- **Provenance:** he9-debt scan 2026-10-24 (`scripts/`), reviewer candidate R-4 (converter track). Verified against the working tree.

### TD-054 — Bilingual caps audio per word, kaikki plans per record — divergence untested and undocumented

- **Priority:** P2
- **Location:** `scripts/bilingual/audio.py:148-183`; `scripts/kaikki/render.py:484`; `scripts/bilingual/audio.py:52,66-86`; `scripts/tests/test_bilingual_to_dsl.py:1089-1118`
- **Symptom:** `plan_words` breaks out once `len(chosen) >= per_word` (:179-182) while kaikki's `render_card` plans every record — for a multi-record headword the converters reference different file sets, contradicting the `plan_words` docstring ("the union of what the kaikki EN card for that headword carries", :148-151).
- **Evidence:** Both cross-check tests use single-record words (`bread`), so the interaction is never exercised.
- **Why it matters:** The "run the kaikki stage verbatim" guarantee (`audio.py:1-9`) silently fails exactly for multi-POS headwords; no test would notice.
- **Direction:** Add a two-record fixture to the cross-check test; then match kaikki's per-record semantics or document the intentional difference.
- **Provenance:** he9-debt scan 2026-10-24 (`scripts/`), reviewer candidate R-5 (converter track). Verified against the working tree.

### TD-055 — Full kaikki build buffers every rendered card body in RAM

- **Priority:** P2
- **Location:** `scripts/kaikki/build.py:162`, `:258-276`
- **Symptom:** `cards` accumulates `(headwords, body, word, count)` for the whole dictionary before the definition-less pruning / `unlink_absent_refs` pass; nothing spills to disk. The flagship full EN build is ~1M cards.
- **Evidence:** `:162` (accumulator), `:258-276` (second pass over the full list); the tool otherwise streams (snapshot, tar, bundle).
- **Why it matters:** Peak memory scales with the whole dictionary (GB-scale for EN); an OOM kill mid-build loses the run.
- **Direction:** Two-pass over a temp spill file (write bodies to a temp `.dsl`, then stream the pruning pass), or prune with a bounded LRU plus deferred second render for split/referenced words.
- **Provenance:** he9-debt scan 2026-10-24 (`scripts/`), reviewer candidate R-6 (converter track). Verified against the working tree.

### TD-056 — Bilingual `collect_records` memo holds every wanted record dict process-wide

- **Priority:** P2
- **Location:** `scripts/bilingual/audio.py:52`; `:66-86`; `scripts/bilingual/build.py:220-231`
- **Symptom:** `_records_cache` is module-global keyed by snapshot+lang storing all parsed record dicts for the requested words; with `--all-lemmas` the word list is every EN lemma, so the memo approaches the whole snapshot's lexical records, pinned for the process lifetime even after bundling.
- **Evidence:** `:52` (cache), `:66-86` (fill), `build.py:220-231` (transcription pass pins it).
- **Why it matters:** A full translation build with audio can OOM where the streaming monolingual build succeeds; memory is never released.
- **Direction:** Store only the fields the two consumers need (sounds/forms), or restructure to one streaming pass that plans audio and picks transcriptions per word and drops the record dicts.
- **Provenance:** he9-debt scan 2026-10-24 (`scripts/`), reviewer candidate R-7 (converter track). Verified against the working tree.

### TD-057 — DSL text utilities duplicated verbatim across the two converters

- **Priority:** P2
- **Location:** `scripts/bilingual/dsl.py:23-73` vs `scripts/kaikki/dsltext.py:13-40`, `:176-188`
- **Symptom:** `escape_dsl`, `unescape_dsl`/`_unescape_dsl`, `clean_headword`, `header_arg` are byte-identical copies (bilingual's docstring even says "Same contract as the kaikki builder"), while bilingual already cross-imports `kaikki.dictzip`, `kaikki.audio`, `kaikki.source`, `kaikki.render._record_transcription`, `kaikki.profiles._RU_POS_LABELS`.
- **Evidence:** Side-by-side diff of the two ranges; repo's own stated pattern is a single source of truth (`kaikki/dictzip.py:1`; `bilingual/audio.py:1-9,110-112`).
- **Why it matters:** An escaping fix (new DSL metacharacter, normalization change) applied to one converter leaves the other emitting markup-breaking DSL; the duplicates are the only DSL-correctness code outside the shared-source discipline.
- **Direction:** Have `bilingual.dsl` import the four functions from `kaikki.dsltext` (established pattern) and keep thin aliases for the tests.
- **Provenance:** he9-debt scan 2026-10-24 (`scripts/`), reviewer candidate R-8 (converter track). Verified against the working tree.

### TD-058 — `resolve_word` duplicates `resolve_words` expansion and is production-dead

- **Priority:** P2
- **Location:** `scripts/bilingual/equivalents.py:405-442` vs `:471-505`
- **Symptom:** The synset→senses block (shell vs per-group expansion, POS sort) appears in both functions; only `resolve_words` is called by `build.py` — `resolve_word`'s callers are all tests.
- **Evidence:** Grep: `resolve_word(` callers are tests only; `resolve_words` is the build path.
- **Why it matters:** The shell-sense policy (the one reviews rejected unlinked shells for) must be edited in two places; a one-sided edit changes test-visible behavior away from shipped behavior.
- **Direction:** Reimplement `resolve_word` as `resolve_words([word], backend, direction)[word]` or delete it and port the tests.
- **Provenance:** he9-debt scan 2026-10-24 (`scripts/`), reviewer candidate R-9 (converter track). Verified against the working tree.

### TD-059 — `extract_audio` swallows per-target `OSError`, misreporting disk failures as archive misses

- **Priority:** P2
- **Location:** `scripts/kaikki/audio.py:418-423` (vs `scripts/kaikki/build.py:439-443`, `scripts/kaikki/prefetch.py:846-849`)
- **Symptom:** A failed member write (`except OSError: continue`) leaves the name in `remaining`, so the build reports "not found in the archive while bundling" and `bundle-audio` reports "not found in the archive or the cache" — even though the member was in the archive and the failure was disk-full or a refused filename.
- **Evidence:** `:418-423` (swallow+continue) vs the two summary sites that only know found/missing.
- **Why it matters:** An operator with a full disk is told the archive lacks the files and re-runs the prefetcher against Wikimedia forever instead of freeing space.
- **Direction:** Distinguish write failure from lookup miss: return `(found, missing, write_failed)` or log the `OSError` text with the target name so the summary can say why.
- **Provenance:** he9-debt scan 2026-10-24 (`scripts/`), reviewer candidate R-10 (converter track). Verified against the working tree.

---

## P3 — polish

### TD-005 — "Four deviation patches" vs. six

- **Priority:** P3
- **Location:** `docs/DEVELOPMENT.md:17`
- **Symptom:** The docs index describes ENGINE.md as covering "the four deviation
  patches"; there are six.
- **Evidence:** `patches/` holds `0001`–`0006`; `docs/ENGINE.md:56-65` tabulates six;
  AGENTS.md says six.
- **Why it matters:** Misleads a newcomer counting deviations before a release bump.
- **Direction:** Change to "the six deviation patches" (or drop the count).
- **Provenance:** scan 2026-10-04, reviewer candidate R-5.

### TD-006 — Dead reference to `openspec/changes/fix-stardict-staging`

- **Priority:** P3
- **Location:** `docs/DEVELOPMENT.md:274`
- **Symptom:** The format-coverage section cites the StarDict fix at
  `openspec/changes/fix-stardict-staging`; that change was archived.
- **Evidence:** The change now lives at
  `openspec/changes/archive/2026-10-01-fix-stardict-staging/`; `openspec/changes/`
  contains only `catalog-dictionary-updates`.
- **Why it matters:** The link points at a non-existent path; the same doc elsewhere
  establishes the archive as the record.
- **Direction:** Update the path to the archive location.
- **Provenance:** scan 2026-10-04, reviewer candidate R-6.

### TD-007 — Editorial TODO parked inside a resolved spec

- **Priority:** P3
- **Location:** `openspec/specs/dictionary-management/spec.md:143-149`
- **Symptom:** The spec carries a blockquote admitting the scenario "Failures are not
  cleaned up without the user asking" is a misleading name, left verbatim only because
  OpenSpec MODIFIED blocks require it, with instructions to rename it "in a later docs
  change."
- **Evidence:** The note is verbatim at `openspec/specs/dictionary-management/spec.md:143-149`.
- **Why it matters:** Self-declared debt in the source-of-truth spec; it keeps confusing
  readers every time the scenario is consulted.
- **Direction:** A small docs-only OpenSpec change (or a spec edit during the next change
  touching this capability) to rename the scenario as the note prescribes, then delete
  the note.
- **Provenance:** scan 2026-10-04, reviewer candidate R-7.

### TD-008 — Stale "Welcome" Dialog example in the accessibility spec

- **Priority:** P3
- **Location:** `openspec/specs/accessibility/spec.md:65`
- **Symptom:** The Dialogs requirement's example list includes `"Welcome"` — a dialog that
  does not exist.
- **Evidence:** The onboarding surface is deliberately a plain `Rectangle` overlay with no
  `Accessible.name`, "not a `Dialog`, which would take taps unreliably on Android"
  (AGENTS.md Onboarding row; `app/main.qml:2554-2582` — heading label only).
- **Why it matters:** An automated test written from the spec would look for a
  nonexistent dialog.
- **Direction:** Replace the `"Welcome"` example with a real dialog name (e.g. `"Delete
  group confirmation"`, `"Add group"`).
- **Provenance:** scan 2026-10-04, reviewer candidate R-8.

### TD-009 — AGENTS.md Qt component list narrower than the carve requires

- **Priority:** P3
- **Location:** `AGENTS.md:41` (golden rule 2)
- **Symptom:** AGENTS.md says the carve "compiles with real Qt 6 (Core/XML/Concurrent)
  for Android"; the carve also requires Gui and Widgets.
- **Evidence:** `carve/CMakeLists.txt:73` — `find_package(Qt6 REQUIRED COMPONENTS Core Xml
  Concurrent Gui Widgets)`; the file header (`carve/CMakeLists.txt:5-9`) explains why
  (QTextDocumentFragment/QStyleHints, tiff.cc, config.cc/utils.hh headers).
- **Why it matters:** Someone auditing dependencies from AGENTS.md alone gets the wrong
  list; the rule's substance (no Qt-type shims) is unaffected.
- **Direction:** Update the parenthetical to "Core/XML/Concurrent (+Gui/Widgets as the
  engine needs them)" or drop the enumeration.
- **Provenance:** scan 2026-10-04, reviewer candidate R-9. Re-confirmed by the
  2026-10-05 `carve/` + `patches/` scan (reviewer candidate R-5) — same finding, no
  new entry.

### TD-010 — Stale notification channel id and small icon in SIGNING.md

- **Priority:** P3
- **Location:** `docs/SIGNING.md:270-271`
- **Symptom:** SIGNING.md says the IndexingService notification uses channel
  `aurelex_indexing` and small icon `ic_menu_search`; the code uses different values.
- **Evidence:** `app/android/src/org/aurelex/pocket/dictionary/IndexingService.java:35` —
  `CHANNEL_ID = "fts-indexing"`; `:171` — `setSmallIcon(R.drawable.ic_notification)`.
- **Why it matters:** Anyone matching the notification by channel id (e.g.
  `adb shell dumpsys notification` or a scripted check) uses the wrong identifier.
- **Direction:** Correct both constants in SIGNING.md.
- **Provenance:** scan 2026-10-04, reviewer candidate R-10.

### TD-011 — Add-group dialog button IDs undocumented; "OK/Cancel" wording stale

- **Priority:** P3
- **Location:** `AGENTS.md` (accessible element IDs table, Groups → Add-group dialog row)
- **Symptom:** The element-ID table describes the add-group dialog as "OK/Cancel"; the
  shipped buttons are "Cancel"/"Create", and the table lists no stable ID for the confirm
  button. The rename dialog's confirm button ("Rename group") is likewise unlisted.
- **Evidence:** `app/main.qml:3008-3020` — add-group dialog buttons `Accessible.name:
  "Cancel"` / `"Create"`; `:3061-3073` — rename dialog buttons `"Cancel"` / `"Rename
  group"`.
- **Why it matters:** The table doubles as the UIAutomator/Appium ID registry; the
  confirm buttons' stable IDs are undocumented and the OK/Cancel wording no longer
  matches the UI.
- **Direction:** Update the add-group row to name both button IDs; add the rename
  dialog's button IDs to its row.
- **Provenance:** scan 2026-10-04, reviewer candidate R-11.

### TD-012 — Patches 0005/0006 lack the mail headers the other four carry

- **Priority:** P3
- **Location:** `patches/0005-iconv-bound-conversion-retries.patch:1`, `patches/0006-stardict-bword-cross-references.patch:1`
- **Symptom:** Patches 0001–0004 carry `Subject: [PATCH] …` mail headers; 0005 and 0006
  are bare diffs starting at `diff --git`. docs/ENGINE.md's table quotes "Change"
  subjects for them that exist only in the doc, not in the artifacts.
- **Evidence:** `patches/0005-iconv-bound-conversion-retries.patch` begins
  `diff --git a/src/common/iconv.cc …`; `patches/0006-stardict-bword-cross-references.patch`
  begins `diff --git a/src/dict/stardict.cc …`. `patches/0001…`/`0004…` begin
  `From: …` / `Subject: [PATCH] …`. `docs/ENGINE.md:64-65` quotes subjects for
  0005/0006.
- **Why it matters:** Cosmetic inconsistency in the patch pipeline; the doc-to-artifact
  correspondence ENGINE.md's table implies does not hold for the two load-bearing
  patches.
- **Direction:** Either add the header lines to 0005/0006 to match the set, or note in
  ENGINE.md that the last two are headerless.
- **Provenance:** scan 2026-10-04, reviewer candidate R-12.

### TD-019 — Stale "source registration" claims on the staging path

- **Priority:** P3
- **Location:** `app/android/src/org/aurelex/pocket/dictionary/StagingService.java:31-32`, `:183-185`; `app/android/AndroidManifest.xml:87`
- **Symptom:** The `StagingService` class doc and the manifest say the service stops when
  "the copy + source registration complete" and that the source "is registered via
  `source.xml` for the C++ poller" — the old persistent-sources model. The same file's
  import path says the opposite.
- **Evidence:** `StagingService.java:31-32` — "Only then is the source registered via
  {@code source.xml}"; `:183-185` — "One-off import: no source.xml registration (that was
  the old 'persistent sources' model)"; `AndroidManifest.xml:87` — "stops itself when
  the copy + source registration complete".
- **Why it matters:** A reader auditing the storage model gets two opposite stories in
  one file.
- **Direction:** Update both comments.
- **Provenance:** scan 2026-10-04 (`app/`), reviewer candidate R-8.

### TD-020 — History cap: header comment says 100, code caps at 500

- **Priority:** P3
- **Location:** `app/EngineController.hpp:284-285`
- **Symptom:** The header comment says the controller "caps the history at 100 entries …
  matching the shipped app's behavior"; the code caps at 500.
- **Evidence:** `EngineController.hpp:284-285`; `EngineController.cpp:3859` — "cap at
  500"; `:3872` — `while (updated.size() > 500)`.
- **Why it matters:** The comment misdescribes the shipped behavior it explicitly claims
  to match.
- **Direction:** Fix the hpp comment to 500.
- **Provenance:** scan 2026-10-04 (`app/`), reviewer candidate R-9.

### TD-021 — `main.qml` state-machine comment lists removed states

- **Priority:** P3
- **Location:** `app/main.qml:38-39`
- **Symptom:** The state comment lists "2 = article, 5 = history" — states that no
  longer exist (history renders inside the article WebView; `_tabIndexForState` carries
  a "no such state anymore" guard for 2).
- **Evidence:** `main.qml:38-39` vs `:900`; the used states are {0,1,3,4,6}.
- **Why it matters:** Misleads anyone reading the state machine.
- **Direction:** Update the comment (the sparse ids themselves are fine and load-bearing).
- **Provenance:** scan 2026-10-04 (`app/`), reviewer candidate R-10.

### TD-022 — `downloadSpeed` is produced end-to-end but rendered nowhere; the format comment is inaccurate

- **Priority:** P3
- **Location:** `app/android/src/org/aurelex/pocket/dictionary/DictionaryDownloadService.java:586-594`; `app/EngineController.hpp:146-147`
- **Symptom:** The download service computes a transfer speed and writes it to disk
  (`writeState` → `commit`) every second during a batch; the C++ side parses and stores
  it — but nothing renders it. The `Q_PROPERTY` comment also misdescribes the format
  ("Human-readable transfer rate, formatted by the service" — the service writes a raw
  byte rate with a `" B/s"` suffix).
- **Evidence:** `DictionaryDownloadService.java:586-594` — `state.speed = … + " B/s"`,
  then `writeState` + `updateNotification` each second; `EngineController.cpp:3270`,
  `:3340`, `:3354` parse/store it; grep `downloadSpeed` in `app/main.qml`: zero hits
  (only `downloadFraction`/`downloadMessage` render).
- **Why it matters:** Dead data path plus a 1 Hz flash write of a value nobody displays.
- **Direction:** Either render the speed in the catalog progress line (formatted
  human-readably) or drop the property and the marker key.
- **Provenance:** scan 2026-10-04 (`app/`), reviewer candidate R-11.

### TD-023 — `applyEffectiveDark()` can run before `gd_init` — the constructor's stated invariant is not enforced on the poller path

- **Priority:** P3
- **Location:** `app/EngineController.cpp:117-121`, `:135-136`, `:4029`, `:2894-2902`
- **Symptom:** The constructor comment states `applyEffectiveDark()` "must not happen
  before `gd_init` has run" (hence is deliberately not called in the constructor), but
  the 500 ms poller started in the constructor calls `pollPendingLookup` →
  `updateSystemDark()` → `applyEffectiveDark()` on a dark-state change, which can land
  before the `gd_init` watcher completes. The pre-init `gd_set_dark_mode` return (−1) is
  swallowed.
- **Evidence:** `EngineController.cpp:117-121` (the invariant comment); `:135-136` (the
  poller starts in the constructor); `:4029` (`pollPendingLookup` calls
  `updateSystemDark`); `:2894-2902` (`updateSystemDark` calls `applyEffectiveDark` on a
  change); `carve/gd_boundary.cc:1321-1324` (`gd_set_dark_mode` returns −1 pre-init).
- **Why it matters:** The consequence is mild (one silently dropped preference write,
  self-corrected by `loadSettings`/the next change), but the documented invariant is not
  actually guaranteed.
- **Direction:** Guard `applyEffectiveDark()` on `m_ready`, or note in the comment that
  pre-init calls are harmless-but-lost.
- **Provenance:** scan 2026-10-04 (`app/`), reviewer candidate R-12.

### TD-024 — ArticleServer allocates a 4 MiB buffer per resource job

- **Priority:** P3
- **Location:** `app/ArticleServer.cpp:65`
- **Symptom:** `runJob` allocates a `std::vector<char> buf(kMaxResourceBytes)` (4 MiB) per
  resource job on the slot threads; most replies are a few KB, and image-rich articles
  mean dozens of jobs.
- **Evidence:** `ArticleServer.cpp:60-69` — the buffer is declared inside `runJob`,
  before the `gd_get_resource`/`gd_get_audio` call.
- **Why it matters:** Avoidable per-job malloc/free churn on the hot article path.
- **Direction:** Hoist the buffer into `ResourceSlot` as a reusable member (the bound
  stays `kMaxResourceBytes`).
- **Provenance:** scan 2026-10-04 (`app/`), reviewer candidate R-13.

### TD-026 — Manifest `id` charset: docs promise `[A-Za-z0-9._-]+`, the parser accepts far more

- **Priority:** P3
- **Location:** `app/RemoteCatalog.cpp:100-108`; `app/RemoteCatalog.hpp:35-38`; `docs/REMOTE-CATALOG.md:112`
- **Symptom:** The documented id contract is `[A-Za-z0-9._-]+`, but `isValidToken` only
  rejects control characters and path separators — a catalog id with spaces or emoji
  parses, installs, and displays.
- **Evidence:** `RemoteCatalog.hpp:35-38` and `docs/REMOTE-CATALOG.md:112` document the
  set; `RemoteCatalog.cpp:100-108` enforces much less.
- **Why it matters:** The documented contract and the enforcement differ; no path risk
  (the content hash is MD5-derived), but UI/log input is looser than promised.
- **Direction:** Tighten `isValidToken` to the documented set (it feeds UI and logs) or
  relax the doc.
- **Provenance:** scan 2026-10-04 (`app/`), reviewer candidate R-15.

### TD-027 — `updateIndexingProgress` javadoc mislabels the percent parameter

- **Priority:** P3
- **Location:** `app/android/src/org/aurelex/pocket/dictionary/AurelexActivity.java:835`
- **Symptom:** The javadoc names the parameter `dictPercent` and describes it as "this
  dictionary's own 0..100 progress", but the caller passes the **overall batch** percent,
  and `IndexingService` uses it as the overall bar.
- **Evidence:** `AurelexActivity.java:830-836` — `@param dictPercent this dictionary's
  own 0..100 progress`; `EngineController.cpp:310-320` — passes `overallPercent =
  qRound(overall * 100.0)`; `IndexingService.java:103-104` — `int overallPercent`.
- **Why it matters:** Misleads JNI readers about which progress the notification bar
  shows.
- **Direction:** Rename the javadoc parameter to `overallPercent`.
- **Provenance:** scan 2026-10-04 (`app/`), reviewer candidate R-16.

### TD-033 — Stale "FTS is deliberately not exposed." comment in the boundary header

- **Priority:** P3
- **Location:** `carve/gd_boundary.cc:9`
- **Symptom:** The file-header comment says "FTS is deliberately not exposed." — the
  same file implements seven `gd_fts_*` functions.
- **Evidence:** `gd_boundary.cc:9` vs the `gd_fts_*` implementations at `:1337-1551`.
- **Why it matters:** Contradicts the file it introduces; misleads a reader about the
  boundary's surface.
- **Direction:** Delete the sentence.
- **Provenance:** scan 2026-10-05 (`carve/` + `patches/`), reviewer candidate R-6.

### TD-035 — Timeout budgets bypass the named constant

- **Priority:** P3
- **Location:** `carve/gd_boundary.cc:68`, `:700`, `:756`, `:801`, `:868`, `:1501`
- **Symptom:** `kEngineRequestDeadlineMs` is used only by `fetchResource` (:868);
  `gd_lookup`, `gd_lookup_in_group`, and `gd_fts_search` hardcode `15000` (:756, :801,
  :1501), and `gd_suggest` a different `10000` (:700). The constant's own comment says
  the value "should be re-chosen against measured engine times" — impossible to do
  coherently while three sites bypass it.
- **Evidence:** `gd_boundary.cc:62-68` (constant + comment), `:700`, `:756`, `:801`,
  `:868`, `:1501`.
- **Why it matters:** The named constant implies a single tunable budget; the bypasses
  make that a fiction.
- **Direction:** Route all sites through the constant (or a second named constant for
  the suggest budget).
- **Provenance:** scan 2026-10-05 (`carve/` + `patches/`), reviewer candidate R-8.

### TD-036 — Dead code in `gd_scan_dicts`: `ArticleMaker` constructed twice; unused `<QThreadPool>` include

- **Priority:** P3
- **Location:** `carve/gd_boundary.cc:32`, `:636-639`
- **Symptom:** `gd_scan_dicts` calls `rebuildGroups()` (:636, which already ends by
  rebuilding `articleMaker` at :290-291) and then constructs an identical `ArticleMaker`
  again two lines later (:638-639) — redundant work on every scan. Also
  `#include <QThreadPool>` (:32) is unused.
- **Evidence:** `gd_boundary.cc:290-291` (`rebuildGroups`' tail), `:636`, `:638-639`;
  the only `QThreadPool` occurrence in the file is the include at :32.
- **Why it matters:** Redundant per-scan work and a dead include in the boundary's hot
  path.
- **Direction:** Delete the second construction and the include.
- **Provenance:** scan 2026-10-05 (`carve/` + `patches/`), reviewer candidate R-9.

### TD-037 — `gd_cleanup` says "Wait (bounded)" but the wait is unbounded

- **Priority:** P3
- **Location:** `carve/gd_boundary.cc:1553-1572`
- **Symptom:** The comment says "Wait (bounded)" but the `for(;;)` loop (:1560-1568) has
  no deadline; if a build wedge ignores cancellation between yield points, cleanup spins
  forever.
- **Evidence:** `gd_boundary.cc:1555` (comment) vs `:1560-1568` (loop). Latent only —
  the app never calls `gd_cleanup` in v1 (the comment says so itself at :1559).
- **Why it matters:** The comment asserts a bound the code does not enforce.
- **Direction:** Bound the wait (N seconds, then proceed/delete anyway or abort) or fix
  the comment.
- **Provenance:** scan 2026-10-05 (`carve/` + `patches/`), reviewer candidate R-10.

### TD-038 — `#include` + engine-class stub defined *inside* `extern "C"`; the stub is undocumented

- **Priority:** P3
- **Location:** `carve/gd_boundary.cc:1574-1583`
- **Symptom:** `#include "audio/internalplayerbackend.hh"` sits inside the `extern "C"`
  block (which closes at :1583), and `InternalPlayerBackend::anyAvailable()` is defined
  there. Harmless today (member functions keep C++ linkage), but any free function ever
  declared in that header silently gets C linkage → link/ODR surprises on an engine bump.
  The stub itself (a link-symbol shim for `config.cc`) is named nowhere — neither
  `docs/ENGINE.md`'s patch table nor the CMake comments mention it, unlike the two GUI
  stubs.
- **Evidence:** `gd_boundary.cc:1574-1581` inside the block closing at :1583.
- **Why it matters:** A latent linkage hazard on the next engine bump, plus an
  undocumented stub.
- **Direction:** Move the include/definition outside the linkage block; give the stub a
  one-line note in `carve/CMakeLists.txt`.
- **Provenance:** scan 2026-10-05 (`carve/` + `patches/`), reviewer candidate R-11.

### TD-060 — Store-asset checker crashes with `ZeroDivisionError` on a zero-dimension PNG

- **Priority:** P3
- **Location:** `scripts/check-store-assets.py:149-159`
- **Symptom:** `actual = shot.width / shot.height` runs before the per-side bound check can `continue` — a corrupt 0-height PNG (passes the IHDR signature check) crashes the run and discards all collected violations. Exit code stays nonzero so CI still fails; only the diagnostics are lost. The module docstring (:15-16) promises every violation is reported.
- **Evidence:** `:155` (division) vs `:149-154` (append-but-never-skip bounds block).
- **Why it matters:** One corrupt file hides every other violation in the run.
- **Direction:** Reject `width == 0 or height == 0` inside `read_geometry`.
- **Provenance:** he9-debt scan 2026-10-24 (`scripts/`), reviewer candidate R-6 (catalog track). Verified against the working tree.

### TD-061 — `derive-native-payload.ps1` reads QML imports from `main.qml` only

- **Priority:** P3
- **Location:** `scripts/derive-native-payload.ps1:54`, `:240-247`
- **Symptom:** The `-AppQml` default and the import scan assume a single QML file (glob confirms exactly one exists today); the design claim "a new `import` in main.qml widens it automatically" (`app/build.ps1:201`) silently assumes that stays true. A second `.qml` file's imports would be invisible to the closure and to CI's set-equality check (`release-qt.yml:601-627`), caught only by the device matrix.
- **Evidence:** `:54` (default), `:240-247` (scan); the two `Write-Warning` "ASSERTION CHANGED" guards (:218, :231) don't fail the run — acceptable, since the 52 MB payload ceiling (`release-qt.yml:555, 593-594`) backstops both.
- **Why it matters:** A second QML file silently narrows the native-payload closure.
- **Direction:** Scan every `app/**/*.qml`, or document the single-file constraint next to the param.
- **Provenance:** he9-debt scan 2026-10-24 (`scripts/`), reviewer candidate R-7 (catalog track). Verified against the working tree.

### TD-062 — Catalog CLI handles only `CatalogError`; malformed inputs produce raw tracebacks

- **Priority:** P3
- **Location:** `scripts/catalogtool/cli.py:154-158` (handler) vs `scripts/catalogtool/core.py:125-126`, `:303`, `:333-350`
- **Symptom:** `load_source`'s `json.load` and `diff_catalogs`' direct key access on unvalidated documents raise `ValueError`/`KeyError` past the handler (`_read_json` wraps its own reads, but `build --source bad.json` and `diff` against a malformed published doc traceback). Exit code is still nonzero — message quality only.
- **Evidence:** Handler at `cli.py:154-158` catches `CatalogError` only.
- **Why it matters:** Operators debugging a bad source/diff get a traceback instead of the tool's clean error shape.
- **Direction:** Wrap the same two exception families at `main()`.
- **Provenance:** he9-debt scan 2026-10-24 (`scripts/`), reviewer candidate R-8 (catalog track). Verified against the working tree.

### TD-063 — Dead reference to `openspec/changes/public-catalog-hosting` in `catalogtool`

- **Priority:** P3
- **Location:** `scripts/catalogtool/__init__.py:9`
- **Symptom:** Module docstring cites `openspec/changes/public-catalog-hosting/`; the change was archived (same defect class as TD-006, different site).
- **Evidence:** The change lives at `openspec/changes/archive/2026-10-03-public-catalog-hosting/`.
- **Why it matters:** Doc link points at a non-existent path.
- **Direction:** Update the path to the archive location.
- **Provenance:** he9-debt scan 2026-10-24 (`scripts/`), reviewer candidate R-9 (catalog track). Verified against the working tree.

### TD-064 — `validate_catalog` requires `sha256` on every file though the manifest contract marks it optional

- **Priority:** P3
- **Location:** `scripts/catalogtool/core.py:180-181`; `docs/REMOTE-CATALOG.md:127`
- **Symptom:** The doc says sha256 absent → "accepted without verification"; `validate` rejects sha256-absent files (`:180-181` requires 64 lowercase hex). Stricter-than-contract is the safe direction, but the docstring's "shape the app's parser depends on" (:140-141) is wrong and `validate` can't be used on a legitimately minimal manifest.
- **Evidence:** `:180-181` vs REMOTE-CATALOG.md:127; the app accepts sha256-absent files.
- **Why it matters:** The validator rejects documents the contract calls legal.
- **Direction:** Make sha256 optional in `validate_catalog` (still required when produced by `build`), or reword the docstring to "the shape the *built* document has".
- **Provenance:** he9-debt scan 2026-10-24 (`scripts/`), reviewer candidate R-11 (catalog track). Verified against the working tree.

### TD-065 — Kaikki cross-ref caps don't compose (effective bound exceeds the documented cap)

- **Priority:** P3
- **Location:** `scripts/kaikki/render.py:47-61`, `:517-525`
- **Symptom:** `_cross_refs(limit=12)` caps per record but the card-level `>= 8` break only exits the inner loop — the effective bound is 8 + (records − 1), not the documented "capped".
- **Evidence:** `:47-61` (per-record limit) vs `:517-525` (inner-loop break).
- **Why it matters:** Cards carry more cross-refs than the documented cap; unbounded-ish growth per multi-record headword.
- **Direction:** Break the outer loop (or count card-wide) so the cap composes.
- **Provenance:** he9-debt scan 2026-10-24 (`scripts/`), reviewer candidate R-14 (converter track). Verified against the working tree.

