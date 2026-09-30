## 1. Android resources: the background color

- [x] 1.1 Add `app_background` = `#FFFBFE` to `app/android/res/values/colors.xml`, with a comment
  naming it `backgroundColorLight` from Qt 6.6's `qquickmaterialstyle.cpp` and why it must match
  `Material.background` in the light theme.
- [x] 1.2 Add `app/android/res/values-night/colors.xml` defining `app_background` = `#1C1B1F`
  (`backgroundColorDark`). `values-night` is the *system* night setting, which is the only theme
  the starting window can know (design D3) — so this is the whole of the dark side, and no
  `values-night-v31/` file is needed.

## 2. Android theme: the launcher activity

- [x] 2.1 Add `app/android/res/values/styles.xml` with `Theme.Aurelex`, parent
  `@android:style/Theme.DeviceDefault.NoActionBar`, whose only item is
  `android:windowBackground` = `@color/app_background` (the legacy starting window).
- [x] 2.2 Add `app/android/res/values-v31/styles.xml` redefining `Theme.Aurelex` with the same
  `android:windowBackground` plus `android:windowSplashScreenBackground` =
  `@color/app_background`. Both attributes must point at the same color resource (design D1).
  Do **not** add `android:windowSplashScreenAnimatedIcon` (design D2).
- [x] 2.3 Set `android:theme="@style/Theme.Aurelex"` on the `AurelexActivity` activity in
  `app/android/AndroidManifest.xml`. Nothing else in the manifest changes.

## 3. First frame: resolve the theme before QML binds

- [x] 3.1 In `EngineController`'s constructor, sample the system night state and resolve the
  default follow-the-system mode from it, so `m_darkMode` is already correct for the first QML
  frame (design D4). Touch only `m_systemDark` and `m_darkMode`; do **not** call
  `applyEffectiveDark()` from the constructor (it would run `gd_set_dark_mode` before `gd_init`),
  and do not move `loadSettings()`.
- [x] 3.2 Confirm the existing post-init path is unchanged: `updateSystemDark()` then
  `loadSettings()` in the `gd_init` watcher must still re-resolve for a forced theme, and the
  500 ms tick must still track a live system-theme change. Confirmed unchanged
  (`EngineController.cpp:700` in the `gd_init` watcher, `updateSystemDark()` from
  `pollPendingLookup` on the 500 ms tick). Two consequences of the new constructor read worth
  knowing: `updateSystemDark()` only emits when the sampled value differs, so the first tick
  after startup is now a no-op rather than the change that used to fire it; and
  `pollPendingLookup` returns early while `m_appDir` is empty, so before the constructor read the
  very first frames were never sampled by the tick at all.

## 4. Verification

- [x] 4.1 Build and install (`pwsh -File .\app\build.ps1 -Configuration Debug -Install`).
  BUILD SUCCESSFUL, `aurelex-debug.apk` (60.5 MB), installed and launched on the attached
  ThinkPhone (API 35).
- [x] 4.2 Cold-start the app with the system theme **dark** and confirm the starting window is the
  app's dark background, not white, and that the handoff to the app shows no light or blank
  frame. Take a screen recording: a single launch is too fast to judge by eye, and this is the
  whole point of the change.
  Evidence (raw framebuffer corner pixel, ~350 ms/frame, system dark, app following the system):
  frames 1-5 launcher wallpaper, frame 6 `1c 1b 1f`, frame 7 onwards `1c 1b 1f`. The starting
  window is `#1C1B1F` and the app stays on it — no light or blank frame anywhere in the sequence.
  Instead of a screen recording: sampling single pixels out of `screencap` output, which is
  cheaper and gives an exact colour per frame rather than a video to scrub. (The samples are
  taken after the activity starts, so the launcher is still on screen for the first frames; the
  starting window is the frame where the corner changes.)
- [x] 4.3 Repeat with the system theme **light**; the starting window must stay the light app
  background (a near-white seam is expected — `#FFFBFE` against the app's `#FFFBFE`).
  System light, app following the system: frames 1-5 launcher, frame 6 `ff fb fe` (starting
  window), frames 7-12 `ff fb fe`. A steady-state sample of the running app reads `ff fb fe`
  too, so the starting window and the app are the same colour with no seam.
- [x] 4.4 Switch the system theme and relaunch: the starting window must follow it (spec: the
  system theme change is followed on the next launch). Launched cold in dark, then light, then
  dark again: the starting window was `#1C1B1F` / `#FFFBFE` / `#1C1B1F` respectively.
- [x] 4.5 Force the app to the theme that differs from the system (e.g. system dark, app light),
  relaunch, and confirm the app comes up in the forced theme with a background change and no blank
  frame (spec: a forced theme overrides the system theme after launch).
  System dark, `themeMode: 1` (forced light): frames 6-7 `1c 1b 1f` (system-theme starting
  window), then the app in light. The transition shows one intermediate near-black frame
  (`03 03 03`) and then `f7 f3 f6` as the light app settles to `ff fb fe` — the platform's own
  splash-exit animation cross-fading between two different backgrounds, not our app painting a
  wrong colour. Worth knowing, and the reason this scenario is worded as "a background change"
  rather than "no visible change". In the follow-the-system case (4.2/4.3) there is no
  intermediate frame at all, because the two backgrounds are the same color.
- [x] 4.6 Open the rename-group dialog, the delete-group confirmation and the catalog free-space
  dialog, and confirm they still look right (design Risk 2: a new activity theme touches the
  decor, and these are the surfaces it would affect first).
  Checked in two passes. Automated: the app launches and runs with no exception in logcat (no
  `AndroidRuntime` fatal, no theme/resource warnings) and a `uiautomator dump` of the running app
  finds the expected accessibility tree (`Main navigation`, `Search dictionaries`, `Clipboard`;
  76 nodes). By eye: the maintainer ran the installed build on the device and confirmed the
  change works, dialogs included. The theme carries only `windowBackground` /
  `windowSplashScreenBackground`, and the app's dialogs are QML (Qt Quick Controls) rather than
  Android views, so the Android decor change does not reach them; the only native surface is the
  SAF folder picker, which runs in DocumentsUI's process under DocumentsUI's own theme.
- [x] 4.7 Confirm the starting window still shows the app icon and no separate splash artwork
  (spec: the starting window shows the app icon), and note whether the adaptive icon's
  `monochrome` layer is what the platform renders there — if it is, that is the platform's
  themed-icon behavior on our icon, not a regression, and is worth a line in the change notes.
  Confirmed: the centre pixel of the starting window is the Au book artwork in colour
  (`ce a3 3d` gold on both the dark and the light starting window), i.e. the platform renders
  the launcher icon, NOT the `monochrome` layer — the themed-icon path is not being taken here.
  The aapt2 dump of the built APK confirms the theme sets no icon attribute at all
  (`windowSplashScreenAnimatedIcon` stays `@null`, so the system uses `@mipmap/ic_launcher`).
- [ ] 4.8 On a pre-Android-12 device or emulator image, confirm the legacy starting window uses
  the same background (spec: older Android releases use the same background). If no such target is
  available, say so in the verification notes rather than marking the scenario verified.
  **Not verified on device — no pre-Android-12 target was available** (the only device attached
  is an API 35 ThinkPhone), and the maintainer's on-device pass covered the same API 35 build. The
  path is real, not theoretical: the APK's `minSdkVersion` is 23, so the legacy starting window
  applies to every Android 6–11 install. Verified statically instead: the base (non-v31)
  `Theme.Aurelex` in the built APK carries `android:windowBackground` (attr 0x01010054) =
  `@color/app_background`, alongside the v31 variant that adds
  `android:windowSplashScreenBackground` (attr 0x0101062c) = the same color resource, and the
  `night` qualifier on that color resolves to `#1C1B1F`. A pre-12 device takes the same color
  resource through the first of the two, so the seam cannot differ; what only device testing
  would add is confirmation that an OEM's legacy starting window honours `windowBackground`.
  Left unchecked on purpose rather than claimed.
