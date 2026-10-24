# Design

## Context

See proposal.md — Why. Two functions must agree on what an update fetches:
`startCatalogDownload` (builds the transfer — already correct: required
always, optional only when the bundle actually changed or is unrecorded)
and `sumRequestedBytes` (sizes the free-space preflight — wrong: optional
only). The fix makes the sizer mirror the builder.

## Goals / Non-Goals

**Goals:**

- An update preflight counts exactly what the update transfer fetches, so
  the free-space gate decides on real numbers and `nothing` stays
  unreachable for a genuine update.

**Non-Goals:**

- No change to the transfer itself, the dialogs, or the `nothing`
  short-circuit (still correct for the truly-nothing case).
- No service/manifest/parser change.

## Decisions

### D1. Mirror the builder in the sizer

The update branch (`installed && update`) sums required files plus the
optional bundle exactly when the request asks for audio — the same rule
`startCatalogDownload` uses to choose files. One rule in two places is a
smell, but the sizer cannot reuse the builder's `chosen` list (it runs
before the request is built and must stay side-effect free); the scenario
below pins them together instead.

## Risks / Trade-offs

- [A future fetch rule must be updated in both functions] → accepted and
  documented by the scenario; unifying them would couple a pure query to
  transfer construction.
