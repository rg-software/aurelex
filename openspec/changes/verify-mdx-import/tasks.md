## 1. Make articles inspectable

- [x] 1.1 Raise the article dump cap in `carve/smoke/main.cpp` (~line 164), which
  prints only the first 800 characters — enough to see the HTML boilerplate, not
  an article's `<img src>`. Done (`2604e22`): the whole body is dumped, every
  distinct `bres://`/`gdau://` reference is listed, all of them are fetched
  rather than just the first, and each payload's magic bytes are sniffed.
- [x] 1.2 Confirm with a real dictionary that an `<img src="bres://…">` reference
  is visible in the dump afterwards, and record which headword shows one —
  Black's `hand` → `img/fig_ufig-h_1.jpg`. Its 800-char cap was also the reason
  the fetch only ever saw the first reference, which for MDX is always the
  stylesheet.
- [x] 1.3 Fix URL parsing for paths containing spaces and commas
  (`bres://<id>/William J. Stewart, … /Image_106.png`) — the whitespace split
  truncated them into a bogus URL that read like a broken dictionary (`ea8ce1e`)
- [x] 1.4 Give the check teeth: hiding a dictionary's `.mdd` makes its resources
  report `FAILED TO RESOLVE`, and a payload's magic bytes are checked so a
  wrong-content/right-length answer cannot pass. All 16 existing CI smoke
  assertions still pass.

## 2. Host confirmation (re-runnable, no device)

- [x] 2.1 Re-run all three MDict shapes through the smoke tool:
  - `demo.zip` — `.mdx` + `.mdd` → loads; **no article references any
    resource**, so this fixture is too small to exercise the resource path
  - Black's Medical Dictionary — `.mdx` + 14 MB `.mdd` → loads, `acne` 5576 B,
    `hand` 4018 B, `blackmed2018.css` 949 B served from the `.mdd`
  - `collinslaw.zip` — `.mdx` + loose `.css`/`.jpg`, **no `.mdd`** → loads,
    `law` 3360 B, CSS 1684 B via the loose-file path
- [x] 2.2 Confirm the loose-file path is exercised: collinslaw has no `.mdd`, so
  its resources resolve only via `mdx.cc:1336` — confirmed, the CSS serves
- [x] 2.3 Confirm an **image** specifically resolves — Black's `hand` →
  `gd_get_resource("…/img/fig_ufig-h_1.jpg")` = **233245 bytes, magic=jpeg**,
  pulled from a nested path inside the `.mdd`. Magic-byte check confirms real
  JPEG bytes rather than a truncated or HTML response.
- [ ] 2.4 Multi-volume `.mdd` (`demo.1.mdd` …) is still unverified — the suffix
  rule should accept it, but no fixture has exercised it

## 3. Regression fixture for MDict (superseded: synthetic, not a committed zip)

- [x] 3.1 ~~Add `demo.zip` under `examples/dictionaries/`~~ → **superseded**.
  MDict now has a generated fixture instead of a committed binary:
  `scripts/make-smoke-mdx.py` (in `fix-iconv-nonprogress-loop`) writes a
  synthetic `.mdx` at build time. That is better on every axis — deterministic,
  no binary in the repo, no provenance/licence question, and it exercises the
  engine's own index build rather than shipping a pre-built artifact. `demo.zip`
  is therefore **not** committed and has been removed from the repo root along
  with the other external test material.
- [x] 3.2 ~~Record its provenance and licence~~ → not applicable; nothing is
  committed to have provenance
- [x] 3.3 Decide whether CI imports it: **yes, a generated MDX fixture**, wired
  into `engine-smoke.yml` with assertions on load, lookup, and article-body
  rendering, plus a per-headword loop so a partial index walk is caught. This
  closes the blind spot named here: MDict previously had *no* fixture at all,
  which is why both this bug and the StarDict one shipped green. The coverage is
  stated plainly — the smoke tool drives the engine directly and does **not** run
  the Java staging layer, so staging is covered separately by
  `staging_rules_test` and the device recipes in `docs/TESTING.md`
- [x] 3.4 Do **not** commit the 15 MB / 16 MB dictionaries; they are external
  test material referenced from `docs/TESTING.md`. The 75 KB `demo.zip` is not
  committed either, now that a generated fixture covers the format

## 4. Stage an MDX set's loose assets

- [x] 4.1 Add `StagingRules::isMdxResourceFileName` — a bounded extension list
  for assets an article embeds, mirrored in Java as `isMdxResourceFileName`
- [x] 4.2 Generalise `folderHasStarDictIfo` into `folderPrimaryKinds` (bitmask),
  so recognising an `.mdx` sibling costs no extra SAF query per folder
- [x] 4.3 Wire it into `stageTreeInto`: a loose asset counts as a resource when a
  `.mdx` sits beside it, which also exempts it from `hasStagedCopy` dedup the
  same way StarDict's `res/` files are (two MDX sets may both ship `style.css`)
- [x] 4.4 Host tests in `staging_rules_test` — verified to **fail before** the
  change (the rule does not exist), 14 new assertions incl. the scoping guard
  and the bound; all 7 host test binaries pass
- [x] 4.5 Measure the flip with the importer's own rules: collinslaw
  **1 staged / 2 dropped → 3 / 0**; Black's 2/1 → 3/0; demo 2/0 unchanged
- [x] 4.6 Android build compiles (`compileDebugJavaWithJavac`, BUILD SUCCESSFUL)
- [x] 4.7 `dictionary-management` delta added; `skip_specs` removed; 19 → 22
  scenarios with none dropped

## 5. Device verification

- [x] 5.1 Import `collinslaw` on device; confirm it is listed and a headword
  resolves. **Verified**: the import completes (see 5.3), `Collins Dictionary of
  Law 2ed` is listed, and the index is built at 88402 bytes with an FTS sibling.
  `demo` remains to be imported — it references no resources, so it adds no
  coverage this fixture does not already give.
- [x] 5.2 Confirm an MDict article **image renders** in the WebView. **Verified on
  device** against Black's Medical Dictionary: the `hand` article's anatomical
  image renders. The `.mdd`-hosted image is proven two ways — `gd_get_resource`
  returns 233245 bytes with `magic=jpeg` (and reports `FAILED TO RESOLVE` with the
  `.mdd` hidden), and the rendered article shows it. Recipe 18's known gap is
  closed.
- [x] 5.3 Import `collinslaw` — **this was blocked by an unrelated engine defect,
  now fixed and verified.** Before: the index build hung and the app was killed
  with no crash record and a 0-byte index. The cause was `Iconv::convert()`
  retrying without consuming input (measured: 517,000 identical iterations,
  `errno=E2BIG inBytesLeft=1`) — **engine**, not staging, reachable by any MDict
  file. Fixed in `fix-iconv-nonprogress-loop` (patch 0005) and confirmed on
  device: `Writing index…` 147 ms after the file opened, scan complete in
  172 ms.
- [x] 5.4 Import Black's on device and confirm a real headword resolves.
  **Verified on device**: `hand` resolves and renders, including its image.
- [x] 5.5 Confirm the staged layout keeps the `.mdd` beside the `.mdx`, and that
  `collinslaw.css` + `collinslaw2ed.jpg` land beside its `.mdx`. **Verified on
  device**: `files/staged/f804830f/` holds `collinslaw2ed.mdx` (498842),
  `collinslaw.css` (1061) and `collinslaw2ed.jpg` (18896) — the loose assets are
  staged exactly as intended. The index for it is 88402 bytes with an FTS
  sibling directory, where before the fix it was 0 bytes.
  **This also closes the earlier same-basename worry for good**: the `.jpg`
  shares its basename with the `.mdx` and the engine loads the dictionary
  normally with it present.

## 6. Close the StarDict leftover in the same sitting

- [x] 6.1 StarDict recipe 6.3 from the archived `stardict-resource-staging`:
  import factbook on device and confirm a flag/map image renders in the WebView.
  **Verified on device** — flags and maps render. Note the entry to open is
  `Afghanistan Geography`, not `Afghanistan`: The World Factbook splits each
  country into ten entries, and the images live in the Geography one. The engine
  serves them as real GIFs (`af-map.gif` 19501 bytes, `af_large_locator.gif`
  10310 bytes, both `magic=gif`).
- [x] 6.2 `fix-stardict-staging` recipe 5.4: remove a StarDict dictionary and
  confirm its files and index go. **Tested on device; the index half passes and
  the files half does not.** The index is correctly removed (3 → 2, including the
  `_FTS_x` companion), but the staged directory keeps `.idx`/`.dict.dz`/`.syn`
  and `res/` because the sharing guard misjudges it. Consequences: about 18 MB
  retained, and the dictionary **cannot be re-imported** afterwards. Tracked as
  its own change, `reclaim-staged-dirs-on-removal`; the removal itself works, the
  cleanup does not.

## 7. Documentation

- [x] 7.1 `docs/TESTING.md`: replace recipe #18's `🔶 (not exercised on-device —
  no MDX fixture yet)` with real recipes and recorded results. The rows are
  `18.1`–`18.5`, a dot-numbered range because `18a`–`18q` already belongs to the
  article-zoom and optional-parts sections and carries cross-references (`#18a`,
  `#18a–#18g`).
- [x] 7.2 Remove the `.mdd` entry from the "Known gaps" list if 5.2 passes.
  **5.2 passed**, so the entry is removed. Multi-volume `.mdd` is called out
  there instead, since that remains untested on either side.
- [x] 7.3 Record the `isolate_css` transformation so the next person does not
  re-investigate a CSS whose served size exceeds its size on disk (collinslaw:
  1061 bytes on disk, 1684 served — correct, not a bug). Recorded in
  `docs/TESTING.md` under the MDict section, alongside the other two entries that
  look like bugs and are not.
- [x] 7.4 Confirm the README's mdict "Works" row is now backed by evidence; the
  intent is to keep the claim, not narrow it. **Kept and strengthened**: it now
  reads "Works (including images from `.mdd` and loose assets beside the
  `.mdx`)". Both were verified on device — Black's renders an `.mdd`-hosted image,
  and collinslaw renders styled from a loose stylesheet.
- [ ] 7.5 Archive

## Notes

### This change's claim is verified on host

The staging rule (§4) is confirmed working, and the engine resolves everything
the staged files reference. Measured on host against the **exact bytes pulled off
the device**:

- 25 of 25 dictionaries load from the nine staged directories
- `collinslaw` alone: loads, `law` → 3360 bytes, article links
  `bres://…/collinslaw.css`, CSS served (1684 bytes)
- all nine together: `law` → 128912 bytes, all 8 article resource references
  resolve (1 CSS + 7 `.wav`)
- staging flip: collinslaw 1 staged / 2 dropped → 3 / 0

### The device pass is blocked, and not by this change

Importing `collinslaw` on device hangs the index build (no crash, no progress,
process eventually killed). That is `Iconv::convert()` in the engine retrying
without consuming input — 517,000 identical iterations, `errno=E2BIG`,
`inBytesLeft` never dropping below 1. It is reachable by any MDict file and has
nothing to do with staging or the loose-resource rule. Tracked separately as
`fix-iconv-nonprogress-loop`.

### Hypotheses that were measured and ruled out

Recorded so they are not re-investigated:

- A bogus record-block count spinning the build — false, `numRecordBlocks=29`
- A headword block without a NUL terminator running `strlen` off the end —
  false, the block walks cleanly and terminates
- `MdictParser::open()` as the hang site — false, it completes in ~1 ms
- A `libgoldendict.so` / `DictMdict` crash — false, those symbols belong to a
  different project and are in neither this repo nor the shipped APK

The CI smoke tool has **no** `.mdx` fixture; its only "mdx" occurrences are a
search term found inside a StarDict article body. Both bugs this change and
`fix-stardict-staging` address were invisible to it for the same reason: it feeds
the engine a complete directory and never runs the Java staging layer.

`collinslaw` additionally references `Image_106.png` under a folder the zip does
not ship, so that one image legitimately fails to resolve — a property of the
fixture, not of the app.
