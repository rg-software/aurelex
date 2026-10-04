## MODIFIED Requirements

### Requirement: Inline article icon rendering

When an article contains a small image drawn inline within a definition, the
system SHALL render it inline at a height consistent with the surrounding text
and vertically aligned with that text, rather than as a full-size block image,
and SHALL NOT draw a background box behind it in either light or dark mode. This
applies to every inline icon the app renders in an article: the inline sense icons
a dictionary places in a definition (for example the ones emitted by the kaikki
converter), the app's hidden-content expand/collapse control, and the app's
pronunciation control.

An inline icon SHALL occupy no visible space beyond its glyph, so that a control
whose box is larger than its glyph — for example one enlarged for a larger tap
target — SHALL NOT paint the surplus area and SHALL NOT obscure any adjacent
text, including the article's headword.

The sizing and alignment rules SHALL apply only to such inline icons and MUST NOT
change how any other dictionary's images are rendered. Dictionary **content**
images — photographs, illustrations and other artwork a dictionary embeds — SHALL
keep the light plate the app paints behind them in dark mode, so that artwork
which assumes a white page still reads correctly; the no-background-box guarantee
is about the app's own controls, not about that plate.

#### Scenario: Inline icon sits in the text flow

- **WHEN** an article definition contains an inline sense icon
- **THEN** the icon renders inline at the text's height, aligned with the text,
  without displacing the definition into a new block

#### Scenario: Inline icon has no background box in dark mode

- **WHEN** an article with an inline sense icon is rendered in dark mode
- **THEN** the icon shows without a light background box behind it

#### Scenario: Hidden-content control draws no background box

- **WHEN** an article containing hidden content is rendered, in either theme
- **THEN** the expand/collapse control shows only its glyph, with no opaque
  rectangle around it

#### Scenario: The control does not obscure the headword

- **WHEN** an article containing hidden content is rendered in dark mode
- **THEN** the headword is fully legible, with none of its characters hidden
  behind the control's painted area

#### Scenario: Pronunciation control draws no background box

- **WHEN** an article with a pronunciation control is rendered, in either theme
- **THEN** the control shows only its glyph, with no opaque rectangle around it

#### Scenario: Dictionary content images keep their light plate

- **WHEN** an article in dark mode embeds a photograph or other artwork supplied
  by the dictionary
- **THEN** that artwork is still presented on the light plate behind it, as it is
  with this feature absent

#### Scenario: Other dictionaries' images are unaffected

- **WHEN** an article from a dictionary that does not emit inline sense icons
  contains images
- **THEN** those images render exactly as they would with this feature absent