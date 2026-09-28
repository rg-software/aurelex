## 1. Root cause confirmation

- [x] 1.1 Confirm `gd_group_info` returns the built-in group's name as a C literal (`carve/gd_boundary.cc:1036`) and that the carve loads no translation catalog, so `engine.groups[0].name` is English in every locale
- [x] 1.2 Confirm `EngineController::groupName()`'s fallback is `tr("All")` (`app/EngineController.cpp:1788`) and that `aurelex_ru.qm` carries `Все` for it, so the two naming paths disagree
- [x] 1.3 Confirm the reproduction: a history row whose `group` id is absent from `engine.groups` renders the `tr("All")` fallback, while the Groups list renders the boundary's `"All"` — same group, two names in one UI
- [x] 1.4 Confirm the dangling id is real and not a lookup bug: `deleteGroup` (`app/EngineController.cpp:933`) prunes neither history nor favorites, and `loadHistory`/`loadFavorites` only default a missing key to `0`
- [x] 1.5 Confirm the ordering constraint in design D4: `loadHistory()`/`loadFavorites()` run at `app/EngineController.cpp:619-620` before `runScan()` populates `m_groups` asynchronously, so a load-time re-point would re-point every entry
- [x] 1.6 Confirm `lookupInGroupWithSwitch` (`app/EngineController.cpp:1476`) already falls back to group 0 on a dangling id, which is why tapping a mislabelled row looks like it worked

## 2. Group label mapping (design D1, D2)

- [x] 2.1 Add a single QML helper on the root object that maps a group id to its display label: id `0` returns `qsTr("All")`, any other id returns the stored `engine.groups[i].name` for the matching id
- [x] 2.2 Route the Groups list row label (`app/main.qml:1890`) through the helper instead of reading `groupData.name` directly
- [x] 2.3 Route the `Select group` picker row label (`app/main.qml:2816`) through the helper
- [x] 2.4 Route the Search group-scope button label (`app/main.qml:891-897`) through the helper, keeping its existing fall-back-to-first-group behavior
- [x] 2.5 Route the FTS group-scope button label (`app/main.qml:2632-2636`) through the helper
- [x] 2.6 Route the history row group subtitle (`app/main.qml:373`) through the helper instead of `engine.groupName(...)`
- [x] 2.7 Leave the `Accessible.name` bindings on the group rows (`app/main.qml:1883`) and picker rows (`app/main.qml:2819`) on the invariant English value — `"All"` for the built-in group, the stored name for a user group (design D2)
- [x] 2.8 Confirm no group-name surface still reads `engine.groups[i].name` or `engine.groupName(...)` for a visible label, and that the count of `qsTr` call sites for the built-in group is exactly one
- [x] 2.9 Route the Favorites list row subtitle (`app/main.qml:2379`) through the helper — it read `engine.groupName(...)`, the same defect as the history row, and was the last QML caller of `groupName`
- [x] 2.10 Route the membership editor header (`app/main.qml:2123`) through the helper by group id, so opening the "All" group no longer shows its untranslated engine name (the rename prefill keeps the raw stored name)

## 3. Re-point entries whose group is gone (design D3, D4)

- [x] 3.1 Add a private `EngineController` pass that rewrites every history and favorites entry whose `group` id is absent from `m_groups` to id `0`, keeping the word, then persists both files
- [x] 3.2 Make the pass a no-op when `m_groups` is empty, so a transient empty list mid-reload cannot re-point every entry (design D4)
- [x] 3.3 Never re-point id `0` itself, and log the count of rewritten entries under the existing `[aurelex]` prefix so the repair is observable in logcat
- [x] 3.4 Invoke the pass from `EngineController::setGroups` (`app/EngineController.cpp:193`) once `m_groups` is populated
- [x] 3.5 Invoke the pass from `deleteGroup`'s success path (`app/EngineController.cpp:943`) so the history panel is correct immediately, not only after a restart
- [x] 3.6 Confirm the pass is idempotent: a second run after the first finds nothing to re-point and does not rewrite the files
- [x] 3.7 Reduce `groupName()`'s fallback to the invariant literal `"All"` (`app/EngineController.cpp:1788`) so any future caller agrees with the rest of the UI instead of introducing a third string (design D5)
- [x] 3.8 Confirm `recordHistory` (`app/EngineController.cpp:1979`) and the favorites toggle are unaffected, and that `_isFavorite` in `app/main.qml:551` still matches a re-pointed entry after the star is tapped

## 4. Localization

- [x] 4.1 Run `scripts/update-translations.ps1` and confirm the new `qsTr("All")` is extracted into `app/i18n/aurelex.ru.ts` and `app/i18n/aurelex.ja.ts`
- [x] 4.2 Confirm the Russian entry resolves to `Все` in the `.ts` and that the `<source>` text is the unchanged `All` — never edit a `<source>` by hand (AGENTS.md localization rule)
- [x] 4.3 Enter the Japanese translation for `All` in `app/i18n/aurelex.ja.ts`
- [x] 4.4 Recompile and recommit `app/i18n/aurelex_ru.qm` and `app/i18n/aurelex_ja.qm`
- [x] 4.5 Confirm no `app/android/res/values*/strings.xml` change is needed (the group name is Qt-side, not an Android resource)

## 5. Verification

- [ ] 5.1 In an English build, confirm all six surfaces show `All` and the Groups list, picker, and both scope buttons are unchanged from before the change **Deferred** at archive time (2026-09-28) - English-build verification is tracked with the separate En/Ja builds goal.
- [ ] 5.2 On a Russian-locale device, confirm the Groups list, the picker, both scope buttons, and a history row all read `Все` — no surface left showing `All` **Partly verified** at archive time (2026-09-28) - on a ru-RU device the Groups row, the Search scope button and history rows read "Все" (row content-desc stayed "All"); the picker and FTS button were not opened separately, though both share the same _groupLabel path.
- [ ] 5.3 On a Japanese-locale device, confirm the built-in group reads the Japanese string, and that a user-created group still shows the name the user typed, untranslated **Deferred** at archive time (2026-09-28) - Japanese-build verification is tracked with the separate En/Ja builds goal.
- [x] 5.4 In an English build, confirm the built-in group row and picker row still expose `content-desc` `All`, so the `docs/TESTING.md` rows 11 and 13 addressing works unchanged
- [ ] 5.5 Record a lookup in a group, delete that group, and confirm the history row's label becomes the built-in group's name immediately and the word is still there **Verified via seed** at archive time (2026-09-28) - the load-time re-point was confirmed on device with a seeded dangling group id (log + persisted files); the delete-button trigger was not exercised separately.
- [ ] 5.6 Tap that re-pointed row and confirm the lookup runs in the group the row now names, and that a headword present only in a dictionary outside the deleted group now resolves **Not verified** at archive time (2026-09-28) - the re-point repair was confirmed on device, but a tap-through with a headword outside the deleted group was not run.
- [x] 5.7 Restart the app and confirm the re-pointed entries survive (the rewrite was persisted) and the pass logs zero further rewrites
- [x] 5.8 Confirm `carve/`, `patches/`, and the CI smoke test are untouched — this change is app-side only
