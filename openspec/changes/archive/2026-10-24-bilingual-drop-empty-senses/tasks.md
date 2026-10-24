# Tasks

## 1. Omit content-free senses at assembly (build.py)

- [x] 1.1 `build_sample` skips senses with no equivalents and no definition;
      headwords left with none join the existing `skipped_empty` path
- [x] 1.2 Unit tests: dropped shell keeps its card clean (парк pattern);
      unlinked-only headword gets no card; resolve-level counts unchanged

## 2. Verification

- [x] 2.1 Full unit suite green; change validates; main spec in sync
- [x] 2.2 en-ru showcase sample rebuilds byte-identical (zero such senses
      in the full build — the rule must be a provable no-op there)
