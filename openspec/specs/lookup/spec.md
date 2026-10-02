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
The Search pane's layout SHALL fit within the height the window gives it at every window size: the inline article area SHALL NOT spill past the bottom navigation dock, and therefore the article surface SHALL never cover the app's own chrome. In particular the bottom navigation dock SHALL remain fully visible and tappable on the Search tab in every window orientation. When the window changes size, the article surface SHALL settle in the new orientation without the user having to switch tabs or re-open the word, and the article that was open SHALL still be displayed afterwards.
Where the article is longer than the visible area, its text SHALL stay clear of the scrolling affordance: the scrollbar SHALL NOT be drawn over the entry text. The inset that keeps them apart SHALL be painted with the article's own background, so it reads as part of the article rather than as a separate strip.

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

#### Scenario: Rotating keeps the bottom dock visible
- **WHEN** the device is rotated while an article is displayed in the Search tab
- **THEN** the bottom navigation dock remains fully visible and tappable in the new orientation, and the article ends above it rather than on top of it

#### Scenario: The article survives an orientation change
- **WHEN** the device is rotated while an article is displayed in the Search tab
- **THEN** the same article is still displayed once the app settles in the new orientation, without the user re-entering the word or switching tabs

#### Scenario: Starting in landscape keeps the bottom dock visible
- **WHEN** the app is launched with the device already in landscape and an article is opened on the Search tab
- **THEN** the bottom navigation dock is visible and tappable, and the article renders above it

#### Scenario: Opening the keyboard does not disturb an article or its suggestions
- **WHEN** the soft keyboard opens while the search field is focused, which shrinks the window without changing its width
- **THEN** the open article stays displayed and headword suggestions still appear as the user types

#### Scenario: Scrolling a long article keeps the text clear of the scrollbar
- **WHEN** an article longer than the visible article area is scrolled
- **THEN** the scrollbar and the entry text do not overlap — the text ends before the edge the scrollbar occupies

#### Scenario: The reserved space is not visible as a gap
- **WHEN** an article is displayed, whether or not it is long enough to scroll
- **THEN** the space kept clear of the scrollbar is the same color as the article's background, so no strip or border is apparent

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

### Requirement: In-article find-in-page

The system SHALL let the user search the text of the displayed article from the
article toolbar and move between the matches. A control in the article toolbar
SHALL open a find mode drawn in place of the toolbar's article-navigation
controls, and the same control, shown in its close state, SHALL close find and
restore those controls. Find mode SHALL offer a query field, a match count, and
previous and next match controls. Every match of the query in the article SHALL
be highlighted, the current match SHALL be visually distinguished from the
others, and the current match SHALL be brought into view. Matching SHALL be
case-insensitive. The searched text SHALL be the article's visible text: text
inside a dictionary's collapsed optional (`[*]…[/opt]`) zone SHALL NOT be
matched. Find SHALL be available only while an article is displayed, and
opening or closing find SHALL NOT by itself change the article that is shown or
where it is scrolled.

#### Scenario: Find is offered only with an article open

- **WHEN** the Search tab is showing an article
- **THEN** the article toolbar offers the find control

#### Scenario: Find is absent with no article open

- **WHEN** the Search tab is showing suggestions or history with no article open
- **THEN** no find control and no find bar are shown

#### Scenario: The find control opens find in place of the navigation controls

- **WHEN** the user taps the find control while an article is shown
- **THEN** the toolbar's back, forward, favorite, and zoom controls are replaced
  in place by the find bar, and the find control is shown in its close state

#### Scenario: The close control restores the navigation controls

- **WHEN** the user taps the find control while find is open
- **THEN** the find bar is dismissed, the article's highlights are removed, and
  the article's navigation controls are restored

#### Scenario: Opening find leaves the article in place

- **WHEN** the user opens find on an article that has been scrolled
- **THEN** the article shown and its scroll position are unchanged until the
  user enters a query

#### Scenario: Typing a query highlights every match and counts them

- **WHEN** the user enters a query that occurs several times in the visible article
- **THEN** every occurrence is highlighted, one of them is marked as the current
  match, and the count shows the current match's position and the total number
  of matches

#### Scenario: Matching is case-insensitive

- **WHEN** the user enters a query whose case differs from the article's text
- **THEN** the occurrences are still found and highlighted

#### Scenario: A match spanning inline markup counts once

- **WHEN** the query occurs in the article across a boundary between inline
  elements, such as inside a bold or link run
- **THEN** it is counted as a single match and highlighted as one

#### Scenario: Moving to the next and previous match

- **WHEN** the user activates next (or previous) match
- **THEN** the current match advances to the following (or preceding) match and
  is scrolled into view, and the count updates

#### Scenario: Match navigation wraps at the ends

- **WHEN** the user activates next on the last match, or previous on the first
- **THEN** the current match wraps to the first or last match respectively

#### Scenario: Submitting the field moves to the next match

- **WHEN** the user presses the keyboard's submit action in the find field
- **THEN** the current match advances to the next match

#### Scenario: A query with no matches

- **WHEN** the user enters a query that does not occur in the article
- **THEN** no text is highlighted, the count reports no matches, and moving to
  the next or previous match does nothing

#### Scenario: Clearing or changing the query updates the highlights

- **WHEN** the user edits or clears the find query
- **THEN** the previous highlights are removed and the article is re-highlighted
  for the new query (or left unhighlighted when the query is empty)

#### Scenario: Collapsed optional content is not searched

- **WHEN** the query occurs only inside a dictionary's collapsed optional zone
- **THEN** it is not counted or highlighted until that content is revealed

#### Scenario: A new article clears find

- **WHEN** the user looks up another word while find is open or retains a query
- **THEN** the new article is shown without highlights and the find query is
  cleared

#### Scenario: A reload while find is open re-applies the query

- **WHEN** an article reloads while find is open with a query, for example after
  a rotation
- **THEN** the query is re-applied to the reloaded article and the same match
  position is restored

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
The system SHALL offer article zoom controls beside the article's back/forward/star controls, and each control SHALL be labelled with a text-size increase/decrease icon (an "A" with a plus / minus) rather than a generic magnifier, so the control states that it changes article text size. Zooming SHALL enlarge article text that inherits the article's root text size, and the enlarged content SHALL re-wrap to the viewport width so that it stays fully visible with no horizontal scrolling. Zooming out SHALL likewise keep the article fitted to the screen width. The zoom level is a single global value shared by all articles (no per-word or per-dictionary zoom memory).

Zoom SHALL scale text the article renders at its root text size. Text and elements whose size a dictionary's own bundled stylesheet sets in an absolute unit (such as px or pt) SHALL NOT be scaled by zoom, because such a declaration overrides the root size for the content it matches; the app SHALL NOT override a dictionary's own typographic declarations in order to force them to scale. A dictionary that sets absolute sizes therefore renders some of its content at the same size at every zoom level, and this is a property of that dictionary, not of its file format.

#### Scenario: Zoom controls state their text-size meaning
- **WHEN** the user views the article toolbar's zoom controls
- **THEN** they show the text-size increase and decrease icons (an "A" with a plus / minus), not a magnifier

#### Scenario: Zooming in reflows text
- **WHEN** the user zooms in on an article using the zoom controls
- **THEN** the article's text is enlarged and re-wraps to the width of the screen so the full line is visible without horizontal panning

#### Scenario: No horizontal slider at high zoom
- **WHEN** the user zooms in on an article far past its default size
- **THEN** the article remains readable at the screen width and does not present a horizontally scrollable page

#### Scenario: Zoom applies to every article
- **WHEN** the user looks up a new headword after setting a zoom level
- **THEN** the new article renders at that same zoom level

#### Scenario: A dictionary that pins absolute text sizes keeps them
- **WHEN** the user zooms in or out on an article whose dictionary sets its entry text to an absolute size in its own stylesheet
- **THEN** that dictionary's text stays at the size the dictionary specified while the rest of the article surface scales, and the article remains legible and free of horizontal scrolling at both extremes

#### Scenario: The zoom limit is per-dictionary, not per-format
- **WHEN** an article is rendered from a dictionary that does not set absolute text sizes, in the same format as one that does
- **THEN** that article's text scales with zoom normally

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

