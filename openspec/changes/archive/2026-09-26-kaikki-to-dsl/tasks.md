## 1. Tool skeleton and snapshot acquisition

- [x] 1.1 Add `scripts/kaikki-to-dsl.py` (Python 3) with a CLI entry point and `--help` documenting all options
- [x] 1.2 Define the pinned-snapshot model: accept an explicit dump date/version and derive the source URLs and cache paths from it
- [x] 1.3 Implement cached download of the raw wiktextract JSONL with size/checksum verification; reuse local data when present
- [x] 1.4 Implement cached download of the Wiktionary audio archive, and skip it entirely when audio is disabled
- [x] 1.5 Record the resolved snapshot date/version for embedding in the output metadata

## 2. Parsing, pair selection, and filtering

- [x] 2.1 Stream-parse the JSONL line by line without loading the whole file into memory
- [x] 2.2 Implement source/target language selection, including the source = target monolingual case, rejecting unsupported pairs with a clear report
- [x] 2.3 Exclude non-lexical entries (soft redirects, romanizations) from headword candidates
- [x] 2.4 Skip malformed records without aborting, and accumulate kept/skipped counts for the final report

## 3. Headwords, base forms, and inflections

- [x] 3.1 Select base-form headwords using the entry `pos` and the absence of `form_of` senses
- [x] 3.2 Collect grammatical/inflected forms per base word from the entry's `forms[]`
- [x] 3.3 Add `--include-inflections` to merge inflected forms as extra headword lines on the base word's card, and document the suggestion-list trade-off in `--help`
- [x] 3.4 Ensure the default mode indexes base forms only, with no inflected forms in the index

## 4. Article rendering

- [x] 4.1 Map parts of speech, glosses, and examples to supported DSL tags (`[p]`, `[mN]`, `[ex]`)
- [x] 4.2 Render grammatical forms inside the base article's card
- [x] 4.3 Render target-language translations for bilingual pairs (`[trn]`), keeping them with their rendered sense
- [x] 4.4 Emit cross-references (`[ref]`) only to indexed headwords, avoiding dead links in base-form-only mode
- [x] 4.5 Implement a central DSL escaping pass for `[`, `]`, `<<`, `>>`, leading tabs, and leading `#`
- [x] 4.6 Degrade complex structures (tables, nested templates) to readable text

## 5. Pronunciation audio

- [x] 5.1 Collect referenced audio filenames from `sounds[]` and match them to archive entries
- [x] 5.2 Extract only the referenced entries from the bulk archive by streaming it, not by per-URL download
- [x] 5.3 Deduplicate audio so the same recording is bundled once, and detect/disambiguate filename collisions across languages
- [x] 5.4 Enforce `--audio-per-word` (default 3) with a source-language preference, and implement `--no-audio` / limit 0
- [x] 5.5 Omit unresolvable audio from an article without failing the run, and count missing files in the report
- [x] 5.6 Name bundled audio so `[s]name[/s]` resolves, in whichever resource container the packaging uses

## 6. Sample and preview

- [x] 6.1 Add `--sample N` to emit a dictionary containing at most N selected headwords
- [x] 6.2 Add a preview mode that renders the sample's articles in a human-readable form for review
- [x] 6.3 Produce a reviewable sample under `examples/dictionaries/` (or a documented output path)
- [x] 6.4 Add `--sample-mode {first,random}` (deterministic random selection across the snapshot) and keep cross-references live within a sample

## 7. Provenance, packaging, and determinism

- [x] 7.1 Write the `#NAME`/metadata attribution: Wiktionary source, CC BY-SA 4.0, wiktextract citation, snapshot dump date
- [x] 7.2 Add an about card inside the dictionary carrying the same attribution and license
- [x] 7.3 Emit the dictionary as a deterministic dictzip-compressed `.dsl.dz` only (no plain `.dsl`), reusing the dictzip writer from `scripts/make-example-dicts.py`
- [x] 7.4 Package referenced audio into a single sibling `<name>.dsl.dz.files.zip` resource archive by default, with an option to emit a loose `.files/` resource directory instead
- [x] 7.5 Make ordering and header emission deterministic, and confirm a rebuild from the same snapshot and options is byte-identical for both the dictionary and the resource archive
- [x] 7.6 Emit the final data-quality report (kept, skipped, missing audio)

## 8. Verification and documentation

- [x] 8.1 Add a small self-contained fixture (a dozen synthetic JSONL records) and a script/test that builds a DSL dictionary and asserts the rendered tags, base-form policy, and flag behaviour
- [x] 8.2 Run the sample build against a real pinned snapshot and review the preview article shape
- [x] 8.3 Verify the produced `.dsl.dz` plus its resource archive (or resource directory) imports and resolves audio through the app's existing folder import (on-device)
- [x] 8.4 Document usage, options, storage expectations, and the CC BY-SA derivative-work note in `docs/`
- [x] 8.5 Run `openspec validate kaikki-to-dsl` and resolve any findings
