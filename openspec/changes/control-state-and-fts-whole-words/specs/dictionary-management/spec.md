## ADDED Requirements

### Requirement: Control styling distinguishes default, disabled, and primary
The app SHALL NOT use the same appearance for a usable default/secondary control, a disabled control, and a primary action. A control that is enabled and is a primary action SHALL use the app's accent styling; a control that is enabled but secondary SHALL use default styling; a control with `enabled: false` SHALL be the only one that reads as disabled. Dialog action buttons SHALL follow the same rule, so a secondary `Cancel` is never mistaken for a disabled `Cancel`.

#### Scenario: A primary action is not grey
- **WHEN** an icon control performs a primary action and is enabled
- **THEN** it is rendered in the app's accent styling, not the default grey

#### Scenario: Disabled is visually distinct
- **WHEN** a control is disabled
- **THEN** it is rendered differently from an enabled secondary control

#### Scenario: Cancel is distinguishable from disabled
- **WHEN** a dialog shows its action buttons
- **THEN** the buttons are rendered so that removing the accent from an enabled button does not make it look disabled

### Requirement: An empty error banner is not shown
The engine-error banner SHALL be shown only when the engine reports a non-blank message; a whitespace-only message MUST NOT paint the banner.

#### Scenario: Blank message paints nothing
- **WHEN** the engine reports a message that is empty or only whitespace
- **THEN** no error banner is shown

#### Scenario: A real message is shown
- **WHEN** the engine reports a non-blank message
- **THEN** the error banner is shown with that message
