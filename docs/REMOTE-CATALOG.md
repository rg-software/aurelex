# Remote dictionary catalog

Aurelex can install a dictionary straight from a curated catalog, with no
sideloading and no computer round-trip. This document is the maintainer how-to:
the manifest format, how to host it, and how to add an entry. The shipped app
knows one URL, compiled in; there is no user-editable catalog address.

The catalog is a **static, hand-authored JSON document**. There is no discovery,
no scraping, no accounts, and no entry versioning. Everything a user installs
from it is downloaded once and then searched entirely on-device, exactly like a
dictionary they imported themselves.

## How it works in the app

- "Add from remote" (the cloud button in the Dictionaries pane) opens the
  catalog sheet and fetches the manifest over HTTPS. Nothing is fetched at app
  start; if the screen is never opened, no catalog request is made.
- The manifest is cached in `settings.json` (`remoteCatalogManifest`,
  `remoteCatalogFetchedAt`). A cached copy still renders read-only while
  offline, but starting a download requires a successful re-probe; per-entry
  download attempts from a stale list fail with a stated reason.
- Choosing entries downloads them in a foreground service
  (`DictionaryDownloadService`) with byte-level progress and a Cancel button.
  Files stream into `files/staging-tmp/<contentHash>/`, are verified, then
  atomically renamed to `files/staged/<contentHash>/`.
- The existing scan → auto-index → refresh chain then picks them up unchanged:
  `runScan()` walks `files/staged` recursively and does not care how the bytes
  arrived. An installed entry is removed by the normal Remove button.
- Optional bundles (audio and other resources) are opt-in. After installing an
  entry, a "Add audio" action fetches the optional files into the **same**
  `files/staged/<contentHash>/` directory and reloads just that dictionary so
  the new resources take effect without an app restart.

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
| `name` | yes | Display name in the list. |
| `langFrom` / `langTo` | yes | Language codes. |
| `attribution` / `license` | no | Shown next to the entry; required by most upstream data licences. |

File fields:

| Field | Required | Notes |
|-------|----------|-------|
| `role` | yes | `"dictionary"` (engine-loadable) or `"resources"` (opt-in companion bundle). An unrecognised role rejects the document: the app has to know whether a file participates in installed-detection. |
| `required` | yes | `false` is what makes a bundle opt-in (audio). |
| `name` | yes | Basename only — no path separators, no `..`. This is the name the engine sees under `files/staged/<contentHash>/` and the value installed-detection matches on. |
| `url` | yes | Must be `https://`. Cleartext is refused at parse time. |
| `sizeBytes` | yes | Integer > 0. Drives the free-space preflight and the progress total. Hand-maintained and NOT verified; the transfer is bounded by the server's `Content-Length`. |
| `sha256` | no | 64 lowercase hex chars. Present → the downloaded file is verified; absent → accepted without verification (best-effort integrity). |

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
`.dsl.dz`, `.ifo`.

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

The URL compiled into the app is:

```
https://rg-software.github.io/aurelex/catalog/catalog.json
```

Hosted on **GitHub Pages** rather than `raw.githubusercontent.com` because the
Pages URL is decoupled from a branch or tag name (renaming a branch cannot break
every installed app) and it is served from a CDN with proper HTTP semantics
(strong `ETag` + `Last-Modified`). To publish an update, commit the new
`catalog.json` to the Pages source branch; no app release is needed. The app
serves a cached copy and re-probes at most once every 6 hours (or on an explicit
refresh), so an update reaches users without hammering the host.

The manifest must be no larger than 4 MiB; the app aborts the fetch past that.

## Adding an entry

1. Decide the `id` (permanent) and where the files are hosted. Anything over
   HTTPS works; a GitHub release asset or a Pages-served file is fine.
2. Compute each file's size in bytes and, ideally, its SHA-256
   (`sha256sum <file>`). Both go in the manifest.
3. Append the entry to `catalog.json`. Keep ids append-only.
4. Validate locally before publishing — the app's parser is the contract. The
   `catalog_test` CMake target under `app/tests` builds against a plain desktop
   Qt Core and runs the checked-in fixtures:

   ```powershell
   cmake -S app/tests -B build-catalog-test -DCMAKE_PREFIX_PATH=C:/Qt/6.6.3/msvc2019_64
   cmake --build build-catalog-test --config Release --target catalog_test
   build-catalog-test/Release/catalog_test.exe
   ```

   Add the new shape to `app/tests/fixtures/catalog.json` if it exercises a new
   file arrangement (an mdict pair, a DSL `.files.zip`, …).
5. Commit the updated `catalog.json` to the Pages source branch. In-app, the
   entry appears on the next re-probe or explicit refresh.

## Privacy

The catalog request carries no identifier, and no installed dictionary or lookup
is ever uploaded. The only outbound requests the catalog feature makes are the
manifest fetch and the file downloads, all over HTTPS and all triggered by an
explicit user action. See the README "Privacy" section.
