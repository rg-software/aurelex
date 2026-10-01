## Why

A dictionary that fails to load leaves its staged files on disk with no way to
remove them. The Dicts tab surfaces the failure in a banner naming the file, and
tells the user to "pick the same folder again to re-copy it" — but that does not
work. Re-picking stages the folder into a **new** directory, leaving the broken
one in place, so every scan re-attempts it, re-fails, and re-raises the banner.
The banner has no dismiss control. The user is stuck with a permanent error and
untouchable wasted storage.

Found on-device while verifying `fix-stardict-staging`: a StarDict import that
staged only part of a dictionary could not be repaired by re-importing, and the
failure survived until its directory was deleted by hand. The bug is
pre-existing and format-independent — any corrupt or truncated `.mdx`, `.dsl` or
`.ifo` does the same — but a half-staged dictionary is the easiest way to hit it.

Two defects share the one root cause, and fixing either alone leaves the user
stuck:

- the broken import's files cannot be reached by any in-app action, because
  removal is driven by the loaded-dictionary list and a failed dictionary is not
  in it; and
- the banner therefore cannot clear, because the failure recurs on every scan.

## What Changes

- **A failed import can be cleaned up.** The failure surfaced for a file the app
  could not load SHALL be removable, deleting that import's staged files (and any
  index entries) so it stops being retried and stops being reported.
- **Re-importing a folder supersedes a previous failed import of the same
  folder**, so the documented remedy ("pick the same folder again") actually
  clears the failure. The stale staging directory SHALL NOT survive the
  successful re-import.
- **The banner tells the truth.** Its guidance SHALL match what the app does, and
  the user SHALL have an action that clears the failure rather than only advice.
- Cleanup SHALL NOT delete files belonging to a **loaded** dictionary, and SHALL
  NOT delete a staging directory that still holds another loaded dictionary's
  files (a single import folder can hold several dictionaries).

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `dictionary-management`: the import requirement currently says a failed load is
  reported; it must also say the failure is actionable and does not survive a
  successful re-import. Adds scenarios for removing a failed import and for a
  re-import superseding it.

## Impact

- `app/EngineController.cpp` — the scan-failure surface (`collectScanFailures`,
  `m_scanFailures`) and the removal path (`deleteDictionaryFiles`, whose
  "shared by siblings" guard is the shape the new cleanup must follow).
- `app/EngineController.hpp` — a new invokable to remove a reported failure.
- `app/main.qml` — the failures banner gains an action; its copy is corrected.
- `docs/TESTING.md` — recipes for the two new behaviours.
- No engine, carve, boundary or patch change: `gd_scan_failures` already returns
  the failing file's full path, which is everything the cleanup needs.

## Risks

- **Deleting the wrong thing.** The cleanup acts on a path string from the
  failure report. It MUST stay inside the app's staged root and MUST consult the
  loaded-dictionary set before removing a directory, or it could delete a
  sibling dictionary that shares the import folder. The existing
  `deleteDictionaryFiles` guard is the precedent to reuse rather than reinvent.
- **A failure that is not a stale file.** A transient failure (a scan interrupted
  mid-write) would be reported like any other. Deleting on request is safe
  because it is user-initiated; auto-deleting on scan would not be, so cleanup
  SHALL NOT be automatic.
