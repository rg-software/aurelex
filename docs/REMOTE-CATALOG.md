# Remote dictionary catalog

Aurelex can install a dictionary straight from a curated catalog, with no
sideloading and no computer round-trip. This document is the maintainer how-to:
the manifest format, how to host it, and how to add an entry. The shipped app
knows one URL, compiled in; there is no user-editable catalog address.

The published catalog is a **static JSON document**, generated from an authored
source (`catalog/source.json`) by `scripts/build-catalog.py`. There is no
discovery, no scraping, no accounts, and no entry versioning. Everything a user
installs from it is downloaded once and then searched entirely on-device,
exactly like a dictionary they imported themselves.

The app knows one catalog address. There is **no UI** for changing it; the
address is a compiled-in default that `settings.json` may override via a
`remoteCatalogUrl` key (a non-`https://` value is ignored and the compiled
default is used instead). The key exists so a maintainer can repoint a build
without a release; making it user-editable is a later, additive settings change.

## How it works in the app

- "Add from remote" (the cloud button in the Dictionaries pane) opens the
  catalog sheet and fetches the manifest over HTTPS. Nothing is fetched at app
  start; if the screen is never opened, no catalog request is made.
- The manifest is cached in `settings.json` (`remoteCatalogManifest`,
  `remoteCatalogFetchedAt`, and a `remoteCatalogReachable` flag). A cached copy
  still renders read-only while offline, but starting a download requires a
  successful re-probe; per-entry download attempts from a stale list fail with a
  stated reason. A failed re-probe deliberately leaves the last good manifest in
  place rather than blanking the list mid-refresh.
- Choosing entries downloads them in a foreground service
  (`DictionaryDownloadService`) with byte-level progress and a Cancel button.
  Files stream into `files/staging-tmp/<contentHash>/`, are verified, then
  atomically renamed to `files/staged/<contentHash>/`.
- The existing scan → auto-index → refresh chain then picks them up unchanged:
  `runScan()` walks `files/staged` recursively and does not care how the bytes
  arrived. An installed entry is removed by the normal Remove button.
- Optional bundles (audio and other resources) are **opt-in per entry**, not a
  separate post-install step: each catalog row carries a music-note toggle
  (`Audio for <name>` / `No audio for <name>`) that arms the optional files for
  the next download, and stays enabled for an installed entry that is still
  missing its bundle. Fetching them writes into the **same**
  `files/staged/<contentHash>/` directory and reloads just that dictionary, so
  the new resources take effect without an app restart.
- Before a batch starts, a free-space preflight runs. It has **two** tiers, and
  the second is advisory: under 512 MiB of headroom the download is refused
  outright ("Not enough free space"); under 2 GiB it proceeds only after an
  explicit confirmation ("Not much free space"), because the FTS index built
  afterwards also needs room. The transfer itself is still bounded by the
  server's `Content-Length`, so a manifest that understates `sizeBytes` fails
  with a real reason rather than silently truncating.

## Layout and shared identity

The staging directory is named by a hash of the entry's **content identity**, not
its URL:

```
contentHash = md5(id + "\n" + join("\n", sorted(required file names)))
```

`contentHash` is implemented once in C++ (`RemoteCatalog::contentHash`) and
mirrored in Java (`DictionaryDownloadService.contentHashFor`). The two MUST agree:
the directory name is what makes an installed entry's files findable again for a
follow-up (adding audio). Because the hash is derived from content and
not the URL, re-installing the same entry is a clean no-op rather than a
duplicate row.

Optional files are deliberately excluded from the seed, so adding audio to an
already-installed entry reuses the same directory.

## Manifest format (`schemaVersion` 1)

```json
{
  "schemaVersion": 1,
  "updated": "2026-09-26",
  "entries": [
    {
      "id": "kaikki-en-ru",
      "name": "Wiktionary (English - Russian)",
      "names": { "ru": "Викисловарь (английский — русский)" },
      "langFrom": "en",
      "langTo": "ru",
      "attribution": "Wiktionary contributors, CC BY-SA 4.0",
      "license": "CC-BY-SA-4.0",
      "files": [
        { "role": "dictionary", "required": true,
          "name": "kaikki-en-ru.dsl.dz",
          "url": "https://…", "sizeBytes": 123456789, "sha256": "…" },
        { "role": "resources", "required": false,
          "name": "kaikki-en-ru.dsl.dz.files.zip",
          "url": "https://…", "sizeBytes": 9876543210, "sha256": "…" }
      ]
    }
  ]
}
```

Top level:

| Field | Required | Notes |
|-------|----------|-------|
| `schemaVersion` | yes | Must be `1`. Any other value rejects the document whole. |
| `updated` | no | ISO date, informational only. |
| `entries` | yes | Array, may be empty. |

Entry fields:

| Field | Required | Notes |
|-------|----------|-------|
| `id` | yes | Stable, unique, matching `[A-Za-z0-9._-]+`. Append-only by convention: renaming breaks installed-detection for anyone who already installed the old id. |
| `name` | yes | Display name in the list; the fallback for `names`. |
| `names` | no | Localized display names: an object from language code (`en`, `ru`, …; keys folded to lowercase) to a non-empty string. The app shows the name for its active UI language and falls back to `name`. A non-object, or a non-string value, rejects the document. |
| `langFrom` / `langTo` | yes | Language codes. |
| `attribution` / `license` | no | Shown next to the entry; required by most source-data licences. |

File fields:

| Field | Required | Notes |
|-------|----------|-------|
| `role` | yes | `"dictionary"` (engine-loadable) or `"resources"` (opt-in companion bundle). An unrecognised role rejects the document: the app has to know whether a file participates in installed-detection. |
| `required` | yes | `false` is what makes a bundle opt-in (audio). |
| `name` | yes | Basename only — no path separators, no `..`. This is the name the engine sees under `files/staged/<contentHash>/` and the value installed-detection matches on. |
| `url` | yes | Must be `https://`. Cleartext is refused at parse time. Emitted by the generator for the permanent release tag. |
| `sizeBytes` | yes | Integer > 0. Drives the free-space preflight and the progress total. Computed by the generator; the transfer is still bounded by the server's `Content-Length`. |
| `sha256` | no | 64 lowercase hex chars. Present → the downloaded file is verified; absent → accepted without verification. The generator always emits it, so published catalogs are always verified. |

Entry-level rules:

- At least one file must have `role: "dictionary"` and `required: true`.
- A required dictionary file in a format this build cannot load (`.epwing`,
  `.bgl`, …) is **not** fatal: the entry parses and is listed as *not
  installable*, with the reason, so the user sees why. This is the shape a
  future entry takes before the format is supported.
- Any other malformed entry rejects the **whole** document. The parser is total:
  it returns an error rather than half-populating a manifest, so a bad catalog
  disables the feature instead of producing a silently-wrong list.

Supported `dictionary`-role extensions in this build: `.mdx`, `.mdd`, `.dsl`,
`.dsl.dz`, `.ifo`, and a StarDict dictionary's companion files `.idx`/`.idx.gz`/
`.idx.dz`, `.dict`/`.dict.dz`, `.syn`/`.syn.gz`/`.syn.dz` plus its resource
archive forms `res.zip`/`<base>.res.zip`.

A StarDict entry lists its whole set, because the `.ifo` header alone carries no
content and the reader fails without its companions:

```json
"files": [
  { "role": "dictionary", "required": true, "name": "word.ifo",  "url": "https://…", "sizeBytes": 1 },
  { "role": "dictionary", "required": true, "name": "word.idx",  "url": "https://…", "sizeBytes": 1 },
  { "role": "dictionary", "required": true, "name": "word.dict", "url": "https://…", "sizeBytes": 1 }
]
```

Marking all three `required` is what makes installed-detection report the entry
installed only once they have all landed.

### StarDict resources

StarDict keeps article images in a sibling `res/` folder, which a manifest cannot
express (file names are bare, no paths). Ship them as a single archive instead
and list it as an optional `resources` file, named so it lands beside the `.ifo`:
either `res.zip`, or `<base>.res.zip` (e.g. `word.res.zip` for `word.ifo`). The
engine opens both forms from the dictionary's folder. Leave it `required: false`
so it stays opt-in and does not change the entry's content hash; a dictionary is
usable without its images, just incomplete.

### mdict pairs

An mdict entry lists both halves as `role: "dictionary"`, `required: true`:

```json
"files": [
  { "role": "dictionary", "required": true, "name": "word.mdx", "url": "https://…", "sizeBytes": 1 },
  { "role": "dictionary", "required": true, "name": "word.mdd", "url": "https://…", "sizeBytes": 1 }
]
```

Installed-detection requires **every** `dictionary`-role file's basename to be
present, so the entry reports installed only once both halves have landed.

### DSL resources

DSL pronunciation audio lives in a sibling `<dict>.files` tree. Package it as a
single archive and list it as an optional `resources` file (e.g.
`kaikki-en-ru.dsl.dz.files.zip`), so it stays opt-in and never affects install
size.

## Hosting

The manifest and the dictionary files are hosted separately, because they have
different constraints:

| Artifact | Host | Why |
|---|---|---|
| `catalog.json` | **GitHub Pages** — `https://rg-software.github.io/aurelex/catalog/catalog.json` | Small, and must live at a URL that never rots: decoupled from a branch or tag, CDN-served, with a good `ETag`/`Last-Modified`. Pages caps a site at ~1 GB, so it cannot hold the files. |
| Dictionary files | **GitHub release assets** under one permanent tag (`catalog-data`) | Multi-GB; free and unmetered for a public repository. |

`catalog.json` is deployed by `.github/workflows/pages.yml`, which validates the
committed document and serves only that file. It is **not** rebuilt in CI: doing
so needs the dictionary files hashed, and those are not in the repository.

The file URLs point at the permanent release tag, so they do not change when the
app releases. **Never delete or reuse that tag** — every installed catalog's file
URLs reference it. `releases/latest/...` is deliberately not used because it
moves on every app release and would silently repoint the catalog.

The address compiled into the app is the constant
`EngineController::kDefaultRemoteCatalogUrl` (`app/EngineController.hpp`),
pointing at the Pages URL above. An install that already persisted a
`remoteCatalogUrl` keeps it — the compiled value is only the first-run default.
The app caches the manifest and re-probes at most once every 6 hours, or on an
explicit refresh, so a published update reaches users without hammering the host.

The manifest must be no larger than 4 MiB; the app aborts the fetch past that.
A fetch also gives up after 15 s, so a slow link fails to a stated error instead
of leaving the catalog spinner up indefinitely.

## Maintaining the catalog

`catalog/source.json` is the **authored source of truth** for entry metadata;
the built dictionary files are the source of truth for content. `catalog.json`
is a **derived artifact** and is never hand-edited. It looks like the manifest
but carries no `url`, `sizeBytes`, or `sha256`, and adds the hosting constants:

```json
{
  "releaseTag": "catalog-data",
  "baseUrl": "https://github.com/rg-software/aurelex/releases/download",
  "entries": [
    { "id": "kaikki-en", "name": "Aurelex Kaikki English",
      "names": { "ru": "…", "ja": "…" },
      "langFrom": "en", "langTo": "en",
      "attribution": "Wiktionary contributors, CC BY-SA 4.0 (via kaikki.org)",
      "license": "CC-BY-SA-4.0",
      "files": [
        { "role": "dictionary", "required": true,
          "name": "au_kaikki_en-en.dsl.dz" },
        { "role": "resources", "required": false,
          "name": "au_kaikki_en-en.dsl.files.zip" }
      ] }
  ]
}
```

`scripts/build-catalog.py` has four modes:

| Mode | Does |
|---|---|
| `import <published>` | Bootstrap or refresh `source.json` from a published catalog (drops the derived fields). Takes a path, `-` (stdin), or an https URL. |
| `build` | `source.json` + files dir → `catalog.json`, computing size, SHA-256, and URL. |
| `diff <published>` | Classify built vs published: new / changed / unchanged / removed, plus identity violations (a published file renamed or moved). Exits `2` on a violation. |
| `validate [catalog]` | Structural check of a catalog document, needing no files; used by CI. |

### Publishing an update

1. Build the dictionaries into `dist/` (or wherever; override with `--files-dir`).
2. Run the whole loop:

   ```powershell
   pwsh -File scripts/publish-catalog.ps1
   ```

   It `build`s `catalog.json`, `validate`s it, `diff`s it against the live
   catalog, uploads only the new/changed files to the permanent release with
   `gh release upload --clobber`, and stages `catalog/catalog.json`. It refuses
   to publish if `diff` reports an identity violation.
3. Commit and push `catalog/catalog.json`; the Pages workflow deploys it. The app
   re-probes within 6 hours (or on an explicit refresh) and shows the change.

Adding an entry: append it to `catalog/source.json` (a new `id`, at least one
required `dictionary` file), place the built file in `dist/`, then publish. Entry
ids, entry names, and file names are **stable and append-only** — renaming a file
breaks installed-detection, and `diff` refuses a publish that renames or moves a
published file.

### Verifying the parser

The app's parser is the contract. `catalog_test` builds against a desktop Qt Core
and runs the checked-in fixtures:

```powershell
cmake -S app/tests -B build-catalog-test -DCMAKE_PREFIX_PATH=C:/Qt/6.6.3/msvc2019_64
cmake --build build-catalog-test --config Release --target catalog_test
build-catalog-test/Release/catalog_test.exe
```

Add a shape to `app/tests/fixtures/catalog.json` if it exercises a new file
arrangement (an mdict pair, a DSL `.files.zip`, …).

### Installed content identity

When a catalog download succeeds the app records, in `settings.json` under
`catalogInstalledDigests`, each installed entry's required-file SHA-256
(`entryId -> { fileName: sha256 }`, matched by entry name, which the generator
keeps unique). This is **inert** today — no UI reads it and no update check runs
— but it is the baseline a future "update available" feature compares the
manifest against, without re-hashing multi-GB files.

## Privacy

The catalog request carries no identifier, and no installed dictionary or lookup
is ever uploaded. The only outbound requests the catalog feature makes are the
manifest fetch and the file downloads, all over HTTPS and all triggered by an
explicit user action. See the README "Privacy" section.
