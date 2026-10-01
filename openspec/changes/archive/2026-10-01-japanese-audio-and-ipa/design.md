## Context

The profile flag and the transcription renderer are separate concerns that met
here: turning Japanese audio on exposed a defect in how a `sounds[]` value is
chosen.

## Decisions

### D1: Flip the flag rather than special-case the language

`has_audio` means "does this language have recordings", and Japanese has 106 of
them. The cost (the audio archive must be resolved) is real, so it is the user's
call at build time: pass `--audio-tar` to reuse a cached archive rather than
download 20 GB.

### D2: Reject a value whose tags name a different notation

Two candidate fixes for the X-SAMPA problem: drop `ipa` from Japanese (losing the
160 real ones), or skip the mismatched sounds. The second is chosen because the
tag is authoritative — the source states the notation — so the rule is general
("a sound tagged as another notation is not shown as this one") and not
Japanese-specific. The tag set lives beside the other pronunciation constants in
`source.py`.

## Risks / Trade-offs

- **The guard is tag-driven.** If a `sounds[]` entry carries X-SAMPA under `ipa`
  *without* the tag, it is not caught. In this snapshot every X-SAMPA value found
  was tagged, so the tag is the reliable signal.
- **Japanese audio is 0.07%.** Most articles will still have no recording; that
  is the source, not the pipeline.
