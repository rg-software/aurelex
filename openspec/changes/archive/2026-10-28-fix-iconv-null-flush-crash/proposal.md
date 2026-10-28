# Proposal

## Why

Play v0.5.1 crash-loops on Android 10 (Huawei VOG-L29): every launch dies ~1s in with `SIGSEGV fault addr 0x0` in bionic `iconv`, called from `Iconv::convert` during the dictionary scan. Any staged dictionary triggers it, so the app is unusable on that OS. The defect is in the engine's charset-conversion flush, invisible on the Android 15 test devices.

## What Changes

- Add patch `0007-iconv-no-null-flush` removing the `iconv(state, NULL, NULL, …)` shift-flush from `Iconv::convert` (the conversion target is always UTF-8, which is stateless, so the flush is a no-op).
- Update `docs/ENGINE.md` patch table (six → seven patches).
- Verify on the reporting device (debug build): Kaikki RU scan completes, dictionary loads and resolves; plus the standard host test + smoke suites.

## Capabilities

### New Capabilities

None — no new user-visible behavior; crashing scans now complete.

### Modified Capabilities

- `dictionary-management`: pin the platform-compat requirement — charset conversion during scan/index MUST NOT terminate the process on any supported Android API level.

## Impact

- `patches/` (+1 file), `docs/ENGINE.md` (patch count/table), `docs/TESTING.md` (device row).
- No boundary API change, no UI change, no format-scope change.
