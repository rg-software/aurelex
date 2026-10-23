# Proposal

## Why

In the remote catalog pane, rows already render dimmed while a download
batch runs (`selectable` includes `!engine.downloadActive`, the audio
toggle disables, the master button becomes Cancel). But the name tap
handler (`_toggleCatalogSelect`) never checks `downloadActive`, so entries
can still be (de)selected mid-download — a highlight with no possible
action, since the only available button is Cancel. Installed entries are
likewise untappable (only their audio toggle works); in-flight entries
should behave the same until the batch lands or fails.

## What Changes

- `_toggleCatalogSelect` ignores taps while `engine.downloadActive` is
  true, matching the row's own `selectable` state.
- One new scenario under "Selecting and downloading dictionaries"; no
  engine, parser, or manifest change. No new dependencies.

## Capabilities

### New Capabilities

<!-- none: this change corrects an existing capability -->

### Modified Capabilities

- `remote-dictionary-catalog`: the "Selecting and downloading dictionaries"
  requirement gains a no-selection-while-downloading scenario.
