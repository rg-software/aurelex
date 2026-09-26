## ADDED Requirements

### Requirement: Article hidden content toggle
The system SHALL render dictionary content that a dictionary's markup marks as hidden (for example the DSL `[*]…[/opt]` optional zone) collapsed and out of view by default, behind a single tappable control placed in the article, and the user SHALL be able to reveal that content and hide it again. No content the dictionary chose to hide SHALL be permanently unreachable. The control SHALL be an icon (no text label) and SHALL be rendered at a size and position that leaves it tappable on a touch screen. Hidden content SHALL stay collapsed again when the article is re-rendered, so the hidden state is never sticky across articles.

Toggling hidden content SHALL NOT change how the rest of the article behaves: links, audio controls, and embedded resources inside revealed hidden content SHALL behave exactly as they do in ordinary article content, and a dictionary entry that contains no hidden content SHALL show no control and SHALL render exactly as before.

#### Scenario: Hidden content starts collapsed
- **WHEN** an article is rendered for a headword whose dictionary entry contains hidden content
- **THEN** the hidden content is not visible and a tappable control for it is present in the article

#### Scenario: Tapping the control reveals the hidden content
- **WHEN** the user taps the control
- **THEN** the hidden content becomes visible in place and the control reflects the now-revealed state

#### Scenario: Tapping the control again re-hides the content
- **WHEN** the user taps the control a second time after revealing the hidden content
- **THEN** the hidden content is hidden again and the control reflects the now-hidden state

#### Scenario: Re-rendering the article restores the collapsed state
- **WHEN** an article with hidden content is rendered again (for example by navigating back to it or by looking the headword up anew)
- **THEN** the hidden content is collapsed again behind the control, as it was on first render

#### Scenario: The control icon renders
- **WHEN** an article containing hidden content is rendered
- **THEN** the control appears as a visible icon rather than a missing or broken image

#### Scenario: Entry without hidden content is unaffected
- **WHEN** an article is rendered for a headword whose dictionary entries contain no hidden content
- **THEN** no hidden-content control appears and the article renders exactly as it would with the feature absent

#### Scenario: Links inside revealed hidden content navigate normally
- **WHEN** the user reveals hidden content and taps a link inside it
- **THEN** the app performs an in-app lookup of the linked word, the same as for a link in ordinary article content
