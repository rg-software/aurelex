## Context

See proposal.md — Why for the motivation. What shapes the approach:

- The audio pipeline already has one normaliser for "is this the same
  recording", `_audio_match_key` in `scripts/kaikki/audio.py`: basename,
  percent-decoded, spaces to underscores, casefolded. Availability checks,
  archive-key generation and the bundle-rebuild command all use it. The
  `--reuse-bundle` verification is the one place that compares names as bytes.
- A bundle name is derived from the *reference*, not from the archive member
  (`AudioPlan._final_name`), so the article is authoritative about spelling.
  `bundle-audio` already rewrites the dictionary when a reference is not
  filesystem-safe, so rewriting the dictionary in that mode has precedent.
- `extract_audio` streams the ~20 GB archive once and assigns each member to a
  single claimant (`next(n for n in owners if n in remaining)`), so two wanted
  names that fold to the same key cannot both be served.
- The CLI is hand-dispatched (`cli.main`): modes return an `int` that becomes the
  process exit status, and the build path currently returns 0 unconditionally.
- The published en-en pair has 210 unresolved references (201 case-only), 9 of
  which exist in no archive at all — those cannot be repaired by any bundling
  step, only removed.

## Goals / Non-Goals

**Goals:**

- Make "every `[s]` reference in a dictionary is a file in its bundle" an
  enforced invariant of every build, and auditable on any existing pair.
- Make `--reuse-bundle` fail rather than publish a mismatched pair, while keeping
  the mode's cost bounded (no archive re-stream for a spelling-only difference).
- Let a published pair be repaired without re-rendering the snapshot.

**Non-Goals:**

- Changing which recording a headword gets, or the per-word audio limit.
- Detecting *duplicate* or *orphaned* bundle entries as errors — extra files are
  reported, not fatal (they are a symptom, not a defect; the shipped en-en
  bundle has 47).
- Reworking the audio archive index or the prefetcher's sharding.

## Decisions

**D1 — Fold case with the existing normaliser, everywhere a bundle entry is
compared to a reference.**
The reuse check and the new assertion both compare with `_audio_match_key`, so a
reference and a bundle entry that differ only in letter case are the same
resource. Alternatives: (a) keep the check byte-exact and simply fail — this
fails legitimate re-renders whenever the snapshot's wiki markup changes a file's
spelling, and sends the operator to a full rebuild for a cosmetic difference;
(b) rename bundle entries to the archive's spelling and rewrite articles — needs
the archive for every name and mutates article text, which `--reuse-bundle`
exists to avoid. Folding is also already the pipeline's own definition of
"same recording", so it introduces no new concept.

**D2 — Repair a case-only mismatch instead of failing; fail only when the
recording is absent under every case.**
Adding the entry means rewriting the bundle, which for en-en streams 1.7 GB once
(entries are `ZIP_STORED`, so it is a byte copy) — one to two minutes and one
bundle's worth of free disk, versus a full re-render that re-streams the archive
and re-extracts ~95k recordings to reach the same result. The repair streams each
entry from the old bundle into a temporary archive and atomically replaces it, so
an interrupted repair leaves the original intact. Only a recording present under
no case variant is fatal, because there is nothing to copy.

**D3 — Verify from the written files, not from in-memory state.**
The check reads the `.dsl.dz` that was just written and the sibling bundle's
entry names. That makes it the one implementation every write path shares
(full build, `--reuse-bundle`, and later any new path) and lets it audit a pair
that already exists. The cost is one gzip pass over the dictionary — about 40 s
for the 70 MB en-en file, which is nothing against a render measured in hours.
The cheap alternative (compare the in-memory `referenced` set against the names
just written) would catch the same defect in a fresh build but could not audit or
repair a published pair, which is the case we actually have to fix.

**D4 — The rule is "every `[s]` name is a bundle entry", classified for the
report.**
`[s]` carries audio *and* the sense-marker icons (`dsltext.py`). The assertion
reads audio-extension names via the existing `AUDIO_EXTENSIONS`, knows the icons
via `_ICON_FILES`, and classifies each unresolved name for the report: an audio
name, a known icon, or an unrecognised resource. All three fail the run; the
classification only shapes the message. Keeping one rule rather than an audio
special case means a future icon added to `app/android/assets/icons/` without a
bundle entry is caught by the same assertion instead of shipping as a blank
marker.

**D5 — Give an archive member to every claimant that folds to its key.**
`extract_audio` keeps extracting the member once (the tar stream visits it once),
then copies the extracted file to the remaining claimants of the same key. The
number of claimants is bounded by `--audio-per-word` and is in practice two.
Alternatives — collapsing case-variant wanted names to one and rewriting the
article, or deduping in `plan()` by fold key — both change the names the
dictionary uses, which contradicts the reference being authoritative (Context).

**D6 — Let `bundle-audio` drop a reference it cannot locate.**
The 9 references in the shipped en-en dictionary exist in no archive and no
cache, so no bundling step can satisfy them; without removal the new invariant
can never hold for that artifact and repairing it would require a full re-render.
The mode already rewrites the dictionary for unsafe names, so this is the same
mechanism with one more trigger. The report states how many links were removed,
and `--keep-unresolved` restores the previous behaviour for an operator who
prefers a dangling link to an edited dictionary.

**D7 — Surface the result through the report and the process exit status.**
`build()` records unresolved references in the report it already returns and
prints them; `cli.main` returns a non-zero status when the set is non-empty or
when `--reuse-bundle` could not satisfy a reference, matching the exit-status
convention the other modes already use. No new exception type crosses the CLI
boundary.

## Risks / Trade-offs

- [The repair streams a 1.7 GB bundle, so it needs the bundle's size in free
  disk and a couple of minutes] → write beside it to a temporary file and replace
  atomically, so a failure leaves the old bundle usable; only attempt the repair
  when something actually differs.
- [The new assertion will fail the en-en pipeline that is currently considered
  green] → that is the intended outcome; run the check against all three published
  pairs before landing it so the failures are known (expected: en-en reports 210,
  ja-ja and ru-ru report none).
- [A build now spends ~40 s re-reading its own output] → the pass is streamed, not
  buffered, and the mode form is available separately for an audit.
- [Case folding could hide a real spelling mistake on a case-insensitive build
  machine] → it cannot: the bundle is always written under the reference's exact
  spelling (D2, D5), so the assertion compares names that are byte-identical on
  every filesystem, and a repair leaves both spellings present.
- [Dropping unlocatable links edits a published dictionary file] → the mode
  already edits it for unsafe names, prints exactly what it removed, and offers
  `--keep-unresolved`; the repaired artifact is republished as a new digest
  rather than patched in place.

## Migration Plan

1. Land the assertion as a standalone mode first and run it against the three
   published pairs; the en-en failures are the evidence for the rest.
2. Repair en-en in place: `bundle-audio dist/au_kaikki_en-en.dsl.dz …`, which adds
   the 201 case-only entries and removes the 9 unlocatable links, then re-verify.
3. Republish the en-en entry with its new digests. Existing installations hold the
   old bundle as an optional resource; see the open question below.
4. Then enable the failure for builds and for `--reuse-bundle`, so the next
   publish cannot ship a mismatched pair.

Rollback is reverting the change; no data migration is involved, and the repaired
artifact is a superset of the old one (201 added entries, 9 removed links).

## Open Questions

- An installed dictionary whose **optional** resource file changes digest: does
  the catalog surface that as an update, or must the user re-add the dictionary to
  pick the new bundle up? This decides whether step 3 above is enough for existing
  installs or whether a forced audio re-fetch is needed. It does not change the
  specs or the approach here — only task 5.2 — and is answerable by reading the
  catalog update path (and, if needed, by the `catalog-dictionary-updates` change).
