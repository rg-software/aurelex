## MODIFIED Requirements

### Requirement: Example qualification

An example SHALL be kept for a sense only when it contains the headword or one of
the base word's listed forms. A cross-reference bookkeeping example SHALL NOT be
kept. An archaic example (Early Modern or Middle English spelling or inflection)
SHALL NOT be kept for a sense that is not marked obsolete, dated or archaic; for
a sense that is so marked, an archaic example SHALL be shown when no other
qualifying example exists, so such a sense is illustrated rather than left bare,
and a modern-readable example SHALL be preferred when one exists. An example
longer than a fixed bound SHALL be shortened at a word boundary.

#### Scenario: Example must use the headword

- **WHEN** a source example does not contain the headword or any of its listed
  forms
- **THEN** that example is not shown

#### Scenario: Archaic and citation examples are dropped

- **WHEN** a sense that is not marked obsolete, dated or archaic has an archaic
  quotation or a cross-reference bookkeeping example
- **THEN** that example is not shown

#### Scenario: An archaic sense falls back to an archaic example

- **WHEN** a sense is marked obsolete, dated or archaic and it has an archaic
  example but no modern-readable one
- **THEN** the archaic example is shown, shortened if it exceeds the bound

#### Scenario: An archaic sense prefers a modern-readable example

- **WHEN** a sense is marked obsolete, dated or archaic and it has both a
  modern-readable example and an archaic one
- **THEN** the modern-readable example is shown

#### Scenario: A bookkeeping example is dropped even on an archaic sense

- **WHEN** a sense is marked obsolete, dated or archaic and its only example is a
  cross-reference bookkeeping line
- **THEN** that example is not shown

#### Scenario: An over-long example is shortened

- **WHEN** a qualifying example exceeds the length bound
- **THEN** it is cut at a word boundary that fits the bound
