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

Because a full run reads the snapshot several times, the tool prints a coarse
progress line to stderr (`selecting headwords`, `scanning audio archive`,
`rendering`, `bundling audio`) with a running count and elapsed seconds. It costs
one counter comparison per record, so it does not slow the run down.

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
| `--translation` | Build a learner's translation dictionary (see below); needs a distinct `--target-lang`. |
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

## Translation dictionaries

By default a pair such as `en/ru` produces an English article with Russian
words appended where the source provides them — an explanatory dictionary with
sporadic translations. `--translation` instead builds a dictionary for a
**Russian speaker learning English**, where the target words are the answer:

```
pub
    [p]сущ.[/p]
    [m1]A public house where beverages… may be bought and consumed…[/m1]
        бар  пивная  кабак  паб  трактир  корчма  таверна  пивнушка
    [*]
    [ex]Reg liked a chat about old times and we used to go and have a chinwag in the pub.[/ex]
    [com]Forms: pubs (pl.)[/com]
    [com]/pʌb/[/com]
    [/opt]
```

How it is built:

- **Senses come from the translation table**, grouped by its own `sense` key and
  merged when two keys yield the same equivalents, so nothing is lost and no
  sense is repeated. A heading is a matching English gloss, else the key itself;
  a MediaWiki placeholder key (for example `translations`) never becomes a
  heading.
- **The record is dropped entirely** when it has no target-language translation,
  so the output contains only entries that are actually bilingual.
- **Source-language attributes are kept** — transcription, forms, examples —
  because a learner needs to pronounce and inflect the word. They are placed in
  the DSL collapsible optional zone (`[*]…[/opt]`), so the equivalents are what
  a lookup user sees first.
- **Target-language attributes are dropped**: transliterations (`бегать` needs no
  `bégatʹ`) and grammar tags (`feminine`, `imperfective`), since a native speaker
  reads their own script and knows their own grammar.
- **Register tags on the source** are likewise excluded from the forms line, so
  a learner sees `ran (past)` and not `rannest (archaic, 2nd sg.)`.

Because translation tables exist only in the English Wiktionary entries, this
mode works for **`en → X`** only; there is no `ru → en` data to build from.

### Adding a source language

Everything language-specific lives in `LANG_PROFILES` in the script, not in the
renderer: the standard-form tag vocabulary, the tags that mean "raw inflection
table", which `sounds[]` fields carry a transcription, and the compact tag
labels. `en`, `de` and `ja` are present; `ja` illustrates why a global tag
whitelist would be wrong (German forms keep case, Japanese keeps its own tag
vocabulary and has no IPA). An unknown language falls back to a permissive
profile and warns, rather than emitting an empty article.

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

The tests build from `scripts/tests/fixtures/sample-en.jsonl`,
`scripts/tests/fixtures/kaikki-edge.jsonl` (which mirrors the real snapshot's
looser shapes: translation keys that are short paraphrases of a gloss, audio
names that differ in case/underscores/percent-encoding from the archive, and
words that carry several records), `scripts/tests/fixtures/kaikki-audio-limit.jsonl`
(a word whose recordings are mostly absent from the archive), and
`scripts/tests/fixtures/kaikki-translation.jsonl` (translation-mode article
shape). They cover the base-form policy, the inflections flag, DSL escaping,
translation sense matching, IPA rendering, audio bundling and name
normalisation (zip and directory), missing-audio omission and slot refill, the
Wikimedia download fallback and its cache, the progress indicator, the
translation article (sense grouping, target-attribute stripping, source
forms/pronunciation, the collapsible zone, dropping untranslated records), the
language profiles (per-language form tags and labels, unknown-language
fallback), determinism, preview output, the sample headword count, and the
unsupported-pair report.
