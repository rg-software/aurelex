## Why

The Play store listing assets are the only shipped artifact with no machine
check. Their constraints live in a comment inside the converter script and in
prose, so the first feedback on a mistake is Play rejecting the upload.

That is not hypothetical. While preparing the closed-beta listing, renumbering
the gallery left five byte-identical orphan PNGs beside their replacements —
`2-search-suggestions.png` next to `3-search-suggestions.png`, and so on. Nothing
caught it: the converter wrote the new names and never pruned the old ones, and
no step compared the committed set against what Play expects. The upload then hit
Play's eight-image cap and had to be done as delete-then-reupload inside a single
edit, purely because the local set had ten files where it should have had six.

The converter now prunes what it did not write, but that only helps whoever runs
it. A stale or wrong-sized file committed by hand, or a second capture of the
same screen, still reaches Play unchallenged.

## What Changes

- Add a repository check over the store listing assets that asserts the
  properties Play actually enforces, so a mistake fails locally and in CI:
  - the phone-screenshot gallery is within Play's per-language limit;
  - every screenshot is within Play's per-side dimension bounds and has a 16:9
    or 9:16 aspect ratio;
  - no two screenshots share the same bytes, which catches orphan duplicates;
  - the `NN-` prefixes are unique and contiguous, so the gallery order stays
    what the filenames claim;
  - the listing icon and feature graphic are present at the dimensions Play
    requires.
- Run it in CI on changes to the assets or the converter, and as a step in the
  release workflow next to the existing packaged-artifact assertions.
- Record the constraint table next to the listing copy, so the numbers a
  maintainer needs are stated once and are the same numbers the check enforces.

- **Not in scope:** re-uploading anything to Play as part of this change, and
  changing the gallery contents or their order. This only makes the existing set
  verifiable.
- **Not in scope:** verifying the listing *text* against Play's field limits.
  Those are recorded in `listing.md` today; a check is possible but belongs with
  the text, not the images.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `distribution-and-polish`: a new requirement that the versioned store listing
  assets are validated against Play's constraints — gallery size, screenshot
  dimensions and aspect ratio, absence of duplicate content, stable gallery
  order, and the listing icon and feature graphic — before they are published,
  so that a malformed or duplicated asset set is caught by the repository rather
  than by Play.

## Impact

- New check script (Python, standard library only — PNG dimensions come from the
  IHDR chunk, so no image library and no ImageMagick on the runner).
- `.github/workflows/release-qt.yml` — one assertion step beside the existing
  vendored-library packaging assertion, plus a trigger so the assets are checked
  outside release builds.
- `app/android/store-listing/listing.md` — the constraint table, stated once.
- `docs/TESTING.md` — a row for the check, including what it does *not* cover.
- No app, engine or `carve/` change; nothing about the APK differs.