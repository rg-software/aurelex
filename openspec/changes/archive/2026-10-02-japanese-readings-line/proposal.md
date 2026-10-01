## Why

A Japanese card listed each reading as if it were an inflected form, with every
scholarly tag spelled out:

```
座
	[i]ザ (読み, 呉音, 常用), サ (読み, 漢音), すわ-る (読み, 訓, 常用), くら (読み, 訓)[/i]
```

That is not how a dictionary reads, and it drowns the actual information:

- `呉音`/`漢音`/`唐音` are historical reading *strata*; a general dictionary says
  音. `常用` is not a property of the reading at all (it says the reading is in
  the Jōyō kanji table). `古訓` is an obsolete kun reading.
- The mark repeats on every reading, where a dictionary groups: `音 ザ・サ　訓
  すわ-る・くら`.
- Readings and inflections share one line, so a verb's conjugation and its
  readings look like the same kind of thing.
- A reading repeated across a card's parts of speech printed once per part.

## What Changes

- A profile can declare which form tags are **readings** rather than inflections,
  the mark each reading's origin prints under, and the default mark for a reading
  the source does not classify. Japanese collapses `go-on`/`kan-on`/`to-on` to
  音 and `kun`/`ko-kun` to 訓, with 読み for the rest.
- Readings move to their own line, grouped under their mark, and leave the forms
  line to inflections only.
- A card whose records agree on their readings shows that line once, above the
  first part of speech.

Result:

```
座
	[com]音: ザ, サ　訓: すわ-る, くら[/com]
	[p]名詞[/p]
	…
	[p]接尾辞[/p]
```
```
保護
	[com]読み: ほご[/com]
	[p]名詞[/p]
	…
	[p]動詞[/p]
	[i]保護し (未然形), 保護する (終止形), …[/i]
```

## Capabilities

Modifies **dictionary-conversion**: "Source-language profiles" (readings are a
declared kind of form) and "Card article layout" (readings are grouped on their
own line).

## Impact

- `scripts/kaikki/profiles.py` (`LangProfile`, the `ja` constants,
  `collect_profile_forms`, new `collect_profile_readings`).
- `scripts/kaikki/render.py` (the readings line, hoisted or per part of speech).
- `scripts/tests/test_kaikki_to_dsl.py`.
- `docs/KAIKKI-CONVERSION.md`.
