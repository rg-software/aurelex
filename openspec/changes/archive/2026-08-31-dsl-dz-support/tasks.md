## 1. Example dictionaries

- [x] 1.1 Create 3 small example DSL dictionaries in `examples/dictionaries/` (aurelex-basic with DSL markup, aurelex-lingvo bilingual EN↔RU, aurelex-phrasebook with multi-word headwords) — done
- [x] 1.2 Add `scripts/make-example-dicts.py` generating both `.dsl` and real `.dsl.dz` (dictzip "RA" extra field) variants — done

## 2. Verification

- [x] 2.1 Host verification: scan a folder with all 6 files → `gd_scan_dicts` returns 6; look up single-word, non-ASCII (EN↔RU), and multi-word headwords → non-empty `gdarticlebody` HTML — done: `gd_scan_dicts→6`, `apple`→2892 B, `hello`→3985 B, `how are you`→4021 B; `.dsl.dz` returns identical HTML to `.dsl` (2892 B)
- [x] 2.2 On-device verification: install debug APK, add `examples/dictionaries/` via the folder picker, confirm all 6 dictionaries list and look up (compressed variants included) — verified on Motorola ThinkPhone Android 15: "Dictionaries (6 loaded)" (3 .dsl + 3 .dsl.dz), "water" article from Aurelex Basic renders (DSL markup), "hello" from Aurelex Lingvo EN-RU renders (Cyrillic + trn)
- [x] 2.3 Optional: extend the CI engine-smoke fixture set with a `.dsl.dz` and assert it loads — `.github/workflows/engine-smoke.yml` now generates the DSL fixtures via `make-example-dicts.py`, copies `aurelex-basic.dsl.dz` into the smoke dict folder, and asserts `gd_scan_dicts -> 2` (stardict + dsl.dz) plus non-empty lookup HTML; validated locally (2 dicts, 2820 B, exit 0)

## 3. Fixes if verification surfaces issues

- [x] 3.1 Fix any `.dsl.dz` handling gap found in `gd_scan_dicts`/`SafResolver`/carve (expected no-op; only if a check fails) — no gap found: `.dsl.dz` loads, lists, and looks up correctly on-device and in the host smoke
