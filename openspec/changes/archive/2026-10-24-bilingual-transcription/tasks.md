# Tasks

## 1. Transcription picker (audio.py)

- [x] 1.1 `collect_records` memoizes per snapshot path + language;
      `transcribe_words` picks most-common per headword via kaikki's
      per-record notation discipline
- [x] 1.2 Unit tests: IPA picked, X-SAMPA skipped, enPR labeled,
      most-common wins, tie goes first-seen, missing → no line

## 2. Card wiring (dsl.py, build.py, preview.py, constants.py)

- [x] 2.1 `Card.transcription` field; `emit_card` renders `[t]` after the
      headword; `[t]` joins the builder tag allowlist; preview mirrors it
- [x] 2.2 Translation build attaches transcriptions whenever a snapshot is
      present (independent of the audio switch)
- [x] 2.3 Unit tests: `[t]` placement; snapshot-less build carries none

## 3. Verification

- [x] 3.1 Full unit suite green; change validates; main spec in sync
- [x] 3.2 Sample translation build eyeballed (transcription beside audio,
      silent card keeps its text); smoke through the real reader
