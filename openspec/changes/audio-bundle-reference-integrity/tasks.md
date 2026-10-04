## 1. Reference-resolution check

- [ ] 1.1 Add a reader that returns every `[s]` resource name a rendered
      `.dsl.dz` references, reusing `dsltext`'s link parsing and unescaping, and
      unit-test it against a small fixture
- [ ] 1.2 Classify each referenced name (audio extension via `AUDIO_EXTENSIONS`,
      known icon via `_ICON_FILES`, otherwise unrecognised) and report the three
      groups separately
- [ ] 1.3 Compare the referenced names with a bundle's entry names through
      `_audio_match_key`, returning the unresolved names and how many of those
      exist in the bundle under another case
- [ ] 1.4 Call it from `build()` after the dictionary and bundle are written, put
      the unresolved names on the report and in its summary, and stream the
      dictionary rather than buffering it
- [ ] 1.5 Return a non-zero exit status from `cli.main` when the set is
      non-empty, matching the other modes' convention
- [ ] 1.6 Expose the same function as a `verify-bundle <dictionary>` mode that
      reports and changes nothing, and document it in the CLI help
- [ ] 1.7 Unit-test: all references resolve, one differs only in case, one is
      absent entirely, a dictionary that references only icons, and a dictionary
      with no bundle beside it

## 2. `--reuse-bundle` verification

- [ ] 2.1 Replace the exact set difference with a `_audio_match_key` comparison so
      a case-only difference is not a missing resource
- [ ] 2.2 Repair a case-only difference by adding the entry under the referenced
      name: stream the existing bundle into a temporary archive beside it and
      replace atomically, doing nothing when no name differs
- [ ] 2.3 Exit non-zero when a referenced resource is absent under every case, and
      when there is no bundle beside the dictionary at all
- [ ] 2.4 Report the number of repaired entries and list any resource that could
      not be satisfied
- [ ] 2.5 Unit-test with a small fixture bundle: complete reuse, a repairable
      case-only difference, an unsatisfiable reference, and no bundle

## 3. Multi-claimant archive extraction

- [ ] 3.1 In `extract_audio`, after writing a member for the first claimant of its
      key, copy the extracted file to the remaining claimants of the same key
- [ ] 3.2 Keep returning a name as missing only when no member claimed it, so a
      truly absent recording is still reported
- [ ] 3.3 Add the regression test from the diagnosis: one member, two wanted names
      differing only in case, both written and neither reported missing

## 4. References that resolve nowhere

- [ ] 4.1 In `bundle_audio`, collect the references no cache or archive satisfies
      and remove their `[s]` links from the dictionary, through the same rewrite
      path that already fixes unsafe names
- [ ] 4.2 Report how many links were removed and name them
- [ ] 4.3 Add `--keep-unresolved` so an operator can keep a dangling link instead
      of an edited dictionary, and cover both paths with tests
- [ ] 4.4 Confirm the rewritten dictionary stays a valid dictzip and its digest is
      reported for republication

## 5. Repairing the published en-en pair

- [ ] 5.1 Run the new check against all three published pairs and record the
      result (expected: en-en 210 unresolved / 201 case-only, ja-ja none,
      ru-ru none)
- [ ] 5.2 Answer the design's open question — does an installed dictionary pick up
      a changed optional-resource digest — and write the answer into
      `docs/REMOTE-CATALOG.md`
- [ ] 5.3 Rebuild the en-en bundle and dictionary with `bundle-audio`, re-run the
      check to zero unresolved, and confirm the 9 genuinely absent links are gone
- [ ] 5.4 Republish the en-en catalog entry with its new digests, or record why
      the republish is deferred

## 6. Documentation

- [ ] 6.1 Rewrite the `docs/KAIKKI-CONVERSION.md` "Known defects" section from a
      diagnosis of live defects into the guarantees now enforced, keeping the
      measured numbers that motivated them
- [ ] 6.2 Document `verify-bundle` and the failure semantics of `--reuse-bundle`
      in the options table and the audio section
- [ ] 6.3 Update `docs/TESTING.md` "Known gaps" to describe the repaired artifact
      and the check that guards it, instead of a published dictionary with dead
      audio links
