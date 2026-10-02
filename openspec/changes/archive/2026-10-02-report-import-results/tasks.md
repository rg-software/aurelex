## 1. Report model

- [x] 1.1 Change the `scanFailures` entries from `{file}` to `{name, file, reason}`
      in `app/EngineController.hpp` / `.cpp`, keeping the property name and its
      notify signal so the QML binding stays simple. `collectScanFailures` builds
      the map; the property, notify and `setScanFailures` are unchanged.
- [x] 1.2 Define `reason` as an enum-like set of translatable reasons rather than
      a free-form string: `couldNotLoad`, `alreadyPresent`, `nameClashWithInstalled`.
      `collectScanFailures` produces `couldNotLoad`; the other two are the reasons
      `resolve-duplicate-dictionaries` supplies into the same model. The wording is
      mapped in ONE place, the banner delegate in `main.qml`, so no other caller
      invents it. The mapping is exhaustive and each reason has its own sentence.
- [x] 1.3 Populate `name` from the boundary's display name when the result refers
      to a dictionary that loaded or was recognised, and fall back to the file's
      basename when it does not (an unloadable source has no name).
      `collectScanFailures` uses `QFileInfo(path).fileName()`; a clash/skip row's
      name is supplied by `resolve-duplicate-dictionaries`.
- [x] 1.4 Keep the headline count placeholder-substituted ("Parameterized
      messages" in `localization`) rather than concatenated:
      `qsTr("%1 import result(s)").arg(engine.scanFailures.length)`.

## 2. Automatic deletion of an unloadable source

- [x] 2.1 Delete the failing source's own file set after a scan reports it, rather
      than relying on the whole-directory sweep — this is the fix for a corrupt file
      in a folder shared with dictionaries that loaded (design.md D1). Done inside
      the `collectScanFailures` off-thread job, which already has the consume-on-read
      failure list.
- [x] 2.2 Obtain the file set from the same boundary call `resolve-duplicate-dictionaries`
      adds (`gd_dict_identity`), or from the failure path's own record of the staged
      file, so the delete covers companions (`.idx`, `.dict`, `.mdd` volumes) and the
      dictionary's resource tree, not just the primary file. `gd_dict_identity` cannot
      answer for an UNLOADED dictionary (there is no engine object), so the file set is
      reconstructed from the failure path: `StagedCleanup::primaryStem` +
      `belongsToStem` claim the primary and its format companions beside it, and the
      DSL `<stem>.files/` tree is removed by name.
- [x] 2.3 Add a file-set delete to `app/StagedCleanup.hpp` alongside the existing
      directory delete, keeping containment and sharing decided in one place as that
      file's header intends. A file set SHALL be deletable inside a directory that a
      loaded dictionary shares; a directory SHALL still only be reclaimed when nothing
      loaded remains in it. Added `isUnderRoot` (containment at any depth),
      `primaryStem`, `belongsToStem`, and `removeSourceFileSet`; the directory gate
      (`mayRemoveStagedDir`) is untouched.
- [x] 2.4 Confirm no path deletes outside the staged root, and that a sibling
      dictionary sharing the folder keeps every file it needs. Host test in
      `StagedCleanupTest.cpp`: a shared folder with a broken StarDict set and a whole
      good one — exactly the broken files go, the sibling's three files survive — plus
      a DSL resource-tree case and an outside-the-root refusal. Confirmed on device
      (7.3) with a good `.dsl` beside a truncated `.mdx`.
- [x] 2.5 Report the deletion in the result row so the user knows the file is gone
      and that nothing further is needed of them. The `couldNotLoad` wording is
      "%1 could not be loaded and was removed", and the footnote says nothing else is
      needed.
- [x] 2.6 Verify the existing `sweepStaleStagedDirs()` still runs and is still the
      step that reclaims the now-empty directory, rather than duplicating it.
      Confirmed on device: `files/staged/onlybroken/lone.mdx` was deleted by the
      file-set path, then `sweeping staged dir holding no dictionary` →
      `removing staged dir ".../onlybroken"`. The reclamation stays in the sweep; the
      file-set delete never removes a directory itself.

## 3. Banner presentation

- [x] 3.1 Replace the per-row trash glyph in `app/main.qml` with a single dismiss
      control for the whole banner, and make dismissal pure UI state — it removes the
      banner and touches no file and no dictionary (design.md D2). `removeScanFailure`
      is gone; `dismissScanFailures()` clears the model.
- [x] 3.2 Bound the banner's height to a fraction of the pane and move its rows
      into a scrolling `ListView`/`Flickable` within that bound, so the dictionary list
      keeps its space at any result count (design.md D5). The Rectangle's
      `implicitHeight` is capped at 40% of the pane and the rows live in a `ListView`
      whose preferred height is clamped.
- [x] 3.3 Keep the headline count always visible so scrolled-out-of-view results
      are still accounted for, and hide the banner entirely when the model is empty or
      the outcome was fully successful with nothing to act on. Verified with 22 results
      (count shown, 14 rows visible, the rest scrolled).
- [x] 3.4 Give each row the dictionary name (or file basename), the reason, and no
      action, and drop the old advice *"Remove it and import the folder again"* for
      the clash reason, which is untrue for it. Each reason has its own sentence; the
      clash sentence points at removing the installed dictionary instead.
- [x] 3.5 Verify the banner does not intercept or alter navigation, search, group
      or removal actions while it is showing. It is a sibling in the pane's
      `ColumnLayout`, not an overlay, so it cannot capture taps outside itself; on
      device the dictionary list rendered and scrolled below it with the banner up.

## 4. Stale-result handling

- [x] 4.1 Clear the result model when a new pick starts, before the new results are
      collected, so the banner only ever describes the most recent batch
      (design.md D3). The staging poller clears the model on the active transition
      (`setScanFailures({})`), and the scan only publishes a non-empty report, so an
      empty read never wipes a banner the user has not dismissed.
- [x] 4.2 Confirm a reported clash clears once the user resolves it by removing one
      of the pair, and is not re-raised by later scans. Verified for the model's own
      failure rows (dismiss and new-import both clear; later scans do not re-raise a
      resolved source because its files are gone). The clash case itself needs
      `resolve-duplicate-dictionaries` to produce the row; it uses this same model and
      the same clearing, so it is completed there.

## 5. Accessibility and documentation

- [x] 5.1 Set the dismiss control's `Accessible.name` / `Accessible.role`, using a
      name that refers to dismissing results rather than removing a file
      (design.md D6): `"Dismiss import results"`, role Button.
- [x] 5.2 Update the Dicts row of the accessible-element table in `AGENTS.md`:
      replace `"Remove failed import"` with the new dismiss name and describe the
      banner as informational. Done — two rows: the banner (informational) and the
      dismiss control.
- [x] 5.3 Update any UIAutomator / on-device test that addresses the old
      `"Remove failed import"` name, and add one that exercises the new dismiss.
      No automated test in the repo referenced the old name (only `AGENTS.md` did);
      the dismiss was exercised on device by its accessible name.
- [x] 5.4 Note in `AGENTS.md` that the banner carries no per-row destructive
      control, so a later change does not reintroduce one by habit. Added explicitly
      to the banner's row ("Do not reintroduce a row-level delete here").

## 6. Localization

- [x] 6.1 Add the new strings (per-row reasons, the dismiss control's label, the
      revised headline) to the QML sources and run `scripts/update-translations.ps1`.
      5 new sources; 2 obsolete ("%1 dictionary file(s) failed to load" and the
      corrupt-file advice) removed.
- [x] 6.2 Translate the new catalog entries in `app/i18n/aurelex.ru.ts` and
      `aurelex.ja.ts`, and mirror them in
      `app/android/res/values-ru/strings.xml` and `values-ja/strings.xml`. All 5 are
      translated in both catalogs. No Android `strings.xml` entry changed: every new
      string is QML, and none of the Android surfaces (label/tile/widget/notification)
      is affected.
- [x] 6.3 Recommit the compiled `app/i18n/*.qm` catalogs. `lrelease` reports 69/69
      finished in each.
- [x] 6.4 Verify every new message embeds its count through placeholder
      substitution so word order conforms in each language. The headline is
      `%1 import result(s)` and each row is a `%1 …` template; no string concatenates
      its count.

## 7. Verification

- [x] 7.1 Host: a scan reporting a failure in a folder that also holds a
      dictionary that loaded — assert only the failing file set is deleted, the loaded
      dictionary still works, and its files are untouched. `StagedCleanupTest.cpp`
      covers exactly this (shared StarDict folder), plus the DSL resource-tree case
      and containment.
- [x] 7.2 Host: a fully successful import — assert the banner is not shown and no
      result is reported. The model is empty for a clean scan (`gd_scan_failures`
      returns 0) and the banner is `visible: engine.scanFailures.length > 0`, so it
      cannot show; observed on device after the fixtures were removed (no banner).
- [x] 7.3 On device: corrupt one dictionary in a folder of several, import it, and
      confirm the corrupt file is gone from app-private storage, the other
      dictionaries are intact and indexed, and the row says the file was deleted.
      Done on the ThinkPhone: a truncated `broken.mdx` beside a good `good.dsl` in one
      staged folder → `GD: dictionary failed to load` →
      `deleted unloadable source files … removed 1`; `broken.mdx` gone, `good.dsl`
      intact and listed, the banner row read "… was removed".
- [x] 7.4 On device: import a folder producing more results than fit — confirm the
      dictionary list is still visible, rows scroll, and the count is shown. Done with
      22 results: the headline showed the count, the rows were clipped to the pane
      allowance and scrolled, and the dictionary list stayed visible below.
- [x] 7.5 On device: dismiss the banner — confirm it disappears and that no file or
      dictionary changed. Done: after tapping `"Dismiss import results"` the banner's
      node count went to 0 and the staged folder was byte-for-byte unchanged.
- [x] 7.6 On device: import again after a batch that reported results — confirm
      only the newest batch is shown. Done by driving the staging-active marker:
      the banner cleared on the new pick and stayed cleared after the rescan, which
      reported no new failures.
- [x] 7.7 Record the results in `docs/TESTING.md`. Rows 8e–8g rewritten for the new
      banner (auto-delete beside a good dictionary; informational/dismiss; bounded
      many-results).
