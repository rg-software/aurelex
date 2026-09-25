## MODIFIED Requirements

### Requirement: Article rendering
The system SHALL render a lookup as HTML built from the dictionaries of the active group that contain the headword, presented in the on-screen web view with the dictionaries ordered per the active group, whether the lookup is initiated by typing in the search field, selecting a suggestion, or an external entry point (share action, clipboard, history, favorites, or full-text search). Every article SHALL be presented in the Search tab's inline article surface; there SHALL NOT be a separate full-pane article view.
Successful article lookups SHALL be recorded in the lookup history.
Unknown words, lookups scoped to a group with no dictionaries, and articles whose embedded resources load or fail concurrently MUST NOT crash or hang the app; navigation (switching tabs, opening other panes, and returning) SHALL remain responsive while an article is displayed.

#### Scenario: Word found in multiple dictionaries
- **WHEN** the user looks up a headword present in several dictionaries of the active group
- **THEN** the article displays each dictionary's entry in the active group's order

#### Scenario: Word not found
- **WHEN** the user looks up a headword none of the active group's dictionaries contain
- **THEN** the app shows a "not found" indication and offers a way to continue searching

#### Scenario: Lookup from an external entry point opens inline
- **WHEN** the user initiates a lookup via a share action, the clipboard, history, favorites, or a full-text-search result
- **THEN** the article is rendered in the Search tab's inline article surface with the active group, the word is added to the lookup history, and it becomes part of the normal back/forward navigation

#### Scenario: Lookup respects the active group
- **WHEN** a word is only present in dictionaries outside the active group
- **THEN** the lookup does not show that dictionary's entry (it is treated as not found for that group)

#### Scenario: Group with no dictionaries does not hang
- **WHEN** the user types a query while the active group has no dictionaries
- **THEN** suggestions are empty and returned promptly (no long stall), and a lookup in that group reports not-found rather than blocking

#### Scenario: Navigation stays responsive while an article with resources is shown
- **WHEN** an article whose entries reference embedded resources is displayed
- **THEN** switching to another tab and back completes without the app freezing or becoming unresponsive to input

### Requirement: Embedded dictionary resources
The system SHALL load resources referenced by an article (for example images and audio stored in mdict `.mdd` archives or referenced from dictionary folders) and display or play them within the article. Resource loading SHALL be robust: resolving the article's resources via the local article server MUST NOT crash the app or deadlock/freeze the UI, including when several resources are requested concurrently, and a request whose client disconnects before the resource is ready SHALL be dropped without error.

#### Scenario: Image in a dictionary archive renders
- **WHEN** an article references an image stored in an mdd archive
- **THEN** the image renders inside the article

#### Scenario: Missing resource does not break rendering
- **WHEN** an article references a resource that does not exist
- **THEN** the article still renders and the missing item is shown as broken or absent without error

#### Scenario: Concurrent resource requests do not freeze the article
- **WHEN** an article references several embedded resources that are requested at the same time
- **THEN** the article finishes rendering and the UI stays responsive; the app does not hang or crash

#### Scenario: Resource request abandoned by the client
- **WHEN** a resource request's client connection closes before the resource is delivered
- **THEN** the server drops that response without error and the app continues normally
