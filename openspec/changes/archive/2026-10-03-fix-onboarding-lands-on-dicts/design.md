## Context

`app/main.qml` decides the start tab in two places:

- On the authoritative async `onOnboardedChanged` (guarded by `_bootRouted`):
  first run (`onboarded == false`) → Dicts (`state = 1`), every other launch
  (`onboarded == true`) → Search (`state = 0`). Chosen deliberately in
  `2026-09-25-groups-tab-polish` (design D1) so a returning user does not land on
  Dicts.
- In the "Get started" `onClicked`: `engine.onboarded = true` then `root.state = 0`
  (Search), with a comment "the Dicts tab was only chosen to host the welcome
  overlay".

The overlay itself is a `Rectangle` inside the Dicts pane (`visible:
!engine.onboarded`), because Dicts has no inline WebView and so cannot be
punctured by the native Android surface.

## Goals / Non-Goals

**Goals**

- After dismissal the user is on the tab whose controls the card just described.

**Non-Goals**

- Changing first-launch or returning-user routing (both already correct).
- Persisting the start tab, or making onboarding skippable — unchanged.

## Decisions

### D1: Dismissing leaves the tab where the overlay was

The "Get started" handler sets `engine.onboarded = true` and **does not** move to
Search — it lands on Dicts (`state = 1`). Dicts is already the current tab while
the overlay shows, so this is a no-op navigation in practice; making it explicit
keeps the destination intentional rather than incidental.

Rationale: the card's own instruction is "Tap the Folder button … Tap the Cloud
button …", both in the Dicts toolbar. Search cannot satisfy that instruction
until a dictionary exists, and the empty Search state only re-teaches the same
thing.

Alternative rejected: keep landing on Search and rely on the empty-search
guidance. That preserves a model — "Search is the start tab" — which the spec
never actually required for this transition; the requirement's other scenarios
already fix the returning-user case, so relaxing this one costs nothing.

### D2: The `_bootRouted` guard already covers the re-entry

The dismissal also flips `engine.onboarded`, which re-emits `onboardedChanged`.
`_bootRouted` is already true by then (set on the first, authoritative emission),
so the connection cannot override the handler's destination. No new guard needed;
verify it rather than add one.

## Risks / Trade-offs

- **A user who dismisses and immediately wants to search now taps Search.** Trivial
  and symmetrical with today's behaviour in reverse.
- **The spec listed the Search destination as a scenario**, so this is a
  deliberate requirement change, not a bug fix → the delta spec and
  `docs/TESTING.md` row 47/48 wording are updated in the same change.
- Nothing else reads the dismissal destination, and the tab index is not
  persisted, so there is no migration.

## Open Questions

None.
