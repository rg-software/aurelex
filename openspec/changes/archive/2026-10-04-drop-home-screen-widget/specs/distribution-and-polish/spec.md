## MODIFIED Requirements

### Requirement: App icon
The system SHALL ship a proper adaptive launcher icon and SHALL use it in the
app notifications and the Quick-Settings tile.

#### Scenario: Launcher shows the app icon
- **WHEN** the user looks at the launcher
- **THEN** Aurelex shows its adaptive icon instead of a default placeholder

#### Scenario: Notification and tile use the icon
- **WHEN** the engine notification or the Quick-Settings tile is rendered
- **THEN** it uses the same app icon
