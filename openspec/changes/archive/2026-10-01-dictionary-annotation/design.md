## Context

`build()` always emits an about article whose headword is the literal
`About this dictionary` (`kaikki-to-dsl.py:2489`), and nothing else. The DSL
header vocabulary the engine understands is fixed (`#NAME`,
`#INDEX_LANGUAGE`, `#CONTENTS_LANGUAGE`, `#SOUND_DICTIONARY`,
`#SOURCE_CODE_PAGE`), so attribution cannot live in headers. But the engine
already reads a Lingvo-style sibling annotation: `Dictionary::getDictionaryDescription`
(`engine/src/dict/dsl.cc:1017`) chops the dictionary filename and reads
`<base>.ann`, plain text (optionally split into `#LANGUAGE "…"` sections). That
gives metadata a real, native home beside the file.

## Goals / Non-Goals

**Goals**

- A user with several produced dictionaries can tell their about articles apart.
- The attribution has a home a DSL reader surfaces as a description, not only as
  a lookupable article.

**Non-Goals**

- No app-side About screen or boundary function; the engine reads the annotation,
  Aurelex does not surface it yet (follow-up).
- No localization of the attribution (the source language is English).
- No change to the header vocabulary or the about article's content.

## Decisions

### D1: Name the about headword after the dictionary

The about article's headword becomes `About <name>`, where `<name>` is the
dictionary's `#NAME` (`--name` or `kaikki-<source>`). It uses only input the
pipeline already has, needs no new option, and is unique per produced dictionary.

### D2: Write the annotation beside the dictionary, as plain text

`write_annotation` produces `<out-dir>/<name>.ann` — the path the engine derives
from `<name>.dsl.dz` (`chop(6)` then `+ "ann"`). The content mirrors the about
card's facts (source, license, citation, snapshot date, language, generator) as
plain text lines, not DSL markup: an annotation is read as a description, not
rendered as an article, so `[com]`/`[trn]` would show up literally.

### D3: Always write it, whatever else the run does

The annotation is metadata about the dictionary, not a bundled resource, so it is
written on every build — including `--no-audio`, `--sample` and `--reuse-bundle`
— and simply overwritten. It never touches the audio bundle or its verification.

## Risks / Trade-offs

- **The annotation is invisible to Aurelex until the app surfaces it.** Harmless:
  GoldenDict desktop and other Lingvo-aware readers show it now, and the about
  article still carries the attribution for the app. A boundary function + a
  details surface is the follow-up.
- **Aurelex's import may not stage `.ann`.** Its picker copies a fixed set of
  dictionary extensions; `.ann` must be added when the app starts using it.
  Noted, not done here.
