## ADDED Requirements

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
