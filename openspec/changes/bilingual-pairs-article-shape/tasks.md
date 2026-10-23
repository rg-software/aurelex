# Tasks

## 1. Protocol the verified pairs article shape

- [x] 1.1 Render pairs cards flat (no zone) with RU lines as `[trn]` — verified: `gd_lookup` returns flat `dsl_ex`/`dsl_trn` lines, no zone, no expander, no markup warnings; unit test asserts no `[*]` and the `[trn]` marking
- [x] 1.2 Drop non-letter-start headwords with a reported count, and merge case variants into one card (lowercase-when-attested, else capitalized) — verified: unit tests for junk skipping, merge-to-attested, alphabetical tiebreak, plus a live 5-word sample run
- [x] 1.3 Document the rules and the `A major`/`The Hague` non-stripping decision with snapshot evidence in `docs/BILINGUAL-EXPERIMENT.md` — verify the section names the rule, the cost, and the corpus-attested case choice
