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
- **Provenance:** scan 2026-10-04, reviewer candidate R-9.

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

### TD-025 — CMake comment/code drift on the API level

- **Priority:** P3
- **Location:** `app/CMakeLists.txt:11-14`
- **Symptom:** The comment says "The shipped app targets API 28+" while the code defines
  `__ANDROID_API__=35` (the build targets platform android-30, minSdk 23, targetSdk 36).
- **Evidence:** `app/CMakeLists.txt:11-14`.
- **Why it matters:** Someone may "correct" 35 down to 28 based on the comment.
- **Direction:** Reword ("iconv needs ≥28; define the full build platform").
- **Provenance:** scan 2026-10-04 (`app/`), reviewer candidate R-14.

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
