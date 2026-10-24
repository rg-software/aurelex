# Proposal

## Why

Tapping Download for an available update does nothing: no dialog, no
transfer. Root cause in `EngineController::sumRequestedBytes`
(`app/EngineController.cpp`): for an installed entry it sums only the
optional bundle, never the required files ("an already-installed entry
gets only the optional bundle" — written before updates existed, and the
update flow falls into that branch). So an update with audio opted out
(or an entry whose bundle is already current) preflights to zero bytes,
`downloadPreflight` reports `nothing`, and `_startRequests` returns
silently despite a non-empty selection and an enabled button. With audio
on it mis-accounts the other way: it demands headroom for the unchanged
452 MB bundle instead of the 4.5 MB dictionary.

## What Changes

- `sumRequestedBytes` accounts for the update flag: installed + update →
  required files always, optional bundle per the audio flag (mirroring the
  `startCatalogDownload` update branch, which already chooses correctly).
  No engine, parser, manifest, or service change.

## Capabilities

### New Capabilities

<!-- none: defect fix, behavior already specified -->

### Modified Capabilities

- `remote-dictionary-catalog`: the "Updating an installed catalog entry"
  requirement gains a preflight-accounting scenario.
