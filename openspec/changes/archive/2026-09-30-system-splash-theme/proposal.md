## Why

Every cold start opens on a bright white screen with the app icon blown up in the middle. That
screen is the Android starting window (the splash screen on API 31+), and Aurelex gets it by
default: `AndroidManifest.xml` applies no theme at all, so the platform falls back to a white
`windowBackground` regardless of which theme the app is actually in. A user in dark mode therefore
starts every launch with a white flash, which reads as a bug even though nothing is broken.

The window also cannot be told to match the app, because the app's background is a Qt Quick
Controls Material palette value (`Material.background`) that the Android resource layer has no way
to see. The two colors have to be tied together by hand, in Android resources, and the values
picked must be the Material 3 ones Qt actually paints.

## What Changes

- Apply an explicit Android theme to the launcher activity, so the starting window has a
  background of our choosing instead of the platform default.
- That background is the app's own Material background, pinned per configuration: `#FFFBFE` in
  light, `#1C1B1F` in dark. Both are Qt's own constants
  (`backgroundColorLight` / `backgroundColorDark` in `qquickmaterialstyle.cpp`), so the starting
  window and the app paint the same color by construction rather than by coincidence.
- Cover Android 12+ (`android:windowSplashScreenBackground`, the modern splash) and older
  releases (`android:windowBackground`, the legacy starting window) from the same theme, so the
  two paths cannot drift.
- Do **not** override `android:windowSplashScreenAnimatedIcon`. The default — the launcher
  adaptive icon, masked and centered by the system — is already correct and stays the single
  source of the app's identity; a second drawable would be a second thing to keep in sync, and the
  system's own mask/scale would crop it differently from the launcher.
- Resolve the theme before the first QML frame. The app's palette is driven by
  `EngineController::darkMode`, which is currently `false` until `loadSettings()` runs from the
  `gd_init` watcher — after the QML has already bound and painted. Sampling the system night mode
  in the controller's constructor makes the first frame correct in the default follow-the-system
  mode, so a dark-mode user does not see a dark starting window followed by a light one.
- No engine, boundary, or upstream change: the starting window is pure Android resources, and the
  constructor addition only reorders a read the 500 ms tick already performs.

## Capabilities

### New Capabilities

<!-- None. The starting window is a launch-appearance concern already covered by
     `distribution-and-polish` (which owns the app icon and first-run appearance);
     a capability of its own for one theme attribute would bury it. -->

### Modified Capabilities

- `distribution-and-polish`: a new requirement covering the launch starting window — its
  background follows the system light/dark theme and matches the app's own background, the
  launcher icon is what it shows, and no bright frame appears between the two.

## Impact

- `app/android/AndroidManifest.xml` — `android:theme` on the launcher activity.
- `app/android/res/values/colors.xml` (new `app_background`), `app/android/res/values-night/colors.xml`
  (new), `app/android/res/values/styles.xml` (new `Theme.Aurelex`),
  `app/android/res/values-v31/styles.xml` (new, splash attrs).
- `app/EngineController.cpp` — sample the system night state in the constructor so the first frame
  resolves the theme; no new method, no new property, no change to the 500 ms `updateSystemDark`
  tick or to `applyEffectiveDark`.
- Not touched: `app/main.qml` (the Material `ApplicationWindow` already sets
  `color: Material.backgroundColor`, so the app's own window never needs a color binding),
  `AurelexActivity.java`, any `gd_*` boundary function, `patches/`, `engine/`.
- Affected APIs: none. Affected dependencies: none. `engine/` stays byte-for-byte at the pinned tag.
- Localization: no user-visible English text changes — no `qsTr`/`tr` argument and no
  `strings.xml` entry is added or altered — so `scripts/update-translations.ps1` is not needed.
- Compatibility: the theme is applied to the launcher activity only. `AurelexActivity` manages
  the system-bar icon appearance programmatically (`setSystemBarAppearance`), so the theme's
  bar attributes never decide the app's own contrast; the launcher's `Theme.DeviceDefault` parent
  supplies default widget/dialog styling and follows the system theme on its own.
