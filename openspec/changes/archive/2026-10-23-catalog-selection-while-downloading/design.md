# Design

## Context

See proposal.md — Why. The catalog pane (`app/main.qml`, `dictsPane`) keeps
the ticked entry ids in `catalogSelected`; the row delegate computes
`selectable` as installable-and-eligible **and not downloading**, but the
tap path never consulted it.

## Goals / Non-Goals

**Goals:**

- A tap during an active batch is a no-op, so the highlight can never
  promise an action the pane cannot take.

**Non-Goals:**

- No per-entry download tracking: `downloadActive` is the honest signal —
  while any batch runs, the master button is Cancel-only, so *no*
  selection can be acted on, not just the downloading entries'.
- No selection clearing on download start: a failed or cancelled batch
  keeps its ticks so the user can retry without re-ticking; landed
  entries are pruned by the existing `_pruneSelection` on rescan.

## Decisions

### D1. Guard the handler, not the delegate

`ItemDelegate.enabled` would also dim the row through the Material
disabled state and fight the custom opacity logic. Guarding the single
tap handler is behavior-precise and leaves the visuals untouched.

## Risks / Trade-offs

- [A user who opened the pane mid-download cannot pre-tick the next
  batch] → they could not start it anyway (Cancel is the only button);
  accepted.
