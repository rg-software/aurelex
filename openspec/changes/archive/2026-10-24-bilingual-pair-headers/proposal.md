# Proposal

## Why

Every bilingual dictionary ships `#INDEX_LANGUAGE "English"` /
`#CONTENTS_LANGUAGE "Russian"`, hardcoded in `dsl.assemble`. The app reads
that pair from the engine (`gd_dict_meta`) for the By-Pair grouping and the
"English/Russian" caption — so the ru→en dictionaries (translation and
pairs) are misclassified as En/Ru. The headers must follow the build
direction; en→ru output must stay byte-identical.

## What Changes

- `dsl.assemble` takes the index/contents language names; `package.build`
  passes them through; both build paths derive them from the direction
  (`en-ru` → English/Russian, `ru-en` → Russian/English).
- No engine, app, boundary, or import-path changes. No new dependencies.

## Capabilities

### New Capabilities

<!-- none: defect fix, behavior already implied by the direction parameter -->

### Modified Capabilities

- `bilingual-dictionary`: the "Import-ready deterministic packaging"
  requirement gains a direction-aware headers scenario.
