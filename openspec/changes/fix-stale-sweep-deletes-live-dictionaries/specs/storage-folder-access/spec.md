## ADDED Requirements

### Requirement: An imported folder's staged copy is stable across restarts

Once the app has staged a picked folder, the staged copy SHALL be treated as the
durable record of that import. Routine app maintenance that runs without user action
— a startup scan, index maintenance, or reclamation of directories nothing reads —
SHALL NOT delete a staged directory whose dictionaries load successfully, and a
dictionary imported from a nested subfolder SHALL be as durable as one imported from
the top level of the picked folder.

#### Scenario: A nested import is still present after a restart
- **WHEN** the user picked a folder whose supported dictionary files are in nested
  subfolders, and the app is restarted
- **THEN** those dictionaries are still listed and searchable, and no re-pick of the
  original folder is needed

#### Scenario: A routine scan does not delete the staged copy of an import
- **WHEN** a scan runs without any user action on the import
- **THEN** the staged copy of every import that loads successfully is left in place

#### Scenario: Re-importing is still required only for a removed dictionary
- **WHEN** a staged directory is deleted automatically
- **THEN** it is one that no dictionary loaded from, so every dictionary the user
  still sees can be re-imported from its original folder and no import the app
  reported as healthy has been discarded