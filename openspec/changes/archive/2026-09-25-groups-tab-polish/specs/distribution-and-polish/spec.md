## MODIFIED Requirements

### Requirement: First-run onboarding
The system SHALL guide a new user through first steps on first launch and SHALL
show helpful guidance when the app has no dictionaries yet. On first launch the
app SHALL land on the Dictionaries tab (which has no article WebView), show an
onboarding card teaching how to add dictionaries, and SHALL NOT pop the onscreen
keyboard. Once onboarding is complete (no onboarding screen shown), the app SHALL
start on the Search tab on every launch.

#### Scenario: First launch shows onboarding on the Dictionaries tab
- **WHEN** the app is launched for the first time
- **THEN** it lands on the Dictionaries tab, shows an onboarding card explaining
  how to add dictionaries, and the onscreen keyboard is not shown

#### Scenario: Onboarding is dismissed
- **WHEN** the user taps "Get started" on the onboarding card
- **THEN** the card disappears, the keyboard is not shown, and the app switches
  to the Search tab

#### Scenario: Subsequent launches start on Search
- **WHEN** the user opens the app after onboarding is complete
- **THEN** the app starts on the Search tab (no onboarding screen)

#### Scenario: Empty search state
- **WHEN** the user opens search with no dictionaries loaded
- **THEN** the app explains (via onboarding guidance or a non-blank empty state)
  that dictionaries must be added first, instead of showing a blank screen