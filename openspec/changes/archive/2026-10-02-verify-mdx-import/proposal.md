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

**Host testing then found a real defect, which is now part of this change.**
`collinslaw` (Collins Dictionary of Law, 2nd ed.) ships `.mdx` + `.css` + `.jpg`
and **no `.mdd`**. Staging kept only `.mdx`/`.mdd` outside a resource directory,
so both loose files were dropped — measured as *1 staged / 2 dropped* — and every
article, each of which links `collinslaw.css`, would render unstyled. It is the
same defect class as `fix-stardict-staging`: a format's resources live somewhere
the importer does not look.

## What Changes

- **Staging an MDX set's loose assets**, bounded to the extensions an article
  embeds and scoped to files sitting beside a `.mdx`, so an unrelated stylesheet
  elsewhere in a picked tree is not dragged in. Measured flip: collinslaw
  *1 staged / 2 dropped → 3 / 0*.
- **Device verification of MDict import**, on all three shipped shapes, including
  that an article image resolves and renders.
- **A redistributable MDict fixture in the repository**, so the format has a
  regression fixture in CI rather than depending on dictionaries a contributor
  happens to own. `demo.zip` is small (73 KB) and the user has confirmed it can
  be redistributed; the multi-megabyte dictionaries are not committed.
- **The smoke tool's article dump cap is raised**, and it now fetches every
  resource an article references instead of only the first. Both limits were
  invisible until a real MDX dictionary was looked up: the 800 characters stop
  inside `<head>`, and MDX emits its stylesheet first, so the image an article
  shows was never requested.
- `docs/TESTING.md`: recipe #18's known gap is replaced with real recipes and
  real results.

The staging rules already accept `.mdx` and `.mdd` by suffix, including
multi-volume `.mdd` (`demo.1.mdd` … `demo.n.mdd`), so no dictionary-file
handling changes — only what counts as a resource beside one.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- **`dictionary-management`** — staging an MDict set's *loose* assets. This was
  not expected when the change was opened; host testing of `collinslaw` found
  the defect described below, and the delta carries it.

> Originally this change declared `skip_specs: true`, on the reasoning that it
> verified behaviour the spec already required. That reasoning was wrong for one
> MDX shape: an MDX set that ships its stylesheet and images loose, with no
> `.mdd` at all, silently lost them. The marker is removed and the requirement
> is modified.

## Impact

- `app/StagingRules.hpp`, `app/tests/StagingRulesTest.cpp` — the new rule and its
  host tests.
- `app/android/src/org/aurelex/pocket/dictionary/AurelexActivity.java` — the
  staging walk, and `folderHasStarDictIfo` generalised to `folderPrimaryKinds`.
- `carve/smoke/main.cpp` — the article dump limit and the resource fetch.
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
- ~~**Verification that finds nothing.**~~ → **It found something.** The first
  real dictionary tested shipped its resources loose and lost them; the fix is
  bounded and scoped, and the measured flip is recorded in `design.md`.
