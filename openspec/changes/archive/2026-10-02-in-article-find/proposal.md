## Why

A rendered article combines the entries of every matching dictionary into one
long page, but once it is open there is no way to locate a word **within** it.
The only search field on the Search tab (`"Search dictionaries"`) looks words up
in the engine; it cannot search the page that is already on screen. Readers fall
back to manually scrolling a multi-dictionary article to find a term — exactly
the case where a find-in-page bar earns its place. The article toolbar has no
room for a permanent extra row, so the feature has to reuse it.

## What Changes

- Add a **find-in-page mode** to the inline article toolbar. A magnifier icon
  opens it; the same control becomes an **X** that closes it and restores the
  back / forward / favorite / zoom controls.
- The find bar is drawn **in place of the toolbar in the same 40 px row**, so
  opening and closing it does not resize the article surface.
- The find bar contains: a compact query field, a `n / total` match counter,
  and previous / next match buttons. Pressing Enter moves to the next match;
  navigation wraps at both ends.
- Matching text is highlighted in the article; the active match is visually
  distinct and is scrolled into view.
- Find is available only while an article is open. It is **cleared when a new
  article loads** and **re-applied after a reload** that happens while find is
  open (for example the IME resizing the window, rotation, or navigation).
- Text inside a dictionary's collapsed optional (`[*]…[/opt]`) zones is **not**
  matched — find locates what is visible.
- Deferred to a later change: whole-word and case-sensitivity toggles.
- New accessible names for every new control, plus RU/JA translations.

## Capabilities

### New Capabilities

<!-- none -->

### Modified Capabilities

- `lookup`: adds an in-article find-in-page requirement — the article toolbar's
  find mode, its controls, highlight and scroll behavior, and its lifecycle
  (available only with an open article, cleared on a new article, re-applied
  after a reload).

## Impact

- `app/main.qml`: the `inlineArticleToolbar` row gains a find mode (new QML
  state, a compact `TextField`, counter, previous/next, magnifier/X toggle), and
  new `runJavaScript` calls drive highlight / next / previous / count against the
  live article document; the article reload path re-applies an active find.
- Article highlighting script: a find controller (vendored mark.js or a small
  hand-rolled highlighter) served from `app/android/assets/scripts/`.
- `app/EngineController.cpp` (`rewriteArticleUrls`): the current strip-list
  removes `mark.min.js` / `mark.js`; the chosen highlighter must be made
  available to the article document.
- Localization: new user-visible strings in `app/i18n/*.ts` (+ compiled `.qm`)
  and `app/android/res/values-ru/`, `values-ja/` in the same change.
- Accessibility: new `Accessible.name` entries recorded in `AGENTS.md`.
