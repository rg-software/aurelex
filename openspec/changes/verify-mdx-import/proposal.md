## Why

MDict (`.mdx`/`.mdd`) is the most widely used format Aurelex claims to support —
it is the dominant bilingual and CJK dictionary format — and it has **no test
coverage and no on-device verification at all**. The CI smoke tool has no `.mdx`
fixture; its only "mdx" strings are a *search term* found inside a StarDict
article body. `docs/TESTING.md` records recipe #18 (`.mdd` images) as a known
gap: *"not exercised on-device — no MDX fixture yet"*.

That is the same position StarDict was in before `fix-stardict-staging`, where a
format advertised as supported turned out to have a real import bug that only a
genuine dictionary exposed. MDict deserves the same scrutiny before its "Works"
claim is trusted.

**Host evidence already gathered** (three real dictionaries, all load):

| Fixture | Shape | Result |
| --- | --- | --- |
| `demo.zip` | `.mdx` + `.mdd` | loads; engine served a 20604-byte `.ttf` from the `.mdd` |
| Black's Medical Dictionary | `.mdx` + 14 MB `.mdd` | loads; real headwords resolve; served `blackmed2018.css` from the `.mdd` |
| `collinslaw.zip` | `.mdx` + **loose** `.css`/`.jpg`, no `.mdd` | loads; served CSS (rescoped by `isolate_css`) |

So the resource pipeline demonstrably works for three distinct shapes on host.
What is unproven is the part host testing cannot reach: the **importer's staging**
of an MDict set, and whether an **image** — not a font or a stylesheet — actually
resolves and renders in the app.

## What Changes

- **Device verification of MDict import**, on all three shipped shapes, including
  that an article image resolves and renders.
- **A redistributable MDict fixture in the repository**, so the format has a
  regression fixture in CI rather than depending on dictionaries a contributor
  happens to own. `demo.zip` is small (73 KB) and the user has confirmed it can
  be redistributed; the multi-megabyte dictionaries are not committed.
- **The smoke tool's article dump cap is raised.** It currently prints only the
  first 800 characters of an article, which is the HTML boilerplate, so an
  article's `<img src>` cannot be inspected. This has now blocked two format
  investigations and is the reason the image question above is still open.
- `docs/TESTING.md`: recipe #18's known gap is replaced with real recipes and
  real results.

This is a **verification change**. A code fix is expected only if the device pass
finds one — the staging rules already accept `.mdx` and `.mdd` by suffix,
including multi-volume `.mdd` (`demo.1.mdd` … `demo.n.mdd`), and the engine's
resource resolution is confirmed working.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

None expected. If the device pass finds a staging defect, a
`dictionary-management` delta is added at that point — the change deliberately
does not pre-commit to a spec edit it cannot yet justify.

> `openspec` rejects a zero-delta change unless `.openspec.yaml` sets
> `skip_specs: true`; that marker is set, because this change verifies behaviour
> the spec already requires rather than changing it. If verification uncovers a
> defect, the marker is removed and a delta added in the same change.

## Impact

- `carve/smoke/main.cpp` — the 800-character article dump limit.
- `docs/TESTING.md` — recipe #18 and the "Known gaps" entry for `.mdd` images.
- A committed MDict fixture (proposed: `examples/dictionaries/`, alongside the
  existing DSL samples) plus whatever generator or script is needed to produce
  or document it.
- `scripts/make-smoke-stardict.py` may gain an MDict sibling if the fixture is to
  be exercised by the CI smoke tool — the same gap that let the StarDict import
  bug ship green.
- No engine, carve-source, boundary or patch change is anticipated.

## Risks

- **A committed binary fixture.** The repository's existing fixtures are
  kilobytes; `demo.zip` is 73 KB and the others are 15 MB. Only the small,
  explicitly redistributable one is proposed for commit, and its provenance and
  licence must be recorded beside it.
- **Verification that finds nothing.** The most likely outcome is that MDict
  works and this change is docs plus a fixture. That is a good outcome, not a
  wasted one: it converts an unverified claim into a tested one.
