# Building dictionaries from kaikki.org (Wiktionary)

`scripts/kaikki-to-dsl.py` turns a pinned [kaikki.org](https://kaikki.org)
Wiktionary snapshot (wiktextract JSONL) into an offline **ABBYY Lingvo DSL**
**monolingual explanatory dictionary** for one language, packaged so it imports
into Aurelex through the normal folder import — no app or engine changes.

- Output: `<name>.dsl.dz` (dictzip) plus a sibling `<name>.dsl.files.zip`
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

For a sample that spreads across thousands of headwords (more representative of
schema variety) rather than the first N words, add `--sample-mode random`; the
selection is deterministic, so re-running yields the same sample.

Both sample modes read only a **bounded part** of the snapshot — `random` scans
a window of `N × 200` distinct headwords and keeps the `N` with the smallest
hash keys — so a sample of a few hundred words takes seconds rather than the
minutes a whole-snapshot scan needs. Two consequences: the sample is drawn from
a window, not from the entire file, and cross-references are limited to words
already emitted, so a sample may omit a `See also` link that a full build would
include. Neither matters for reviewing article shape, which is the point of
`--sample`.

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
progress line to stderr (`selecting headwords`, `sampling headwords`, `scanning
audio archive`, `rendering`, `bundling audio`) with a running count and elapsed
seconds. It costs
one counter comparison per record, so it does not slow the run down.

Copy `dist/kaikki-en.dsl.dz` and `dist/kaikki-en.dsl.files.zip` to the
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
| `--force-audio-index` | Rebuild the cached audio-archive name index even if it looks current. |
| `--audio-layout {zip,dir}` | Bundle audio as one archive (default) or a loose directory. |
| `--sample N` | Emit exactly N headwords (a word with several records is one headword); reads only a bounded part of the snapshot, so it is quick. |
| `--sample-mode {first,random}` | How `--sample` picks headwords: first N in file order, or a reproducible spread over thousands of headwords (default `first`). |
| `--preview` | Also write `<name>.preview.html`. |
| `--force-download` | Re-download cached files. |
| `--timeout SECONDS` | Network timeout (default 60). |

## Headwords, base forms, and inflections

Indexed headwords are **base forms only** by default. Entries that are inflected
forms of another word (a `form_of` sense) are not indexed; instead the base
word's grammatical forms (from `forms[]`) are rendered as an italic line directly
beneath the part of speech they belong to. A `See also:` line links
synonyms/related words, but only to words that are themselves indexed in the
output, so links never point at nothing.

`--include-inflections` additionally adds each base word's inflected forms as
extra headword lines on its card, so looking up `ran` returns the full `run`
article. **Trade-off:** in DSL every indexed word also appears in the suggestion
list — there is no hidden-alias concept — so enabling this adds inflected forms
to suggestions as well. Leave it off for clean suggestions; enable it when
direct lookup of inflected forms matters more.

## Article shape

A card is one headword; its records are its parts of speech (`run` is a verb and
a noun). Records that share a part of speech are **merged into one block**, so an
interleaved `noun, verb, noun` reads `noun, verb` instead of repeating the
heading. The visible article is part of speech → forms → senses. Pronunciation is
**hoisted to the top of the card** when the whole card has a single
transcription, so the common one-audio-per-word case prints it once instead of
repeating it; when parts of speech differ, each keeps its own under its own
heading. Audio is never duplicated: each file is printed once, under the first
part of speech that references it. An example sits in the DSL collapsible
optional zone (`[*]…[/*]`) **under the sense it illustrates**, not pooled at
the card, so expanding a gloss reveals the use of the word it defines rather than
an arbitrary sample. Cross-references stay in a single card-level optional zone
at the end. A lookup therefore shows definitions first and the reader expands
the rest on demand:

```
run
    [com]/ɹʌn/  [s]En-us-run.ogg[/s][/com]

    [p]verb[/p]
    [i]runs (3rd sg.), running (part., pres.), ran (past), run (part., past)[/i]
    [m1]• To move swiftly on foot.[/m]
    [*]
    [ex]I run every morning.[/ex]
    [/*]
    [m1]• To operate or manage.[/m]

    [p]noun[/p]
    [m1]• A flow, or the act of running.[/m]
    [m1]• [s]gd_tag_obsolete.svg[/s] (fig.) A period of performing.[/m]
    [*]
    [com]See also: [ref]runner[/ref][/com]
    [/*]
```

Every leaf sense begins with a **bullet**, so sibling definitions read as a list;
a group heading (a sense with sub-senses under it) is a category, not a sense,
and carries no bullet. A blank line separates consecutive parts of speech, so the
sections read as blocks rather than one list; it goes strictly between them, so
none precedes the first (nor follows a transcription hoisted above it).

The engine renders every `[*]…[/*]` as its own hidden `.dsl_opt` span and emits
a single `[+]` expander per article, which reveals all of that entry's zones at
once — so per-sense zones need no engine support, and each still shows its own
examples when expanded.

wiktextract splits a Wiktionary definition on `:` into a shared parent phrase
plus the specific part. Senses that share a parent become one group: the parent
is a `[m1]` heading and each specific part a `[m2]` sub-sense, which the engine
indents one level deeper — so sub-senses read as definitions rather than flat
comments, and a table of near-identical senses does not reprint the parent. A
verbatim repeat of a heading or sub-sense is dropped.

### Sense tags

Common tags are shown as **small inline icons** instead of parenthetical words, so
they stop breaking up the gloss text:

| Icon | Tag(s) it stands for |
| --- | --- |
| `gd_tag_countable.svg` | countable |
| `gd_tag_uncountable.svg` | uncountable |
| `gd_tag_initialism.svg` | initialism, abbreviation, acronym |
| `gd_tag_obsolete.svg` | obsolete, dated, archaic |

Countability is shown only when it is the marked case: Wiktionary tags most nouns
**both** countable and uncountable ("can be either"), and that unmarked case shows
neither icon — only a sense tagged one way or the other shows the icon.

An alternative/other-form sense (`swop` → *Alternative spelling of swap.*) gets no
icon: the gloss already states the relation, and the headword it names is rendered
as a **link**, so tapping *swap* opens the `swap` article. The link is only
emitted when the dictionary actually contains that headword.

An initialism/abbreviation/acronym sense shows the icon and drops the phrase the
icon already says, leaving the linked headword: `cat` → *[inv icon] catapult.*
rather than *"Abbreviation of catapult."*. A relation with no icon (a clipping,
an ellipsis) keeps its words as text.

At most one further register/context tag is kept per sense as abbreviated text
(`(fig.)`, `(derog.)`, `(regional)`, …). Tags that state an unremarkable case
(`transitive`, `intransitive`) or a relation the gloss already spells out
(`synonym`, `ellipsis`, `clipping`) are dropped. A sense can show an icon and a
text tag together. The icons are `[s]gd_tag_*.svg[/s]` picture references that the
engine renders as inline images; the files are vendored in
`scripts/assets/kaikki-tag-icons/` and bundled into **every** produced dictionary
(see Output layout), so they render with no network access. The app sizes them to
the surrounding text with a rule scoped to the `gd_tag_` filename, which leaves
other dictionaries' images untouched. The about card carries a legend mapping each
icon to its meaning.

A sense keeps at most **one** example, the shortest that qualifies, so the zone
is a crisp illustrative phrase rather than a wall of quotations. Example
sentences can run to a whole paragraph in Wiktionary; anything longer than 200
characters is cut at the last word boundary that fits and given an ellipsis. A
sense with no surviving example gets no zone at all rather than an empty one.

An example is kept only if it actually contains the headword: an exact token
match against the headword or one of its listed forms (which catches irregular
inflections such as `ran`/`children`), or a shared stem of at least three
characters with the headword (which pairs `swop` with `swopping` without a
stemmer). An example that never uses the word being defined proves nothing about
it, so it is dropped. Archaic quotations — Early Modern spellings such as `haue`
or `worke`, a long s `ſ`, Middle English inflections such as `wolde`/`seyde` — and
`Citations:…` bookkeeping, both the bare `Citations:work.` placeholder and the
`For quotations using this term, see Citations:work.` sentence that wraps it, are
dropped too, since the source records far more of them than modern usage and they
would otherwise crowd out the few current examples.

## Forms and pronunciations

The forms line shows only the **standard paradigm**, compactly labelled and set
in italics directly beneath its part of speech:
`runs (3rd sg.), running (part., pres.), ran (past), run (part., past)`.
Wiktionary records many more forms — archaic inflected tables (`runnest`,
`goest`, `goeth`), dialect and nonstandard variants (`yode`, `goed`,
`childer`) and raw inflection-table machinery — none of which belongs in a
learner-facing forms line.

The policy is a **blocklist**: a tagged form is kept unless it carries a
register/dialect tag (`archaic`, `obsolete`, `dialectal`, `nonstandard`,
`rare`, `slang`, …) or table machinery. Bookkeeping tags Wiktionary adds
(`canonical`, and the like) therefore do not silently drop an otherwise ordinary
form. What the tags mean, and how each is abbreviated, is **per-language** and
lives in the `LANG_PROFILES` table in the script rather than in the renderer:
adding a language is a data change, not a code change. `en`, `de` and `ja` are
populated as examples, and any language without a profile falls back to a
permissive default and warns.

Pronunciation is likewise driven by the profile: each `sounds[]` field that
carries a transcription (for English, `ipa` then `enpr`) is shown once, as a bare
`/ɹʌn/`, with the word's audio links on the **same line** — the transcription and
its playback controls together. The line is always a transcription, so the
common IPA value is printed without an `IPA:` label; a second notation (`enPR`) is
labelled, since it is not IPA. Where the whole card shares a single
transcription it is printed once at the top; where parts of speech differ, each
is printed under its own part of speech. A recording whose part of speech has no
transcription still gets its own line. Each audio file appears exactly once per
card regardless, so a word whose parts of speech share a recording does not
repeat it.

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

Downloads identify the tool with a descriptive User-Agent and space out requests
to Wikimedia; a rate limit (HTTP 429) is retried with backoff rather than being
treated as a missing file.

### Audio archive index

Resolving audio needs to know which recordings the archive holds, which means
streaming all ~940k members once (about 100 s on the real archive). That name set
is cached next to the archive as `<archive>.keys.txt` (~25 MB) and validated
against the archive's path, size, modification time and `sha256` sidecar, so it
is rebuilt only when the archive actually changes. The first run with audio pays
the scan; later runs reuse the index. `--force-audio-index` rebuilds it anyway.

## Output layout and storage

```
dist/
  kaikki-en.dsl.dz          # the dictionary (dictzip)
  kaikki-en.dsl.files.zip   # sense-marker icons + any audio (default)
  kaikki-en.preview.html    # only with --preview
```

The resource bundle always holds the sense-marker icons (see Article shape), so it
is written even with `--no-audio`; audio is added to the same archive when
enabled. With `--audio-layout dir` both go into a `kaikki-en.dsl.files/`
directory instead. The bundle is named after the dictionary **without** the
dictzip suffix — `<name>.dsl.files.zip`, not `<name>.dsl.dz.files.zip` — because
that is the name the reader looks for first (it strips `.dsl.dz` to form the base
name); the `.dsl.dz.files.zip` spelling is only its fallback.

A full English build with audio is multi-GB on disk and thousands of small
files inside the archive; the phone's import stages the whole folder. Use
`--sample` and `--audio-per-word` to keep test builds small.

## Reproducibility and provenance

- Same snapshot + options ⇒ byte-identical output (dictionary and resource
  archive; the vendored icons are fixed bytes in a sorted archive).
- The snapshot dump date is embedded in the `#NAME` metadata block and in an
  **About this dictionary** card inside the file, which also carries the
  sense-icon legend.

## Licensing

The output is a **derivative work of Wiktionary** (via kaikki.org / wiktextract)
and is licensed **CC BY-SA 4.0** (share-alike). The tool always embeds the
attribution, license, and the wiktextract citation in the output. If you
redistribute a generated dictionary you must keep that attribution and share
alike. The Aurelex repository itself ships no dictionary data.

The bundled sense-marker icons are **Material Symbols** (Copyright Google LLC),
licensed under the **Apache License 2.0**; `scripts/assets/kaikki-tag-icons/`
holds their provenance, and the about card credits them.

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
inflections flag, DSL escaping, IPA rendering and pronunciation hoisting, sense
grouping (a shared parent rendered once with one abbreviated tag per child,
sub-senses indented as `[m2]` definitions, repeated and noise/structural tags
dropped), the sense-tag policy (each mapped tag rendered as its icon, the
countable-only/uncountable-only rule, icons coexisting with a register tag, no
marker for an alternative-form sense), the sense bullet (leaf senses bulleted, a
group heading not), the alternative-form link (the related headword linked when
the dictionary contains it, plain otherwise, never self-linked), the dropping of
the wording an iconised relation already carries and the unlabelled primary
transcription, transcription hoisting for a one-record card, the language filter
(a sample rejecting a record whose raw line carries a nested source-language
marker), same-POS merging
and card-wide audio de-duplication, the per-sense
example cap and headword verification (plus dropping archaic and `Citations:`
examples), the form policy
(paradigms kept and shown beneath their part of speech, register/dialect variants
and table machinery dropped), one optional zone per sense holding that sense's
own examples, and a separate card-level zone for the cross-references,
the icon bundle (present in the zip and the directory layout, with audio
disabled, and advertised in the about card), profile-driven form labels,
non-ASCII URL encoding for Wikimedia audio downloads, audio bundling and name
normalisation (zip and directory), missing-audio omission and slot refill, the
Wikimedia download fallback and its cache, the progress indicator, preview tag
balance and icon rendering, determinism, the bounded sample selection (both
modes, and that a small file is not over-strided), the sample headword count,
and the no-headwords report. No test touches the network: every audio build
either passes `--no-audio-download` or injects a stub downloader.
