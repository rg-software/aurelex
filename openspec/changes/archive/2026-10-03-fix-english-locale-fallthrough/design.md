## Context

`QLocale()` on Android is backed by the platform's locale list, not a single
locale. Measured on a motorola ThinkPhone (Android 15) with the app's `resConfigs`
`en, ru, ja`:

| per-app locale | `QLocale().uiLanguages()` |
| --- | --- |
| `en-US` (device `ru-RU`) | `en-US,en-Latn-US,en,ru-RU,ru-Cyrl-RU,ru,ja-JP,ja-Jpan-JP,ja` |
| `ja-JP` | `ja-JP,ja-Jpan-JP,ja,ru-RU,ru-Cyrl-RU,ru,en-US,en-Latn-US,en` |
| unset (device `ru-RU`) | `ru-RU,ru-Cyrl-RU,ru,en-US,en-Latn-US,en,ja-JP,ja-Jpan-JP,ja` |

The primary locale is first; the remaining entries are the app's
resource-supported locales. The earlier `main.cpp` loop treated the whole list as
an ordered fallback chain (a reasonable reading of a desktop `uiLanguages()`),
which made an English primary resolve to the RU catalog — English has no `.qm`
by design, so the chain never terminates there.

## Goals / Non-Goals

**Goals**

- The primary UI language decides the display language; English is the terminal
  fallback for a primary language with no catalog.
- One rule for both catalog selection (`main.cpp`) and catalog-name lookup
  (`EngineController::refreshCatalogEntries`).

**Non-Goals**

- Adding an English catalog or an in-app language switcher (both remain
  deliberate non-goals of `2026-09-25-localization`).
- Rejecting non-primary languages from `uiLanguages()` generally — the reduction
  is applied at the two call sites that consume it as a preference chain.
- Declaring `android:localeConfig` (a separate, user-visible change).

## Decisions

### D1: Reduce the list to its primary entry at the call sites

Try `uiLanguages().value(0)` in full (`ru_RU`) and then its language code
(`ru`); if neither loads, install no translator. This keeps the documented
full-locale → language → English chain while removing the unintended
cross-language fall-through. It also preserves the region-variant requirement
(`pt-BR` → `pt`) because the base-code candidate is derived from the *same*
primary entry.

Alternative considered and rejected: keep iterating but stop at the first
language that has *any* catalog. That still lets a region variant of an
unknown language fall into an unrelated catalog, and it is not what "the
device's UI language preference" means.

### D2: The same reduction for catalog display names

`RemoteCatalog::Entry::nameFor()` already does the full-code → base-code
fallback *within* each entry it is given, so passing a one-element list keeps its
behaviour and its unit tests intact; only the caller changes. `CatalogTest`
continues to exercise `nameFor` with explicit lists.

### D3: Log the primary language, keep the phrase greppable

The `no matching translation catalog` wording is kept because `docs/TESTING.md`
greps for it; the message now appends the primary language so a test can tell
"English by design" from "locale never applied".

## Risks / Trade-offs

- **A genuine multi-preference device no longer chains to its second language.**
  A user who prefers `fi` and lists `ru` second now sees English, where before
  they saw Russian. This is the spec's intent ("unsupported UI language →
  English") and the cost of not being able to distinguish real preferences from
  the resource-locale tail that Android appends. Accepted.
- **Untested branches for other Qt/Android combinations.** The reduction is a
  no-op on any platform whose `uiLanguages()` returns only real preferences
  (desktop), because the first entry is then the preference itself.
- **Observable log wording changed** → `docs/TESTING.md` row 52 and the
  `docs/DEVELOPMENT.md` check text are updated in the same change.

## Migration Plan

Single app-side fix; no data migration, no persisted state. Verify on device:
`en-US` → English, `ja-JP` → Japanese, device `ru-RU` unset → Russian.

## Open Questions

None.
