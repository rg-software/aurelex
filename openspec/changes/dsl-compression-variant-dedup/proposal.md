# Proposal

## Why

A dictionary folder may contain both `foo.dsl` and `foo.dsl.dz` (the same
dictionary, uncompressed and compressed). Both are staged and loaded, so the
lookup renders the same article twice and the list shows two entries. The
duplicate resolver cannot collapse them automatically: they share a name but
their file sets differ (`.dsl` vs `.dsl.dz`), so they are classified as a
name clash and left for the user to remove. That is correct for genuinely
different dictionaries, but it is a poor fit for the compression-variant case,
where the two are unambiguously the same dictionary. The fix should collapse
them automatically while still telling the user what happened.

## What Changes

- Detect, during duplicate resolution, a same-named group whose members differ
  only in whether the primary file is stored compressed (`.dsl.dz`) or plain
  (`.dsl`), with matching companion files.
- Auto-collapse such a group, keeping the compressed (`.dsl.dz`) copy and
  removing the redundant plain copy.
- Report the collapse in the import-results banner with an informational reason
  (`dslCompressionVariant`) so the user knows a redundant copy was removed.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `dictionary-management`: duplicate resolution gains a compression-variant rule —
  a `.dsl`/`.dsl.dz` pair with matching companions is collapsed automatically
  (compressed copy kept) and reported informationally rather than as a clash.

## Impact

- `app/DictIdentity.hpp` (variant detection helpers) and `app/EngineController.cpp`
  (resolution path) plus a banner reason in `app/main.qml`.
- No engine, boundary, patch, or localization changes beyond a new translated
  string.