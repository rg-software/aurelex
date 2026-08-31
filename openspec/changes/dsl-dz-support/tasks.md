## 1. Example dictionaries

- [x] 1.1 Create 3 small example DSL dictionaries in `examples/dictionaries/` (aurelex-basic with DSL markup, aurelex-lingvo bilingual EN↔RU, aurelex-phrasebook with multi-word headwords) — done
- [x] 1.2 Add `scripts/make-example-dicts.py` generating both `.dsl` and real `.dsl.dz` (dictzip "RA" extra field) variants — done

## 2. Verification

- [x] 2.1 Host verification: scan a folder with all 6 files → `gd_scan_dicts` returns 6; look up single-word, non-ASCII (EN↔RU), and multi-word headwords → non-empty `gdarticlebody` HTML — done: `gd_scan_dicts→6`, `apple`→2892 B, `hello`→3985 B, `how are you`→4021 B; `.dsl.dz` returns identical HTML to `.dsl` (2892 B)
- [ ] 2.2 On-device verification: install debug APK, add `examples/dictionaries/` via the folder picker, confirm all 6 dictionaries list and look up (compressed variants included) — task-gated on the real-device test pass
- [ ] 2.3 Optional: extend the CI engine-smoke fixture set with a `.dsl.dz` and assert it loads

## 3. Fixes if verification surfaces issues

- [ ] 3.1 Fix any `.dsl.dz` handling gap found in `gd_scan_dicts`/`SafResolver`/carve (expected no-op; only if a check fails)
