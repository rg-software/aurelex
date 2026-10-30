# Design

## Context

Duplicate resolution (`EngineController::resolveDuplicateDictionaries`) groups loaded
dictionaries by normalized name. Identical content is collapsed silently; differing
content is reported as a name clash and left for the user. A `.dsl`/`.dsl.dz` pair
shares a name but has different file basenames, so it currently falls into the
clash branch even though the two are unambiguously the same dictionary. See
proposal.md for motivation.

## Goals / Non-Goals

**Goals:**
- Auto-collapse a `.dsl`/`.dsl.dz` pair (same stem, matching companions), keeping
  the compressed copy, regardless of where the two files live.
- Report the collapse informationally (`dslCompressionVariant`) instead of as a
  name clash or silently.

**Non-Goals:**
- No change to the general identity rule or the clash handling for genuinely
  different same-named dictionaries.
- No engine edits.

## Decisions

1. **Detect at resolution time, not import time.** The clash is already detected
   there, and operating on loaded dictionaries handles cross-subdir and
   cross-pick cases that sibling checks cannot. Alternative (import-time dedup)
   rejected for not covering cross-subdir/cross-pick.
2. **Keep the compressed (`.dsl.dz`) copy.** It is the smaller on-disk form and
   the one the engine prefers; dropping the plain copy loses nothing.
3. **Helpers in `DictIdentity.hpp`.** Header-only and host-testable, matching
   the existing pattern (StagedCleanup, IndexCleanup). Variant detection compares
   stems and companion sets.

## Risks / Trade-offs

- [Risk] A dictionary named with a `.dsl`/`.dsl.dz` suffix in an unusual way
  could be misclassified. → Mitigation: require matching companion sets and at
  least one compressed + one plain member.
- [Risk] Reporting adds a banner row on every scan until dismissed. → Mitigation:
  same dismiss path as other result rows; idempotent on re-scan.

## Open Questions

None.