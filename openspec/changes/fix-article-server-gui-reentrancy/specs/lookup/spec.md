## MODIFIED Requirements

### Requirement: Embedded dictionary resources
The system SHALL load resources referenced by an article (for example images and audio stored in mdict `.mdd` archives or referenced from dictionary folders) and display or play them within the article. Resource loading SHALL be robust: resolving the article's resources via the local article server MUST NOT crash the app or deadlock/freeze the UI, including when several resources are requested concurrently, and a request whose client disconnects before the resource is ready SHALL be dropped without error. Resolving a resource MUST NOT block the user interface and MUST NOT require the user interface thread to run a nested event loop; resource work SHALL be performed off the user interface thread, and a resource that cannot be produced SHALL be abandoned within a short bounded time rather than after a long fixed wait.

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

#### Scenario: User input is accepted while a resource is being resolved
- **WHEN** an article is displayed and one or more of its resources are still being resolved
- **THEN** the user interface keeps accepting and responding to input, including switching tabs and picking a different group, and does not stop responding

#### Scenario: Unresolvable resource is abandoned within a bounded time
- **WHEN** a referenced resource cannot be produced by the dictionary engine
- **THEN** the request is given up within a bounded time rather than never, the article reports the resource as missing, and the user interface does not become unresponsive for an extended period

#### Scenario: Content renderer terminates during a resource request
- **WHEN** the web content renderer process terminates while a resource request is in flight
- **THEN** the app does not crash, and the user can continue using it after the article pane is rebuilt

#### Scenario: Navigating away during a resource request leaves no residue
- **WHEN** the user navigates away from an article while one of its resources is still being resolved
- **THEN** the abandoned request is cleaned up, and a later article that references the same resource still resolves it
