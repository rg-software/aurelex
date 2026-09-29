## Why

Rebuilding a dictionary to change only its text (for example after a filtering
change) re-runs the whole resource-bundle step — streaming the audio archive and
writing tens of thousands of entries — even though the recordings a dictionary
references only ever shrink when cards are pruned or merged. Reusing the bundle
already beside the dictionary turns a text-only rebuild into a render-only run.

## What Changes

- Add a `--reuse-bundle` option to the build: render `<name>.dsl.dz` and leave
  the resource bundle already beside it untouched.
- Verify the reused bundle actually contains every resource the new dictionary
  references, and report any that are missing (or an absent bundle), so reuse
  cannot silently leave a broken reference.

## Capabilities

### New Capabilities

<!-- none -->

### Modified Capabilities

- `dictionary-conversion`: the packaging requirement gains an option to reuse an
  existing resource bundle instead of rebuilding it, with a verification step.

## Impact

- `scripts/kaikki-to-dsl.py`: a new `--reuse-bundle` flag, a helper to read an
  existing bundle's entry names, and a verification/report path in `build()`.
- `scripts/tests/test_kaikki_to_dsl.py`: tests for reuse with a complete bundle,
  a bundle missing a referenced file, and an absent bundle.
