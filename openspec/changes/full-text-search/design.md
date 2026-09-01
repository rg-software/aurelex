## Context

FTS is fully stubbed in the carve today (see proposal.md — Why). The carve's
boundary includes a shadow `ftshelpers.hh`, a no-op `fts_stub.cc`, and a shim
`ui_fulltextsearch.h`; `common/globalregex.cc` includes upstream
`fulltextsearch.hh` (for the `FTS::*` enums), which is why the shim exists.
The upstream FTS implementation splits cleanly:

- `engine/src/ftshelpers.cc/.hh` — the engine-side work: `makeFTSIndex`,
  `ftsIndexIsOldOrBad`, `FTSResultsRequest` (Xapian query + result headwords).
  Depends only on Qt Core/Concurrent + Xapian + dict internals that the carve
  already compiles (`fulltextsearch.hh` enums, `folding.hh`, `dictfile.hh`,
  `utils.hh`).
- `engine/src/fulltextsearch.cc` — the desktop Qt Widgets dialog. Not desired
  on mobile; the Kotlin UI replaces it.

The dict backends (StarDict/DSL/mdx) already declare `makeFTSIndex()` overrides
and construct `FtsHelpers::FTSResultsRequest` exactly as upstream (verified in
`stardict.cc:1143`, `dsl.cc:1682`, `mdx.cc:493`). So re-enabling FTS is mostly
a matter of giving the carve the *real* `ftshelpers.cc/.hh` + a Xapian build and
replacing the boundary C stubs with `gd_fts_*` exports that drive that surface.

## Goals / Non-Goals

**Goals**
- Real Xapian-backed full-text index + search for the three v1 formats,
  reachable from a Kotlin FTS screen.
- Results drive the existing article flow (active group respected).
- Minimal, patch-pipeline-friendly deviation from upstream.

**Non-Goals**
- Porting the desktop `FullTextSearchDialog`/Qt Widgets UI.
- FTS result highlighting in the article (upstream uses WebEngine
  `findText()`, unavailable) — results open the article like any lookup.
- Config UI for FTS settings in v1 beyond search mode (kept minimal).
- FTS across resources/audio; article body text only.

## Decisions

### D1: Compile real `ftshelpers.cc`, drop the boundary shadow header
The carve switches `fts_stub.cc` → `engine/src/ftshelpers.cc` and removes the
shadow `ftshelpers.hh` so the upstream one wins (it is identical in API surface,
so the dict backends need no change). `ui_fulltextsearch.h` shim stays
(`globalregex.cc` still needs it); `fulltextsearch.cc` (the dialogs) is not
compiled. This is the smallest change to the merge contract: one stub becomes
a real upstream source + one header stops being shadowed.

### D2: Xapian availability and build strategy
The upstream build takes xapian from vcpkg on Windows (`vcpkg.json` port
`xapian`) and pkg-config on Linux/macOS. For Android we need a cross-compiled
xapian-core for `arm64-android`/`x64-android`.

Chosen: **try the stock vcpkg `xapian` port for the android triplets first**;
if the port is missing or fails on the given vcpkg baseline, fall back to a
scripted build of a pinned xapian release (its own `./configure` for the NDK
toolchain) that installs into `${VCPKG_ANDROID_ROOT}` so the carve link line
stays `xapian` either way. Rationale: keeps CMakeLists uniform (one
`link_directories` + `find` already used for the other deps), and localizes the
xapian bootstrap to CI/scripts rather than touching CMake logic per-triplet.

### D3: Boundary API shape — `gd_fts_*`
Mirror the existing blocking `gd_*` style (see `goldendict.h` conventions):

- `gd_fts_index( int dict_index )` — build the dictionary's full-text index if
  missing/stale; `0` done, negative on error.
- `gd_fts_index_state( int dict_index, int * out )` — `0` present, `1` missing,
  `2` building (only `0`/`1` initially; building state comes from the UI, see
  D4).
- `gd_fts_search( const char * query, int mode, int group_id, char * out, int
  out_size )` — serialize matching headwords+dict ids (newline-delimited, like
  `gd_suggest`); `-1` invalid args, `-2` buffer too small, `-3` index missing.
  Returning **headwords** (not raw articles) keeps the results→article flow
  uniform and small.

The `FtsHelpers::FTSResultsRequest` is async internally (`QtConcurrent`); the
boundary wraps it with a blocking `.waitForFinished()`/result read on the caller
thread, matching how the engine service already shields the UI (bounded wait).

### D4: Index build is engine-thread, state surfaced to UI
Indexing is expensive for large dictionaries. The boundary runs it on the
engine's existing single-worker thread (like `gd_scan_dicts`); Kotlin triggers
it per dictionary on demand and shows a per-dictionary "Building…" state by
tracking in-flight requests in the ViewModel. A full multi-dict background
indexer with parallel threads and timers (upstream `FtsIndexing`) is out of
scope — lazy per-dict build + visible state satisfies the spec and keeps the
boundary simple.

### D5: Search modes map 1:1 to `FTS::SearchMode`
Expose `mode` as an int on `gd_fts_search` (0 whole-words/Xapian syntax,
1 plain text, 2 wildcards, 3 regexp) matching `FTS::SearchMode`, with a small
enum on the Kotlin side. Upstream's parser handles mode inside
`FTSResultsRequest::run()`; the boundary just forwards the int.

### D6: Results → existing article flow
`gd_fts_search` returns **headwords**; the Kotlin screen builds a results list
of `headword (dict name)` rows and a tap calls the existing `viewModel.lookup()`.
This reuses active-group handling, history recording, and the not-found
indication with zero new lookup logic (same reasoning as the launcher-shortcuts
change). Spec scenarios ("Result respects active group", "Results lead to
articles") fall out of that reuse.

## Risks / Trade-offs

- [No android `xapian` vcpkg port on the pinned baseline (2026.07.29), or port
  build failures for the android triplets.] → Mitigation: D2's scripted
  xapian-core build fallback; CI smoke (host tool) needs only the host xapian
  (vcpkg `xapian` on x64-windows already available), so the CI gate can pass
  while the android build is nailed, but the on-device APK depends on it.
- [Per-dict lazy indexing means a first search on a large dictionary visibly
  stalls the engine worker (UI stays responsive via IPC, but the request
  blocks).] → Mitigation: surface index state (D4) so the user sees "Building…"
  and only queries after state is ready; the spec's "Large dictionary" scenario
  only requires responsiveness, not results.
- [Xapian query syntax on the whole-words mode can surprise users (AND/OR etc.).]
  → Mitigation: default the UI to the plain-text mode (mode 1) like upstream's
  safest default; expose the mode selector for power use.
- [Index storage: per-dict xapian DBs live next to the staged dictionary files
  (as upstream `ftsIndexName()` dictates); rescan/re-stage deletes them with the
  source.] → Mitigation: index state recomputed on scan (`ftsIndexIsOldOrBad`),
  so a stale/absent index simply rebuilds; covered by the "Index respects
  content changes" scenario.

## Migration Plan

No persisted-schema changes. On the engine side: revert the FTS stub (delete
`fts_stub.cc`, restore upstream `ftshelpers.hh`-driven behavior) behind the same
carve structure — rollback is re-adding the stub files. On CI: host smoke adds
an FTS assertion so a future stub regression fails CI. On device: existing
staged dictionaries simply gain indexes on first FTS use; no migration of
existing data.

## Open Questions

None — the two unknowns (android xapian port availability, exact build tail)
are contained by D2's dual path and can be resolved during implementation
without changing specs or task breakdown.