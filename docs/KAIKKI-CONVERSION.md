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
| `--skip-date-check` | Do not verify the pinned dump date against kaikki.org. Needed for any date kaikki has since rotated away. |
| `--cache-dir DIR` | Download cache (default `~/.cache/aurelex-kaikki`). |
| `--out-dir DIR` | Output directory (default `dist`). |
| `--name NAME` | Output base name (default `kaikki-<source>`); names the output files. |
| `--title TITLE` | Display name (default `--name`); used for `#NAME`, the `About …` headword and the description. |
| `--include-inflections` | Also index inflected forms (see below). |
| `--audio-per-word N` | Max audio files per headword (default 3; `0` disables). |
| `--no-audio` | No audio and no audio download. |
| `--audio-lang TAG` | Prefer audio whose tags match this language/accent (e.g. `US`). |
| `--no-audio-download` | Do not fetch audio that the archive lacks from Wikimedia (archive only). |
| `--force-audio-index` | Rebuild the cached audio-archive name index even if it looks current. |
| `--audio-layout {zip,dir}` | Bundle audio as one archive (default) or a loose directory. |
| `--reuse-bundle` | Render the dictionary only and reuse the resource bundle already beside it instead of rebuilding it; the existing bundle is checked to cover every resource the dictionary references. Use it when a re-render changes only the text — it skips the audio-archive pass entirely. Fails rather than shipping a dictionary whose bundle is missing a referenced file. |
| `--sample N` | Emit exactly N headwords (a word with several records is one headword); reads only a bounded part of the snapshot, so it is quick. |
| `--sample-mode {first,random}` | How `--sample` picks headwords: first N in file order, or a reproducible spread over thousands of headwords (default `first`). |
| `--preview` | Also write `<name>.preview.html`. |
| `--force-download` | Re-download cached files. |
| `--timeout SECONDS` | Network timeout (default 60). |

The table above is the **build** parser. The tool has three more modes, each
with flags of its own that this table does not accept:

| Mode | Its own flags | Covered in |
| --- | --- | --- |
| `prefetch-audio` | `--list`, `--limit N`, `--spacing`, `--retries`, `--max-backoff`, `--manifest`, `--split N` | [Filling the audio cache separately](#filling-the-audio-cache-separately) |
| `fetch-list FILE` | `--into DIR` (required), `--dead PATH`, `--force-download`, `--limit N`, `--spacing`, `--retries`, `--max-backoff` | [Splitting the job across machines](#splitting-the-job-across-machines) |
| `bundle-audio` | — (reuses the build's audio options) | [Recovering a failed bundle](#recovering-a-failed-bundle) |

`prefetch-audio` also accepts the build's *selection* options — `--source-lang`,
`--dump-date`, `--jsonl`, `--audio-tar`, `--cache-dir`, `--audio-per-word`,
`--audio-lang`, `--sample`, `--sample-mode` — because they decide which articles,
and so which recordings, are wanted. Give it the **same** values as the build: a
mismatched `--audio-per-word` fetches a different set of files than the build
will reference.

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

and a headword whose senses group (the `Employment` / `Effort` / `Product` outline
of `work`):

```
work
    [p]noun[/p]
    [m1]1. Employment.[/m]
    [m2]• Labour, occupation, job.[/m]
    [m2]• The place where one is employed.[/m]
    [m1]2. Effort.[/m]
    [m2]• Effort expended on a particular task.[/m]
    [m1]3. Product; the result of effort.[/m]
    [m2]• A literary, artistic, or intellectual production.[/m]
    [m1]• [s]gd_tag_obsolete.svg[/s] A factory; a works.[/m]
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

A heading that carries sub-senses is **numbered** (`1. `, `2. ` …), counting
within its part of speech and restarting for the next one, so the top-level
sections of a long article read as an outline. A sense with no sub-senses is an
ordinary sense and is not numbered, so a card with no groups is unchanged.

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
treated as a missing file, and a `Retry-After` on the response overrides the
computed backoff (capped, so a mistaken header cannot park a run for hours).

### Filling the audio cache separately

On a long dictionary run Wikimedia will rate-limit partway through, and because an
unresolved recording is deliberately left out of the article, the run finishes
with gaps. Those gaps are cheap to close later: `prefetch-audio` enumerates the
recordings the articles reference but the archive lacks, and downloads them into
the same cache the build reads. Everything it writes is verified by a `.sha256`
sidecar, so a build that follows finds the files without making a single request.

```bash
# see the size of the job, spending no rate limit
python scripts/kaikki-to-dsl.py prefetch-audio \
    --source-lang en --dump-date 2026-09-02 --list

# fetch what fits in this rate-limit window
python scripts/kaikki-to-dsl.py prefetch-audio \
    --source-lang en --dump-date 2026-09-02 --limit 500

# repeat until it reports the cache is complete, then build as usual
python scripts/kaikki-to-dsl.py --source-lang en --dump-date 2026-09-02
```

The run ends with a verdict rather than a bare count, because "should I run this
again?" is the question that matters after a rate limit:

```
fetched 500 of 500 attempted file(s) this run
  12 permanently gone (12 HTTP 404) -- recorded in audio-dead.tsv, never requested again
  3 rate-limited, blocked or interrupted -- re-run later
  stopped at --limit 500; more files remain -- re-run to continue
```

against a finished cache, which costs one re-read of the snapshot and no
requests at all:

```
fetched 0 of 0 attempted file(s) this run
  done: every recording that exists is now cached -- run the build
```

Notes:

- It is **resumable by construction**: a file already in the cache is skipped, so
  repeating the command continues where the last one stopped, and a completed
  pass is a no-op.
- **Each run tells you whether you are finished, and the exit status agrees.**
  `0` means every recording that exists is now cached — build. `1` means a rate
  limit or `--limit` cut the run short, and there is more to come back to. The
  failures inside a run are reported in two classes, because they want opposite
  things from you:
  - **Permanently gone** (HTTP 404 and similar). A deleted file cannot come back,
    so it is appended to `<cache>/<dump-date>/audio-dead.tsv` with the reason and
    never requested again. It does *not* count as outstanding work — otherwise a
    cache that can never grow past a 404 would report itself unfinished forever.
  - **Rate-limited, blocked or interrupted.** A refusal or a dropped connection is
    a statement about the moment, not the file, so it is left for the next run
    and is *not* written to the dead list.
- **A failed recording is replaced, not left as a gap.** The plan is built
  assuming every file it considered will land, so a failure invalidates it; the
  headword is replanned with the hole known and the next candidate is fetched
  instead — in the same run, whichever class the failure fell into. That is what
  the build would do on its own, and doing it here keeps the article whole.
- **Fetching is interleaved with the scan.** A headword's decision needs only its
  own records, which are contiguous in the snapshot, so the first files land
  within seconds and `--limit N` stops before the rest of the snapshot is read at
  all. There is no "scan the whole dictionary, then download" phase.
- `--limit N` bounds **attempts, not successes**. That is the point: a run where
  files are failing is the run most at risk of a harder rate limit, so it must
  not sail on through the rest of the dictionary. The summary line reports both
  counts — `fetched 480 of 500 attempted file(s) this run` — so you can tell a
  window you spent on trouble from one you spent on volume.
- The wishlist is exactly what the build will reference, not a superset — a
  candidate past the `--audio-per-word` cap is not fetched. `--list` is the way
  to size the job: it downloads nothing, so it reads everything and writes a
  complete manifest (`<cache>/<dump-date>/audio-missing.tsv`, one
  `name<TAB>url` per line, in the order the scan found them). A run stopped by
  `--limit` writes only what it reached, which is a partial record; `--list` is
  always the complete one.
- Give it the **same** `--source-lang`, `--audio-per-word`, `--audio-lang` and
  snapshot as the build. Those decide which candidates an article gets, and so
  which files are wanted; a mismatched `--audio-per-word` fetches a different set.
- The build must be re-run afterwards, because the `[s]…[/s]` references are
  written while rendering. That pass is CPU and local archive I/O only — the
  expensive part of a build, the network, is skipped entirely.
- Fetching is deliberately slower than the build's own fallback: `--spacing`
  (default 2 s), `--retries` (default 6) and `--max-backoff` (default 600 s) are
  there because a back-fill is exactly the bulk client Wikimedia's robot policy
  asks to be gentle with. A file that still fails is logged and skipped, not
  fatal, and stays in the manifest for the next run.

#### Splitting the job across machines

One machine at a polite 2 s per request would spend hours on a big gap, even
though Wikimedia's rate limit is **per client** — a pool of rooms on a
university network, say, is one client. That is the case for shards:
`--split N` records the same work as `N` disjoint list files instead of one
manifest, for other machines to fetch. Each carries a header saying how it was
planned and the command that fetches it.

```bash
# on the machine that owns the snapshot: plan, and write 4 shards
python scripts/kaikki-to-dsl.py prefetch-audio \
    --source-lang en --audio-per-word 3 --dump-date 2026-09-02 --split 4
```

`--split` implies `--list` (a shard is a plan to hand out, not a job to finish
here), cannot be combined with `--limit`, and writes
`audio-missing.shard-01-of-04.tsv` … `audio-missing.shard-04-of-04.tsv` next to
where the manifest would have gone. The shards are **disjoint and balanced**: no
recording appears in two of them, and their sizes differ by at most one file, so
no machine is asked for another's work.

On each machine, fetch one shard into its own directory. There is nothing else
to set up — the needs are the list, Python, and the network:

```bash
python scripts/kaikki-to-dsl.py fetch-list \
    ~/.cache/aurelex-kaikki/2026-09-02/audio-missing.shard-01-of-04.tsv \
    --into ./fetch-01
```

`fetch-list` has no snapshot options by design: the shard already names the
files and the directory they belong in. It spaces, retries, verifies and writes
`.sha256` sidecars exactly as `prefetch-audio` does, so what lands is
indistinguishable from files this machine fetched itself, and it accepts a plain
manifest too (`prefetch-audio --list` can be handed to a worker as-is). It
bounds `--limit`, `--spacing`, `--retries` and `--max-backoff` the same way, and
a permanently-gone file is recorded in `<shard>.dead.tsv` — next to the shard,
never inside the directory. One thing it does **not** do is substitute a missing
candidate: with no records to choose the next one from, a worker records the
404 and lets the build slot-fill past it. A build run with `--no-audio-download`
is the one case that shows the difference — there the affected headword may
carry fewer than `--audio-per-word` recordings, because the substitution never
happened. Losing a worker's `<shard>.dead.tsv` only costs re-requests: the
closing `prefetch-audio` pass asks for those files again, records them dead
itself, and still finishes.

Combine the filled directories by copying — the building machine's audio cache
is a flat set of named, verified files, and a file already there is left alone:

```bash
cp -r ./fetch-*/* ~/.cache/aurelex-kaikki/2026-09-02/audio-cache/
```

Then re-run `prefetch-audio` with the same options in the usual place. It skips
every file the cache now holds, so a complete transfer costs no requests at all;
anything a worker gave up on is picked up here, and the run's verdict tells you
whether that pass is finished. A silence or a `0` against a shard directory that
you know the workers filled means the transfer missed something — the two lists
were planned from different snapshots, or a shard went to two machines and the
first copy was overwritten.

One plan per set of options: a shard is a snapshot of what one `--source-lang` /
`--audio-per-word` / `--audio-lang` combination wanted, so shards planned with
different options can overlap. Fetch only shards from the same plan into the
same cache.

#### Recovering a failed bundle

A build writes `<name>.dsl.dz` **before** it assembles `<name>.dsl.files.zip`. If
bundling fails — a filename the filesystem refuses, a kill, a full disk — the
dictionary survives but its audio bundle does not, and re-running the build
would pay the whole render again (about an hour for a full snapshot) to repeat a
step that never needed the records.

`bundle-audio` rebuilds just the bundle from the dictionary itself: it reads the
`[s]…[/s]` links the dictionary already carries as the list of recordings, finds
each in the cache or the archive, and writes the same bundle a build would have,
beside the dictionary. Nothing is re-rendered and the snapshot is never read.

```bash
python scripts/kaikki-to-dsl.py bundle-audio \
    dist/kaikki-en.dsl.dz \
    --dump-date 2026-09-02 --audio-tar ~/.cache/aurelex-kaikki/audios.tar.gz
```

- The recordings come from the dictionary, so the rebuild bundles exactly what
  the articles reference — no more and no less.
- A reference whose filename a filesystem refuses is bundled under the same
  safe name a build gives it, and the dictionary's link is rewritten to match,
  so no link points at a file that is not there. A dictionary whose links are
  already safe is not modified.
- A recording is looked for in the audio cache first, then the archive; one in
  neither is reported and left out, as a build leaves out an archive-missing
  recording.
- Pass `--dump-date` (or `--jsonl`) and, for a fully offline run, `--audio-tar`:
  the mode contacts nothing, reads neither the JSONL nor the dump date, and
  consults nothing but the cache directory and the archive.
- The bundle is written to the same place and name a build uses
  (`<base>.dsl.files.zip`, or `<base>.dsl.files/` with `--audio-layout dir`), so
  the recovered dictionary is indistinguishable from a clean build.

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
- The dictionary's `#NAME` metadata, its **About &lt;title&gt;** card, and the
  description (in the card and the sibling `.ann`) all use the display **title**
  (`--title`, defaulting to `--name`), while the output file names — the
  `.dsl.dz`, its `.files.zip` and the `.ann` — use the output **name**. So a
  human-readable title can coexist with a clean file name. The about card also
  carries the snapshot date, the wiktextract reference and the sense-icon legend.
- A sibling `<name>.ann` annotation sits beside the dictionary carrying the same
  description and entry count as plain text. DSL headers have no description
  field, but a Lingvo-aware reader (goldendict-ng) surfaces `<base>.ann` as the
  dictionary description; keep it beside the `.dsl.dz` when you copy or
  redistribute.

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
either passes `--no-audio-download`, injects a stub downloader, or blocks
`_open_with_retries` outright.

The audio prefetcher is covered end to end by driving the real sequence a user
does — build (gaps), prefetch, build again — and asserting the second build
reaches the network zero times. Its resume, `--limit` chunking (bounded by
attempt, and stopping before the rest of the snapshot is read), failure
isolation, replacement of a failed recording, the two failure classes (a
permanently gone file is recorded and never requested again while the run
reports itself finished; a rate-limited one is left for the next run and
reported as not finished), manifest contents, and `Retry-After` handling
(honoured, capped, and falling back to exponential backoff when unparseable) each
have a test.
