# UPSTREAM.md — goldendict-ng engine pin

This project reuses the goldendict-ng dictionary engine verbatim. Follow the
merge contract in `AGENTS.md` (never edit `engine/` in place; deviations live
in `patches/` or the boundary layer).

## Pin

- **Upstream:** https://github.com/xiaoyifang/goldendict-ng
- **License:** GPLv3 or later (see `LICENSE`)
- **Pinned tag:** `v26.8.0` (latest stable release, 2026-08-05)
- **Commit:** `c84e0113b84fc9ee6d5cfef8de646b0eb95d7707`
- **Resolved:** 2026-08-31

## Updating the pin

1. Check upstream release tags (`git ls-remote --tags origin`).
2. Bump the pin in `engine/` and this file.
3. Apply `patches/` (see below), build, run the CI smoke test (lookup a known word).
4. If index format changed, the reindex-on-version rule (see design.md D5) applies.

## Applying the deviation patches

`patches/` holds every deviation from upstream. Before any build/CI run, the
engine submodule must be patched. The engine working tree starts clean (the
submodule itself is never committed with edits):

- Windows: `.\scripts\apply-patches.ps1`
- Unix/CI: `./scripts/apply-patches.sh`

`git -C engine checkout -- .` reverts the working tree back to the pinned tag.

The set is deliberately short — four patches, applied in numeric order:

| # | Patch | Upstream change | Why |
| --- | --- | --- | --- |
| 0001 | `dsl-drop-unused-qtsvg-include` | `dsl: drop unused QSvgRenderer include` | Dead include, but a hard failure for us: upstream builds with QtSvg available, the Android carve does not, so `<QSvgRenderer>` failed to resolve. Behaviour-neutral. |
| 0002 | `android-no-gui-app-writable-home` | `android carve: no QGuiApplication; writable config home` | Three fixes so the engine runs with only a `QCoreApplication` and no platform plugin: `getOptimalIconSize` no longer reads `qGuiApp`, `tiff2img` guards `QApplication::primaryScreen()` (null screen → use the image's own size) instead of crashing, and `getHomeDir` uses the `HOME` env var (the boundary points it at the app dir) rather than the XDG/`QStandardPaths` branch, which needs a Qt application. |
| 0003 | `fts-wildcards-expansion-cap` | `fts: raise wildcard expansion cap for full-text search` | Upstream caps wildcard expansion at 1 term, which makes `read*`-style prefix FTS useless. Raised to 100. |
| 0004 | `fts-sliced-build` | `fts: build in slices, commit periodically, publish atomically` | Upstream holds the engine mutex for a whole index build, so lookups over other dictionaries block until it finishes. Slices the build, commits periodically (resume after a kill) and publishes by atomic rename instead of a second `compact()` pass. |

0003 and 0004 are the two FTS changes the user-visible behaviour in
`docs/TESTING.md` (§ Full-text search, #32a-#32c) depends on, so treat both as
load-bearing rather than as optional tuning. Any new deviation is a fifth row
here plus a matching note in `AGENTS.md`; if the list is growing, the boundary
(`carve/`) is probably the right home instead.

## Why a tag, not a branch

Daily alpha builds (`v26.9.0_alpha.*`) churn weekly. A tag pins the engine and
its index format together so bumps are batched and reproducible.