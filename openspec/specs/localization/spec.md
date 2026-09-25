# localization Specification

## Purpose
Makes every user-visible string in the app follow the device's UI language via
per-language translation catalogs, with English as the base fallback, while
keeping automated-test IDs invariant.
## Requirements
### Requirement: Display language follows the device locale
The app SHALL derive its initial display language from the device's UI language
preference and SHALL use English whenever no translation catalog matches.

#### Scenario: Device UI language is supported
- **WHEN** the app starts on a device whose first UI language has a translation catalog
- **THEN** all app-controlled text is displayed in that language

#### Scenario: Device UI language is unsupported
- **WHEN** the app starts on a device whose UI language has no translation catalog
- **THEN** all app-controlled text is displayed in English

#### Scenario: Region-specific language
- **WHEN** the device UI language is a region variant (e.g. `pt-BR`) and no region-specific catalog exists but a language catalog (`pt`) does
- **THEN** the app displays text using the language catalog

### Requirement: Per-language external catalogs
The system SHALL keep user-visible app strings in catalogs split by language,
outside the UI source files, and SHALL allow adding a language without touching
app source code.

#### Scenario: Adding a new language
- **WHEN** a translator adds a new language catalog
- **THEN** no QML, C++, or Java source file changes are required for the new language to be served to devices using that language

### Requirement: No inline user-visible strings
The system MUST NOT hardcode user-visible text wherever the app generates it:
QML labels, dialog and onboarding copy, status banners, and the WebView chrome
rendered by the app's QML JavaScript (history rows, favorites, suggestion
dropdown, clear actions).

#### Scenario: QML-label string
- **WHEN** a QML element displays a user-visible label
- **THEN** the label text is resolved from the active language's catalog, not from an inline literal

#### Scenario: App-generated WebView chrome
- **WHEN** the app renders history, favorites, suggestions, or in-article chrome inside the article WebView
- **THEN** any user-visible English words in that chrome are resolved from the active language's catalog

### Requirement: Accessibility test identifiers remain invariant
The `Accessible.name` of every interactive element SHALL remain the documented
English value regardless of the display language, so accessibility content
descriptions and automated tests are unchanged across locales.

#### Scenario: Element identifier under a non-English locale
- **WHEN** the app displays in a non-English language
- **THEN** each element's `Accessible.name` matches the value documented in AGENTS.md for an English build

### Requirement: Android-managed surfaces localized
The installed-app launcher label, Quick-Settings tile label, home-screen search
widget label, and foreground-service notification title and text SHALL follow
the Android system string resources for the device locale with an English
default.

#### Scenario: Localized Android labels and notifications
- **WHEN** the app is installed on a device whose UI language has Android string resources and a foreground service (staging or indexing) is shown
- **THEN** the launcher/tile/widget labels and the notification title and text are presented in the device's language

#### Scenario: Missing Android localization
- **WHEN** the device UI language has no Android string resources
- **THEN** the Android-managed labels and notifications fall back to the default (English) resources

### Requirement: Parameterized messages
User-visible messages that embed values (counts, dictionary names) SHALL use
placeholder substitution so word order and plural forms conform to the active
language's rules instead of concatenation.

#### Scenario: Count in a localized message
- **WHEN** a message embeds numbers such as indexing progress ("N of M" dictionaries) or membership counts
- **THEN** the numbers are substituted into the active language's message template and the result is well-formed in that language

