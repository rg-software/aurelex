## MODIFIED Requirements

### Requirement: References stay consistent with the bundle

The system SHALL give each bundled recording the same filesystem-safe name a
build gives it, and SHALL rewrite the dictionary's reference when that name
differs from the reference, so every `[s]` link names a file in the bundle. A
dictionary whose references already match SHALL be left unchanged. The system
SHALL write each bundled file under the name the dictionary references even when
the recording is held in the cache or the archive under a name that differs from
it only in letter case, and SHALL NOT report such a recording as unlocatable. When
two references name the same recording and differ from each other only in letter
case, the system SHALL bundle the recording under both names.

#### Scenario: An unsafe reference is rewritten

- **WHEN** a reference carries a character a filesystem refuses
- **THEN** the recording is bundled under the sanitised name and the dictionary
  is rewritten to reference that name

#### Scenario: An already-safe dictionary is untouched

- **WHEN** every reference is already filesystem-safe
- **THEN** the dictionary is not modified

#### Scenario: Reference and file agree

- **WHEN** a bundle is rebuilt
- **THEN** every recording in it is referenced under exactly its bundled name

#### Scenario: A reference differs from the stored recording only in case

- **WHEN** a reference names a recording the archive or cache holds under a name
  differing only in letter case
- **THEN** the file is written under the reference's own spelling, counted as
  located, and the run reports no missing recording

#### Scenario: Two references differ only in case

- **WHEN** two references name the same recording and differ from each other only
  in letter case
- **THEN** the recording is written under both names and neither reference is
  reported missing

### Requirement: A reference that resolves nowhere stops being a link

The system SHALL remove a referenced recording's link from the dictionary when
the recording is found in neither the local cache nor the audio archive, so that
a rebuilt dictionary references nothing the bundle cannot serve, and SHALL report
how many links it removed. The system SHALL offer an option that keeps such a
reference in place instead, leaving the link as it was.

#### Scenario: An unlocatable reference is removed

- **WHEN** a referenced recording is in neither the cache nor the archive
- **THEN** its link is removed from the dictionary, the bundle omits the
  recording, and the run reports the removed link

#### Scenario: Removing an unlocatable reference leaves the rest intact

- **WHEN** one reference is removed
- **THEN** every other reference and its bundled file is unchanged

#### Scenario: The operator keeps unresolvable references

- **WHEN** the option that keeps unresolvable references is given and a reference
  resolves to no recording
- **THEN** the dictionary keeps the link, the bundle omits the recording, and the
  run reports the unresolved link
