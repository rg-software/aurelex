## MODIFIED Requirements

### Requirement: The resolved theme drives all app appearance

Which theme is in effect SHALL be derived from the theme mode and the system theme, and that single resolved theme SHALL drive every part of the app's appearance together: the app chrome and controls, the system status- and navigation-bar icon contrast, the theme dictionaries render articles in, and the article currently on screen. Switching modes SHALL take effect on the article already displayed without re-running the lookup, and a dictionary article SHALL be readable in both themes.

The background of the surface that shows an article — and of the headword-suggestion and recent-lookups pane that stands in for one — SHALL be the same color as the app's background, so that no seam is visible between the two. This SHALL hold in both themes, on the article's first painted frame as well as after the theme changes, and it SHALL hold whether or not the article's own content has finished loading.

#### Scenario: All appearance follows the resolved theme
- **WHEN** the resolved theme changes, whether because the mode changed or because the system theme did
- **THEN** the app chrome, the system bar icon contrast, the dictionary rendering theme, and the open article all change to that theme together

#### Scenario: The open article switches in place
- **WHEN** the resolved theme changes while an article is displayed
- **THEN** the displayed article changes to the new theme in place without losing the looked-up word or returning to an empty article

#### Scenario: Articles are readable in either theme
- **WHEN** an article is rendered in the light theme and again in the dark theme
- **THEN** the entry's text is legible against its background in both

#### Scenario: The article surface matches the app background
- **WHEN** an article, or the candidate pane shown in its place, is displayed in either theme
- **THEN** the surface behind the content is the same color as the surrounding app background, with no visible border or change of shade where the two meet

#### Scenario: The theme change carries the surface background
- **WHEN** the resolved theme changes while an article or the candidate pane is displayed
- **THEN** the surface's background becomes the new theme's background at the same moment as the rest of the app, without the previous theme's color being left behind
