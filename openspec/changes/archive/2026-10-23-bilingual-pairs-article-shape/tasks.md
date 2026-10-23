# Tasks

## 1. Pairs article decisions (verified before writing)

- [x] 1.1 Flat `[ex]`/`[trn]` pairs with no collapsible zone — verified through the real reader: `gd_lookup("bread")` returns flat pairs, no zone, no expander, no markup warnings; unit test asserts no `[*]` and the `[trn]` marking
- [x] 1.2 Letter-start headword rule with ill-shaped counting — verified on the full build (192 junk headwords dropped, e.g. `'dog`, `-er`, `007`); unit test covers quotes, suffix fragments, digits, and empty headwords
- [x] 1.3 Case-fold merge keyed on the card body — verified by unit test (`maduro`/`Maduro` → `maduro`, `Sisyphus` stays) and a live 4-headword build (`Sisyphus`, `a major`, `dog`, `maduro` kept; `-er`, `007`, `-a`, `"'dog"` dropped)

## 2. Translation article decisions (verified before writing)

- [x] 2.1 Equivalents-first layout with subordinate italic definition and one card per headword — verified through the real reader: `gd_lookup("give")` returns POS sections with restarted numbering, `dsl_trn` equivalents, `dsl_i` definitions, zoned examples with working expanders, `gdau://` audio resolving; unit tests pin order, numbering restart, and tag set
- [x] 2.2 Common-first equivalent ranking (exact dupes removed, deterministic ties) — verified by unit test on the `парламент`/`высший законодательный…` group; no collapsing, per the no-semantic-judgment rule
