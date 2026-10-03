## 1. Repository readiness

- [x] 1.1 Replace the GoldenDict program notice in `LICENSE` with Aurelex's own
      (holder: Maxim Mozgovoy); confirm GitHub detects GPL-3.0
- [x] 1.2 Add `NOTICES.md` (project copyright + third-party attributions) and
      reference it from the README's license section
- [x] 1.3 Add `.openchamber/` (local agent/session state) to `.gitignore`
- [x] 1.4 Run a secret scan over the full git history (gitleaks or trufflehog) and
      record the result before any visibility flip
- [x] 1.5 Set the repository description and topics

## 2. Catalog generator

- [x] 2.1 Add `catalog/source.json` (authored metadata + the `releaseTag`/`baseUrl`
      hosting constants); bootstrap it from the live catalog with the generator's
      `import` mode
- [x] 2.2 Add `scripts/build-catalog.py` with three modes: `import`
      (published catalog → `source.json`), `build` (`source.json` + files dir →
      `catalog.json`), and `diff` (built vs published → new/changed/unchanged)
- [x] 2.3 Make `build` compute `sizeBytes` and `sha256` and derive each file's
      URL for the permanent release tag; reject a non-HTTPS base, a missing file,
      or any file exceeding GitHub's 2 GiB release-asset cap
- [x] 2.4 Enforce stable identity: ids unique and append-only, and no file name
      renamed or moved between entries
- [x] 2.5 Add generator tests: digest/size correctness, import round-trip,
      identity violations, over-cap rejection, and diff classification
- [x] 2.6 Build the catalog from `dist/` and `diff` it against the live catalog;
      validate the output against the manifest parser (`catalog_test`)

## 3. Publication pipeline

- [x] 3.1 Create the permanent `catalog-data` release tag and document that it is
      never deleted or reused
- [x] 3.2 Add a script/workflow to upload the dictionary files to that release
      (idempotent, manual dispatch)
- [x] 3.3 Add `.github/workflows/pages.yml` to generate the catalog and deploy it
      to GitHub Pages
- [x] 3.4 Verify the deployed URL serves over HTTPS and the JSON parses with the
      expected sizes and digests

## 4. App changes

- [x] 4.1 Point `EngineController::kDefaultRemoteCatalogUrl` at the Pages URL,
      replacing the Seafile share
- [x] 4.2 Persist `entryId -> { fileName: sha256 }` for the required dictionary
      files when a catalog download batch completes, in `settings.json`;
      tolerate missing digests and entries not installed from the catalog
- [x] 4.3 Keep the record inert: no new UI, no update/version-comparison action,
      and no change to installed-detection
- [x] 4.4 Extend `settings.json` save/load with the recorded digests without
      breaking older settings files

## 5. Documentation

- [x] 5.1 Update `docs/REMOTE-CATALOG.md`: Pages hosting, release-asset file URLs,
      the permanent tag, generator usage, mandatory digests, and remove the note
      that the compiled-in URL does not point at Pages yet
- [x] 5.2 Update `docs/DEVELOPMENT.md` catalog/test sections for the generator
- [x] 5.3 Review `README.md` catalog/privacy wording against the new hosting

## 6. Verification

- [ ] 6.1 On device: fetch the Pages catalog and install an entry from a release
      asset; confirm integrity verification and digest recording
- [ ] 6.2 On device: interrupt a download and confirm resume through the
      release-asset redirect, or a clean restart if the validator does not survive
- [x] 6.3 Run `catalog_test` and the generator tests
- [ ] 6.4 Confirm an installed entry shows no update/upgrade/reinstall affordance
      (read-only contract preserved)

## 7. Make public

- [x] 7.1 Enable GitHub Pages (source: GitHub Actions) and confirm the catalog URL
      is live
- [x] 7.2 Flip repository visibility to public (last, after 1.4)
- [x] 7.3 Confirm the license shows GPL-3.0, the notices are present, and the
      catalog and a dictionary file are anonymously reachable
