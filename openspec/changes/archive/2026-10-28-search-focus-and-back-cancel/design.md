# Design

## Context

See proposal.md (Why). The Search pane is a QML `TextField` plus an inline
native WebView that renders both articles and the suggestion/history overlay
(QML items cannot stack above Android's native WebView surface). Suggestions
fired only on `displayTextChanged`; concealing an article
(`_hideInlineArticle`) already retained `currentWord`/`currentHtml`/nav
stacks. Verified on-device: the Android back press arrives as a window
close event.

## Goals / Non-Goals

- Goals: focus re-query through the typing path; Back-cancel restores the
  concealed article with no lookup, history, or nav change; Back keeps its
  prior behavior everywhere else.
- Non-Goals: keyboard visibility or IME behavior; cancelling an in-flight
  lookup (its reply still wins); any cancel affordance beyond system Back;
  engine, boundary, patch, or localization changes.

## Decisions

- Focus gain calls `_doSuggest` (guarded by `_suppressSuggest`) rather than
  a new path: identical semantics to typing (conceal + suggest, history
  fallback on empty/no-match), no new surface states. Programmatic box
  writes (Back/Forward restore, clipboard paste, group flows) set the guard
  so they never re-query.
- Cancel rejects the root `onClosing` event rather than BackHandler /
  Shortcut / Java `onBackPressed`: verified on-device that this Qt kit
  ships no `BackHandler` type (fatal QML load), a `Shortcut` on
  `StandardKey.Back` never fires, and a Java `onBackPressed` override is
  never called (the platform dispatcher finishes the activity). `onClosing`
  fires with full QML state, so the guard is a plain condition and the
  restore runs synchronously on the Qt thread.
- Restore flips the surface back (hide overlay, restore box text under the
  guard, `inlineArticle = true`, blur, restart the article load timer):
  the retained HTML re-renders, so no re-lookup, and nav history is
  untouched.
- Cancel stays disabled while a lookup is in flight or a modal picker is
  open: the in-flight reply keeps its precedence, and the picker owns Back.

## Risks / Trade-offs

- [Risk] An accidental focus hides the article the user was reading →
  Mitigation: Back restores it losslessly (this change); typing over an
  article already behaved this way.
- [Risk] `onClosing` also fires for non-Back closes → Mitigation: the
  handler only rejects the close when the cancellable condition holds; all
  other closes proceed unchanged.
- [Risk] With the keyboard open, the first Back still only dismisses the
  keyboard → Accepted as unchanged prior behavior; the next press cancels.

## Migration Plan

QML-only and backward compatible; rollback is reverting the `app/main.qml`
hunks. No data, settings, or catalog migration.

## Open Questions

None — the behavior was verified on-device during the experiment.
