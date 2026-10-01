## 1. Make articles inspectable

- [ ] 1.1 Raise the article dump cap in `carve/smoke/main.cpp` (~line 164), which
  prints only the first 800 characters — enough to see the HTML boilerplate, not
  an article's `<img src>`. It has now blocked two format investigations.
- [ ] 1.2 Confirm with a real dictionary that an `<img src="bres://…">` reference
  is visible in the dump afterwards, and record which headword shows one

## 2. Host confirmation (re-runnable, no device)

- [ ] 2.1 Re-run all three MDict shapes through the smoke tool and record the
  results in `docs/TESTING.md`:
  - `demo.zip` — `.mdx` + `.mdd`
  - Black's Medical Dictionary — `.mdx` + 14 MB `.mdd`, real headwords
  - `collinslaw.zip` — `.mdx` + **loose** `.css`/`.jpg`, no `.mdd`
- [ ] 2.2 Confirm the loose-file path is exercised: collinslaw has no `.mdd`, so
  its resources resolve only via `mdx.cc:1336` (a file beside the `.mdx`)
- [ ] 2.3 Confirm an **image** specifically resolves (not only a `.css` or
  `.ttf`), and record its byte count against the file's real size
- [ ] 2.4 If a multi-volume `.mdd` can be assembled (or one is found), test it.
  The suffix rule should accept `demo.1.mdd`; this is unverified

## 3. Redistributable fixture

- [ ] 3.1 Add `demo.zip` (73 KB, confirmed redistributable) under
  `examples/dictionaries/` in whatever form fits — unzipped, or archived
- [ ] 3.2 Record its provenance and licence beside it, following
  `app/openssl/README.md` / `scripts/assets/kaikki-tag-icons/README.md`
- [ ] 3.3 Decide whether the CI smoke tool should import it. If yes, this closes
  the gap that let the StarDict import bug ship green — state in the coverage
  which half is exercised (engine only, or staging too)
- [ ] 3.4 Do **not** commit the 15 MB / 16 MB dictionaries; reference them in
  `docs/TESTING.md` as external test material instead

## 4. Device verification

- [ ] 4.1 Import `demo` and `collinslaw` on device; confirm each is listed and a
  headword resolves
- [ ] 4.2 Confirm an MDict article **image renders** in the WebView — this is
  recipe #18's known gap and the main open question
- [ ] 4.3 Import Black's on device and confirm a real headword resolves (host
  showed `acne` 5576 bytes, `abscess` 6519)
- [ ] 4.4 Confirm the staged layout keeps the `.mdd` beside the `.mdx` (the
  engine resolves the archive relative to the `.mdx`)

## 5. Close the StarDict leftover in the same sitting

- [ ] 5.1 StarDict recipe 6.3 from the archived `stardict-resource-staging`:
  import factbook on device and confirm a flag/map image renders in the WebView.
  It is the one unchecked item from that change and belongs with the MDict image
  check — same fixture, same session.
- [ ] 5.2 `fix-stardict-staging` recipe 5.4: remove a StarDict dictionary and
  confirm its files and index go. `factbook` serves.

## 6. Documentation

- [ ] 6.1 `docs/TESTING.md`: replace recipe #18's `🔶 (not exercised on-device —
  no MDX fixture yet)` with real recipes and recorded results
- [ ] 6.2 Remove the `.mdd` entry from the "Known gaps" list if 4.2 passes
- [ ] 6.3 Record the `isolate_css` transformation so the next person does not
  re-investigate a CSS whose served size exceeds its size on disk (collinslaw:
  1061 bytes on disk, 1684 served — correct, not a bug)
- [ ] 6.4 Confirm the README's mdict "Works" row is now backed by evidence; the
  intent is to keep the claim, not narrow it
- [ ] 6.5 Archive, or add a `dictionary-management` delta first if §4 found a
  defect

## Notes

Host evidence already in hand before this change started, for the record:

| Fixture | Result |
| --- | --- |
| `demo.zip` | loads; `gd_get_resource` served a 20604-byte `.ttf` out of the `.mdd` |
| Black's | loads; `acne`/`abscess`/`blood` resolve; `blackmed2018.css` served from the `.mdd` |
| `collinslaw.zip` | loads; `law` resolves (3360 bytes); CSS served via the loose-file path |

The CI smoke tool has **no** `.mdx` fixture; its only "mdx" occurrences are a
search term found inside a StarDict article body (`carve/smoke/main.cpp:315`).
