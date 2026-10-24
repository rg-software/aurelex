# Spec Delta

## ADDED Requirements

### Requirement: 16 KB page-size compliance
The system SHALL ship release artifacts in which every `arm64-v8a` native library is 16 KB ELF-aligned (`LOAD align 2**14`, RELRO-safe) and the APK/AAB is 16 KB zip-aligned (`PAGE_ALIGNMENT_16K`), and SHALL fail the release before publication when any check fails.

#### Scenario: Shipped libraries are 16 KB ELF-aligned
- **WHEN** a release APK or AAB is inspected with `check_elf_alignment.sh` or `llvm-objdump -p`
- **THEN** every shipped `.so` reports `ALIGNED` (`align 2**14`, no sub-16 KB `LOAD` segment)

#### Scenario: Packaged artifact is 16 KB zip-aligned
- **WHEN** a release APK is checked with `zipalign -c -P 16` and its AAB with `bundletool dump config`
- **THEN** zipalign reports success and the bundle reports `PAGE_ALIGNMENT_16K`

#### Scenario: Non-compliant artifact fails the release
- **WHEN** any shipped `.so` is `UNALIGNED` or the zip-alignment check fails
- **THEN** the release build fails before publication instead of shipping the artifact

#### Scenario: App runs on a 16 KB device
- **WHEN** the release artifact is installed on a 16 KB environment (`getconf PAGE_SIZE` returns `16384`)
- **THEN** the app launches, loads its native libraries without backcompat warnings, and dictionary lookup renders
