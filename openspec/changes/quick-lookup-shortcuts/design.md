## Context

Aurelex already has a single-activity Compose app where `MainActivity`
runs lookups off a ViewModel, and an existing intent-routing seam
(`handleLookupIntent` in `MainActivity.kt`) that turns external intents
(share/`ACTION_VIEW`) into lookups. Lookups route through `MainViewModel.lookup`
and land on the article screen regardless of entry point (see the `usability-utilities`
spec, "External lookup entry points"). The process model is fixed: the Qt engine
lives in a separate `:engine` process behind `EngineClient`; the UI process is
pure Kotlin/Compose. This change adds two Android-standard launcher surfaces on
top of that seam — no engine or boundary involvement.

## Goals / Non-Goals

**Goals**
- A Quick Settings tile that looks up the current clipboard text.
- A resizable home-screen widget with a search field that looks up the entered word.
- Both surfaces reach the article via the existing `MainViewModel.lookup` flow
  so active-group semantics, history recording, and not-found handling "just work".
- Pure Kotlin/manifest/resources; no changes under `engine/`, `patches/`, or the `gd_*` API.

**Non-Goals**
- No clipboard-monitor or "auto lookup on copy" behavior.
- No per-user widget configuration (one fixed widget, system-resizable).
- No FTS, no changes to how the engine builds articles.
- No support for non-clipboard text in the tile (it is deliberately clipboard-only).

## Decisions

### D1: Clipboard is read by the foreground activity, not by the tile service
Android 10+ restricts background apps from reading the clipboard. A `TileService`
runs while the user is in the Quick Settings shade, where the app is usually
background. Reading the clipboard there is unreliable and version-dependent.

Chosen approach: the tile's `onClick` fires `startActivityAndCollapse()` with an
intent carrying action `aurelex.android.action.LOOKUP_CLIPBOARD` (defined as a
const string). `MainActivity` is already `singleTop`/`launchMode`-stable and
handles both cold and warm intent delivery (`onCreate` + `onNewIntent`). When the
intent arrives, the app is foreground, so `clipboardText(context)` reads the
clipboard deterministically, then `viewModel.lookup(text)` runs.

Alternatives: reading the clipboard inside `TileService.onClick()` (rejected:
background clipboard access is unreliable on modern Android); a listening
`ClipboardManager` service (rejected: Non-Goal, more moving parts, battery cost).

### D2: Widget search field confirmation fires an intent to the activity
`AppWidgetProvider` renders RemoteViews. Widget text capture has a known
pattern: the field is an `EditText` with `android:imeOptions="actionSearch"`;
the widget wires a PendingIntent (via `RemoteViews.setOnClickPendingIntent`) on
the search/GO action carrying the entered text as an `Intent.EXTRA_TEXT`-style
extra in a custom action `aurelex.android.action.SEARCH`. The pending intent
targets `MainActivity`; `handleLookupIntent` gains a branch for that action that
looks up the extra directly.

Tapping the field (without confirming) fires the same action with an empty word,
which routes to "open search screen" — matching the spec scenario.

Alternatives: a widget that only launches the app (rejected: the spec requires
in-widget search); a dedicated receiver broadcast (rejected: an activity target
reuses the existing single-activity + intent path with no extra component).

### D3: Same intent-seam reuse for both surfaces
Both the tile and the widget funnel into `handleLookupIntent`. This keeps the
"entry point" contract in one place (matching how share/`ACTION_VIEW` already
work), so the active group applies automatically (see `usability-utilities`
"External lookup entry points" + the `launcher-shortcuts` "No dictionary
interference" requirement).

### D4: Widget is fixed content, system-resizable
One `appwidget-provider` with `resizeMode="horizontal|vertical"` and a sensible
`minWidth`/`minHeight`. The layout is a single search field (edit text + hint).
No configuration activity (`configure` absent) — matches the "one fixed size"
decision. Icons for the tile and widget are simple vector drawables reused from
the existing drawable set where possible.

## Risks / Trade-offs

- [EditText in RemoteViews can be finicky: some launchers deliver the text
  intent inconsistently on older OS/launcher combos.] → Mitigation: the same
  action with an empty word opens the search screen (still useful); verify on
  the ThinkPhone before release, and keep the field as a fallback that drops
  the user into in-app search.
- [Quick Settings tiles are user-toggleable; a tile can be hidden or removed,
  so discoverability varies by launcher/OS.] → Mitigation: rely on the system's
  standard tile onboarding; document in release notes. Behavior, not presence,
  is what the specs pin down.
- [Widget text needs `IME_ACTION_SEARCH` wiring that a few launchers provide
  different affordances for.] → Mitigation: task list includes on-device
  validation for widget submit + tile clipboard lookup before review.

## Migration Plan

No migration: this adds new declarative manifest entries and two new components,
no existing behavior changes. Rollback is removing the manifest entries /
classes. Widgets/tiles added by users disappear from their shelf if the app is
uninstalled, standard Android behavior. No state or persisted schema changes.

## Open Questions

None — deferrable unknowns are handled by the mitigation above and on-device
verification tasks.