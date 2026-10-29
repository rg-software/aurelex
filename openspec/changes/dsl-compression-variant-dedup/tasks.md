# Tasks

## 1. Detect and collapse DSL compression variants

- [ ] 1.1 Add variant-detection helpers to `DictIdentity.hpp` (`dslStem`, `isDslPrimaryFile`, `isDslCompressionVariant`, `allDslCompressionVariants`) and verify `dict_identity_test` still compiles and passes
- [ ] 1.2 In `resolveDuplicateDictionaries`, treat an all-variant group as identical (auto-collapse, keep `.dsl.dz`) and verify the plain copy is removed
- [ ] 1.3 Report the collapse via a `dslCompressionVariant` row in the import-results banner and verify the informational message shows (not the clash message)

## 2. Validation

- [ ] 2.1 Import a folder containing both `foo.dsl` and `foo.dsl.dz` on a device; verify only the compressed copy remains and the banner reports `dslCompressionVariant`
- [ ] 2.2 Confirm `openspec validate dsl-compression-variant-dedup` passes