## Context

See `proposal.md` — Why for motivation. What follows is the current state that
constrains the approach.

`app/build.ps1` stages native libraries in three wholesale copies (the
"[3/5] stage app .so" step):

```powershell
Get-ChildItem -Path "$KitRoot/lib"     -Filter "*.so"                    | Copy-Item -Destination $LibOut -Force
Get-ChildItem -Path "$KitRoot/qml"     -Recurse -Filter "libqml_*.so"     | Copy-Item -Destination $LibOut -Force
Get-ChildItem -Path "$KitRoot/plugins" -Recurse -Filter "libplugins_*.so" | Copy-Item -Destination $LibOut -Force
```

and a fourth, separately, into the asset tree:

```powershell
Copy-Item (Join-Path $KitRoot "qml/*") (Join-Path $ApkDir "assets/qml/") -Recurse -Force
```

So the module `.so` files are staged **twice** — once into `apk/libs/<abi>/` and
again under `apk/assets/qml/` (5.45 MB duplicated). Both copies are consumed
today, by different lookups, which is why this is not simply a delete.

`Write-QtLibResources` then enumerates `apk/libs/<abi>/` and emits
`bundled_libs`/`qt_libs` in `res/values/libs.xml`. The function is already
filter-shaped: it derives its output from whatever it finds on disk. It also
carries a hard constraint — the comment above it records that a mismatch between
that file and what the APK actually ships produces
`Resources$NotFoundException` / "Can't create main activity", so it must keep
mirroring the staged set exactly. A filter that changed the set must not change
the derivation.

### Measured baseline (release, `arm64-v8a`, after `embed-native-debug-symbols`)

Verified against the built AAB and APK (`base/lib/<abi>/` and `lib/<abi>/` —
140 `.so`, identical basename sets, every one stripped, no `.symtab`):

| | libs | MB |
|---|---|---|
| Packaged native payload | 140 | 86.32 |
| Reachable (derived) | 52 | 48.88 |
| Unreachable | 88 | 37.44 |

The derivation is `scripts/derive-native-payload.ps1`. Two things about it are
load-bearing and were both found by running it:

- **The candidate set is not just the kit.** It is the kit's `lib/`, `qml/**` and
  `plugins/**` (136) plus the built app library plus the two libraries staged from
  outside the kit — the vendored OpenSSL pair from `app/openssl/<abi>/` and
  `libc++_shared.so` from the NDK. Deriving over the kit alone reports all three
  as dropped, and since none has a link edge nothing puts them back.
- **`readelf -d` must be parsed for `NEEDED` specifically.** It also prints
  `SONAME` in brackets, and a library's SONAME is its own filename, so an
  unfiltered parse makes every library appear to link itself. That surfaced as a
  false "something now needs ShaderTools" assertion.

Following a module's own imports closes the set — and it must include the
`import` statements in the module's **`.qml` sources**, not just its `qmldir`.
That is not a refinement: `QtQuick.Controls.Material/ApplicationWindow.qml` does
`import QtQuick.Window`, and `QtQuick.Window`'s `qmldir` never mentions it, so a
`qmldir`-only closure drops the module and the app dies at startup with
`Type ApplicationWindow unavailable` / `module "QtQuick.Window" is not
installed`. Found on device, not by reading. `QtQuick.Window` ships a plugin
library of its own (11,888 B), so the plugin filter drops it too and the failure
is total, not degraded.

Both the module closure and the `assets/qml` prune are biased toward
over-inclusion: a module wrongly kept costs a few kilobytes, a module wrongly
dropped costs the whole UI.

Largest unreachable libraries: `libQt6Widgets` 6.45, `libQt6Designer` 5.12,
`libQt6ShaderTools` 3.38, `libQt6DesignerComponents` 2.95,
`libQt6QuickControls2Imagine` 1.90, `libQt6QuickDialogs2QuickImpl` 1.82,
VirtualKeyboard plugins 4.60 across 15, `libQt6QmlCompiler` 1.32,
`libplugins_sqldrivers_qsqlite` 1.10, Fusion/Universal styles 1.98.

Two of these were checked individually because they are the plausible false
positives:

- `libQt6Widgets` is reachable *only* from `libplugins_styles_qandroidstyle`, a
  widget-based Controls style plugin. A Qt Quick app never loads it, so the plugin
  and the library go together.
- `libQt6ShaderTools` is in no library's `DT_NEEDED` at all (checked across the
  whole staged set), and no app QML uses `ShaderEffect`.

## Goals / Non-Goals

**Goals**

- Remove every library the app cannot reach, from both the library tree and the
  asset tree, without a hand-maintained list.
- Keep the derived set honest as the app and the kit change.
- Make an unreachable library or an over-budget payload fail before publication.

**Non-Goals**

- Changing what the app links or imports. `app/CMakeLists.txt`'s
  `find_package(Qt6 ...)` list and `main.qml`'s import list are **inputs** to the
  filter. Changing them to shrink the payload would be a product change wearing a
  build change's clothes, and would need its own spec.
- Stripping. Already handled; verified working (all 140 shipped libraries have no
  `.symtab`, `libaurelex` 34.60 → 9.00 MB).
- ABI splitting. `qtTargetAbiList=arm64-v8a` already settles it.
- `useLegacyPackaging`. It governs whether the payload is extracted at install,
  not what is in it. Worth measuring separately; not entangled with this.

## Decisions

### D1: Derive the kept set from the built artifact, do not hand-maintain it

Compute the kept set at build time by walking `DT_NEEDED` from the freshly built
`libaurelex_<abi>.so`, union the QML modules the app imports, and intersect with
what the kit offers.

**Why not a checked-in allowlist.** A hand-written list is correct on the day it
is written and silently wrong after the next Qt upgrade, which is the exact
failure mode the current wholesale copy has. Deriving it means a Qt bump that
introduces a new dependency widens the payload correctly rather than being
dropped by a stale list — the failure mode inverts from silent-bloat to
silent-missing, and the latter is caught by the reachability assertion plus an
on-device launch.

**Cost:** the derivation needs `llvm-readelf` on the build host. The NDK already
provides it and `build.ps1` already resolves the NDK for the strip and symbol
steps, so this adds no new toolchain requirement, and it runs identically in CI.

### D2: Closure over `DT_NEEDED` alone is insufficient — curate the roots

Two classes of library have no `DT_NEEDED` edge from the app and would be
wrongly dropped by a pure closure:

1. **QML modules.** `QtQuick.Controls.Material` is not linked; it is discovered
   from a `qmldir` `plugin` line and loaded by the QML engine. The Material style
   in turn `depends` on `QtQuick.Controls.Basic` (its `qmldir` says
   `import QtQuick.Controls.Basic auto`), so Basic's style plugin and impl are
   reachable only through that chain.
2. **Libraries loaded without a link edge at all.** Measured: `libcrypto_3.so`
   comes out of a pure closure as *dead*, because Qt `dlopen`s the vendored
   OpenSSL at TLS init (see `AGENTS.md` — it is wired through
   `QT_ANDROID_EXTRA_LIBS` precisely because Qt has no link-time dependency on
   it). Dropping it would reproduce, in miniature, the failure the vendoring
   exists to prevent: a build that looks healthy and fails only when the catalog
   is opened. `libssl_3.so` and `libc++_shared.so` are curated for the same
   reason.

**Resolution:** the kept set is the closure over an explicit root list — the
built app library, the module set named by the app's QML imports, a short
curated plugin list (Android platform plugin, WebView, TLS backends, network
information, image formats and SVG icon engine), and the vendored/injected
libraries. The curated entries are each justified by a comment naming *how* they
are reached.

**Image formats are kept deliberately.** Dictionaries embed JPEG, GIF, ICO and
SVG artwork in articles; the article path renders them through `QImage`. These
plugins are small (0.87 MB together) and dropping them trades a real
feature for a rounding error.

### D3: One filter, two destinations — drive `assets/qml/` from the same set

The `assets/qml/` copy must lose exactly what `libs/<abi>/` loses. Filtering only
the library tree would leave the unreachable modules' `qmldir` files and `.qml`
sources addressable on the asset path, so a module could still resolve and then
fail on its missing library — strictly worse than not filtering at all, because
the failure moves from "module absent" to "module present, broken".

The asset tree additionally carries module *content* (`.qml`, `qmldir`,
`plugins.qmltypes`) that has no library to filter on — 2.67 MB, mostly the
VirtualKeyboard, Effects, Particles and Shapes modules. It is pruned by module
*directory*, using the same reachable set.

**Open trade-off, measured before deciding:** the module `.so` are duplicated
(5.45 MB). If the QML engine resolves module plugins from `libs/<abi>/` alone, the
copies under `assets/qml/` are redundant and can go; if it needs them there, they
stay. This is settled by experiment in task 2.3, not by argument here — the QML
import path is not something to reason about when it can be observed.

### D4: Assert on the artifact, reusing the assertion that already exists

`embed-native-debug-symbols` already added a native-payload step to
`.github/workflows/release-qt.yml` that extracts every `.so` under the AAB's
`base/lib/<abi>/` and the APK's `lib/<abi>/` and runs `llvm-readelf -S` over them,
failing on any `.symtab`. Extending that step is far cheaper than adding a second
one, and keeps every native-payload guarantee in a single place.

Two additions: a total-bytes ceiling for `lib/<abi>/`, and a reachability check
that the shipped name set matches the derived set. The ceiling is recorded as a
number in the workflow with the derivation that produced it, so the next person to
see it fail knows whether it is a regression or a legitimately wider kit.

**Why a ceiling and not only a denylist.** A denylist of known-dead libraries
(`libQt6Designer`, `libQt6Widgets`, `libQt6VirtualKeyboard`,
`libplugins_qmltooling_*`) catches the regressions we can name. The ceiling
catches the ones we cannot — a new Qt module nobody looked at.

### D5: Local derivation is checked, not assumed

The build derives the set, but a build-time-only derivation has no reviewable
artifact: a wrong filter is invisible until a launch fails. So the derivation is
also runnable as a host-side check in the same shape as the existing
`catalog_test` / `staging_rules_test` suite, printing the kept and dropped
libraries with their sizes so the diff is reviewable in a commit.

## Risks / Trade-offs

**[A reachable library gets filtered out and the app dies at startup]** → This is
the real risk; the failure is loud (no interface at all), not silent, but it is
only visible on a device. Mitigation: the reachability assertion runs on the
artifact, the derivation is reviewable in a commit (D5), and
`docs/TESTING.md` gains explicit on-device rows for app start, both themes, a
dictionary lookup with an embedded image, audio, the remote catalog (the
`dlopen` path from D2), and FTS — before the change is archived. If a library is
genuinely needed but unreachable by the derivation, it joins the curated root list
with a comment naming how it is reached.

**The curated root list becomes a second hand-maintained list** → Bounded by
construction: it holds only libraries with *no* link edge, which is a short,
stable set (three vendored/injected libraries plus the platform and run-time
plugins), not a general allowlist. Each entry carries its justification, and D1's
derivation covers everything else.

**Dropping a module breaks a dictionary nobody tests with** → Dictionaries supply
their own resources, but the *article* renders through Qt's image and text
machinery. Mitigation: keep all image formats (D2); run the existing
`TESTING.md` device matrix, which covers MDX/DSL/StarDict articles and embedded
imagery.

**A future Qt upgrade makes the budget assertion fail on a legitimate widening**
→ Intended. The failure names the measured size and the newly added library, so
the response is a judgement call rather than a mystery. Recorded in the workflow
next to the number.

**Filtering `assets/qml/` breaks module resolution** → Task 2.3 determines
empirically whether module plugins resolve from the library tree; the asset tree
is pruned by module directory in step with it either way (D3).

## Migration Plan

Single change, no data or schema migration, no version gate — the payload is
internal to the artifact. Rollback is reverting the commit; nothing on device
persists across it.

Ordering constraint: this change must land **after** `embed-native-debug-symbols`,
which owns stripping and the existing native-payload assertion. Both edit the
generated `build.gradle` and the same workflow step, and `androiddeployqt`
regenerates that file, so the later change's overrides must be re-applied
idempotently on top of the earlier one's — the failure mode this repository has
already hit once with the `debugSymbolLevel` line.

## Open Questions

- Does the QML engine resolve module plugins from `apk/libs/<abi>/` alone, making
  the 5.45 MB duplicated copy under `assets/qml/` removable? Deferred to task 2.3
  because it is observable, and the answer changes only which files are copied —
  not the spec, the approach, or the rest of the task breakdown.
- Is `libc++_shared.so` (6.61 MB staged) the right size, and does it carry debug
  sections the strip pass should have removed? Noted during measurement; it ships
  stripped and is orthogonal to this change.