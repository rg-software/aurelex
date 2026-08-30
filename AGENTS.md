# AGENTS.md — Working notes for AI agents and contributors

This file tells agents and contributors how to work in this repository safely. Read it before making changes.

## What this project is

Aurelex is an Android port of [goldendict-ng](https://github.com/xiaoyifang/goldendict-ng).
It reuses the upstream C++ dictionary engine (rendered via Android WebView) rather than reimplementing
dictionary formats. Design is tracked with OpenSpec in `openspec/changes/goldendict-mobile-port/`
(`proposal.md`, `design.md`, `specs/`). The project is currently in the **planning phase** — code
implementation has not started.

## Golden rules

1. **Never edit upstream engine code in place.** Upstream lives in the `engine/` Git submodule,
   pinned at a release *tag*. Any deviation from upstream must live in `patches/` or in the boundary
   layer outside `engine/`. Long-hand: the goal is that `git diff` between a bump and our tree stays
   tiny, and a CI smoke test catches breakage.
2. **Do not shim Qt types.** The carve compiles with real Qt 6 (Core/XML/Concurrent) for Android.
   Do not write `QString`/`QList`/`QXmlStreamReader` reimplementations on std:: — that would make
   every upstream merge expensive. Reconsidering this is a design decision (see design.md D1), not
   something an agent may do to make a build pass.
3. **The boundary is the C API.** Kotlin talks to the engine only through the `gd_*` JNI boundary
   (`gd_init`, `gd_scan_dicts`, `gd_lookup`, `gd_suggest`, `gd_get_resource`, `gd_get_audio`,
   `gd_cleanup`) plus whatever the boundary later grows to. New features either:
   - touch the boundary / carve → go through the patch pipeline (`patches/` + CI smoke), or
   - are pure Kotlin → can be added anytime without engine involvement.

## Repository layout (target)

- `engine/` — goldendict-ng submodule, pinned at a release tag, never edited.
- `patches/` — the only deviations from upstream (icon stubs and glue). Keep < ~3 files if possible.
- `app/` — Android app (Kotlin, Compose, WebView) + JNI boundary + C API header.
- `openspec/` — OpenSpec planning artifacts (the design is the source of truth for scope).

## Scope constraints

- **v1 formats:** mdict (`.mdx`/`.mdd`), DSL (`.dsl`/`.dsl.dz`), StarDict (`.ifo`). Other formats are
  converted on a computer (e.g. pyglossary) and copied to the phone.
- **Cut for v1:** network dictionary sources, full-text search (xapian), Zim/EPWING/Aard/SLOB/BGL/
  SDict/GLS/XDXF natively, scan popup, system tray, global hotkeys, TTS, print/PDF. See
  `design.md` — Cut scope register for the full (a)/(b) lists.
- **Audio:** ogg/mp3/wav play; speex (`.spx`) is unsupported-but-graceful in v1.

## OpenSpec commands

```bash
openspec list --json
openspec status --change goldendict-mobile-port --json
openspec instructions <artifact-id> --change goldendict-mobile-port --json
openspec validate goldendict-mobile-port
```

The schema is `spec-driven`. Spec scenario/requirement format is strict (4-hashtag scenarios,
SHALL/MUST language) — follow the instructions output before writing any artifact.

## Conventions

- Spec capability paths: kebab-case, flat layout (`dictionary-management`, `lookup`, ...).
- Commit messages: concise, matching the change being described; never commit unless asked.
- Before any upstream bump: build the engine, run the CI smoke test, and update specs only if
  observable behavior changed (never massage specs to fit a refactor).
- Work flows through OpenSpec changes first; implementation does not run ahead of the plan.