# Bilingual builders (En↔Ru, En↔Ja, Ja↔Ru)

`scripts/bilingual-to-dsl.py` builds offline bilingual dictionaries (`.dsl.dz` +
sibling resources) for the existing folder import. The implementation lives in
the `scripts/bilingual/` package; this script is a launcher. Full recipes with
exact commands live under `docs/builds/`: `*-wordnet.md` (translation
dictionaries) and `*-tatoeba.md` (example-sentences dictionaries) for each
supported direction.

Modes (`--mode`):

- `skeleton` (default) — headword-list input only; packaging path exercisable
  without sources.
- `translation` — full translation dictionary: PWN synsets bridged to the
  target thesaurus (`ili` into RuWordNet, shared PWN ids into Japanese
  WordNet, or the Ja↔Ru PWN-id pivot), one anchored Tatoeba example per
  sense, source-language kaikki audio verbatim, provenance + `.ann` +
  sibling bundle.
- `pairs` — example-sentences dictionary: keep-N concordance pairs per
  headword, Tatoeba-only provenance, no audio, no bundle.

Headwords come from `--word` (repeatable), `--words-file` (one per line),
`--all-lemmas` (the English thesaurus universe: RuWordNet EN subset for
en→ru, JaWN-linked EN lemmas for en→ja — both need their `wn`/`ruwordnet`
package plus downloaded data), or `--all-kaikki` (every lexical headword of
the source-language kaikki snapshot from `--snapshot`; the pairs
dictionaries keep only the headwords that have pairs). `--index-readings`
additionally indexes hiragana reading headwords for Japanese sources
(needs `--snapshot`; a no-op for other languages).

Sample either mode before a full run (`--sample N --preview`); `random` spreads
across the list deterministically.

Long builds print coarse progress to stderr (same habit as the kaikki tool):
`resolving equivalents: N/M` every 1,000 headwords, `snapshot scan: N lines`
every 1M snapshot lines, `counting phrases: N/M` for the Japanese frequency
pass, `indexing readings: N cards` when `--index-readings` is on,
`audio cached: N` every 1,000 cache hits, plus one line per audio
download or unresolvable recording. Nothing prints per card.

## Options

| Option | Meaning |
| --- | --- |
| `--mode {skeleton,translation,pairs}` | What to build (default `skeleton`). |
| `--word WORD` / `--words-file FILE` | Headwords (repeatable / one per line). |
| `--all-lemmas` | Use the full EN thesaurus universe (see above). |
| `--all-kaikki` | Use the full lexical kaikki headword universe of the source language (needs `--snapshot`). |
| `--source-lang {en,ru,ja}` / `--target-lang {en,ru,ja}` | Dictionary direction (target defaults to ru for en, en otherwise). |
| `--index-readings` | Also index hiragana reading headwords (Japanese sources only; needs `--snapshot`). |
| `--resolve-cache FILE` | Cache resolved equivalents here (keyed by thesaurus file + headwords); reruns skip resolution. |
| `--sample N` / `--sample-mode {first,random}` | Bounded deterministic subset. |
| `--preview` | Also write `<name>.preview.html`. |
| `--out-dir DIR` | Output directory (default `dist`). |
| `--name NAME` / `--title TITLE` | Output base name / display name. |
| `--snapshot PATH` | Pinned kaikki source-language snapshot (translation audio and readings; unneeded with `--no-audio`). |
| `--audio-tar PATH` | Shared bulk audio archive. |
| `--audio-cache-dir DIR` | Download cache dir for recordings the archive lacks. |
| `--no-audio` / `--audio-per-word N` / `--audio-lang TAG` | Audio controls (defaults: on, 3, none; `--audio-lang` is an English-only filter). |
| `--tatoeba-dir DIR` / `--tatoeba-date DATE` | Per-pair Tatoeba files (`<src>_sentences`, `<tgt>_sentences`, `<pair>_links`) + pinned export date. |
| `--keep-pairs N` | Pairs kept per headword in pairs mode (default 5). |
| `--kaikki-dump-date DATE` | Snapshot dump date recorded in provenance. |
| `--ruwordnet-pwn TEXT` / `--ruwordnet-version TEXT` | Version labels for provenance. |

## Outputs

- `<name>.dsl.dz` — dictzip-compressed DSL, byte-identical across rebuilds from
  the same inputs (cards render in headword order).
- `<name>.dsl.files.zip` — sibling resource bundle (translation mode with audio).
- `<name>.ann` — sibling annotation with attribution and pinned versions.
- `<name>.preview.html` — standalone article preview (with `--preview`).
