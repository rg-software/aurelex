## Context

Japanese is the first language whose readings are `forms[]` entries rather than
a pronunciation field, so the renderer had no concept of a "reading" and treated
them as inflections. The fix belongs in the profile (what the tags mean) plus a
small renderer rule (where the line goes).

## Decisions

### D1: Readings are a profile concept, not a Japanese special case

`LangProfile` gains `reading_tags`, `reading_marks` and `reading_default`.
`collect_profile_forms` skips a form carrying a reading tag, and the new
`collect_profile_readings` groups the rest. English, German and Russian declare
nothing, so their behaviour is untouched by construction rather than by a
language check.

### D2: `音`/`訓`, not the strata

The origin tags collapse to the two marks a general dictionary uses. The finer
distinction is real but scholarly, and the change's point is that the line reads
like a dictionary. The mapping is data (`reading_marks`), so a kanji dictionary
could map `go-on` to `呉音` instead without a code change.

### D3: A card's readings hoist when the records agree

`座` carries the same readings under 名詞 and 接尾辞, and printing them twice was
part of the noise. Hoisting mirrors the transcription's existing rule (one line
above the first part of speech when every record agrees, else one per block).

## Risks / Trade-offs

- **Dropping `呉音`/`漢音`/`常用` loses information** that is in the source. It is
  recoverable: the change is a mapping in `reading_marks`, and the source data is
  untouched.
- **`読み` is the largest group.** ~6,400 form instances carry only
  `transliteration`, so many entries show `読み: …` rather than 音/訓 — we show
  what the source knows, and nothing more.
- **`--include-inflections` no longer indexes readings** (they are not
  inflections). That is a correction, but it means kana lookup still needs the
  dedicated "index the readings" option that remains unbuilt.
