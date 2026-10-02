## MODIFIED Requirements

### Requirement: Article zoom reflows to the screen width
The system SHALL offer article zoom controls (zoom in, zoom out) beside the article's back/forward/star controls. Zooming SHALL enlarge article text that inherits the article's root text size, and the enlarged content SHALL re-wrap to the viewport width so that it stays fully visible with no horizontal scrolling. Zooming out SHALL likewise keep the article fitted to the screen width. The zoom level is a single global value shared by all articles (no per-word or per-dictionary zoom memory).

Zoom SHALL scale text the article renders at its root text size. Text and elements whose size a dictionary's own bundled stylesheet sets in an absolute unit (such as px or pt) SHALL NOT be scaled by zoom, because such a declaration overrides the root size for the content it matches; the app SHALL NOT override a dictionary's own typographic declarations in order to force them to scale. A dictionary that sets absolute sizes therefore renders some of its content at the same size at every zoom level, and this is a property of that dictionary, not of its file format.

#### Scenario: Zooming in reflows text
- **WHEN** the user zooms in on an article using the zoom controls
- **THEN** the article's text is enlarged and re-wraps to the width of the screen so the full line is visible without horizontal panning

#### Scenario: No horizontal slider at high zoom
- **WHEN** the user zooms in on an article far past its default size
- **THEN** the article remains readable at the screen width and does not present a horizontally scrollable page

#### Scenario: Zoom applies to every article
- **WHEN** the user looks up a new headword after setting a zoom level
- **THEN** the new article renders at that same zoom level

#### Scenario: A dictionary that pins absolute text sizes keeps them
- **WHEN** the user zooms in or out on an article whose dictionary sets its entry text to an absolute size in its own stylesheet
- **THEN** that dictionary's text stays at the size the dictionary specified while the rest of the article surface scales, and the article remains legible and free of horizontal scrolling at both extremes

#### Scenario: The zoom limit is per-dictionary, not per-format
- **WHEN** an article is rendered from a dictionary that does not set absolute text sizes, in the same format as one that does
- **THEN** that article's text scales with zoom normally
