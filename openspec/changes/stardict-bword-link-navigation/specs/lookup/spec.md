## MODIFIED Requirements

### Requirement: In-article link navigation
The system SHALL open links within an article as in-app lookups of the linked word rather than leaving the app, and SHALL keep the user able to navigate back to the previous article. Navigation between articles SHALL be browser-like: a back path through previously opened articles and a forward path through articles the user has backed out of. Each navigation entry SHALL carry the dictionary group the article was produced in; returning or forwarding SHALL restore that group before re-rendering (falling back to "All" if the group no longer exists). A fresh lookup clears the forward path.
Link schemes a dictionary emits for in-app cross-references SHALL be recognised and resolved as lookups, regardless of which dictionary format produced them. A scheme a dictionary uses for cross-references SHALL NOT reach the article as an inert link whose tap does nothing.

#### Scenario: Tapping an article link
- **WHEN** the user taps a link inside an article
- **THEN** the app performs a lookup of the linked word within the app, in the current active group

#### Scenario: Cross-reference links from any format navigate
- **WHEN** an article produced by any supported dictionary format contains a link to another of its entries
- **THEN** tapping it performs an in-app lookup of the linked word, rather than doing nothing

#### Scenario: StarDict cross-references navigate
- **WHEN** a StarDict article contains a cross-reference link, which the StarDict format expresses with the `bword:` scheme
- **THEN** tapping it performs an in-app lookup of the linked word in the current active group

#### Scenario: Back navigation
- **WHEN** the user navigates from one article to another via links
- **THEN** the app's back action returns to the previous article and restores the dictionary group that produced it

#### Scenario: Forward navigation
- **WHEN** the user has backed out of at least one article and chooses forward
- **THEN** the app re-opens the most recently backed-out article and restores the dictionary group that produced it

#### Scenario: A fresh lookup clears forward history
- **WHEN** the user backs out of an article and then performs any fresh lookup (typed search, suggestion, history or favorites tap, or in-article link)
- **THEN** the forward path is cleared and the forward control is unavailable
