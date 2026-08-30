# UPSTREAM.md — goldendict-ng engine pin

This project reuses the goldendict-ng dictionary engine verbatim. Follow the
merge contract in `AGENTS.md` (never edit `engine/` in place; deviations live
in `patches/` or the boundary layer).

## Pin

- **Upstream:** https://github.com/xiaoyifang/goldendict-ng
- **License:** GPLv3 or later (see `LICENSE` / `NOTICE`)
- **Pinned tag:** `v26.8.0` (latest stable release, 2026-08-05)
- **Commit:** `c84e0113b84fc9ee6d5cfef8de646b0eb95d7707`
- **Resolved:** 2026-08-31

## Updating the pin

1. Check upstream release tags (`git ls-remote --tags origin`).
2. Bump the pin in `engine/` and this file.
3. Apply `patches/`, build, run the CI smoke test (lookup a known word).
4. If index format changed, the reindex-on-version rule (see design.md D5) applies.

## Why a tag, not a branch

Daily alpha builds (`v26.9.0_alpha.*`) churn weekly. A tag pins the engine and
its index format together so bumps are batched and reproducible.