## 1. Report model

- [ ] 1.1 Change the `scanFailures` entries from `{file}` to
  `{name, file, reason}` in `app/EngineController.hpp` / `.cpp`, keeping the
  property name and its notify signal so the QML binding stays simple.
- [ ] 1.2 Define `reason` as an enum-like set of translatable reasons rather than
  a free-form string: `couldNotLoad`, `alreadyPresent`, `nameClashWithInstalled`.
  Keep the mapping in one place so the banner never invents wording
  (design.md D4).
- [ ] 1.3 Populate `name` from the boundary's display name when the result refers
  to a dictionary that loaded or was recognised, and fall back to the file's
  basename when it does not (an unloadable source has no name).
- [ ] 1.4 Keep the headline count placeholder-substituted ("Parameterized
  messages" in `localization`) rather than concatenated.

## 2. Automatic deletion of an unloadable source

- [ ] 2.1 Delete the failing source's own file set after a scan reports it, rather
  than relying on the whole-directory sweep — this is the fix for a corrupt file
  in a folder shared with dictionaries that loaded (design.md D1).
- [ ] 2.2 Obtain the file set from the same boundary call `resolve-duplicate-dictionaries`
  adds (`gd_dict_identity`), or from the failure path's own record of the staged
  file, so the delete covers companions (`.idx`, `.dict`, `.mdd` volumes) and the
  dictionary's resource tree, not just the primary file.
- [ ] 2.3 Add a file-set delete to `app/StagedCleanup.hpp` alongside the existing
  directory delete, keeping containment and sharing decided in one place as that
  file's header intends. A file set SHALL be deletable inside a directory that a
  loaded dictionary shares; a directory SHALL still only be reclaimed when nothing
  loaded remains in it.
- [ ] 2.4 Confirm no path deletes outside the staged root, and that a sibling
  dictionary sharing the folder keeps every file it needs.
- [ ] 2.5 Report the deletion in the result row so the user knows the file is gone
  and that nothing further is needed of them.
- [ ] 2.6 Verify the existing `sweepStaleStagedDirs()` still runs and is still the
  step that reclaims the now-empty directory, rather than duplicating it.

## 3. Banner presentation

- [ ] 3.1 Replace the per-row trash glyph in `app/main.qml` with a single dismiss
  control for the whole banner, and make dismissal pure UI state — it removes the
  banner and touches no file and no dictionary (design.md D2).
- [ ] 3.2 Bound the banner's height to a fraction of the pane and move its rows
  into a scrolling `ListView`/`Flickable` within that bound, so the dictionary list
  keeps its space at any result count (design.md D5).
- [ ] 3.3 Keep the headline count always visible so scrolled-out-of-view results
  are still accounted for, and hide the banner entirely when the model is empty or
  the outcome was fully successful with nothing to act on.
- [ ] 3.4 Give each row the dictionary name (or file basename), the reason, and no
  action, and drop the old advice *"Remove it and import the folder again"* for
  the clash reason, which is untrue for it.
- [ ] 3.5 Verify the banner does not intercept or alter navigation, search, group
  or removal actions while it is showing.

## 4. Stale-result handling

- [ ] 4.1 Clear the result model when a new pick starts, before the new results are
  collected, so the banner only ever describes the most recent batch
  (design.md D3).
- [ ] 4.2 Confirm a reported clash clears once the user resolves it by removing one
  of the pair, and is not re-raised by later scans.

## 5. Accessibility and documentation

- [ ] 5.1 Set the dismiss control's `Accessible.name` / `Accessible.role`, using a
  name that refers to dismissing results rather than removing a file
  (design.md D6).
- [ ] 5.2 Update the Dicts row of the accessible-element table in `AGENTS.md`:
  replace `"Remove failed import"` with the new dismiss name and describe the
  banner as informational.
- [ ] 5.3 Update any UIAutomator / on-device test that addresses the old
  `"Remove failed import"` name, and add one that exercises the new dismiss.
- [ ] 5.4 Note in `AGENTS.md` that the banner carries no per-row destructive
  control, so a later change does not reintroduce one by habit.

## 6. Localization

- [ ] 6.1 Add the new strings (per-row reasons, the dismiss control's label, the
  revised headline) to the QML sources and run `scripts/update-translations.ps1`.
- [ ] 6.2 Translate the new catalog entries in `app/i18n/aurelex.ru.ts` and
  `aurelex.ja.ts`, and mirror them in
  `app/android/res/values-ru/strings.xml` and `values-ja/strings.xml`.
- [ ] 6.3 Recommit the compiled `app/i18n/*.qm` catalogs.
- [ ] 6.4 Verify every new message embeds its count through placeholder
  substitution so word order conforms in each language.

## 7. Verification

- [ ] 7.1 Host: a scan reporting a failure in a folder that also holds a
  dictionary that loaded — assert only the failing file set is deleted, the loaded
  dictionary still works, and its files are untouched.
- [ ] 7.2 Host: a fully successful import — assert the banner is not shown and no
  result is reported.
- [ ] 7.3 On device: corrupt one dictionary in a folder of several, import it, and
  confirm the corrupt file is gone from app-private storage, the other
  dictionaries are intact and indexed, and the row says the file was deleted.
- [ ] 7.4 On device: import a folder producing more results than fit — confirm the
  dictionary list is still visible, rows scroll, and the count is shown.
- [ ] 7.5 On device: dismiss the banner — confirm it disappears and that no file or
  dictionary changed.
- [ ] 7.6 On device: import again after a batch that reported results — confirm
  only the newest batch is shown.
- [ ] 7.7 Record the results in `docs/TESTING.md`.
