## 1. Code

- [x] 1.1 `app/main.qml`: the "Get started" handler leaves the user on the Dictionaries tab (`root.state = 1`) instead of Search (`root.state = 0`), and its comment is updated to say why
- [x] 1.2 Confirm the `_bootRouted` guard keeps the re-emitted `onboardedChanged` from overriding the destination (design D2) — no new guard needed; on-device the handler's destination held
- [x] 1.3 Confirm first-launch routing (onboarded == false → Dicts) and returning-user routing (onboarded == true → Search) are untouched

## 2. Spec and docs

- [x] 2.1 Delta spec updates the "Onboarding is dismissed" scenario to the Dictionaries destination; other scenarios unchanged
- [x] 2.2 `docs/TESTING.md`: rows 47/47a/47b cover the first-launch tab, the dismissal destination, and the unchanged returning-user start

## 3. Verification

- [x] 3.1 Reset onboarding, relaunch: overlay shows over Dicts (uiautomator: "Get started" present, Dicts toolbar present)
- [x] 3.2 Tap "Get started": overlay clears, `content-desc="Dicts" checked="true"` (Search false), Search field absent, Dicts toolbar present, no keyboard
- [x] 3.3 Force-stop and relaunch: app starts on Search (`content-desc="Search" checked="true"`), overlay absent
- [x] 3.4 No new i18n strings; `git diff` shows no `app/i18n/*` change
