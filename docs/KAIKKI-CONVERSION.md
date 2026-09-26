# Building dictionaries from kaikki.org (Wiktionary)

`scripts/kaikki-to-dsl.py` turns a pinned [kaikki.org](https://kaikki.org)
Wiktionary snapshot (wiktextract JSONL) into an offline **ABBYY Lingvo DSL**
**monolingual explanatory dictionary** for one language, packaged so it imports
into Aurelex through the normal folder import — no app or engine changes.

- Output: `<name>.dsl.dz` (dictzip) plus a sibling `<name>.dsl.dz.files.zip`
  (or `.files/` directory) holding the referenced pronunciation audio.
- The tool runs on a desktop/laptop, not on the phone.
- DSL is the only supported import format that carries audio; StarDict is
  text-only in this engine.
- The dictionary's headwords and definitions are in the same language
  (`--source-lang`). Cross-language translation data is not used; see
  [Why monolingual only](#why-monolingual-only).

## Requirements

- Python 3.9+ (standard library only; no third-party packages).

## Quick start (small, reviewable)

Build a 25-headword sample for English from a small real kaikki extract and
render a preview to eyeball the article shape:

```powershell
python scripts\kaikki-to-dsl.py `
  --source-lang en `
  --dump-date 2026-09-20 --skip-date-check `
  --jsonl-url https://kaikki.org/dictionary/downloads/simple/simple-extract.jsonl.gz `
  --out-dir dist --sample 25 --preview --no-audio
```

Then open `dist/kaikki-en.preview.html`.

For a sample that spreads across the whole snapshot (more representative of
schema variety) rather than the first N words, add `--sample-mode random`; the
selection is deterministic, so re-running yields the same sample.

A tiny committed sample (built from the synthetic test fixture, not real data)
lives in `examples/kaikki-sample/` — open its `kaikki-sample-en.preview.html` to
see the article shape without running anything.

## Full run

```powershell
python scripts\kaikki-to-dsl.py --source-lang en --dump-date 2026-09-02 `
  --out-dir dist
```

The first run downloads the raw wiktextract JSONL (about 2.7 GB gzipped) and,
unless `--no-audio` is set, the Wiktionary audio archive (about 20 GB). Both are
cached under `--cache-dir` (default `~/.cache/aurelex-kaikki/<dump-date>/`) with
`.sha256` sidecars; later runs reuse and verify the cache.

Because a full run reads the snapshot several times, the tool prints a coarse
progress line to stderr (`selecting headwords`, `scanning audio archive`,
`rendering`, `bundling audio`) with a running count and elapsed seconds. It costs
one counter comparison per record, so it does not slow the run down.

Copy `dist/kaikki-en.dsl.dz` and `dist/kaikki-en.dsl.dz.files.zip` to the
phone (same folder) and add that folder in Aurelex.

## Options

| Option | Meaning |
| --- | --- |
| `--source-lang CODE` | Language of the dictionary (required), e.g. `en`. |
| `--dump-date YYYY-MM-DD` | Pinned snapshot; required unless `--jsonl` is given. Verified against kaikki.org unless `--skip-date-check`. |
| `--jsonl PATH` | Use a local JSONL/`.jsonl.gz` instead of downloading. |
| `--jsonl-url URL` / `--audio-url URL` | Override the source URLs (e.g. a small per-language extract). |
| `--audio-tar PATH` | Use a local audio tar instead of downloading. |
| `--cache-dir DIR` | Download cache (default `~/.cache/aurelex-kaikki`). |
| `--out-dir DIR` | Output directory (default `dist`). |
| `--name NAME` | Output base name (default `kaikki-<source>`). |
| `--include-inflections` | Also index inflected forms (see below). |
| `--audio-per-word N` | Max audio files per headword (default 3; `0` disables). |
| `--no-audio` | No audio and no audio download. |
| `--audio-lang TAG` | Prefer audio whose tags match this language/accent (e.g. `US`). |
| `--no-audio-download` | Do not fetch audio that the archive lacks from Wikimedia (archive only). |
| `--audio-layout {zip,dir}` | Bundle audio as one archive (default) or a loose directory. |
| `--sample N` | Emit exactly N headwords (a word with several records is one headword); good for reviewing output first. |
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

## Forms and pronunciations

The `Forms:` line shows only the **standard paradigm**, compactly labelled:
`runs (3rd sg.), running (part., pres.), ran (past), run (part., past)`.
Wiktionary records many more forms — archaic inflected tables (`runnest`,
`goest`, `goeth`), dialect and nonstandard variants (`yode`, `goed`,
`childer`) and raw inflection-table machinery — none of which belongs in a
learner-facing forms line.

What counts as a standard form, and how each tag is abbreviated, is
**per-language** and lives in the `LANG_PROFILES` table in the script rather
than in the renderer: adding a language is a data change, not a code change.
`en`, `de` and `ja` are populated as examples. German forms keep case
(`dative`, `genitive`), Japanese keeps its own tag vocabulary and has no IPA,
and any language without a profile falls back to a permissive default and warns.

Pronunciation is likewise driven by the profile: each `sounds[]` field that
carries a transcription (for English, `ipa` then `enpr`) is shown once, as
`IPA: /ɹʌn/`, with audio links alongside.

## Why monolingual only

The tool deliberately does not build translation dictionaries, because
kaikki.org's cross-language data is too sparse and too loosely aligned to make
one that is honest. Measured against the 2026-09-02 snapshot:

- only **6.7%** of English lexical records carry any Russian translation, and
  **3.9%** carry one that lines up with a rendered sense;
- only **English** records carry translations at all (Russian, German and
  Japanese records carry none), so `en → X` is the only usable direction and
  `ru → en` cannot be built;
- Wiktionary's definitions and its translation table use **two different sense
  inventories at different granularity** — `monkey` has 20 English senses but a
  Russian equivalent for 1, and `mirror` has 5 senses and 0 — so any
  sense-to-sense alignment is guesswork;
- example sentences are almost never translated (3 of 271 sampled), and
  Wiktionary has no collocation pairs, which is where a bilingual dictionary
  earns its keep.

A faithful translation dictionary would need alignment or AI-assisted work
over these sources, which is a separate project. Until then the tool builds
what the data supports well: complete, well-formed monolingual articles.

## Audio

Audio comes from the bulk archive, so there are no per-file network requests to
Wikimedia. A recording is referenced by its **canonical MediaWiki file name**,
taken from the sound's URL (`ogg_url`/`mp3_url`) rather than the raw `audio`
argument, which is unreliable (it may differ in case, use spaces instead of
underscores, or contain HTML entities). Matching folds case, spaces/underscores,
and percent-encoding, and accepts either the stored original or its transcoded
form, so an `X.wav` reference resolves to the archived `X.wav.ogg`/`X.wav.mp3`.

The archive is only a **subset** of Wikimedia Commons, so a referenced recording
is sometimes absent. The tool then falls back to downloading it from its
Wikimedia URL into `<cache-dir>/<dump-date>/audio-cache/` (with a `.sha256`
sidecar, reused on later runs). Records the archive lacks are resolved before
any article is rendered, which means:

- a recording that cannot be resolved is **logged and left out** — the article
  never carries a link to a file that was not bundled;
- an unresolved recording does **not** consume one of the per-word slots, so
  `--audio-per-word 3` still yields three playable files when the first few
  candidates are missing.

Set `--no-audio-download` to skip the Wikimedia fallback and use the archive
only. Bundling is bounded to `--audio-per-word` (default 3), de-duplicated, and
prefers the source language/accent (`--audio-lang`).

## Output layout and storage

```
dist/
  kaikki-en.dsl.dz              # the dictionary (dictzip)
  kaikki-en.dsl.dz.files.zip    # referenced audio (default)
  kaikki-en.preview.html        # only with --preview
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

The tests build from `scripts/tests/fixtures/sample-en.jsonl`,
`scripts/tests/fixtures/kaikki-edge.jsonl` (which mirrors the real snapshot's
looser shapes: audio names that differ in case/underscores/percent-encoding from
the archive, and words that carry several records), and
`scripts/tests/fixtures/kaikki-audio-limit.jsonl` (a word whose recordings are
mostly absent from the archive). They cover the base-form policy, the
inflections flag, DSL escaping, IPA rendering, profile-driven form filtering and
labels, audio bundling and name normalisation (zip and directory), missing-audio
omission and slot refill, the Wikimedia download fallback and its cache, the
progress indicator, preview tag balance, determinism, the sample headword count,
and the no-headwords report. No test touches the network: every audio build
either passes `--no-audio-download` or injects a stub downloader.
