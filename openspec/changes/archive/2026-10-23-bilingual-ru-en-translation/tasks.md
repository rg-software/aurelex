# Tasks

## 1. RU→EN resolution (equivalents.py)

- [x] 1.1 Mirror resolver: RU senses → RU synset → `ili` → EN synsets;
      equivalents verbatim, PWN gloss as definition, RU lemmas as synonyms;
      unlinked RU synsets resolve unlinked
- [x] 1.2 English POS labels for the target language (PWN letters map
      directly; bridge pairs always agree)
- [x] 1.3 Unit tests: resolution counts, verbatim glosses, unlinked fallback

## 2. Direction plumbing (build.py, cli.py, provenance.py, audio.py)

- [x] 2.1 Translation mode honors `--source-lang ru`: flipped corpus,
      RU resolver, EN labels, eng-side ranking via the flipped counter
- [x] 2.2 `select_for_sense` proven unchanged on flipped pairs (unit test)
- [x] 2.3 `collect_records` language parameter; RU audio plan wired in build
- [x] 2.4 Translation provenance kind direction-aware, both wordings tested

## 3. Verification

- [x] 3.1 Full unit suite green; change validates; main spec in sync
- [x] 3.2 Sample ru→en translation build (bounded headwords + `--preview`)
      from the pinned export and the RU snapshot; article shape eyeballed
- [x] 3.3 Smoke through the real reader on a Cyrillic headword, no
      `unclosed`/`Unknown tag` warnings; audio refs verified or absent
