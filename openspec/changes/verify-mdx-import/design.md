## Context

See `proposal.md` — Why. This design has one job: record why **no code change is
expected**, and what would change that conclusion. It is deliberately short.

Two facts from the tree decide it:

- **The staging rules already accept MDict.** `AurelexActivity`'s supported-name
  filter and `kDictionaryExtensions` both match `.mdx` and `.mdd` by suffix.
  Multi-volume `.mdd` (`demo.1.mdd` … `demo.n.mdd`) therefore matches too, because
  a suffix test does not care about the volume number.
- **The engine resolves MDict resources from three places**
  (`engine/src/dict/mdx.cc`):
  - `<dictionary folder>/<name>` — a **loose file beside the `.mdx`**, checked
    first (`:1336`);
  - the `.mdd` archive(s), including volumes (`:1341`, found by
    `findResourceFiles` at `:1439-1453`).

Host testing has already confirmed the engine side for all three shipped shapes
(demo, Black's, collinslaw — see `proposal.md`), including the loose-file path and
a resource served out of a `.mdd`.

## Goals / Non-Goals

**Goals:**

- Establish, on a device, that an MDict dictionary imported through the picker
  has a working article **and** resolves an image — the one thing host testing
  cannot reach, because it bypasses the Java staging layer entirely.
- Leave a redistributable fixture so the format has a regression path in CI.

**Non-Goals:**

- Changing any **engine** code, or the boundary. Nothing found so far implicates
  either; the defect is in staging alone.
- Committing the large dictionaries. Only `demo.zip` (73 KB, confirmed
  redistributable) is proposed; the 15 MB and 16 MB dictionaries are test
  material, not repository content.
- Building a general MDict fixture generator. Nothing needs it yet; the StarDict
  generator exists because the smoke tool had no StarDict input at all.

**Superseded:** this design originally listed "changing any staging or engine
code" as a non-goal, on the basis that the evidence said MDict worked. Host
testing of `collinslaw` disproved that for one MDX shape — see the decision
below — so the change now carries a `dictionary-management` delta and
`skip_specs` is removed.

## Decisions

### Decision: verify first, change only if the verification fails

The alternative — hardening the MDict paths speculatively because StarDict turned
out to be broken — would mean editing code with no failing case to justify it,
and adding tests for behaviour already covered by suffix matching. The evidence
so far says the paths work; the honest move is to test the claim, not assume the
worse of it.

**Alternatives considered:** *Add a defensive MDict staging change now.* Rejected:
it would be change for its own sake, and would obscure whether the verification
actually proved anything.

### Decision: stage an MDX set's loose assets, bounded and scoped

**The defect.** `collinslaw` (Collins Dictionary of Law, 2nd ed.) ships
`collinslaw2ed.mdx`, `collinslaw.css` and `collinslaw2ed.jpg` — and **no `.mdd`
at all**. Its articles link `collinslaw.css`. Staging kept only `.mdx`/`.mdd`
outside a resource directory, so both loose files were dropped and every article
would render unstyled. Measured against the importer's own rules:

| Fixture | before | after |
| --- | --- | --- |
| collinslaw | 1 staged / **2 dropped** | 3 staged / 0 dropped |
| Black's | 2 staged / 1 dropped (cover) | 3 staged / 0 dropped |
| demo | 2 staged / 0 dropped | unchanged |

This is the same defect class as `fix-stardict-staging`: a format's resources
live somewhere the importer does not look. It was invisible for the same reason —
the CI smoke tool feeds the engine a complete directory and never runs the Java
staging layer.

**The bound.** Recognised only when a `.mdx` sits beside the file, and only for
extensions an article actually embeds (`.css .js .png .jpg .jpeg .gif .svg .ttf
.woff .woff2`). Copying everything beside a dictionary was rejected: an
intersecting pick of a folder holding several dictionaries would drag in
unrelated media — the over-capture problem `res/` already had. `.otf` and audio
are left out deliberately; no fixture justifies them yet, and the tests say so,
so adding them later is a deliberate act rather than an accident.

**Also changed: one pre-scan answers two questions.** `folderHasStarDictIfo`
became `folderPrimaryKinds`, returning a bitmask, so recognising an `.mdx` costs
no extra SAF query per folder. Extending the existing listing rather than adding
a second one keeps the "decision independent of child order" property the
original comment was written for.

**Resources are exempt from `hasStagedCopy` dedup**, exactly as StarDict's `res/`
files are. Two MDX sets in an intersecting pick can legitimately both ship a
`style.css`; deduping the second one away would leave that dictionary unstyled.

### Decision: raise the smoke tool's article dump cap

`carve/smoke/main.cpp` prints only the first 800 characters of a looked-up
article. That is the HTML head and boilerplate, so an article's `<img src>` is
never visible. This has blocked two format investigations — the StarDict resource
question and now the MDict image question — and it is cheap to fix. The cap
becomes large enough to inspect a body, or is made a parameter.

### Decision: commit only the small fixture, and record its provenance

`examples/` and `app/tests/fixtures/` are kilobytes today. `demo.zip` at 73 KB is
a proportionate addition and the user has confirmed it may be redistributed; the
multi-megabyte dictionaries are not, and are referenced as external test material
in the docs instead. Provenance and licence go beside the fixture, following
`app/openssl/README.md` and `scripts/assets/kaikki-tag-icons/README.md`.

### Decision: exercise the fixture where the StarDict bug was missed

The StarDict import bug shipped green because the CI smoke tool feeds the engine
a **complete directory** and never runs the Java staging layer. A committed MDict
fixture is only worth having if it closes that gap rather than repeating the same
blind spot. The tasks therefore place the fixture where it can be exercised, and
state plainly which half any given check covers.

## Risks / Trade-offs

- **[Verification finds nothing]** ~~The likely outcome is that MDict works and
  this change is docs plus a fixture.~~ → **It did not.** `collinslaw` exposed a
  real staging defect on its second shape; see the decision below.
- **[A committed binary fixture]** Provenance can be lost. → Record source,
  licence and digest beside it, as the existing vendored assets do.
- **[`collinslaw`'s CSS size looked wrong]** Served 1684 bytes for a 1061-byte
  file. → Not a defect: `mdx.cc:811` runs `isolate_css()`, which rescopes CSS
  links per dictionary. Recorded so the next person does not re-investigate it.

## Migration Plan

None. No stored state, no format change, no code change expected. Rollback is
reverting the commit.

## Open Questions

None that affect the approach. Whether an MDict *image* renders on device is the
question this change exists to answer, not one to resolve before starting.
