# ENGINE — the goldendict-ng source pin

Aurelex is an **independent project**. It is not a fork, a downstream, or a
branch of goldendict-ng, and nothing here is meant to flow back there.

What Aurelex does is **consume** the goldendict-ng dictionary engine verbatim
from a pinned release tag and drive it in-process through the `gd_*` boundary.
That engine is the single most relied-upon external source in this repository —
everything about reading a dictionary file is goldendict-ng's work, not ours.
Our responsibility is the opposite of a fork's: keep the foundation solid and
take relevant releases, without diverging into maintenance of our own engine.

There is no merge relationship in either direction:

- We do **not** maintain a goldendict-ng fork, and we do not track its `master`.
- We do **not** send changes back, and we do not aim to.
- We **do** keep local deviations — but as patches applied to a pristine
  checkout, never as commits in the engine tree (see `AGENTS.md`, golden rule 1).

## Pin

- **Source:** https://github.com/xiaoyifang/goldendict-ng
- **License:** GPLv3 or later (see `LICENSE`)
- **Pinned tag:** `v26.8.0` (release 2026-08-05)
- **Commit:** `c84e0113b84fc9ee6d5cfef8de646b0eb95d7707`
- **Resolved:** 2026-08-31

The engine lives in the `engine/` submodule at this tag, with the working tree
kept pristine except for the applied patches below.

## Taking a new release

1. Check the available release tags (`git ls-remote --tags origin`).
2. Update the submodule to the new tag and record the new tag + commit here.
3. Apply `patches/` (see below), build, and run the CI smoke test (look up a
   known word). The smoke test is the gate: an engine release can compile
   cleanly and still break the boundary.
4. If the index format changed, the reindex-on-version rule applies (see the
   archived `goldendict-mobile-port` design, D5).

Only stable tags are worth taking. Daily `v26.9.0_alpha.*` builds churn weekly;
a tag pins the engine and its index format together, so releases are batched and
reproducible.

## Local deviations (the patch set)

`patches/` holds every deviation from the pinned source. The engine submodule is
never committed with edits, so before any build or CI run the patches must be
applied to its working tree:

- Windows: `.\scripts\apply-patches.ps1`
- Unix/CI: `./scripts/apply-patches.sh`

`git -C engine checkout -- .` reverts the working tree back to the pinned tag.

The set is deliberately short — four patches, applied in numeric order:

| # | Patch | Change | Why |
| --- | --- | --- | --- |
| 0001 | `dsl-drop-unused-qtsvg-include` | `dsl: drop unused QSvgRenderer include` | Dead include, but a hard failure for us: goldendict-ng builds with QtSvg available, the Android carve does not, so `<QSvgRenderer>` failed to resolve. Behaviour-neutral. |
| 0002 | `android-no-gui-app-writable-home` | `android carve: no QGuiApplication; writable config home` | Three fixes so the engine runs with only a `QCoreApplication` and no platform plugin: `getOptimalIconSize` no longer reads `qGuiApp`, `tiff2img` guards `QApplication::primaryScreen()` (null screen → use the image's own size) instead of crashing, and `getHomeDir` uses the `HOME` env var (the boundary points it at the app dir) rather than the XDG/`QStandardPaths` branch, which needs a Qt application. |
| 0003 | `fts-wildcards-expansion-cap` | `fts: raise wildcard expansion cap for full-text search` | The engine caps wildcard expansion at 1 term, which makes `read*`-style prefix FTS useless. Raised to 100. |
| 0004 | `fts-sliced-build` | `fts: build in slices, commit periodically, publish atomically` | The engine holds its lock for a whole index build, so lookups over other dictionaries block until it finishes. Slices the build, commits periodically (resume after a kill) and publishes by atomic rename instead of a second `compact()` pass. |

0003 and 0004 are the two FTS changes the user-visible behaviour in
`docs/TESTING.md` (§ Full-text search, #32a–#32c) depends on, so treat both as
load-bearing rather than as optional tuning.

Adding a deviation means a fifth row here plus a matching note in `AGENTS.md`.
If the list is growing, the boundary (`carve/`) is probably the right home
instead — the smaller this table stays, the cheaper every future release is.
