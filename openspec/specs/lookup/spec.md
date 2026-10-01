# lookup Specification

## Purpose

Provides the core lookup experience on Android: searching headwords, rendering dictionary articles as HTML in a WebView, loading embedded resources, navigating between articles, and playing pronunciation audio.
## Requirements
### Requirement: Headword suggestions
The system SHALL offer headword suggestions as the user types, matching dictionary headwords by prefix and fuzzy (approximate) search.
Submitting a suggestion or the typed text SHALL trigger a full article lookup. A query submitted from the keyboard (the IME action) SHALL open the top (most relevant) suggestion when the query has suggestions, and SHALL look up the literal typed text when it has none.
When the search field is empty, or when a typed query matches no dictionary headwords, the candidate surface SHALL show the recent lookup history instead of suggestions.
A suggestion response SHALL NOT paint the candidate surface over an article that is being loaded, or has loaded, for the submitted query: an in-flight or completed article lookup takes precedence over suggestions for the same query.

#### Scenario: Typing produces suggestions
- **WHEN** the user enters text in the search field
- **THEN** the app shows matching headword suggestions from the loaded dictionaries

#### Scenario: Selecting a suggestion looks up the article
- **WHEN** the user taps a suggestion
- **THEN** the app renders the combined article for that headword

#### Scenario: Submitting from the keyboard opens the top suggestion
- **WHEN** the user presses the keyboard's submit action while the query has one or more suggestions
- **THEN** the app opens the article for the top (most relevant) suggestion, the same article tapping that suggestion would open

#### Scenario: Submitting from the keyboard with no suggestions looks up the typed text
- **WHEN** the user presses the keyboard's submit action while the query has no suggestions
- **THEN** the app looks up the literal typed text

#### Scenario: Empty search field shows history
- **WHEN** the search field is empty
- **THEN** the candidate surface shows the most recent lookup history instead of suggestions

#### Scenario: No matches falls back to history
- **WHEN** the user types a query that matches no dictionary headwords
- **THEN** the candidate surface reverts to showing the recent lookup history

#### Scenario: Switching group with a query triggers a lookup
- **WHEN** the user selects a different group in the Search group picker while the search field has text
- **THEN** the app performs an article lookup of that query in the newly selected group, makes it the active group, records the entry in lookup history, and shows the article without the suggestion list left covering it

#### Scenario: Switching group with an empty field re-shows history
- **WHEN** the user selects a different group in the Search group picker while the search field is empty
- **THEN** the app sets that group active and re-shows the lookup history scoped to it, without navigating

#### Scenario: A late suggestion response does not cover the article
- **WHEN** a suggestion query is still in flight when the article for the submitted text starts loading or finishes rendering
- **THEN** the article is what remains shown, and the arriving suggestions do not repaint over it

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

### Requirement: In-article link navigation
The system SHALL open links within an article as in-app lookups of the linked word rather than leaving the app, and SHALL keep the user able to navigate back to the previous article. Navigation between articles SHALL be browser-like: a back path through previously opened articles and a forward path through articles the user has backed out of. Each navigation entry SHALL carry the dictionary group the article was produced in; returning or forwarding SHALL restore that group before re-rendering (falling back to "All" if the group no longer exists). A fresh lookup clears the forward path.
Link schemes a dictionary emits for in-app cross-references SHALL be recognised and resolved as lookups, regardless of which dictionary format produced them. A scheme a dictionary uses for cross-references SHALL NOT reach the article as an inert link whose tap does nothing.

#### Scenario: Tapping an article link
- **WHEN** the user taps a link inside an article
- **THEN** the app performs a lookup of the linked word within the app, in the current active group

#### Scenario: Cross-reference links from any format navigate
- **WHEN** an article produced by any supported dictionary format contains a link to another of its entries
- **THEN** tapping it performs an in-app lookup of the linked word, rather than doing nothing

#### Scenario: StarDict cross-references navigate
- **WHEN** a StarDict article contains a cross-reference link, which the StarDict format expresses with the `bword:` scheme
- **THEN** tapping it performs an in-app lookup of the linked word in the current active group

#### Scenario: Back navigation
- **WHEN** the user navigates from one article to another via links
- **THEN** the app's back action returns to the previous article and restores the dictionary group that produced it

#### Scenario: Forward navigation
- **WHEN** the user has backed out of at least one article and chooses forward
- **THEN** the app re-opens the most recently backed-out article and restores the dictionary group that produced it

#### Scenario: A fresh lookup clears forward history
- **WHEN** the user backs out of an article and then performs any fresh lookup (typed search, suggestion, history or favorites tap, or in-article link)
- **THEN** the forward path is cleared and the forward control is unavailable

### Requirement: Pronunciation audio
The system SHALL play pronunciation audio referenced by articles (ogg, mp3, wav) using an on-device player, triggered by audio links in the article.
Audio formats the player cannot decode (for example speex) MUST NOT crash the app and SHALL be gracefully indicated as unsupported.

#### Scenario: Playing an article audio link
- **WHEN** the user taps an audio control in an article whose format is supported
- **THEN** the app plays the pronunciation audio

#### Scenario: Unsupported audio format
- **WHEN** the user taps an audio control whose format the device cannot decode
- **THEN** the app does not play sound and signals that the format is unsupported

### Requirement: Article zoom reflows to the screen width
The system SHALL offer article zoom controls (zoom in, zoom out) beside the article's back/forward/star controls. Zooming in SHALL re-render the article so that text re-wraps to the viewport width: enlarged content stays fully visible on screen with no horizontal scrolling for regular article text. Zooming out SHALL likewise keep the article fitted to the screen width. The zoom level is a single global value shared by all articles (no per-word or per-dictionary zoom memory).

#### Scenario: Zooming in reflows text
- **WHEN** the user zooms in on an article using the zoom controls
- **THEN** the article's text is enlarged and re-wraps to the width of the screen so the full line is visible without horizontal panning

#### Scenario: No horizontal slider at high zoom
- **WHEN** the user zooms in on an article far past its default size
- **THEN** the article remains readable at the screen width and does not present a horizontally scrollable page

#### Scenario: Zoom applies to every article
- **WHEN** the user looks up a new headword after setting a zoom level
- **THEN** the new article renders at that same zoom level

### Requirement: Article hidden content toggle
The system SHALL render dictionary content that a dictionary's markup marks as hidden (for example the DSL `[*]…[/opt]` optional zone) collapsed and out of view by default, behind a single tappable control placed in the article, and the user SHALL be able to reveal that content and hide it again. No content the dictionary chose to hide SHALL be permanently unreachable. The control SHALL be an icon (no text label) and SHALL be rendered at a size and position that leaves it tappable on a touch screen. Hidden content SHALL stay collapsed again when the article is re-rendered, so the hidden state is never sticky across articles.

Toggling hidden content SHALL NOT change how the rest of the article behaves: links, audio controls, and embedded resources inside revealed hidden content SHALL behave exactly as they do in ordinary article content, and a dictionary entry that contains no hidden content SHALL show no control and SHALL render exactly as before.

#### Scenario: Hidden content starts collapsed
- **WHEN** an article is rendered for a headword whose dictionary entry contains hidden content
- **THEN** the hidden content is not visible and a tappable control for it is present in the article

#### Scenario: Tapping the control reveals the hidden content
- **WHEN** the user taps the control
- **THEN** the hidden content becomes visible in place and the control reflects the now-revealed state

#### Scenario: Tapping the control again re-hides the content
- **WHEN** the user taps the control a second time after revealing the hidden content
- **THEN** the hidden content is hidden again and the control reflects the now-hidden state

#### Scenario: Re-rendering the article restores the collapsed state
- **WHEN** an article with hidden content is rendered again (for example by navigating back to it or by looking the headword up anew)
- **THEN** the hidden content is collapsed again behind the control, as it was on first render

#### Scenario: The control icon renders
- **WHEN** an article containing hidden content is rendered
- **THEN** the control appears as a visible icon rather than a missing or broken image

#### Scenario: Entry without hidden content is unaffected
- **WHEN** an article is rendered for a headword whose dictionary entries contain no hidden content
- **THEN** no hidden-content control appears and the article renders exactly as it would with the feature absent

#### Scenario: Links inside revealed hidden content navigate normally
- **WHEN** the user reveals hidden content and taps a link inside it
- **THEN** the app performs an in-app lookup of the linked word, the same as for a link in ordinary article content

### Requirement: Inline article icon rendering

When an article contains a small image a dictionary places inline within a
definition (for example a sense-tag icon emitted by the kaikki converter), the
system SHALL render it inline at a height consistent with the surrounding text
and vertically aligned with that text, rather than as a full-size block image,
and SHALL NOT draw a background box behind it in either light or dark mode. This
styling SHALL apply only to such inline icons and MUST NOT change how any other
dictionary's images are rendered.

#### Scenario: Inline icon sits in the text flow

- **WHEN** an article definition contains an inline sense icon
- **THEN** the icon renders inline at the text's height, aligned with the text,
  without displacing the definition into a new block

#### Scenario: Inline icon has no background box in dark mode

- **WHEN** an article with an inline sense icon is rendered in dark mode
- **THEN** the icon shows without a light background box behind it

#### Scenario: Other dictionaries' images are unaffected

- **WHEN** an article from a dictionary that does not emit inline sense icons
  contains images
- **THEN** those images render exactly as they would with this feature absent

