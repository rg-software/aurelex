## 1. Write the check

- [ ] 1.1 Add `scripts/check-store-assets.py`, standard library only: read each PNG's IHDR for width, height and colour type, and hash the file for the uniqueness rule.
- [ ] 1.2 Put Play's limits in named constants — screenshot count (2–8 per language), per-side bounds (320–3840), accepted aspect ratios (16:9, 9:16), listing icon 512×512, feature graphic 1024×500 — with the source of each number in a comment.
- [ ] 1.3 Assert the screenshot rules: count within the limit, each file within the per-side bounds, each aspect ratio within a stated tolerance of 16:9 or 9:16, no two files byte-identical, and `NN-` prefixes unique and contiguous from 1.
- [ ] 1.4 Assert the listing icon and feature graphic are present at their required dimensions.
- [ ] 1.5 Collect every violation before exiting, print one line per violation naming the file and the limit broken, and exit non-zero when there is at least one.
- [ ] 1.6 Print a one-line summary of what passed on success (count and dimensions), so a passing run in CI logs what it actually checked.

## 2. Verify it against good and bad input

- [ ] 2.1 Run it against the committed gallery; it must pass and report six screenshots at 1080×1920 plus the icon and feature graphic.
- [ ] 2.2 Prove each rule fires, on a scratch copy rather than the repository: a ninth screenshot (count), a 200×200 image (bounds), a 1080×2000 image (ratio), a byte-identical duplicate, two files sharing a prefix, and a missing feature graphic.
- [ ] 2.3 Confirm a run with several faults reports all of them, not just the first.
- [ ] 2.4 Confirm the check does not need ImageMagick, by running it with `magick` removed from `PATH`.

## 3. Wire it into CI

- [ ] 3.1 Add a step to `.github/workflows/release-qt.yml`, next to the existing vendored-library packaging assertion, so a release cannot ship an invalid asset set.
- [ ] 3.2 Add a path-triggered workflow (or job) covering `app/android/store-listing/**`, `scripts/make-store-screenshots.ps1` and the check itself, so the commit that introduces a mistake is the one that fails.
- [ ] 3.3 Confirm the CI step runs on `windows-latest` with no extra setup, and that its log states what it checked.

## 4. Document the constraints once

- [ ] 4.1 Add the constraint table to `app/android/store-listing/listing.md`: the count, bounds, ratios and the two fixed asset sizes, each naming `scripts/check-store-assets.py` as the enforcing copy, so the prose and the check cannot drift apart silently.
- [ ] 4.2 Note in that table which Play fields the check does **not** cover — the listing text limits and whether a given screenshot is *appropriate* — so nobody reads a green check as more than it is.
- [ ] 4.3 Add a row to `docs/TESTING.md` for the check, recording that it validates shape and not content.
- [ ] 4.4 Run `openspec validate check-store-assets` and confirm the delta merges into `openspec/specs/distribution-and-polish/spec.md`.