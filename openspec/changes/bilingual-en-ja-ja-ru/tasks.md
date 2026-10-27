# Tasks

## 1. Japanese thesaurus resolution (JaWN + PWN-ID pivot)

- [x] 1.1 Add JaWN backend (pinned `wnja` 2.x via `wn`, PWN-ID join; records lemmas + Japanese definitions) and verify `resolve_word("dog", direction="en-ja")` returns Japanese equivalents in a unit test
- [x] 1.2 Add Ja↔Ru pivot join (JaWN ↔ PWN ID ↔ RuWordNet `ili`, target-language definitions) and verify a pivot probe word resolves both directions in a unit test
- [x] 1.3 Wire unlinked-synset counting and content-free-sense omission for the new directions and verify the resolution report counts match the spec scenarios in `test_bilingual_to_dsl.py`
- [x] 1.4 Document the JaWN pin, license link-back, and pivot rule in `docs/BILINGUAL-EXPERIMENT.md` (appendix note) and verify the stated versions match the code constants

## 2. Tatoeba Japanese pairs and matching

- [x] 2.1 Generalize corpus acquisition to per-pair files (`eng-jpn`, `jpn-rus` sentences + links, pinned date) and verify `acquire` loads both pairs with correct pair order in a unit test
- [x] 2.2 Add Japanese tokenizer (substring match, no `\w` boundaries, `。` sentence bound, Japanese-side frequency counter) and verify CJK match/bound scenarios in a unit test
- [x] 2.3 Wire anchored-first + concordance-fallback ranking for Japanese sides (rarity from the Japanese counter) and verify anchored-preferred and fallback scenarios in a unit test

## 3. Cards, CLI, packaging, provenance

- [ ] 3.1 Render Japanese-target cards (Japanese POS labels, equivalents-first order with Japanese frequency ranking, `[ex]`/`[trn]` marking per direction) and verify `emit_card` output for En→Ja and Ja→Ru fixtures in a unit test
- [ ] 3.2 Extend CLI to `--source-lang {en,ru,ja}` with direction validation and per-pair Tatoeba discovery, and verify `--help` plus a `--mode translation --source-lang ja` sample invocation parses in a test
- [ ] 3.3 Extend headers (`#INDEX/#CONTENTS_LANGUAGE` incl. Japanese) and provenance (`Sources` gains `wnja` version, direction-aware labels, link-back, conditional non-commercial line) and verify about/`.ann` text for all four directions in a unit test
- [ ] 3.4 Update `docs/BILINGUAL-BUILDER.md` option table for the new flags/pins and verify every documented flag exists in `--help` output

## 4. Audio, transcription, pairs dictionaries

- [ ] 4.1 Reuse source-language kaikki audio verbatim for Japanese headwords (JA snapshot/archive/cache via existing `lang` params) and verify a JA headword's `[s]` refs resolve with `verify_bundle` in a test
- [ ] 4.2 Reuse source-language transcription (`[t]` under headword, kana-marked readings per JA profile) for the new directions and verify transcription-present/absent scenarios in a test
- [x] 4.3 Build pairs dictionaries for En↔Ja and Ja↔Ru (flat `[ex]`/`[trn]`, letter-eligibility, case-fold no-op for Japanese, deterministic) and verify headword-eligibility and direction-marking scenarios in a test

## 5. Probes, recipes, catalog

- [ ] 5.1 Run bounded `--sample --preview` probes for all four translation directions plus pairs, eyeball article shape, and verify each preview renders equivalents, zoned examples, and audio refs with no markup warnings
- [ ] 5.2 Add `docs/builds/` recipes (`en-ja`, `ja-en`, `ja-ru`, `ru-ja` wordnet + Tatoeba pairs) with exact fetch/build commands and verify each documented command parses against the CLI
- [ ] 5.3 Append the eight catalog entries to `catalog/source.json` (translation + pairs × 4 directions, Japanese `names` included) and verify `scripts/build-catalog.py validate` passes
- [ ] 5.4 Full smoke verification: import each built `.dsl.dz` through the folder import and verify `gd_lookup` returns full articles with no `unclosed`/`Unknown tag` warnings and audio refs resolving

## 6. Opt-in reading indexing

- [x] 6.1 Collect hiragana reading keys per headword from the kaikki snapshot (same transliteration forms as the monolingual `--index-readings`, katakana folded) and verify most-common voting and ties in a unit test
- [x] 6.2 Emit alias cards for Japanese-source translation dictionaries (same article under each reading, opening with the primary headword as title; collisions keep the real card) and verify in a unit test
- [x] 6.3 Emit alias cards for Japanese-source pairs dictionaries and wire the `--index-readings` CLI flag (needs `--snapshot`, no-op for non-Japanese sources), and verify end to end in a unit test
