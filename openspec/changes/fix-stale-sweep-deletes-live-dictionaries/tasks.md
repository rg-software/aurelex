## 1. Make the orphan test follow the recursive scan

- [x] 1.1 Add a recursive `holdsPrimaryDictionaryFile( const QString &dir )` helper to
      `app/StagedCleanup.hpp`, applying `StagingRules::isPrimaryDictionaryName` to every
      file beneath `dir` at any depth and short-circuiting on the first match. Use
      `QDirIterator( ..., QDir::Files | QDir::NoDotAndDotDot, QDirIterator::Subdirectories )`
      rather than the `QDir::entryInfoList( QDir::Subdirectories )` first drafted here:
      `entryInfoList` materialises the entire listing, so a match on the first entry still
      costs a stat of every file in a multi-thousand-file `<dict>.files` / `res` tree.
      Leave `FollowSymlinks` off so a cycle cannot trap the sweep. Include `<QDirIterator>`
      and `"StagingRules.hpp"`; keep the header dependency-light.
- [x] 1.2 Replace the inline top-level-only `hasPrimary` loop in
      `sweepStaleStagedDirs()` (`app/EngineController.cpp:1415-1426`) with a call to the
      new helper, and delete the dead local. Keep the `"sweeping staged dir holding no
      dictionary"` log line so on-device verification can still assert on it.
- [x] 1.3 Extend `app/tests/StagedCleanupTest.cpp` with cases: a directory whose only
      primary is one level down is reported as holding a dictionary; a flat directory is;
      a directory with only companions/resources is not; a directory with only subfolders
      containing no primaries is not. Use `QTemporaryDir` with nested dirs created
      explicitly.
- [x] 1.4 Build and run the host test binary; confirm the nested case fails against the
      old top-level-only logic and passes against the new one. **Done:** 48/48 pass against the
      new logic; the old top-level-only loop was then rebuilt against the same binary by
      shadowing the header on the include path, and fails exactly the 8 nested cases
      (3 levels down, 1 level down, sibling subfolders, and all four primary extensions at
      depth incl. case-insensitive) while the flat and negative cases pass on both — so the new
      tests catch the defect and the reclaim behaviour did not loosen.

## 2. Give the sweep an authoritative in-use set

- [x] 2.1 Extend the scan task in `runScan()` (`app/EngineController.cpp:412-418`) to
      enumerate each loaded dictionary's source path via `gd_dict_info()` after
      `gd_scan_dicts()`, and return them with the count. Reuse the same
      size/`QString::fromLocal8Bit` handling `refreshDictionaries()` already uses
      (`:799-845`) so the two reads cannot drift.
- [x] 2.2 Change `sweepStaleStagedDirs()` to take the loaded-source list as a parameter
      and stop calling `liveDictionarySources()` internally. Log the count it was handed,
      so a cold start is verifiable in logcat (a `0` here means the guard is still vacuous).
- [x] 2.3 Give `removeStagedDirIfUnused()` the source list as an explicit parameter too,
      so no caller can skip the containment/sharing gate.
- [x] 2.4 Update the removal and failed-import call sites to pass
      `liveDictionarySources()` explicitly, preserving today's behaviour there (the UI
      model is the right authority for an edit the user just made, including the
      `m_unloadedSources` exclusions).

## 3. Verify on device

Done on a ThinkPhone by motorola (`ZY22HC8LTR`, Android 15), which already carried a
debug build with a **flat** staged tree — the shape the old sweep spared, so it reproduced
the defect only once a nested import was added. Every assertion below is a logcat line or a
`run-as` listing, not an inference from the code.

- [x] 3.1 Build and install the debug APK per `docs/DEVELOPMENT.md`
      (`pwsh -File .\app\build.ps1 -Configuration Debug -Install`).
      **Done.** The NDK *is* present: `app/build.ps1:42` defaults to
      `C:\Program Files (x86)\Android\AndroidNDK\android-ndk-r23c` (a standalone tree, not
      the SDK-managed `android-sdk\ndk` this change had earlier been reported as missing).
      Configure, ninja, androiddeployqt, gradle and install all succeeded; the APK upgraded
      the existing debug build in place, preserving the staged tree.
- [x] 3.2 Import a folder whose supported dictionary files are **only in a subfolder** —
      the case that was previously fatal — and confirm it loads.
      **Done.** Picked `/sdcard/AurelexTest`, whose dictionaries each sit in their own
      subfolder, via the `ACTION_OPEN_DOCUMENT_TREE` picker. Staged as
      `files/staged/485ea40a/{demo,shared,black,collinslaw,factbook,dslonly}/…`, i.e.
      `staged/<sourceId>/<subfolder>/<dict>` — the normal nested shape, and the same shape
      as the Xiaomi's `GoldenDict/English/<Name>/<dict>.dsl.dz`. It loaded: the scan
      reported `gd_dict_count = 8`, and two dictionaries resolved from the nested paths
      (`485ea40a/demo/demo.mdx`, `485ea40a/shared/aurelex-phrasebook.dsl`).
- [x] 3.3 Force-stop and relaunch. Confirm the dictionary is still listed and searchable,
      and that logcat contains **no** `sweeping staged dir holding no dictionary` and no
      `removing staged dir` for that source. Confirm the handed source count is non-zero
      on the startup scan (per 2.2).
      **Done**, on three consecutive cold starts. Each shows, in order:
      `setDictionaries count= 0` (the model is cleared before the scan — exactly why the
      old code handed the sweep an empty list), then `scan done; gd_dict_count = 8`, then
      **`staged sweep: in-use sources handed to the sweep = 8`** (pre-fix this line read
      `0`), with no reclaim line anywhere. `485ea40a` was still on disk afterwards, both
      its dictionaries were still listed, and a lookup for `thank you` rendered an article
      sourced from **Aurelex Phrasebook**, i.e. from
      `485ea40a/shared/aurelex-phrasebook.dsl` — one level *inside* a staged dir, after the
      restart that used to destroy it. So: nested import survives a restart and is
      searchable.
- [x] 3.4 Confirm a genuinely empty leftover staged directory is still reclaimed, so the
      disk-reclaim behaviour the sweep exists for has not regressed.
      **Done.** Created `files/staged/emptyleftover/leftoversub` (no primary file at any
      depth) via `run-as`. The next cold start logged
      `sweeping staged dir holding no dictionary ".../staged/emptyleftover"` and the
      directory was gone, while every real dir including the nested one stayed. The
      recursive test therefore does not defeat reclaim — a nested subdirectory with no
      primary still reads as an orphan.
- [x] 3.5 Confirm a flat, top-level import and a StarDict import with companions are
      unaffected.
      **Done.** The five pre-existing flat staged dirs survived every restart. A lookup for
      `abandonment` rendered a full article from **Collins Dictionary of Law 2ed** (flat
      `f804830f/collinslaw2ed.mdx`), and `Iceland` / `Zimbabwe` both returned article
      sections from the StarDict `70549544/stardict.ifo`, whose 828-file `res/` tree is
      intact. Additionally, to check the case that motivated refusing to flatten the
      staging layout, `stardict.*` was copied into the **nested** `485ea40a/factbook/`
      beside its own nested `res/`: both dictionaries then loaded (`gd_dict_count = 9`,
      sweep handed `9`), the app reported the expected `name clash: The World Factbook 2014
      is present 2 times`, and a `Zimbabwe` lookup returned **two** dictIds and two full tab
      sets — one per `res/` tree. Had staging been flattened, the two `res/` trees would
      have merged. (The synthetic duplicate was removed afterwards.)

**D5 verified separately — the recursive test is load-bearing, not belt-and-braces.**
Beyond 3.1–3.5, D5's claim (the in-use set cannot protect a dictionary the boundary cannot
*name*, so only `holdsPrimaryDictionaryFile` saves it) was tested directly, because it is the
assertion that forbids ever deleting the recursive test. Two trees were staged straddling
`gd_dict_info`'s 512-byte buffer boundary, each holding a valid `aurelex-phrasebook.dsl`:

| tree | staged path length | named by `gd_dict_info` |
|---|---|---|
| `staged/zzunder/…` | 500 | yes |
| `staged/zzover/…` | 530 | no |

Cold start with both present: `scan done; gd_dict_count = 10`, then
`staged sweep: in-use sources handed to the sweep = 9` and `dictionaries available: 9`. The
dictionary that vanished from those two counts is `zzover`'s — loaded by the engine, absent
from the in-use set, and **invisible in the Dictionaries list**. Neither directory was
reclaimed, so `zzover` survived on the recursive test alone; `zzunder` was protected by the
in-use set as well, which proves the two layers really are independent rather than one
subsuming the other.

The counterfactual was then made empirical rather than argued: deleting **only** the deep
primary file inside `zzover` — leaving the directory and its long subdirectories, and leaving
`zzover`'s in-use status identical — made the next cold start reclaim it
(`sweeping staged dir holding no dictionary ".../staged/zzover"` → `removing staged dir`),
while `zzunder` stayed. So the presence of the deep file was the sole protection, and the
sweep genuinely evaluates that directory rather than skipping it for an unrelated reason.
Both synthetic trees were removed afterwards; the real nested import (`485ea40a`) remains
staged as the regression fixture.

**Not covered here, deliberately:** the *reported-failure* branch
(`sweeping stale failed import`). A deliberately corrupt nested `.dsl` is reclaimed by that
branch rather than by the orphan test, which is correct but out of scope for this change
(see the design's Open Questions and `report-import-results`); that run only confirms the two
branches stay distinct.

## 4. Document

- [x] 4.1 Add the nested-import-across-restart case to `docs/TESTING.md` as a
      regression check, since this shipped once and the device is where it is catchable.
      Added rows 8k (nested import survives a restart, with the logcat assertions) and 8l (a
      genuinely empty leftover is still reclaimed, so the sweep is not simply off).
- [x] 4.2 Note in the change's release notes that dictionaries already lost to this
      behaviour are unrecoverable and must be re-imported, so affected users are not
      left expecting the fix to restore them. Added as a `### Release note` block in
      `proposal.md`, including the interim advice to avoid importing a folder whose
      dictionaries live in subfolders while an affected build is installed.
- [x] 4.3 Run `openspec validate fix-stale-sweep-deletes-live-dictionaries`, then sync
      the delta into `openspec/specs/` on archive. Validation passes. The spec sync happens
      at archive time, so this stays ticked for the archiver.
