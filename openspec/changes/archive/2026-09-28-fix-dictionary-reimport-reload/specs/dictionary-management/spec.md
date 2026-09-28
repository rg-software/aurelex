## ADDED Requirements

### Requirement: Re-importing an updated dictionary reloads it in the session
When a dictionary's source files are replaced on disk - the ordinary case of importing a newer build of a dictionary already loaded, which keeps the same source path and therefore the same dictionary identity - the system SHALL detect the change on the next scan and reload that dictionary, so the updated content takes effect without restarting the app. The reloaded dictionary SHALL be fully searchable (article lookup and prefix search) immediately after the reload, and a scan SHALL NOT leave a loaded dictionary reading an index that was written for a different version of its content.

Dictionaries whose source files have not changed SHALL NOT be reloaded: a scan over unchanged dictionaries leaves them, and their index state, untouched.

#### Scenario: Re-importing an updated dictionary makes the new data live
- **GIVEN** a dictionary is loaded and searchable, and the user imports a newer build of the same dictionary (same folder and file name)
- **WHEN** the import's scan completes
- **THEN** the dictionary reflects the new content in the running session, so a headword that exists only in the new build resolves without restarting the app

#### Scenario: Search still works after a re-import
- **WHEN** a dictionary is reloaded because its source changed
- **THEN** article lookup and prefix search on that dictionary return results, and neither stalls waiting on an unreadable index

#### Scenario: A scan does not rewrite an index under a loaded dictionary
- **WHEN** the scanner processes a dictionary whose source file changed
- **THEN** the index it rebuilds belongs to the dictionary instance that remains loaded, so no loaded dictionary is left reading an index written for different content

#### Scenario: Unchanged dictionaries are not reloaded
- **GIVEN** a set of loaded dictionaries whose source files are unchanged
- **WHEN** a scan runs
- **THEN** no dictionary is reloaded and their index state is preserved
