# Spec Delta

## Purpose

Name taps during an active catalog download must be no-ops, matching the
rows' dimmed non-selectable rendering.

## MODIFIED Requirements

### Requirement: Selecting and downloading dictionaries
The system SHALL let the user select one or more catalog entries and download
them as a single batch, and SHALL report the batch's progress as a fraction
along with the entry currently being transferred. The system SHALL keep the
transfer running when the app is in the background, and SHALL NOT require any
storage permission to download. A completed download SHALL place the entry's
files in the app's private dictionary storage and make the dictionary available
in the main list. While a download batch is in progress, name taps on catalog
entries SHALL NOT change the selection.

#### Scenario: Downloading a single entry
- **WHEN** the user selects one catalog entry and starts the download
- **THEN** the entry's required files are downloaded, and the dictionary appears
  in the main list and is indexed like any imported dictionary

#### Scenario: Downloading a batch
- **WHEN** the user selects several catalog entries and starts the download
- **THEN** every selected entry is downloaded in turn, and they become available
  in the main list once the batch completes and is scanned and indexed

#### Scenario: Progress is reported while downloading
- **WHEN** a download is in progress
- **THEN** the app shows a progress fraction and the entry currently being
  transferred, and keeps that indication current

#### Scenario: Download continues while backgrounded
- **WHEN** the user leaves the app while a download is in progress
- **THEN** the download continues and the app shows that it is in progress when
  the user returns

#### Scenario: Download is resumed after an interruption
- **WHEN** a download was interrupted and the user retries it
- **THEN** the transfer resumes from what was already received where the remote
  source allows it, and starts over cleanly where it does not, never producing
  a partially written dictionary

#### Scenario: No storage permission is requested
- **WHEN** the user downloads a dictionary from the catalog
- **THEN** the app requests no storage permission and the download succeeds

#### Scenario: Downloaded dictionaries need no further action
- **WHEN** a dictionary has been downloaded from the catalog
- **THEN** it is stored permanently in the app, is listed with the other
  dictionaries, and remains available after the app restarts

#### Scenario: Taps during a download change nothing
- **WHEN** the user taps a catalog entry while a download batch is in progress
- **THEN** the selection is unchanged and the entry's highlight state does not
  change
