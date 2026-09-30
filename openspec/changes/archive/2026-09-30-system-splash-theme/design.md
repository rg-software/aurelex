## Context

See proposal.md — Why. What constrains the approach:

- The starting window is drawn by the OS from the launcher's theme, so everything it can be told
  must exist as an Android resource. There is no hook from `ApplicationWindow`/QML into it, and
  none is wanted: the app must not depend on the platform splash API existing (Android 12+ only),
  nor on a compatibility library for it.
- `AndroidManifest.xml` currently applies **no** `android:theme` and carries
  `android.app.extract_android_style = minimal`, so the activity runs on the platform default
  theme. The starting window therefore gets the default white `windowBackground`.
- The app's background is `Material.background` (aliased as `uiBg` in `main.qml:193`). Qt 6.6
  is Material 3: `qquickmaterialstyle.cpp` defines
  `backgroundColorLight = 0xFFFFFBFE` and `backgroundColorDark = 0xFF1C1B1F`, and
  `backgroundColor()` returns one of them directly whenever the app does not override
  `Material.background` (it does not). Those two constants are the only values the Android
  resource layer may use — anything else is a color that does not exist in the app.
- The Material `ApplicationWindow.qml` in the kit sets `color: Material.backgroundColor`, so the
  Qt window's own clear color is already the app background. The app is not painting a white
  window; the mismatch is purely `Material.theme` being wrong on the first frame, not a missing
  color binding.
- `Material.theme` is bound to `EngineController::darkMode` (`main.qml:29`), and `m_darkMode`
  starts `false` and is only resolved by `applyEffectiveDark()` — which first runs when
  `loadSettings()` is called from the `gd_init` watcher (`EngineController.cpp:685`). The QML
  engine is constructed at `main.cpp:92`, the controller at `main.cpp:89`, so the controller
  exists strictly before any QML binding evaluates.
- The app is edge-to-edge and paints its own status/nav strips; `AurelexActivity` sets the system
  bar icon contrast programmatically through `setSystemBarAppearance` on every theme change. A
  new activity theme must not be relied on for that contrast, or the two would fight.

## Goals / Non-Goals

**Goals:**

- One place that decides the app's background color for the Android resource layer, with the two
  values traceable to Qt's own constants.
- Identical treatment on both platform paths (API 31+ splash, legacy starting window) from one
  theme, so the two cannot drift apart later.
- The first frame the app renders already carries the right palette in the default mode, so a
  correct starting window is not immediately followed by an incorrect one.

**Non-Goals:**

- Keeping the starting window on screen longer (a real splash with a progress state). That is the
  `androidx.core-splashscreen` `setKeepOnScreenCondition` mechanism, i.e. a new Gradle
  dependency plus a second theme and a hold that Qt's single-start activity cannot release early
  (see `AurelexActivity.onDestroy`'s comment about `startApplication` blocking). A longer hold is
  strictly worse here: it would freeze on the icon for the whole engine init.
- A custom splash icon (see D2).
- Changing the app's own window color or the Material palette in any way.
- Making the starting window follow a *forced* app theme. It is drawn before the app has read
  `settings.json`; the platform offers no way to know the preference in time. The spec states
  this limit rather than hiding it.

## Decisions

**D1 — A `Theme.Aurelex` on the launcher activity, with one `app_background` color resource.**

```
values/colors.xml        app_background = #FFFBFE   (light)
values-night/colors.xml  app_background = #1C1B1F   (dark)
values/styles.xml        Theme.Aurelex (parent Theme.DeviceDefault.NoActionBar)
                             android:windowBackground = @color/app_background
values-v31/styles.xml    Theme.Aurelex + android:windowSplashScreenBackground = @color/app_background
```

`values-night` resolves against the *system* night setting, which is exactly the only theme the
starting window can know (D3) — so light and dark need no duplicate night styles file, just the
color. Pointing both attributes at the same color resource is what makes the two platform paths
provably identical rather than coincidentally similar.

Rejected: hardcoding the two colors separately into `windowBackground` and
`windowSplashScreenBackground` — four literals that can drift, and the drift is invisible until
someone launches on a device we did not test.

Rejected: `?android:attr/colorBackground` (or any other platform theme reference) instead of an
explicit color. It would be zero-maintenance, but it is the *platform's* dark grey (Material You
surface tonal value), not the app's `#1C1B1F`. The whole point of the change is that the handoff is
invisible, and a different dark grey reintroduces a (softer) version of the same flash.

Rejected: reading the color at run time and pushing it into the theme from C++/Java. The starting
window is already gone by the time any app code runs, so it could only ever fix the *second*
frame, and at the cost of a JNI hop and a second source of truth for a constant.

**D2 — Keep the platform default splash icon.**

`android:windowSplashScreenAnimatedIcon` is the designated override, and it is not needed: with no
theme, the system already renders the launcher adaptive icon (`@mipmap/ic_launcher`, the Au book
artwork) masked and centered, which is the correct-looking result the user sees today. Setting
the attribute would introduce a second drawable that (a) has to be re-keyed whenever the icon art
changes, (b) is masked and scaled by the system to its own fixed container, so it would not
look like the launcher icon, and (c) loses the adaptive icon's themed/monochrome handling.

The "animated" in the name refers to accepting an `AnimatedVectorDrawable`, not to a different
visual treatment. Nothing here needs animation — a static logo on the starting window is the
platform's own behavior, not a design choice of ours.

**D3 — The starting window follows the system theme, not the app's resolved theme.**

A forced app theme lives in `settings.json` and is applied by `applyEffectiveDark()` after
`gd_init` returns. The OS draws the starting window before any of that, so the strongest possible
guarantee is "matches the system theme", and `values-night` delivers exactly that. The spec's
forced-theme scenario documents the resulting one-time switch instead of pretending it does not
happen.

**D4 — Sample the system night mode in the controller's constructor.**

Without this, a dark-mode user gets: dark starting window (D1) → **light** app frame (because
`m_darkMode` is still `false` and `Material.theme` is `Material.Light`) → dark app once
`loadSettings()` runs. Fixing the starting window without fixing the first frame would have made
the launch *worse*, not better.

So the constructor gains the two lines that the existing 500 ms tick already does a moment later:
read the system night state, and resolve the default (follow-the-system) mode from it. Only
`m_systemDark` and `m_darkMode` are touched. `applyEffectiveDark()` is deliberately **not** called
from the constructor: it invokes `gd_set_dark_mode` off-thread, which must not happen before
`gd_init` has run, and it pushes system-bar appearance over JNI, which the activity already
re-applies on the real theme change. Nothing is connected to a brand-new controller yet, so there
is no signal to emit either.

Rejected: reading `themeMode` from `settings.json` early so a forced mode is also right on the
first frame. That means loading settings before the engine is ready — moving `loadSettings()`
into the constructor path, which currently runs after `gd_init` returns, and which touches the
remote-catalog URL, paths, and saved defaults. That is a much larger blast radius than the flash
it would remove, for the minority of users who have pinned a theme.

Rejected: setting `color:` on the QML `ApplicationWindow`. The Material style already sets it
(`color: Material.backgroundColor` in the kit's `ApplicationWindow.qml`); a second binding would
only be a way to disagree with the palette.

## Risks / Trade-offs

- **The Android color and the Qt palette can drift if Qt's Material constants change.**
  → Both are pinned constants in Qt's own source; a Qt upgrade that changes them shows up as a
  one-color seam on launch, not a crash. The values are commented in `colors.xml` with their Qt
  source symbol, and task 5.2 verifies the match on-device rather than by reading the XML.
- **Applying a theme changes the activity's decor.** The parent is
  `@android:style/Theme.DeviceDefault.NoActionBar`, which supplies normal widget/dialog styling
  and follows the system theme on its own. Mitigated by keeping the theme to background
  attributes only, and by task 5.1 exercising the dialogs (rename group, delete confirmation,
  free-space) that a decor change would be most likely to affect.
- **A forced theme still starts in the system theme's background.** → Spec scenario, stated as a
  platform limit; the handoff is a background change, not a flash.
- **The constructor's JNI read is new at that point in the process.** `readSystemDark()` calls
  `AurelexActivity.isNightModeActive()`, which null-checks `QtNative.activity()` and returns
  `false` on any exception, so a not-yet-ready activity degrades to light rather than crashing —
  and the 500 ms tick corrects it. Mitigated by task 5.1 confirming a dark device starts dark.
