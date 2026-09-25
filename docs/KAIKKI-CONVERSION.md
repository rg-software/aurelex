# Building dictionaries from kaikki.org (Wiktionary)

`scripts/kaikki-to-dsl.py` turns a pinned [kaikki.org](https://kaikki.org)
Wiktionary snapshot (wiktextract JSONL) into an offline **ABBYY Lingvo DSL**
dictionary for a chosen language pair, packaged so it imports into Aurelex
through the normal folder import — no app or engine changes.

- Output: `<name>.dsl.dz` (dictzip) plus a sibling `<name>.dsl.dz.files.zip`
  (or `.files/` directory) holding the referenced pronunciation audio.
- The tool runs on a desktop/laptop, not on the phone.
- DSL is the only supported import format that carries audio; StarDict is
  text-only in this engine.

## Requirements

- Python 3.9+ (standard library only; no third-party packages).

## Quick start (small, reviewable)

Build a 25-headword sample for English from a small real kaikki extract and
render a preview to eyeball the article shape:

```powershell
python scripts\kaikki-to-dsl.py `
  --source-lang en --target-lang en `
  --dump-date 2026-09-20 --skip-date-check `
  --jsonl-url https://kaikki.org/dictionary/downloads/simple/simple-extract.jsonl.gz `
  --out-dir dist --sample 25 --preview --no-audio
```

Then open `dist/kaikki-en-en.preview.html`.

For a sample that spreads across the whole snapshot (more representative of
schema variety) rather than the first N words, add `--sample-mode random`; the
selection is deterministic, so re-running yields the same sample.

A tiny committed sample (built from the synthetic test fixture, not real data)
lives in `examples/kaikki-sample/` — open its `kaikki-sample-en.preview.html` to
see the article shape without running anything.

## Full run

```powershell
python scripts\kaikki-to-dsl.py --source-lang en --target-lang ru --dump-date 2026-09-02 `
  --out-dir dist
```

The first run downloads the raw wiktextract JSONL (about 2.7 GB gzipped) and,
unless `--no-audio` is set, the Wiktionary audio archive (about 20 GB). Both are
cached under `--cache-dir` (default `~/.cache/aurelex-kaikki/<dump-date>/`) with
`.sha256` sidecars; later runs reuse and verify the cache.

Copy `dist/kaikki-en-ru.dsl.dz` and `dist/kaikki-en-ru.dsl.dz.files.zip` to the
phone (same folder) and add that folder in Aurelex.

## Options

| Option | Meaning |
| --- | --- |
| `--source-lang CODE` | Language of the **indexed headwords** (required), e.g. `en`. |
| `--target-lang CODE` | Language of the glosses/translations (defaults to source ⇒ monolingual). |
| `--dump-date YYYY-MM-DD` | Pinned snapshot; required unless `--jsonl` is given. Verified against kaikki.org unless `--skip-date-check`. |
| `--jsonl PATH` | Use a local JSONL/`.jsonl.gz` instead of downloading. |
| `--jsonl-url URL` / `--audio-url URL` | Override the source URLs (e.g. a small per-language extract). |
| `--audio-tar PATH` | Use a local audio tar instead of downloading. |
| `--cache-dir DIR` | Download cache (default `~/.cache/aurelex-kaikki`). |
| `--out-dir DIR` | Output directory (default `dist`). |
| `--name NAME` | Output base name (default `kaikki-<source>-<target>`). |
| `--include-inflections` | Also index inflected forms (see below). |
| `--audio-per-word N` | Max audio files per headword (default 3; `0` disables). |
| `--no-audio` | No audio and no audio download. |
| `--audio-lang TAG` | Prefer audio whose tags match this language/accent (e.g. `US`). |
| `--audio-layout {zip,dir}` | Bundle audio as one archive (default) or a loose directory. |
| `--sample N` | Emit at most N headwords (good for reviewing output first). |
| `--sample-mode {first,random}` | How `--sample` picks headwords: first N in file order, or a reproducible random spread across the snapshot (default `first`). |
| `--preview` | Also write `<name>.preview.html`. |
| `--force-download` | Re-download cached files. |
| `--timeout SECONDS` | Network timeout (default 60). |

## Headwords, base forms, and inflections

Indexed headwords are **base forms only** by default. Entries that are inflected
forms of another word (a `form_of` sense) are not indexed; instead the base
word's grammatical forms (from `forms[]`) are rendered as a `Forms:` line inside
its article. A `See also:` line links synonyms/related words, but only to words
that are themselves indexed in the output, so links never point at nothing.

`--include-inflections` additionally adds each base word's inflected forms as
extra headword lines on its card, so looking up `ran` returns the full `run`
article. **Trade-off:** in DSL every indexed word also appears in the suggestion
list — there is no hidden-alias concept — so enabling this adds inflected forms
to suggestions as well. Leave it off for clean suggestions; enable it when
direct lookup of inflected forms matters more.

## Audio

Audio comes from the bulk archive and is matched by filename
(`sounds[].audio`), so no per-file network requests to Wikimedia. Bundling is
bounded to `--audio-per-word` (default 3), de-duplicated, and prefers the source
language/accent (`--audio-lang`). Audio that cannot be resolved is omitted and
counted in the final report; the article is still produced.

## Output layout and storage

```
dist/
  kaikki-en-ru.dsl.dz              # the dictionary (dictzip)
  kaikki-en-ru.dsl.dz.files.zip    # referenced audio (default)
  kaikki-en-ru.preview.html        # only with --preview
```

A full English build with audio is multi-GB on disk and thousands of small
files inside the archive; the phone's import stages the whole folder. Use
`--sample` and `--audio-per-word` to keep test builds small.

## Reproducibility and provenance

- Same snapshot + options ⇒ byte-identical output (dictionary and audio archive).
- The snapshot dump date is embedded in the `#NAME` metadata block and in an
  **About this dictionary** card inside the file.

## Licensing

The output is a **derivative work of Wiktionary** (via kaikki.org / wiktextract)
and is licensed **CC BY-SA 4.0** (share-alike). The tool always embeds the
attribution, license, and the wiktextract citation in the output. If you
redistribute a generated dictionary you must keep that attribution and share
alike. The Aurelex repository itself ships no dictionary data.

## Tests

```powershell
python -m unittest discover -s scripts/tests
```

The tests build from `scripts/tests/fixtures/sample-en.jsonl` and cover the
base-form policy, the inflections flag, DSL escaping, audio bundling (zip and
directory), determinism, preview output, and the unsupported-pair report.
