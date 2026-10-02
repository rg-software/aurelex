## MODIFIED Requirements

### Requirement: Display language follows the device locale
The app SHALL derive its initial display language from the device's UI language
preference and SHALL use English whenever no translation catalog matches. Only
the first (primary) preferred UI language may select a catalog: the platform's
language list also contains locales the app merely ships resources for, and an
entry that appears later in that list SHALL NOT override the primary one.

#### Scenario: Device UI language is supported
- **WHEN** the app starts on a device whose first UI language has a translation catalog
- **THEN** all app-controlled text is displayed in that language

#### Scenario: Device UI language is unsupported
- **WHEN** the app starts on a device whose UI language has no translation catalog
- **THEN** all app-controlled text is displayed in English

#### Scenario: Region-specific language
- **WHEN** the device UI language is a region variant (e.g. `pt-BR`) and no region-specific catalog exists but a language catalog (`pt`) does
- **THEN** the app displays text using the language catalog

#### Scenario: A later language in the platform list does not override the primary
- **WHEN** the platform reports multiple preferred UI languages and the first has no translation catalog while a later one does
- **THEN** the app displays English, not the later language
