## MODIFIED Requirements

### Requirement: Android-managed surfaces localized
The installed-app launcher label, Quick-Settings tile label, and
foreground-service notification title and text SHALL follow the Android system
string resources for the device locale with an English default.

#### Scenario: Localized Android labels and notifications
- **WHEN** the app is installed on a device whose UI language has Android string resources and a foreground service (staging or indexing) is shown
- **THEN** the launcher/tile labels and the notification title and text are presented in the device's language
