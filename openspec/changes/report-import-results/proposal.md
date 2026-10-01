## Why

Import currently reports itself through a red banner in the Dictionaries pane whose
rows carry a trash glyph (`main.qml:1712-1792`). That design carries two defects
and one contract problem.

**The trash is a data-destroying control wearing a notification's clothes.**
`removeScanFailure()` → `removeStagedDirIfUnused()` →
`QDir::removeRecursively()` (`EngineController.cpp:1086`). The row disappears
*because* the directory was deleted. Every row therefore offers a one-tap,
unconfirmed permanent delete for something that is, first and foremost, a message.

**That delete silently fails for the case it is most needed for.**
`removeStagedDirIfUnused()` refuses when the directory still holds a loaded
dictionary (`EngineController.cpp:1077-1080`, logging *"left in place (shared or
refused)"*). When one file in a folder of twenty is corrupt, the folder is used by
the nineteen good dictionaries — so `sweepStaleStagedDirs()` skips it *and* the
trash refuses. That corrupt file sits on disk, reported, and is **not deletable
through the UI at all**. The one-click cleanup the banner appears to offer does
nothing exactly when there is something to clean up.

**The banner has no capacity.** It is `implicitHeight: failuresCol.implicitHeight + 12`
in a `ColumnLayout` above a `ListView` with `Layout.fillHeight: true`. Failures
push the dictionary list off-screen, so the user cannot see the banner and the
dictionaries together — which is precisely what they need in order to notice two
identically-named dictionaries and act on one.

## What Changes

- **The banner becomes purely informational.** It reports what an import did and
  did not do. It contains no control that deletes anything, because by the time
  it is visible there is nothing left to delete.
- **Broken sources are deleted automatically, at file-set granularity.** A corrupt
  or unreadable dictionary has no value to the user and cannot become valid, so
  its files go without a prompt. Deleting the individual file set rather than the
  whole directory is what makes this work in a folder shared with good
  dictionaries, which is the bug above.
- **A row names the dictionary and the reason.** The current row shows a basename
  inside an opaque hashed directory, which is unreadable and is worst precisely in
  the cases that matter — a duplicate or a clash has a dictionary *name*, and that
  is what the user recognises.
- **The banner grows to fit its content without squeezing the dictionary list.**
  Its height is capped at a fraction of the pane and its rows scroll internally,
  with the count always visible in the header. Any number of results is readable,
  and the dictionaries stay on screen underneath at all times.
- **One dismiss control removes the banner**, and starting another import clears
  stale results first, so the banner never describes a batch that is no longer the
  most recent one. The user otherwise uses the app as usual — the report is
  something to read and dismiss, not a mode.

The user resolves anything actionable in the Dictionaries list itself, which is
where a dictionary can be selected and removed through the existing multi-select
path with its confirmation.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `dictionary-management`: the import-results banner becomes informational only,
  carries per-row reasons, is bounded in height with internal scrolling, and gains
  a dismiss that also fires when a new import starts; automatic deletion of broken
  sources becomes a requirement, at file-set granularity.

`localization` is deliberately **not** modified. Its existing requirements already
cover this: "No inline user-visible strings" names status banners explicitly, and
"Accessibility test identifiers remain invariant" already requires the dismiss
control's English name to be documented in `AGENTS.md`. The work is obligation
under those requirements, not a change to them, so no delta is warranted.

One existing requirement does constrain the implementation: "Parameterized
messages" requires the result count to be substituted into a translated template
rather than concatenated, so the banner headline stays a placeholder-based
message.

## Impact

- **`app/main.qml`** — the banner block: bounded height, an internal scrolling
  list, a new model shape, and a dismiss control replacing the per-row glyph. Its
  accessible name changes from `"Remove failed import"` to a dismiss name, so
  **`AGENTS.md`'s accessible-element table and any UIAutomator test that addresses
  it must be updated in the same change.**
- **`app/EngineController.cpp`** — the report model becomes
  `{name, file, reason}`; automatic deletion of a broken source's file set;
  `removeScanFailure()`'s delete path is removed, since deletion is now automatic
  and the dismiss is pure UI state.
- **`app/StagedCleanup.hpp`** — the containment and sharing guards are reused as
  they are. Deleting a file set inside a shared directory is new, so the guard
  needs to express "delete these files" as well as "delete this directory".
- **`app/i18n/*.ts` / `app/i18n/*.qm`, `app/android/res/values-ru/`, `values-ja/`**
  — new and changed strings, via `scripts/update-translations.ps1`.
- **`openspec/changes/resolve-duplicate-dictionaries`** — depends on this change
  for the surface it reports a rejected dictionary into. This change lands first.

## Risks / Trade-offs

- **Rows are informational, so a user who ignores the banner may believe an
  import fully succeeded.** → The reason text is explicit about what was not
  imported and why, and a fresh import clears stale rows rather than adding to
  them, so what is on screen always describes the latest batch.
- **Deleting broken sources without asking is irreversible.** → They are corrupt
  or unreadable and cannot become valid; nothing the user wants is lost. This is
  the one automatic deletion, and it is justified by the file having no value.
- **Losing the per-row trash loses a cleanup path for a genuinely stranded
  directory** — one that no scan reported and no dictionary uses. → The existing
  sweep already handles reported failures; a directory in that state is outside
  this change's scope, and the dismiss still removes the banner so the app is not
  left showing stale information.
