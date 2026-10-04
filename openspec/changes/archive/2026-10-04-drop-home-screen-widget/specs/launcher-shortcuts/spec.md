## REMOVED Requirements

### Requirement: Home-screen shortcut widget
**Reason**: The widget was never more than a shortcut that opens the app on the
Search tab — `RemoteViews` cannot capture typed text, so it never looked a word
up. The Quick Settings tile reads the clipboard and performs a real lookup, and
the share sheet, the selection toolbar and the `aurelex://lookup` deep link cover
the rest. The surface is removed rather than left claiming a capability the app
cannot deliver.

## MODIFIED Requirements

### Requirement: No dictionary interference
Launcher shortcuts SHALL respect the currently active group: a lookup launched by
the tile uses the same group settings as a typed lookup and must not change the
active group or dictionary order.

#### Scenario: Shortcuts respect the active group
- **WHEN** a lookup is launched via the tile while a specific group is active
- **THEN** the article reflects that group's dictionaries and order, and the group selection is unchanged
