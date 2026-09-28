## ADDED Requirements

### Requirement: Inline article icon rendering

When an article contains a small image a dictionary places inline within a
definition (for example a sense-tag icon emitted by the kaikki converter), the
system SHALL render it inline at a height consistent with the surrounding text
and vertically aligned with that text, rather than as a full-size block image,
and SHALL NOT draw a background box behind it in either light or dark mode. This
styling SHALL apply only to such inline icons and MUST NOT change how any other
dictionary's images are rendered.

#### Scenario: Inline icon sits in the text flow

- **WHEN** an article definition contains an inline sense icon
- **THEN** the icon renders inline at the text's height, aligned with the text,
  without displacing the definition into a new block

#### Scenario: Inline icon has no background box in dark mode

- **WHEN** an article with an inline sense icon is rendered in dark mode
- **THEN** the icon shows without a light background box behind it

#### Scenario: Other dictionaries' images are unaffected

- **WHEN** an article from a dictionary that does not emit inline sense icons
  contains images
- **THEN** those images render exactly as they would with this feature absent
