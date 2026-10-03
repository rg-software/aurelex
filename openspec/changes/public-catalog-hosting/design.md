## Context

See `proposal.md` for motivation. The constraints that shape this design:

- The compiled-in catalog URL is `EngineController::kDefaultRemoteCatalogUrl`
  (`app/EngineController.hpp:843`), currently a Seafile share
  (`seafile.rt247a.ddns.me`). Seafile serves a one-off share link, not a stable
  CDN location, and the hostname is maintainer infrastructure.
- The app already has, and the specification already relies on, the full
  download path: `RemoteCatalog` parses `sizeBytes` (mandatory) and `sha256`
  (optional), the Android `DictionaryDownloadService` resumes with
  `Range`/`If-Range`, and the app caches the last-good manifest. This change
  swaps the *source* of the document and the files, not the machinery.
- `remote-dictionary-catalog` explicitly excludes "entry version comparison,
  update checks, or any other catalog-side lifecycle action". This change keeps
  that contract; it only makes future comparison possible.
- The repository is private and currently detects "Other" as its license.

## Goals / Non-Goals

**Goals:**

- A stable, generated, HTTPS publication path for the catalog document and the
  dictionary files it references, suitable for a public release.
- Every published file carries a computed size and SHA-256, so integrity
  verification always applies.
- Recording enough on-device state that a future update capability can compare
  manifest and installed content **without** re-hashing multi-GB files.
- A repository that is safe and conventional to make public.

**Non-Goals:**

- Any update/upgrade/reinstall UI or version comparison (a separate change).
- Choosing a user-editable catalog URL; it stays compiled in.
- Reworking the download service, the resume logic, or the free-space rules.
- Hosting dictionary files anywhere other than GitHub (no CDN migration).

## Decisions

### 1. Split the two artifacts: JSON on Pages, files on release assets

The catalog document is small and must be reachable at a URL that never rots, so
it goes on **GitHub Pages** (`https://rg-software.github.io/aurelex/catalog/catalog.json`),
which is CDN-backed, HTTPS, and decoupled from branch/tag names. The dictionary
files are multi-GB and Pages caps a site at about 1 GB, so they go on **GitHub
release assets**, which are free and unmetered for a public repository.

*Alternatives considered:* `raw.githubusercontent.com` (throttled for abuse and
tied to a branch/ref, so renaming a branch breaks every install — the original
design already rejected it); GitHub Packages / OCI artifacts (require an
authenticated pull, unusable for anonymous in-app downloads); all files on Pages
(exceeds the site size cap).

### 2. One permanent, never-deleted release tag for the files

Release-asset URLs are
`https://github.com/rg-software/aurelex/releases/download/<tag>/<file>`, so the
`<tag>` is part of a URL the catalog hardcodes. Use a single dedicated tag (e.g.
`catalog-data`) that is **never deleted and never reused for app releases**, so
the URLs are stable for as long as the catalog references them. Do **not** use
`releases/latest/download/...`: that path tracks whichever release is newest,
which changes on every app release and would silently repoint the catalog.

### 3. A generator owns the catalog, from an authored source

`catalog.json` stops being a hand-edited file and becomes a **derived build
artifact**. There are exactly two inputs:

- **Authored metadata** in a checked-in `catalog/source.json`: entry `id`,
  `name`/`names`, language pair, attribution/license, each file's `name`,
  `role`, and `required`, plus the hosting constants (`releaseTag`, `baseUrl`).
  This is the reviewable source of truth for catalog metadata.
- **Content bytes**: the built dictionary files (by default under `dist/`),
  matched by their stable basenames. This is the source of truth for content.

Everything else — `sizeBytes`, `sha256`, each file's `url`, the document
`schemaVersion`/`updated` — is **computed** by `scripts/build-catalog.py`, never
typed. The generator also enforces stable identity: ids unique and append-only,
a file name may not move between entries, and an existing entry's file names may
not change when its content changes. Output is deterministic.

The generator has three modes matching how the catalog is actually maintained:

- `import` — bootstrap or re-sync `source.json` from an already-published
  `catalog.json` (drops the derived fields), so authoring starts from the live
  catalog instead of a blank page.
- `build` — `source.json` + files dir → `catalog.json` with computed sizes,
  digests, and URLs.
- `diff` — built `catalog.json` vs a published one → lists new/changed/unchanged
  files, so publication uploads only what changed while always deploying the
  (tiny) catalog document.

This removes the "hand-maintained `sizeBytes` can be wrong" risk the original
catalog design recorded, and it is why `sha256` can be assumed present on
published files. The common maintainer loop is: build the dictionaries into
`dist/`, `build`, `diff` against the live catalog, upload the changed files to
the permanent release, deploy `catalog.json` to Pages.

*Alternative considered:* keep editing `catalog.json` by hand. Rejected: it makes
digests optional and error-prone, and SHA is now load-bearing.

### 4. SHA-256 is the content identity; record the installed digest now

To detect a future update you must compare the manifest's digest with what is
installed. Nothing records the latter today. So when a catalog download batch
completes, persist `entryId -> { requiredFileName: sha256 }` in `settings.json`.

- This is **inert**: no UI reads it, no update action appears, the spec's
  read-only contract is untouched.
- It is recorded from the manifest that was used for the install, so no
  multi-GB file is ever hashed on device.
- The download service already verifies these digests when present; the app is
  simply remembering them.

Recording now is what keeps a later update change clean: without it, every
already-installed user would have no baseline (forcing a one-time device-side
hash of multi-GB files, or a blanket "reinstall" prompt).

*Alternative considered:* a per-entry `version` integer in the manifest. Rejected:
it is content-blind (a silent rebuild that forgets to bump it goes unnoticed) and
redundant with the digest that is already there. File names stay stable, which is
what actually preserves the staging `contentHash` and the engine dictionary id,
so group membership and list position survive an in-place update.

### 5. No schema change

`sha256` is already an optional field and the parser already ignores unknown
fields, so always publishing it needs no `schemaVersion` bump and no parser
change. Older builds keep working ("verify when supplied, accept when absent").

### 6. Public repository readiness

License notice and `THIRD-PARTY-NOTICES.md` are added; `.openchamber/` (local
agent/session state, currently untracked and not ignored) is added to
`.gitignore`; git history is scanned for secrets before the flip; the Seafile
hostname leaves the tree with decision 1; repository description/topics are set
and Pages is enabled. **Visibility is flipped last**, after the scan.

## Risks / Trade-offs

- **GitHub caps a single release asset at 2 GiB.** The largest current audio
  bundle is 1.6 GiB (`au_kaikki_en-en.dsl.files.zip`), so headroom is thin. →
  Verify sizes in the generator and fail the publication if any file exceeds the
  cap; if a bundle grows past it, split it into parts and list them, or host that
  one file elsewhere.
- **Release-asset URLs are tied to the tag.** Deleting the tag would break every
  install. → One permanent tag, documented as never-delete; the generator emits
  URLs for that fixed tag only.
- **The download service resumes with `Range`/`If-Range`, and release-asset URLs
  redirect (302) to a signed host.** Whether the validator and range survive the
  redirect must be confirmed on device. → Test an interrupted download through
  the real URL; the existing fallback (restart on any non-206) means the worst
  case is a re-download, never a corrupt install.
- **Pages caches and propagates asynchronously.** → The app already caches the
  last-good manifest and re-probes at most every 6 hours; a stale catalog renders
  read-only, so publication latency is benign.
- **A public repository exposes history.** → Secret scan before the flip; the
  only known sensitive datum (the Seafile hostname) is removed by this change.
- **`sha256` stays optional in the parser.** A hand-crafted catalog could still
  omit it. → The generator always emits it; the app remains tolerant for
  forward/backward compatibility, and an entry without a digest simply cannot be
  identified for a future update.

## Migration Plan

1. Add the generator, the Pages workflow, and the permanent release tag; populate
   the tag with the current dictionary files. This is additive — nothing the
   shipped app does changes yet.
2. Generate and publish the catalog to Pages.
3. Add installed-digest recording to the app and swap
   `kDefaultRemoteCatalogUrl` to the Pages URL; ship in the next app release.
   Existing installs keep working against Seafile until they update, and the new
   catalog's file URLs point at the release assets regardless.
4. Complete the repository-readiness items, then flip visibility to public.

Rollback: restore the previous URL constant and stop publishing to Pages. No
stored state is reinterpreted; the recorded digests are inert.

## Open Questions

- Whether to surface the per-entry update date as a display-only string later.
  Deferrable; needs no schema change now.
- Whether to split the largest audio bundle preemptively or only when it
  approaches the 2 GiB cap.
