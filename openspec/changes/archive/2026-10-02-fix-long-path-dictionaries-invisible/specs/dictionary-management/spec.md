## ADDED Requirements

### Requirement: Every loaded dictionary is listed and can be removed

The system SHALL list every dictionary the engine has loaded, so that any loaded
dictionary can be selected and removed. The list SHALL be complete regardless of the
depth or the encoded length of a dictionary's staged source path, or of its name.

A loaded dictionary MUST NOT be reachable through lookups while being absent from the
list. The list is the only surface from which a dictionary can be removed, and the app
retains any staged directory a loaded dictionary reads from, so a dictionary that is
loaded but unlisted can never be removed: it keeps its storage until the app's data is
cleared, which takes every other staged dictionary with it.

#### Scenario: A dictionary with a long staged path is listed
- **WHEN** a folder is imported whose dictionary lies deep enough that its staged source
  path exceeds the fixed-size buffer the app reads source paths through
- **THEN** the dictionary is listed in the Dicts tab like any other dictionary

#### Scenario: A listed dictionary can be removed however long its path is
- **WHEN** the user removes a listed dictionary whose staged source path exceeds that
  buffer
- **THEN** its staged copy and its built indexes are deleted, and it stops appearing in
  lookups, exactly as for any other dictionary

#### Scenario: The list matches what the engine loaded
- **WHEN** the app scans the staged tree on launch and the engine loads dictionaries
- **THEN** the Dicts list contains one row per loaded dictionary, so no loaded dictionary
  is left unlisted
