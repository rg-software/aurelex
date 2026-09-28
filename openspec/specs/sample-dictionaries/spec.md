# sample-dictionaries Specification

## Purpose

Generates the small example DSL dictionaries committed under
`examples/dictionaries/` (and their dictzip-compressed variants) that developers
import into the app and stage into the engine smoke run. They exist to exercise
DSL markup end to end, so the generator guarantees coverage of the markup
features the app renders specially.

## Requirements

### Requirement: Example dictionaries cover DSL optional content

The generated example dictionaries SHALL include at least one headword entry
whose article contains DSL optional/hidden content (the `[*]…[/opt]` hidden
zone), so a dictionary that hides content behind a collapsed control is always
available to import and test against without building one by hand. The generator
SHALL keep that entry present in every generated variant of the dictionary, and
regenerating the fixtures SHALL keep the coverage.

#### Scenario: Generated dictionary contains a hidden zone
- **WHEN** the example dictionaries are generated
- **THEN** at least one headword in them has an article containing optional/hidden
  content

#### Scenario: Coverage survives regeneration
- **WHEN** the example dictionaries are regenerated from the same generator
- **THEN** the regenerated dictionaries still contain a headword with
  optional/hidden content
