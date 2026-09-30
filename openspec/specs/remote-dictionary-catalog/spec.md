# remote-dictionary-catalog Specification

## Purpose
Lets a user install dictionaries from a curated online catalog without
sideloading files, covering catalog availability, browsing, batch download with
progress and cancellation, optional audio bundles, integrity and free-space
preflight, and the downloaded dictionary's arrival in the app's dictionary set.
## Requirements
### Requirement: Catalog availability
The system SHALL provide a single curated catalog of installable dictionaries
published as one static document at a location compiled into the app, and SHALL
reach it over HTTPS only. The system SHALL NOT require the user to configure,
supply, or authenticate to a catalog location, and SHALL NOT perform discovery
or scraping of any other source. The system SHALL keep the remote-add action
available regardless of reachability, and SHALL report a catalog that cannot be
reached with a stated reason inside the catalog view rather than disabling the
action. Folder import SHALL continue to be offered and unaffected. A build
distributed to users SHALL have a working TLS transport for the catalog fetch: a
build whose TLS cannot initialize is a build defect, and the system SHALL NOT
ship such a build as a catalog that is merely unreachable.

#### Scenario: Catalog is reachable
- **WHEN** the user opens the Dictionaries pane and the catalog can be fetched
- **THEN** the remote-add action is enabled and the catalog's entries can be listed

#### Scenario: Catalog cannot be reached
- **WHEN** the user opens the remote catalog and it cannot be fetched
- **THEN** the catalog states why it could not be loaded and offers nothing to
  download, while the folder-import action remains available and unaffected

#### Scenario: Catalog was previously read and is now unreachable
- **WHEN** the catalog cannot be fetched but a previously fetched catalog is known
- **THEN** the last known catalog entries remain visible and readable, while
  starting a download reports that the catalog is unreachable

#### Scenario: Catalog is not re-read at app start
- **WHEN** the app starts
- **THEN** the catalog is not fetched as part of startup, and a remote-add
  request fetches it on demand

#### Scenario: A distributed build completes the catalog fetch
- **WHEN** a user runs a build obtained from a release channel rather than one
  produced on a maintainer's machine, and opens the remote catalog
- **THEN** the catalog is fetched over TLS and its entries are listed, with no
  transport-level failure attributable to the build

### Requirement: Browsing the catalog
The system SHALL present the catalog as a list of entries shown in place over the
Dictionaries pane, without adding a navigation destination. Each entry SHALL show
its display name, its source/target language pair, and the size of what will be
downloaded for it, and SHALL indicate whether the entry is already installed. The system SHALL NOT offer entry version comparison, update checks,
or any other catalog-side lifecycle action.

#### Scenario: Entries are listed
- **WHEN** the user opens the remote catalog
- **THEN** each entry is listed with its name, language pair, and download size

#### Scenario: Already-installed entry is marked
- **WHEN** a catalog entry's dictionary files are already present in the app's
  dictionary set
- **THEN** the entry is shown as installed and a fresh install is not offered
  for it (only its optional resources can still be added)

#### Scenario: Catalog is a read-only list
- **WHEN** the user views an installed catalog entry
- **THEN** the app offers no action to update, upgrade, or reinstall that entry

#### Scenario: Leaving the catalog
- **WHEN** the user dismisses the catalog
- **THEN** the Dictionaries pane is shown as it was before the catalog opened

### Requirement: Selecting and downloading dictionaries
The system SHALL let the user select one or more catalog entries and download
them as a single batch, and SHALL report the batch's progress as a fraction
along with the entry currently being transferred. The system SHALL keep the
transfer running when the app is in the background, and SHALL NOT require any
storage permission to download. A completed download SHALL place the entry's
files in the app's private dictionary storage and make the dictionary available
in the main list.

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

### Requirement: Cancelling a download
The system SHALL let the user cancel a download in progress, and that cancel
SHALL stop the whole batch. The system SHALL report the batch as cancelled
rather than failed, and SHALL NOT leave a partially written dictionary that the
app would later try to load. Bytes already received MAY be kept in the
transfer's private scratch space so a later retry can resume them; they never
become a loadable dictionary. Cancelling a download SHALL NOT
stop or alter any dictionary scanning or index building that is already in
progress, and SHALL NOT clear or interrupt any processing indication belonging to
that work.

#### Scenario: Cancelling stops the whole batch
- **WHEN** the user cancels while a batch of entries is downloading
- **THEN** the entire batch stops and no further entries are downloaded

#### Scenario: Cancelled files are not installed
- **WHEN** a download is cancelled
- **THEN** no dictionary from that batch is added to the main list or reported
  as a load failure; any partially received bytes remain only in private scratch
  space, never as a dictionary

#### Scenario: Cancelled is distinct from failed
- **WHEN** the user cancels a download
- **THEN** the app reports the batch as cancelled, not as an error or a failure

#### Scenario: Cancelling does not disturb indexing
- **WHEN** the user cancels a download while dictionaries from an earlier
  import are still being scanned or indexed
- **THEN** that scanning and indexing continues and its processing indication
  remains visible and correct until it finishes on its own

### Requirement: Download integrity and size preflight
The system SHALL use the size the catalog declares for each file to plan the
transfer and to check free space before starting. The system SHALL verify a
downloaded file against a checksum when the catalog supplies one for it, and
SHALL accept the file without checksum verification when the catalog supplies
none. A file that fails checksum verification SHALL be rejected and the failure
SHALL name the affected entry.

#### Scenario: Checksum is supplied and matches
- **WHEN** the catalog supplies a checksum for a file and the downloaded file
  matches it
- **THEN** the file is accepted and the download continues

#### Scenario: Checksum is supplied and does not match
- **WHEN** the catalog supplies a checksum for a file and the downloaded file
  does not match it
- **THEN** the download fails, the app names the affected entry, and the
  rejected file is not installed

#### Scenario: No checksum is supplied
- **WHEN** the catalog supplies no checksum for a file
- **THEN** the app accepts the downloaded file without checksum verification

#### Scenario: Not enough free space
- **WHEN** the device does not have enough free space to hold the selected
  downloads
- **THEN** the app refuses to start the download, names what is short, and
  starts nothing

#### Scenario: Free space is tight
- **WHEN** the device has enough space for the selected downloads but little
  headroom afterwards
- **THEN** the app warns that space is tight and asks before proceeding

### Requirement: Optional audio resources
The system SHALL treat a catalog entry's pronunciation-audio resources as
optional but selected by default: selecting an entry for download SHALL include
its audio, and the user SHALL be able to turn an entry's audio off before
downloading it. The system SHALL let the user add the audio resources to an
entry that is already installed, and SHALL make those resources take effect for
the installed dictionary without the user having to reinstall it or restart the
app. Adding audio SHALL NOT require the dictionary's full-text index to be
rebuilt.

#### Scenario: Audio is included with the entry
- **WHEN** the user selects a catalog entry that has optional audio resources
- **THEN** the entry's audio is selected too and is downloaded with it

#### Scenario: User turns the audio off
- **WHEN** the user turns off an entry's audio before downloading
- **THEN** only the entry's required files are downloaded, and the audio is not

#### Scenario: User asks for the audio
- **WHEN** the user requests the optional audio for a catalog entry
- **THEN** the audio resources are downloaded, subject to the same free-space
  and integrity checks as any other download

#### Scenario: Audio added to an installed dictionary
- **WHEN** the user adds optional audio to a dictionary that is already
  installed
- **THEN** the dictionary's pronunciation audio becomes available in place, the
  dictionary keeps its existing position and group membership, and the app does
  not ask the user to restart

#### Scenario: Audio added does not rebuild the full-text index
- **WHEN** the user adds optional audio to an already-indexed dictionary
- **THEN** the dictionary keeps the full-text index it already has and does not
  undergo a full-text rebuild

### Requirement: Reporting a failed download
The system SHALL report a download that could not be completed, SHALL say which
entry it affected, and SHALL leave the other dictionaries in the batch and the
app's existing dictionaries unaffected. The system SHALL NOT install a file it
could not fully receive.

#### Scenario: One entry in a batch fails
- **WHEN** an entry in a multi-entry batch fails to download
- **THEN** the app reports which entry failed, the remaining entries still
  complete, and already-installed dictionaries are unaffected

#### Scenario: The catalog is unreachable when a download is started
- **WHEN** the user starts a download and the catalog has become unreachable
- **THEN** the app reports that the catalog is unreachable and downloads nothing

### Requirement: Downloading does not block the app
The system SHALL NOT make a download part of the dictionary scanning and indexing
chain, and SHALL NOT require the user to wait for a download before removing a
dictionary, browsing groups, or searching.

#### Scenario: Search while downloading
- **WHEN** a download is in progress
- **THEN** the user can still search, browse groups, and remove dictionaries,
  and the app's processing indication continues to reflect only the scanning and
  indexing work, if any

#### Scenario: Removal while downloading
- **WHEN** a dictionary is removed while an unrelated download is in progress
- **THEN** the removal proceeds and is not blocked by the download, and the
  download continues

