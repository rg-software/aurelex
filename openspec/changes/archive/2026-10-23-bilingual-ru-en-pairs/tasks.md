# Tasks

## 1. Symmetric corpus (tatoeba.py)

- [x] 1.1 `Corpus` gains `eng_freq`, `index_ru`, and a `lang` tokenizer
      marker (`"en"` default); `acquire()` builds both sides in the same pass
- [x] 1.2 `Corpus.flipped()` view: pairs/counters/indexes swapped,
      `lang="ru"`; `pairs_for` picks tokenizer and index from the view
- [x] 1.3 Unit tests: RU-side matching, dedupe on the RU text, case merge on
      RU pairs, single-character RU headword matches nothing

## 2. Direction plumbing (cli.py, provenance.py)

- [x] 2.1 `--source-lang {en,ru}` flag for pairs mode (default `en`); `ru`
      flips the corpus before `build_pairs`
- [x] 2.2 `Sources.direction` (`"en-ru"` default) driving the kind strings;
      unit tests for both wordings
- [x] 2.3 `kaikki_headwords` takes the snapshot language; `--all-kaikki`
      with `--source-lang ru` enumerates the RU snapshot (the hardcoded
      `"en"` filter silently returned English strays from it)

## 3. Verification

- [x] 3.1 Full unit suite green; change validates; main spec in sync
- [x] 3.2 Sample ru→en build (bounded headwords + `--preview`) from the
      pinned export and the kaikki RU snapshot; article shape eyeballed
- [x] 3.3 Smoke through the real reader: `gd_lookup` on a Cyrillic headword,
      no `unclosed`/`Unknown tag` warnings; audio-free as specified
