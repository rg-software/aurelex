## 1. Implementation

- [x] 1.1 Fold dead-file names to match keys when the prefetcher loads them
- [x] 1.2 Make `fetch-list` skip names its `<shard>.dead.tsv` already holds (and report the count)
- [x] 1.3 Give `AudioPlan` a dead set and an `on_gone` callback; skip a known-gone candidate without requesting it
- [x] 1.4 Have `build` read and append `<snapshot>/audio-dead.tsv`

## 2. Tests and docs

- [x] 2.1 Build records a 404 and the next build skips it (capitalised name)
- [x] 2.2 A capitalised dead name matches in the prefetcher
- [x] 2.3 A shard re-run skips a name its dead file holds
- [x] 2.4 `python -m unittest scripts.tests.test_kaikki_to_dsl`
- [x] 2.5 Update `docs/KAIKKI-CONVERSION.md`
- [x] 2.6 `openspec validate reuse-audio-dead-record --strict`
