# Design

## Context

See proposal.md — Why. The digest pipeline has three steps: (1)
`startCatalogDownload` remembers request-time SHAs per entry name in
`m_downloadRequested`; (2) the service reports success by name;
(3) `recordInstalledDigests` merges the remembered SHAs into
`catalogInstalledDigests` in `settings.json`. Step 3's fail-closed skip
("an entry with no request record is skipped") is correct in isolation —
it turns a wiped map into *silently recording nothing, forever*.

## Goals / Non-Goals

**Goals:**

- Request-time SHAs survive from batch start to batch terminal, so the
  first catalog install after this fix records a baseline and later
  manifest moves flag updates.

**Non-Goals:**

- No backfill for installs that landed while recording was broken: their
  staged bytes are fine, but no baseline exists to compare against. One
  remove + catalog reinstall re-baselines; the pane's update flow then
  works from there.
- No service/manifest/parser change; no new persistence.

## Decisions

### D1. Move the clear, keep the outcome resets

`m_downloadSucceeded`/`m_downloadFailed` clears at batch start correctly
reset previous terminal state and stay. Only `m_downloadRequested.clear()`
moves — to just before the request-building loop, where it drops the
*previous* batch's records instead of the current one's. The
`clearDownloadOutcome` wipe (4s after terminal) is harmless: recording is
synchronous at terminal, already saved by then.

## Risks / Trade-offs

- [A batch refused at the free-space gate leaves a populated
  `m_downloadRequested`] → the next batch start clears it first; a stale
  map can never leak into a later record.
- [No C++ unit harness covers `startCatalogDownload`] → verification is
  diff review plus the existing catalog test suite staying green; the
  function cannot run outside the Android activity.
