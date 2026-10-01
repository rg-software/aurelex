## Why

The `ja` profile declared `has_audio=False` and an empty `pron_fields`, on a
comment that actually said the source has no **IPA** — not no audio. Wiring the
flag up (in the Japanese-profile change) therefore made every Japanese build
silently discard the pronunciations the source *does* have.

Measured against the 2026-09-01 jawiktionary extract (148,282 Japanese records):

| | count | share |
| --- | --- | --- |
| records with an audio URL | 106 | 0.07% |
| records with an IPA sound | 205 | 0.14% |

Sparse, but real (`日本語 → Ja-nihongo.ogg`, `広島 → Ja-Hiroshima.ogg`), so
`has_audio=False` was simply untrue. The same probe found the `ipa` field is a
mix: of 277 `ipa` sounds, **117 are tagged `X-SAMPA`** — showing those as IPA
would be wrong.

## What Changes

- Japanese declares `has_audio=True` and prefers the `ipa` field, so its
  recordings are planned and its transcriptions shown.
- A `sounds[]` entry whose tags name a **different notation** is skipped instead
  of being shown as the notation its field claims.

## Capabilities

Modifies **dictionary-conversion**: the "Card article layout" requirement (a
sound in another notation is not shown as this one). The `ja` flag itself is
profile data, covered by "Source-language profiles".

## Impact

- `scripts/kaikki/profiles.py` (the `ja` entry), `source.py` (the notation tag
  set), `render.py` (`_record_transcription`).
- `scripts/tests/test_kaikki_to_dsl.py`.
- `docs/KAIKKI-CONVERSION.md`.
