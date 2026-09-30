## ADDED Requirements

### Requirement: Recent lookups fill the candidate pane
The recent-lookups (history) surface SHALL fill the Search pane's candidate area from the top of that area down to the bottom navigation dock, rather than stopping partway, and the bottom dock SHALL remain visible. This full-height presentation SHALL apply to the history surface only: the headword-suggestion dropdown SHALL keep its bounded height.

#### Scenario: History fills the candidate area
- **WHEN** the search field is empty and the recent-lookups surface is shown
- **THEN** the list extends to the bottom of the candidate area, adjacent to the bottom navigation dock, and the dock stays visible

#### Scenario: A no-match query's history also fills the pane
- **WHEN** a typed query matches no headwords and the surface falls back to recent lookups
- **THEN** the history list fills the candidate area the same as on an empty field

#### Scenario: Suggestions keep their bounded dropdown
- **WHEN** the candidate surface is showing headword suggestions
- **THEN** it remains a bounded dropdown rather than filling the whole pane
