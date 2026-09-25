## Context

See `proposal.md` — Why. Relevant constraints established by the codebase:

- Aurelex supports exactly three import formats (`dictionary-management`), and
  only DSL exposes pronunciation audio: `dsl.cc` maps `[s]file[/s]` to a `gdau://`
  URL resolved from a sibling `<dict>.files/` directory (`dsl.cc:279`,
  `dsl.cc:810-829`), while `sdict.cc` has no resource/audio path at all.
- The DSL reader stays within a fixed tag set (`dsl.cc:765-989`): `b i u c m mN
  * trn ex com s url !trs p ' lang ref @ sub sup t br`; unknown tags are
  downgraded, not fatal.
- The DSL reader indexes **every** headword line of a card and every inside-card
  headword into the same search index (`dsl.cc:1941-1970`, `dsl.cc:2088-2095`);
  there is no hidden-alias concept, so indexed words are also suggestions.
- `scripts/make-example-dicts.py` already emits real dictzip (`.dsl.dz`) with the
  dictd "RA" extra field, and `examples/dictionaries/` is the existing fixture
  location.

## Goals / Non-Goals

**Goals:**

- A reproducible, resumable desktop converter from a pinned kaikki.org snapshot
  to an import-ready DSL dictionary for a source/target language pair.
- Base-form headwords by default; opt-in inflected-form indexing.
- Correct article shape (POS, glosses, examples, grammar forms, translations)
  using only DSL tags the reader supports.
- Bounded, deduplicated audio bundled as a sibling resource directory.
- Sample/preview output and always-present provenance.

**Non-Goals:**

- Any change to the Android app, QML, or the carve/engine; the output uses the
  existing import path unchanged.
- Images/video, inflection tables rendered as tables, or Wikipedia/Wikidata
  linkage.
- Redistributing dictionaries from the repository, or converting on the device.
- Any format other than DSL (StarDict is text-only in this engine; MDX authoring
  is impractical here).

## Decisions

### D1. Target format is DSL, compressed, with zipped audio resources

Only DSL satisfies both "importable by Aurelex" and "carries pronunciation
audio". StarDict is engine-supported but has no audio path in `sdict.cc`; MDX
would carry audio but needs an MDX writer and is far harder to author. DSL is
plain text, the reader's tag set is known and bounded, and dictzip (`.dsl.dz`)
is already supported. The dictionary is therefore always emitted as `.dsl.dz` —
no uncompressed `.dsl` — and referenced audio ships either as a sibling
`<baseName>.dsl.dz.files.zip` archive or as a sibling `.files` directory. The
engine resolves resources from the directory first and then the zip
(`dsl.cc:1607-1620`), and looks for both `<baseName>.dsl.files.zip` and
`<baseName>.dsl.dz.files.zip` (`dsl.cc:1743-1746`). The zip is the default
because it keeps the many small audio files as one staged import unit.

*Alternative rejected:* emit StarDict via an existing library — loses audio.
*Alternative rejected:* always emit an uncompressed `.dsl` too — redundant, and
the reader handles `.dsl.dz` natively.

### D1a. Resource packaging is a choice, with the archive as default

The tool packages audio into a single resource archive by default, and offers
loose-file output as an option. Both are engine-supported; the choice only
affects how the user copies and how many files SAF stages.

### D2. Source is the raw wiktextract JSONL, not the per-language postprocessed files

The per-language postprocessed downloads are explicitly deprecated in favour of
the raw data, and the raw JSONL is one object per (word, part-of-speech,
etymology), which maps cleanly to cards. The converter streams the JSONL line by
line to bound memory instead of loading it.

### D3. Pair semantics: source = headword language, target = gloss/translation language

`en/en` is monolingual. `en/ru` indexes English headwords and adds Russian
translations from `translations[]`. The reverse (`ru/en`) reads the Russian
headword set (Russian words, English glosses) from the snapshot. This keeps the
pair meaning unambiguous: the first code always selects the indexed headwords.

### D4. Base-form selection and grammar forms

An entry is a candidate headword when it is a lexical entry: its `pos` is a
lexical part of speech, and it is not a soft redirect or romanization. Entries
whose senses are inflected forms (`form_of`) are not headwords by default.
Grammatical forms for an article come from the entry's `forms[]` and are
rendered as a forms line inside the base article's card.

*Alternative rejected:* relying on title heuristics — `pos`/`form_of` is
explicit and stable in the schema.

### D5. Inflected-form indexing merges forms onto the base card, behind a flag

With `--include-inflections`, each inflected form is added as an additional
headword line on the base word's card, matching the reader's multi-headword card
handling. The consequence — those forms also appear in suggestions — is inherent
to DSL (no hidden aliases) and is documented in the tool's help. Separate stub
cards ("ran → run") are rejected: they add articles without giving the user the
full base article the merged form provides.

### D6. Audio is subset from the bulk archive by exact filename match

`sounds[].audio` is the Commons file name, and the bulk archive's entries are
named with the last URL component, so matching is direct. The converter collects
the referenced names, then extracts only those from the archive (streaming the
tar) rather than fetching URLs individually, which would take days and load
Wikimedia. Deduplication is by file content/name. Preference is given to the
source language (via sound `tags`/entry `lang_code`), capped at
`--audio-per-word` (default 3; 0 disables). Files are bundled under their
original names — in the resource archive by default, or in the resource
directory when requested — so `[s]name[/s]` resolves.

*Alternative rejected:* download per-URL — slow and abusive to the source.

### D7. Rendering uses only the reader's supported DSL tags, with escaping

Each wiktextract field maps to a supported tag (`[p]` for POS, `[mN]` for
numbered senses, `[ex]` for examples, `[trn]` for translations, `[ref]` for
cross-references, `[s]` for audio). Free text is escaped for DSL
metacharacters (`[`, `]`, `<<`, `>>`, leading tabs, leading `#`) so gloss text
cannot accidentally form tags. Tables and other complex structures degrade to
readable text.

### D8. Deterministic output

Card order is by headword, then entry language, then part of speech; header
fields and provenance are fixed-order; no build timestamps are embedded in a way
that changes bytes; the dictzip container and the resource archive are written
deterministically (reusing the dictzip writer in `scripts/make-example-dicts.py`,
and pinning archive entry order, names, and per-entry metadata). Same snapshot +
options ⇒ byte-identical output, which is what makes the tool reproducible.

### D9. Provenance is always embedded

`#NAME` and an about card carry: Wiktionary as source, CC BY-SA 4.0, the
wiktextract citation, and the pinned dump date. The repository ships no data;
the user generates and holds the derivative work.

### D10. Tooling is a standalone Python 3 script under `scripts/`

Matches the existing generators (`make-example-dicts.py`,
`make-smoke-stardict.py`) and keeps the dependency surface off the Android app.
Existing projects are references only: `pyglossary` cannot write DSL, and
`kaikki-to-yomitan` targets a different format but is a useful model for the
filter/group/audio stages.

## Risks / Trade-offs

| Risk | Mitigation |
| --- | --- |
| Full snapshot + audio is multi-GB and slow to first import on device | `--sample`, per-language filtering, and `--audio-per-word`/`--no-audio` bound the work; document storage expectations |
| Inflected-form indexing pollutes suggestions | Off by default; the flag's help states the trade-off; base-form mode keeps suggestions clean |
| Audio filename collisions across languages (last URL component only) | Detect collisions and disambiguate names while keeping `[s]` references consistent |
| DSL text with unescaped metacharacters breaks cards | Central escaping pass; a rendered sample is reviewed before full runs |
| Schema drift in wiktextract JSONL across snapshots | Pin the snapshot; unknown fields are ignored, not fatal; quality report counts skips |
| Output licensing (CC BY-SA share-alike) | Attribution embedded by default; tool documents that the output is a derivative work |
| Postprocessed vs raw differences confuse users | The tool consumes the raw snapshot only; documentation states why |

## Migration Plan

Not applicable — this adds an offline desktop tool and changes no existing code.
Adoption is: run the converter, copy `<name>.dsl.dz` + `<name>.dsl.files/` to the
phone, import the containing folder through the existing picker. Rollback is
deleting the generated files and the dictionary from the app.

## Open Questions

- Whether the about/attribution card should be written in the source language,
  the target language, or English. Does not affect the specs or approach.
