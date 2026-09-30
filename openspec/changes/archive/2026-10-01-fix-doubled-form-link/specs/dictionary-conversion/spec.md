## MODIFIED Requirements

### Requirement: Linked related headwords

When a source sense states that a word is an alternative or other form of another
headword, the system SHALL render that related headword as a link the reader can
tap to open its article. The link SHALL be emitted only when the produced
dictionary actually contains the related headword, so no link points at an entry
that does not exist. A related headword named by more than one relation SHALL be
linked once, never nested inside another link. The related headword SHALL NOT be
added as a separate cross-reference when it is already linked inside the sense's
gloss.

#### Scenario: An alternative form links to its base headword

- **WHEN** the source renders a sense as an alternative or other form of a
  headword that the dictionary contains
- **THEN** that headword appears as a tappable link within the sense

#### Scenario: No link to an absent headword

- **WHEN** a sense names a related headword that the produced dictionary does not
  contain
- **THEN** the headword is left as plain text and no link is emitted

#### Scenario: A target named by several relations is linked once

- **WHEN** a sense names the same related headword in both its alternative-form
  and form-of relations
- **THEN** the headword appears as a single link, not a link inside a link

#### Scenario: The related headword is not duplicated as a cross-reference

- **WHEN** a sense already links the headword it is a form of
- **THEN** that headword is not also listed in the card's cross-reference list
