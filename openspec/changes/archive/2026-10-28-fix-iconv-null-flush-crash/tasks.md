# Tasks

- [x] 1. Add `patches/0007-iconv-no-null-flush.patch` removing the NULL-flush block from `Iconv::convert`
- [x] 2. Update `docs/ENGINE.md` patch table (six → seven patches)
- [x] 3. Re-apply patches (`scripts/apply-patches.ps1`) and confirm the engine tree shows the change
- [x] 4. Host suites green: `app/tests` targets, `python -m unittest discover -s scripts/tests`, `aurelex_smoke` on both fixture layouts
- [x] 5. Device (Android 10): debug build + staged Kaikki RU → scan completes, dict listed, headword resolves, no new `data_app_native_crash`
- [x] 6. `docs/TESTING.md`: record the Android 10 scan row
- [x] 7. `openspec validate fix-iconv-null-flush-crash`
