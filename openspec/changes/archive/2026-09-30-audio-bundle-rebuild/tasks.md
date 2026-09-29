## 1. Reading the rendered dictionary

- [x] 1.1 Add `read_dictzip(path)` returning the dictionary text (gzip-decompress, drop a leading BOM), the inverse of the existing `make_dictzip(encode_dsl(...))` write
- [x] 1.2 Add a helper that returns the `[s]…[/s]` references of a dictionary in order, un-escaping each captured name (inverse of `escape_dsl`), plus a helper that substitutes a name in that text

## 2. Rebuild routine

- [x] 2.1 Add `bundle_audio(args)`: read the dictionary, collect its references, sanitise each name with `_safe_audio_filename`, and rebuild the resource bundle beside it
- [x] 2.2 Locate each sanitised name first in the audio cache (`download_dir`) and then in the archive via `_audio_name_variants`; for an unresolved name also try the variants of the name with a trailing `-<8 hex>` digest stripped
- [x] 2.3 Write the bundle as `<base>.dsl.files.zip`, or `<base>.dsl.files/` for the directory layout, always including the sense-marker icons, reusing `write_audio_zip` and the same directory copy the build uses
- [x] 2.4 Rewrite the `.dsl.dz` only when a sanitised name differs from its reference, so a dictionary that needs no change is left byte-for-byte as it was
- [x] 2.5 Report the recordings found and, as a warning, those found nowhere, and exit 0

## 3. CLI

- [x] 3.1 Add a `bundle_audio_parser` and a `bundle-audio` mode word in `main()`, taking the `.dsl.dz` as a positional argument
- [x] 3.2 Expose `--audio-tar`, the snapshot location options (`--dump-date`, `--jsonl`, `--cache-dir`), `--audio-url`, `--force-download`, `--timeout` and `--audio-layout`; do not require `--source-lang` or `--audio-per-word`, which the dictionary has already applied
- [x] 3.3 Resolve the cache directory and the archive without checking the dump date against kaikki.org and without downloading or reading the JSONL, so a local archive makes the mode offline

## 4. Tests

- [x] 4.1 References are extracted from a dictionary in order, including a name carrying escaped DSL characters
- [x] 4.2 A referenced recording in the archive is extracted, one only in the cache is copied, and one in neither is warned about and omitted
- [x] 4.3 A reference naming a recording with a filesystem-unsafe character is bundled under the sanitised name and the dictionary is rewritten to match
- [x] 4.4 A dictionary whose references are already safe is not modified, and rebuilding twice produces the same bundle
- [x] 4.5 Both layouts write the bundle beside the dictionary with the expected name, and the icons are present
- [x] 4.6 With a local archive the rebuild makes no network request
- [x] 4.7 End to end: a build whose bundle is removed is recovered by rebuilding from its `.dsl.dz`, and the result carries the same audio and references a build would have written

## 5. Documentation

- [x] 5.1 Add a "recovering a failed bundle" note to `docs/KAIKKI-CONVERSION.md` with the `bundle-audio` command, and mention the mode in the build parser's help epilog

## 6. Validation

- [x] 6.1 Run `python -m unittest scripts.tests.test_kaikki_to_dsl` and confirm it is green
- [x] 6.2 Run `openspec validate audio-bundle-rebuild --strict` and resolve any findings

## 7. Bundle writer

- [x] 7.1 Write the bundle from a name -> source map so a cache hit is read once instead of copied to a staging directory; store entries rather than deflate, stream each, give the writing progress a total, and report the build's cache hits as a running count plus a summary total
