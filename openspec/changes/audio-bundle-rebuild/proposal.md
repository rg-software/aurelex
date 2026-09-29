## Why

A dictionary build writes the rendered `<name>.dsl.dz` before it assembles the
`<name>.dsl.files.zip` resource bundle. If bundling fails — a filesystem that
refuses a recording's name, a killed process, a disk error — the rendered
dictionary survives but the bundle is absent, and re-running the build pays the
full render again (about an hour for a full kaikki snapshot) to recover a step
that never needed the records. The dictionary itself already names every
recording it wants, so the bundle can be rebuilt from it alone.

## What Changes

- Add a `bundle-audio` mode that reads an existing `.dsl.dz`, takes the audio it
  references from the `[s]…[/s]` links in that dictionary, and writes the
  resource bundle (`<base>.dsl.files.zip`, or the `.files/` directory with
  `--audio-layout dir`) beside it, with no re-render and no snapshot read.
- Locate each referenced recording first in the local audio cache, then in the
  audio archive tar; a recording found nowhere is reported and left out.
- Apply the same filename sanitisation a build applies, and rewrite the
  dictionary's references only when one of them changes, so the article and the
  bundled file always agree.
- Reuse the existing bundling primitives (`_audio_name_variants`,
  `extract_audio`, `write_audio_zip`) so the rebuilt bundle is byte-for-byte what
  a successful build would have produced.

## Capabilities

### New Capabilities

- `audio-bundle-rebuild`: rebuild a rendered dictionary's resource bundle from
  the dictionary file itself, without re-rendering, so an interrupted build is
  recovered cheaply and the resulting bundle matches a normal build's.

### Modified Capabilities

<!-- none: the build and prefetch behavior is unchanged -->

## Impact

- `scripts/kaikki-to-dsl.py`: new `bundle-audio` mode word, parser, a dictzip
  reader, and the rebuild routine; the existing build/prefetch paths are
  untouched.
- `scripts/tests/test_kaikki_to_dsl.py`: tests covering reference extraction,
  cache and archive resolution, sanitisation-and-rewrite, and idempotence.
- `docs/KAIKKI-CONVERSION.md`: a short "recovering a failed bundle" note.
