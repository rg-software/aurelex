# Proposal

## Why

Refining a query after opening an article took a delete-and-retype to bring
suggestions back (suggestions fired only on text change), and tapping the
field — accidentally or to continue typing — hid the article with no way
back except a fresh lookup: Android Back exited the app. Both behaviors are
already implemented and confirmed working on-device; this change records the
intended behavior in spec.

## What Changes

- Focusing the search field re-queries suggestions for the text still in the
  box through the same path as typing: a shown article is concealed (its
  nav history retained) and the candidate surface shows headword
  suggestions — or history when the field is empty or nothing matches.
- System Back while the candidate surface is shown over a concealed article
  restores that article (its query restored in the box, no new lookup,
  history, or nav-stack change) instead of exiting the app. Back keeps its
  previous behavior everywhere else: article shown, lookup in flight, modal
  picker open, or no previous article.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `lookup`: the Headword suggestions requirement gains a focus-without-edit
  re-query and a dismiss-without-submit path that restores the concealed
  article (in-flight lookups excluded).

## Impact

- `app/main.qml` only (search-field `onActiveFocusChanged`, root
  `onClosing`, `_cancelCandidates`). No engine, boundary, patch, or
  localization changes.
