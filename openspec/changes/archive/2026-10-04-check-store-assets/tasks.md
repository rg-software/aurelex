## 1. Write the check

- [x] 1.1 Add `scripts/check-store-assets.py`, standard library only: read each PNG's IHDR for width, height and colour type, and hash the file for the uniqueness rule.
  `read_geometry` opens the file, checks the 8-byte signature and that the
  first chunk is `IHDR`, then unpacks `>IIBB` from the chunk data. The
  signature and chunk-type checks are what let a truncated or mislabelled file
  be reported as unreadable instead of being read as some plausible size.
  Uniqueness is `hashlib.sha256` over the whole file.
- [x] 1.2 Put Play's limits in named constants — screenshot count (2–8 per language), per-side bounds (320–3840), accepted aspect ratios (16:9, 9:16), listing icon 512×512, feature graphic 1024×500 — with the source of each number in a comment.
  `MIN_SCREENSHOTS`/`MAX_SCREENSHOTS`, `MIN_SIDE_PX`/`MAX_SIDE_PX`,
  `ACCEPTED_RATIOS`, `RATIO_TOLERANCE` (1% relative, so a rounding artefact is
  not a failure), `ICON_SIZE`, `FEATURE_GRAPHIC_SIZE`, each under one comment
  citing the Console's graphic-asset requirements. Every failure message
  interpolates the constant it broke rather than a literal.
- [x] 1.3 Assert the screenshot rules: count within the limit, each file within the per-side bounds, each aspect ratio within a stated tolerance of 16:9 or 9:16, no two files byte-identical, and `NN-` prefixes unique and contiguous from 1.
  One function per rule, all appending to a shared violation list. Contiguity
  compares the sorted distinct prefixes against `1..n`, so a gap fails. A file
  with no `NN-` prefix is itself a violation — it has no defined gallery
  position — which is what makes the ordering rule total over the directory.
- [x] 1.4 Assert the listing icon and feature graphic are present at their required dimensions.
  `check_fixed_asset` reports absent, unreadable and wrongly-sized separately,
  since "the regeneration changed a dimension" and "the file is gone" are
  different mistakes.
- [x] 1.5 Collect every violation before exiting, print one line per violation naming the file and the limit broken, and exit non-zero when there is at least one.
  Violations go to stderr under a count header; exit 1. Proved by 2.3.
- [x] 1.6 Print a one-line summary of what passed on success (count and dimensions), so a passing run in CI logs what it actually checked.
  `summarise` reports the count, the distinct sizes present, both fixed assets
  and that content and ordering were checked, so a green CI line is a
  statement about what was verified rather than just "ok".

## 2. Verify it against good and bad input

- [x] 2.1 Run it against the committed gallery; it must pass and report six screenshots at 1080×1920 plus the icon and feature graphic.
  `python scripts/check-store-assets.py` → exit 0,
  `OK  6 phone screenshot(s) at 1080x1920, listing icon 512x512, feature
  graphic 1024x500, unique content and contiguous NN- order from 1`. Read
  independently off the committed PNGs: all six screenshots 1080×1920
  (depth 16, colour type 2), icon 512×512, feature graphic 1024×500.
- [x] 2.2 Prove each rule fires, on a scratch copy rather than the repository: a ninth screenshot (count), a 200×200 image (bounds), a 1080×2000 image (ratio), a byte-identical duplicate, two files sharing a prefix, and a missing feature graphic.
  Ten cases on temp copies (`copytree` per case, nothing written under the
  repository), all firing as intended: count (9 files), bounds (200×200 →
  both sides), ratio (1080×2000 → 0.5400), duplicate content, shared prefix,
  a numbering gap, missing feature graphic, wrongly sized feature graphic
  (1024×501), a four-fault run, and an untouched copy still passing. Faults
  are injected as synthetic stdlib PNGs so each case is isolated — in
  particular the shared-prefix case uses a *distinct* image, so it proves the
  prefix rule without the duplicate-content rule firing alongside it.
- [x] 2.3 Confirm a run with several faults reports all of them, not just the first.
  Four independent faults in one run reported all **7** resulting violations
  (the count, both sides of the bounds, the ratio, the duplicate, the shared
  prefix, the missing feature graphic) — 1 header + 7 lines, exit 1.
- [x] 2.4 Confirm the check does not need ImageMagick, by running it with `magick` removed from `PATH`.
  ImageMagick 7.1.2-Q16-HDRI *is* on this machine's `PATH`, so the absence is a
  real change: with `PATH` cut to `C:\Windows\System32;C:\Windows`,
  `Get-Command magick` finds nothing and the check still exits 0. The
  converter, by contrast, needs ImageMagick and Montserrat — which is the
  asymmetry D1 turns on.

## 3. Wire it into CI

- [x] 3.1 Add a step to `.github/workflows/release-qt.yml`, next to the existing vendored-library packaging assertion, so a release cannot ship an invalid asset set.
  "Assert the store listing assets match Play's constraints", `shell: pwsh`,
  `run: python scripts/check-store-assets.py`, placed immediately before the
  vendored-TLS assertion so the three pre-publication assertions sit together.
  The comment records why the step exists at all: these assets are committed
  files no build rule reads, so Play is otherwise the only thing that would
  reject them.
- [x] 3.2 Add a path-triggered workflow (or job) covering `app/android/store-listing/**`, `scripts/make-store-screenshots.ps1` and the check itself, so the commit that introduces a mistake is the one that fails.
  New `.github/workflows/check-store-assets.yml`, shaped like `engine-smoke.yml`
  (push on `"**"` with a `paths:` filter, plus `workflow_dispatch`) rather than
  bolted onto an unrelated workflow. Paths: the asset directory, the converter,
  the check, and the workflow file itself — the last so the check cannot rot
  untested.
- [x] 3.3 Confirm the CI step runs on `windows-latest` with no extra setup, and that its log states what it checked.
  Both jobs are `windows-latest` with **no** `setup-python`: the runner ships
  Python and `release-qt.yml` already depends on the preinstalled interpreter
  (`python -m aqt`). Verified for real by copying only the script and the asset
  directory into an empty temp tree (no repo, no `.git`, no ImageMagick, `PATH`
  cut to `C:\Windows\System32;C:\Windows`) and running the exact CI command:
  exit 0. The CI log line is
  `OK  6 phone screenshot(s) at 1080x1920, listing icon 512x512, feature graphic 1024x500, unique content and contiguous NN- order from 1`
  — it names the count, the dimensions, both fixed assets and the two
  content/order rules, so a green run states what it verified. Both workflow
  files re-parsed with PyYAML after editing (24 steps in `build`, 2 in `check`,
  triggers as intended).

## 4. Document the constraints once

- [x] 4.1 Add the constraint table to `app/android/store-listing/listing.md`: the count, bounds, ratios and the two fixed asset sizes, each naming `scripts/check-store-assets.py` as the enforcing copy, so the prose and the check cannot drift apart silently.
  New "### Constraints Play enforces" subsection under **Assets**, one row per
  rule with the enforcing constant named (`MIN_SCREENSHOTS`, `MIN_SIDE_PX`,
  `ACCEPTED_RATIOS`, `ICON_SIZE`, …). The prose that previously stated the
  per-side bounds and ratios inline is folded into it, and the two rules with no
  constant (duplicate content, ordering) are named as rules. Also recorded
  *why* the duplicate rule exists — the upload appends in file order, so an
  orphan occupies a gallery slot.
- [x] 4.2 Note in that table which Play fields the check does **not** cover — the listing text limits and whether a given screenshot is *appropriate* — so nobody reads a green check as more than it is.
  A "What this check does not cover" paragraph directly under the table: it
  reads PNG headers, so it validates *shape*, not *content* — it does not check
  the text limits (stated at the top of the file; the script never reads
  `listing.md`) and it cannot tell whether a screenshot belongs in the gallery
  or shows anything true. "A well-formed capture of the wrong screen passes."
- [x] 4.3 Add a row to `docs/TESTING.md` for the check, recording that it validates shape and not content.
  Row **52** in *Distribution & polish*, following rows 49–51 which cover the
  other release-pipeline assertions. The Expected cell states the pass line and
  bolds "Shape, not content" with the two omissions spelled out; the Status
  cell records what was actually run.
- [x] 4.4 Run `openspec validate check-store-assets` and confirm the delta merges into `openspec/specs/distribution-and-polish/spec.md`.
  `Change 'check-store-assets' is valid`. The delta is `## ADDED Requirements`
  only and its single requirement, *Store listing assets are validated before
  publication*, is **not** among the seven requirements already in the main
  spec (`Signed release artifacts`, `Google Play signing`, `F-Droid signing`,
  `App icon`, `First-run onboarding`, `Self-contained release builds`,
  `Launch starting window matches the app background`), so the merge is purely
  additive and collides with nothing.