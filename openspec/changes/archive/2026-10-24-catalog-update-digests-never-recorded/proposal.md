# Proposal

## Why

No catalog-installed dictionary can ever show "Update available", for any
entry, on any phone. Root cause in `EngineController::startCatalogDownload`
(`app/EngineController.cpp`): the function records per-entry request-time
SHAs into `m_downloadRequested` while building the transfer, then calls
`m_downloadRequested.clear()` a few lines later before handing the payload
to the download service. When the batch lands,
`recordInstalledDigests()` finds the map empty and — by its fail-closed
rule — records nothing, so `catalogInstalledDigests` stays empty in
`settings.json` forever and the update comparison in
`refreshCatalogEntries()` can never fire.

The spec already requires the intended behavior ("Recorded digests drive
update detection", "Updating an installed catalog entry"); the code never
matched it. This change restores it with a two-line move and no spec edit.

## What Changes

- `m_downloadRequested.clear()` moves from after the request-building loop
  (where it wipes what was just recorded) to before it (where it drops the
  previous batch's records). The terminal-outcome clears stay where they
  are. No engine, parser, manifest, or service change.

## Capabilities

### New Capabilities

<!-- none: defect fix, behavior already specified -->

### Modified Capabilities

<!-- none: `remote-dictionary-catalog` already specifies update detection;
      this change makes the code match it -->
