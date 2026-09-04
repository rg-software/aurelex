## Why

Aurelex has zero accessibility annotations in its QML UI. This means TalkBack users hear nothing useful — every button is just "button," every text field is just "text field." Beyond the accessibility gap, this also prevents any automated on-device UI testing via UIAutomator/Appium, which rely on `content-desc` (derived from `Accessible.name`) to locate elements. Adding accessibility annotations is the right thing to do for users and unblocks future testability.

## What Changes

- Add `Accessible.name` and `Accessible.role` properties to every interactive QML element in `main.qml` (~63 elements across all panes: navigation, search, dictionaries, groups, article, FTS, history, favorites, onboarding, and dialogs).
- Dynamic `Accessible.name` bindings on state-dependent elements (e.g., the favorites star toggles between "Add to favorites" / "Remove from favorites"; the dark-mode toggle announces current state).
- Informational/progress elements (ProgressBar, error labels, section headers) also receive appropriate `Accessible.role` values so TalkBack announces their purpose.
- No new files, no new dependencies, no behavioral changes — purely additive `Accessible.*` property annotations on existing QML elements.

## Capabilities

### New Capabilities
- `accessibility`: System-wide accessibility annotations for all interactive and informational QML elements, enabling TalkBack screen reader support and UIAutomator-based element discovery.

### Modified Capabilities
_(none — this is purely additive; no existing spec-level behavior changes)_

## Impact

- **Code:** `app/main.qml` — the only file modified. Each interactive element gains 1–2 lines (`Accessible.name`, `Accessible.role`).
- **Dependencies:** None. `QtQuick.Accessibility` is already available via the existing `import QtQuick` (it's part of the QtQuick module).
- **Behavioral:** No functional change. The app behaves identically; screen readers and accessibility services gain semantic information.
- **Risks:** Minimal. `Accessible.*` properties are no-ops when no accessibility service is active. They add zero runtime cost in the normal (non-TalkBack) path.
