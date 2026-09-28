## MODIFIED Requirements

### Requirement: No inline user-visible strings
The system MUST NOT hardcode user-visible text wherever the app generates it:
QML labels, dialog and onboarding copy, status banners, and the WebView chrome
rendered by the app's QML JavaScript (history rows, favorites, suggestion
dropdown, clear actions).

A user-visible name that originates outside the app's own sources — for example
a name produced by the dictionary engine and returned across the C boundary —
SHALL still be presented in the active language: the app resolves it from the
catalog rather than passing the engine's own name through unchanged.

#### Scenario: QML-label string
- **WHEN** a QML element displays a user-visible label
- **THEN** the label text is resolved from the active language's catalog, not from an inline literal

#### Scenario: App-generated WebView chrome
- **WHEN** the app renders history, favorites, suggestions, or in-article chrome inside the article WebView
- **THEN** any user-visible English words in that chrome are resolved from the active language's catalog

#### Scenario: Engine-supplied name shown in the interface
- **GIVEN** the dictionary engine returns a user-visible name that is not stored by the app (the built-in group's name)
- **WHEN** the app displays that name
- **THEN** the app presents the active language's catalog string for it, not the engine's name

#### Scenario: One name per item across the interface
- **WHEN** the same group is named in more than one place (the groups list, a group picker, a search scope control, a history row, a favorites row, the membership editor header)
- **THEN** every one of those places shows the same string for that group in the active language

### Requirement: Accessibility test identifiers remain invariant
The `Accessible.name` of every interactive element SHALL remain the documented
English value regardless of the display language, so accessibility content
descriptions and automated tests are unchanged across locales.

Where a display label is a localized name, the element's `Accessible.name` SHALL
stay the invariant English value rather than following the display language, so a
group row remains addressable by a stable identifier.

#### Scenario: Element identifier under a non-English locale
- **WHEN** the app displays in a non-English language
- **THEN** each element's `Accessible.name` matches the value documented in AGENTS.md for an English build

#### Scenario: Localized display label with an invariant identifier
- **GIVEN** a group whose display name is localized
- **WHEN** the app displays in a non-English language
- **THEN** the visible label follows that language while the element's `Accessible.name` remains its English value
