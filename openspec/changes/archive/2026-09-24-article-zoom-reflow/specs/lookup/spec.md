# Spec Delta

## ADDED Requirements

### Requirement: Article zoom reflows to the screen width
The system SHALL offer article zoom controls (zoom in, zoom out) beside the article's back/forward/star controls. Zooming in SHALL re-render the article so that text re-wraps to the viewport width: enlarged content stays fully visible on screen with no horizontal scrolling for regular article text. Zooming out SHALL likewise keep the article fitted to the screen width. The zoom level is a single global value shared by all articles (no per-word or per-dictionary zoom memory).

#### Scenario: Zooming in reflows text
- **WHEN** the user zooms in on an article using the zoom controls
- **THEN** the article's text is enlarged and re-wraps to the width of the screen so the full line is visible without horizontal panning

#### Scenario: No horizontal slider at high zoom
- **WHEN** the user zooms in on an article far past its default size
- **THEN** the article remains readable at the screen width and does not present a horizontally scrollable page

#### Scenario: Zoom applies to every article
- **WHEN** the user looks up a new headword after setting a zoom level
- **THEN** the new article renders at that same zoom level