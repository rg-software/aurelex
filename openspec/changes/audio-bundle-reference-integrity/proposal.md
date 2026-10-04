## Why

The published `au_kaikki_en-en` dictionary references 210 recordings its resource
bundle does not hold, 201 of them only differing from a bundled file in letter
case. Android's storage is case-sensitive, so about 185 entries render a play
control that does nothing, while the same files resolve on a Windows build
machine. The run that shipped it only printed a warning, because
`--reuse-bundle`'s documented promise to "fail rather than shipping a dictionary
whose bundle is missing a referenced file" is a `print` in `build.py`, and
nothing in the build or in CI asserts the one invariant that matters: every
recording a rendered dictionary references must be a file in its bundle.

## What Changes

- `--reuse-bundle` verification becomes the contract the documentation already
  describes: resource names are compared **case-insensitively** (as the rest of
  the audio pipeline already does), and a bundle that lacks a referenced
  resource **fails the run** with a non-zero exit instead of publishing.
- `--reuse-bundle` becomes self-healing for a case-only difference: a referenced
  name the bundle holds under another spelling is added under the name the
  dictionary references, so a re-render cannot desynchronise text from bundle.
- `extract_audio` stops letting one archive member satisfy only one wanted name.
  Two names that fold to the same archive key (two records whose `ogg_url` spell
  the same recording differently) currently starve each other, which can drop a
  recording from a bundle that is built from scratch — reproduced, and
  independent of `--reuse-bundle`.
- A new post-build check reads the written `.dsl.dz` and the sibling bundle's
  entry names and fails the build when any audio-extension `[s]` reference has no
  file. It also runs as a standalone command so an existing published pair can be
  audited without re-rendering.
- The published en-en pair is repaired in place with the existing
  bundle-rebuild command and re-published, so the shipped artifact stops carrying
  185 dead audio links.

## Capabilities

### New Capabilities

None. This changes how existing build guarantees are kept, not what the converter
can do.

### Modified Capabilities

- `dictionary-conversion`: "Optional reuse of an existing resource bundle" now
  folds case when matching resource names, fails on any missing referenced
  resource, and repairs a case-only mismatch; a new requirement makes a build
  verify its own rendered references against its bundle before finishing.
- `audio-bundle-rebuild`: "References stay consistent with the bundle" gains the
  case-only case — a reference whose spelling differs from the archive's own must
  still resolve to a bundled file rather than be reported missing.

## Impact

- `scripts/kaikki/build.py` — the reuse check becomes failing, case-folding and
  self-healing; the new reference assertion runs after the dictionary and bundle
  are written.
- `scripts/kaikki/audio.py` — `extract_audio` writes a member to every claimant
  of its key.
- `scripts/kaikki/prefetch.py` — inherits the fix through `extract_audio`; the
  bundle-rebuild command gains the same self-healing name handling.
- `scripts/tests/` — new tests for the reuse check, the multi-claimant
  extraction, and the reference assertion.
- `docs/KAIKKI-CONVERSION.md`, `docs/TESTING.md` — the defect write-up added
  while diagnosing this; its "known defect" text is updated to the fixed
  behaviour.
- `catalog/catalog.json` and the published artifacts — the repaired en-en bundle
  changes the entry's digests.
- No engine, app, or boundary code is touched; no app behaviour changes beyond a
  play control that now works.
