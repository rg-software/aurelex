# Spec Delta

## ADDED Requirements

### Requirement: Inline article surface persistence
The inline article surface on the Search tab SHALL persist across Search-tab leave/return and across group-picker open/close: its native surface and document SHALL be retained (parked offscreen, clipped by the window) rather than destroyed and recreated, and returning to the Search tab with an article showing SHALL restore that article and its scroll position without a visible flash or reload. When no article is showing, returning SHALL refocus the search field and re-query suggestions for the typed text.

#### Scenario: Article survives a tab round trip
- **WHEN** the user leaves the Search tab with an article showing and returns
- **THEN** the same article is shown with its scroll position preserved and no visible flash or reload

#### Scenario: Article survives a picker round trip
- **WHEN** the user opens the group picker with an article showing and closes it
- **THEN** the article remains shown with its scroll position preserved

#### Scenario: No article restores suggestions on return
- **WHEN** the user leaves the Search tab with no article showing and returns
- **THEN** the search field is refocused and suggestions are re-queried for the typed text