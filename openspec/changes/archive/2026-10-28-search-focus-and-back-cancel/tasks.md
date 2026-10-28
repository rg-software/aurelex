# Tasks

- [x] Focus gain re-queries suggestions (`onActiveFocusChanged` →
      `_doSuggest`, suppressed during programmatic box writes)
- [x] Concealed-article restore (`_cancelCandidates`) with the `onClosing`
      guard (Search tab, article concealed, previous article retained, no
      lookup in flight, no modal picker)
- [x] On-device verification: focus shows suggestions; Back restores the
      article with its query; Back still exits with an article shown, during
      a lookup, under a picker, or with no previous article
