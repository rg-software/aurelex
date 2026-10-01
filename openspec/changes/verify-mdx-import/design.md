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

- Changing any staging or engine code. If that turns out to be necessary, this
  design is superseded and the change grows a spec delta.
- Committing the large dictionaries. Only `demo.zip` (73 KB, confirmed
  redistributable) is proposed; the 15 MB and 16 MB dictionaries are test
  material, not repository content.
- Building a general MDict fixture generator. Nothing needs it yet; the StarDict
  generator exists because the smoke tool had no StarDict input at all.

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

- **[Verification finds nothing]** The likely outcome is that MDict works and this
  change is docs plus a fixture. → Accepted and called out in the proposal: it
  converts an unverified claim into a tested one. Not a wasted change.
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
