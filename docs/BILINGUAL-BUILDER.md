# Bilingual builder (En→Ru)

`scripts/bilingual-to-dsl.py` builds two offline dictionaries (`.dsl.dz` +
sibling resources) for the existing folder import. The implementation lives in
the `scripts/bilingual/` package; this script is a launcher. Full recipes with
exact commands: `docs/builds/en-ru-wordnet.md` (translation dictionary) and
`docs/builds/en-ru-tatoeba.md` (example-sentences dictionary).

Modes (`--mode`):

- `skeleton` (default) — headword-list input only; packaging path exercisable
  without sources.
- `translation` — full translation dictionary: PWN → `ili` → RuWordNet
  equivalents, one anchored Tatoeba example per sense, kaikki EN audio
  verbatim, provenance + `.ann` + sibling bundle.
- `pairs` — example-sentences dictionary: keep-N concordance pairs per
  headword, Tatoeba-only provenance, no audio, no bundle.

Headwords come from `--word` (repeatable), `--words-file` (one per line), or
`--all-lemmas` (every English lemma in the RuWordNet EN subset — needs the
`ruwordnet` package + downloaded db).

Sample either mode before a full run (`--sample N --preview`); `random` spreads
across the list deterministically.

## Options

| Option | Meaning |
| --- | --- |
| `--mode {skeleton,translation,pairs}` | What to build (default `skeleton`). |
| `--word WORD` / `--words-file FILE` | Headwords (repeatable / one per line). |
| `--all-lemmas` | Use the full RuWordNet EN lemma universe. |
| `--sample N` / `--sample-mode {first,random}` | Bounded deterministic subset. |
| `--preview` | Also write `<name>.preview.html`. |
| `--out-dir DIR` | Output directory (default `dist`). |
| `--name NAME` / `--title TITLE` | Output base name / display name. |
| `--snapshot PATH` | Pinned kaikki EN snapshot (translation audio; unneeded with `--no-audio`). |
| `--audio-tar PATH` | Shared bulk audio archive. |
| `--audio-cache-dir DIR` | Download cache dir for recordings the archive lacks. |
| `--no-audio` / `--audio-per-word N` / `--audio-lang TAG` | Audio controls (defaults: on, 3, none). |
| `--tatoeba-dir DIR` / `--tatoeba-date DATE` | Per-pair Tatoeba files + pinned export date. |
| `--keep-pairs N` | Pairs kept per headword in pairs mode (default 3). |
| `--kaikki-dump-date DATE` | Snapshot dump date recorded in provenance. |
| `--ruwordnet-pwn TEXT` / `--ruwordnet-version TEXT` | Version labels for provenance. |

## Outputs

- `<name>.dsl.dz` — dictzip-compressed DSL, byte-identical across rebuilds from
  the same inputs (cards render in headword order).
- `<name>.dsl.files.zip` — sibling resource bundle (translation mode with audio).
- `<name>.ann` — sibling annotation with attribution and pinned versions.
- `<name>.preview.html` — standalone article preview (with `--preview`).
