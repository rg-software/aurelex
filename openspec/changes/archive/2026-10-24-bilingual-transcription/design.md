# Design

## Context

See proposal.md — Why. `audio.py` already scans the source-language
snapshot per headword (`collect_records`); transcription reuses those
records. The notation discipline (which `sounds[]` field wins, which tags
disqualify) lives in `kaikki.render._record_transcription`; importing that
one private function beats copying its 15 lines and drifting from it.

## Goals / Non-Goals

**Goals:**

- Transcription wherever kaikki has it, in both translation directions,
  with zero new downloads (same snapshot scan the audio planner does).

**Non-Goals:**

- No per-sense or per-POS transcriptions: kaikki records do not map onto
  RuWordNet senses, so anything finer than one-per-card would imply an
  alignment we do not have. Disagreement collapses to most-common.
- No pairs cards: examples-only cards stay minimal.

## Decisions

### D1. Reuse the per-record picker, decide the per-card policy locally

`kaikki.render._record_transcription(record, profile)` (explicit
same-repo private reuse, documented at the import) decides one record's
text; bilingual counts votes across the headword's records, first-seen
wins ties. Deterministic for a pinned snapshot.

### D2. One scan per build, not per feature

`collect_records` memoizes per snapshot path + language in-process, so the
audio planner and the transcription picker share the single streaming
pass. Test fixtures use temp paths, so no cross-test leakage.

### D3. `[t]` under the headword, audio untouched

`[s]` lines stay exactly where they are; the `[t]` line goes right after
the headword line, before everything else. A card with a transcription
but no recordings keeps the text.

## Risks / Trade-offs

- [Records disagree (`read` /riːd/ vs /rɛd/)] → most-common wins; the
  card cannot show both without implying a sense split. Accepted, same
  trade-off as kaikki's hoist.
- [Importing a private across modules] → one documented import; the
  alternative (a copy) drifts silently.
