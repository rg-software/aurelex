# Aurelex Qt build script.
# One command: cmake configure -> ninja -> stage .so -> androiddeployqt ->
# gradle overrides -> gradle assembleDebug.
#
# Toolchain facts (proven 2026-09-02, see openspec/changes/qt-quick-frontend/design.md):
# - Qt android kits: C:\Qt\6.6.3\android_arm64_v8a (+ android_x86_64, host msvc2019_64)
# - ANDROID_PLATFORM=android-30 (NDK r23c caps at 33; carve needs iconv >= 28,
#   pthread_cond_clockwait >= 30)
# - NDK bionic sysroot include needed for iconv.h
# - Gradle must run under JDK 17 (AGP 7.4.1 + JDK 21 -> D8 NPE); Unity ships 17.0.9
# - compileSdk is bumped to android-36 for Play's targetSdk 36 requirement.
#   AGP 7.4.1 predates SDK 36, so android.suppressUnsupportedCompileSdk silences
#   its "not supported" warning. AGP's default aapt2 (7.4.1-8841542) cannot link
#   against SDK 36's android.jar, so gradle.properties pins
#   android.aapt2FromMavenOverride to the aapt2 from build-tools 36.0.0.
# - androiddeployqt regenerates local.properties/gradle.properties -> re-apply overrides
# - Qt has no qt_add_apk_target in the aqt carve subset -> package via androiddeployqt

param(
    [string]$Abi = "arm64-v8a",
    [ValidateSet("Debug", "Release")]
    [string]$Configuration = "Debug",
    [switch]$SkipConfigure,
    [switch]$Install,
    # Release only: also run bundleRelease so a signed AAB is produced for the
    # Google Play upload (distribution-and-polish design D3). The release APK
    # is still output for GitHub/F-Droid/sideload.
    [switch]$Bundle
)

$ErrorActionPreference = "Stop"

$RepoRoot   = Split-Path -Parent $PSScriptRoot
$AppDir     = $PSScriptRoot
$BuildDir   = Join-Path $RepoRoot "build-qtquick"
$ApkDir     = Join-Path $BuildDir "apk"

# Local defaults assume the Unity-2025 install layout; CI overrides via env.
$QtBase     = if ($env:AURELEX_QT_BASE)     { $env:AURELEX_QT_BASE }     else { "C:\Qt\6.6.3" }
$QtHost     = if ($env:AURELEX_QT_HOST)     { $env:AURELEX_QT_HOST }     else { "$QtBase\msvc2019_64" }
$VcpkgBase  = if ($env:AURELEX_VCPKG_BASE)  { $env:AURELEX_VCPKG_BASE }  else { "C:\vcpkg" }
$NdkRoot    = if ($env:AURELEX_NDK_ROOT)    { $env:AURELEX_NDK_ROOT }    else { "C:\Program Files (x86)\Android\AndroidNDK\android-ndk-r23c" }
$RealSdk    = if ($env:AURELEX_ANDROID_SDK) { $env:AURELEX_ANDROID_SDK } else { "C:\Program Files (x86)\Android\android-sdk" }
# JDK: CI overrides via AURELEX_JDK17 (actions/setup-java). Locally, hardcode
# the Unity 17 used for the proven AGP 7.4.1 setup — never pick up the host
# JAVA_HOME, which may be JDK 21+ and triggers the D8 NPE (see header comment).
$Jdk17 = if ($env:AURELEX_JDK17) { $env:AURELEX_JDK17 } else {
    "C:\Program Files\Unity\Hub\Editor\6000.0.62f1\Editor\Data\PlaybackEngines\AndroidPlayer\OpenJDK"
}
$UnitySdk   = if ($env:AURELEX_UNITY_SDK)   { $env:AURELEX_UNITY_SDK }   else { "C:\Program Files\Unity\Hub\Editor\6000.0.62f1\Editor\Data\PlaybackEngines\AndroidPlayer\SDK" }
$CmakeExe   = if ($env:AURELEX_CMAKE_EXE)   { $env:AURELEX_CMAKE_EXE }   else { "$UnitySdk\cmake\3.22.1\bin\cmake.exe" }
$DeployQt   = if ($env:AURELEX_DEPLOYQT)    { $env:AURELEX_DEPLOYQT }    else { "$QtHost\bin\androiddeployqt.exe" }

if (-not (Test-Path $CmakeExe)) { throw "cmake not found at $CmakeExe" }
if (-not (Test-Path $DeployQt)) { throw "androiddeployqt not found at $DeployQt" }

$env:JAVA_HOME         = $Jdk17
$env:ANDROID_SDK_ROOT  = $RealSdk
$env:ANDROID_HOME      = $RealSdk
$env:ANDROID_NDK_ROOT  = $NdkRoot

$gradleTask = "assemble$Configuration"

# ---- helper functions (defined before the call sites) ----

# The carve-subset androiddeployqt does not fill the Qt resource template
# (res/values/libs.xml from <kit>/src/android/templates). Without it the
# runtime lookups in QtLoader.startApp (qt_libs / bundled_libs / load_local_libs)
# are null -> android.content.res.Resources$NotFoundException: String array
# resource ID #0x0 -> "Can't create main activity" -> the app dies on the splash
# screen before any engine code runs. Build.gradle packages apk/res via
# sourceSets.main.res.srcDirs, so generate the file deterministically right after
# the libs are staged (it must mirror exactly what the APK ships).
function Write-QtLibResources {
    param([string]$ApkDir, [string]$Abi)

    $libDir = Join-Path $ApkDir "libs/$Abi"
    if (-not (Test-Path $libDir)) { return }

    # bundled_libs: EVERY .so the APK ships (Qt runtime + QML modules + plugins
    # + the app + libc++_shared), in a stable order. Qt's java loader expects a
    # "<abi>;<name>" pair per entry (QtLoader.prefferedAbiLibs filters by the
    # device's preferred ABI). For bundled_libs / qt_libs, <name> is the bare
    # library STEM (no "lib" prefix / ".so" suffix): the loader prepends
    # "lib" and appends ".so" (QtLoader.java:284-286 / QtNative's loader loop),
    # so "Qt6Core_arm64-v8a" -> "libQt6Core_arm64-v8a.so". load_local_libs is
    # the exception: its entries are used verbatim (QtLoader.java:291-295), so
    # it keeps the full filename ("libaurelex_arm64-v8a.so").
    $abiPrefix = "$Abi;"
    $all = @(Get-ChildItem -Path $libDir -Filter "*.so" -File |
        Select-Object -ExpandProperty Name | Sort-Object)
    # qt_libs: the Qt native libraries Qt's java loader System.load()s directly
    # before handing off to the native QML app.
    $qtLibs = @($all | Where-Object { $_ -like "libQt6*" -or $_ -like "libqml_*" -or $_ -like "libplugins_*" })
    # load_local_libs: the application's own library (android.app.lib_name + abi),
    # full filename, used verbatim.
    $appLib = "libaurelex_$Abi.so"
    $local  = @($all | Where-Object { $_ -eq $appLib })

    function LibraryStem([string]$fileName) {
        # "libQt6Core_arm64-v8a.so" -> "Qt6Core_arm64-v8a" ; "libc++_shared.so" -> "c++_shared"
        $s = $fileName
        if ($s.StartsWith("lib")) { $s = $s.Substring(3) }
        if ($s.EndsWith(".so"))   { $s = $s.Substring(0, $s.Length - 3) }
        return $s
    }

    function ItemsXml([string[]]$items, [bool]$fullName) {
        if ($items.Count -eq 0) { return "        <!-- none -->" }
        if ($fullName) {
            return ($items | ForEach-Object { "        <item>$abiPrefix$_</item>" }) -join "`n"
        }
        return ($items | ForEach-Object { "        <item>$abiPrefix$(LibraryStem $_)</item>" }) -join "`n"
    }

    $bundled = ItemsXml -items $all -fullName $false
    $qt      = ItemsXml -items $qtLibs -fullName $false
    $loc     = ItemsXml -items $local -fullName $true

    $bundled = ItemsXml $all
    $qt      = ItemsXml $qtLibs
    $loc     = ItemsXml $local
    $xml = @"
<?xml version='1.0' encoding='utf-8'?>
<resources>
    <!-- Generated by build.ps1 from the staged jniLibs; mirrors the template
         that a full androiddeployqt run would populate. -->
    <array name="bundled_libs">
$bundled
    </array>
    <array name="qt_libs">
$qt
    </array>
    <array name="load_local_libs">
$loc
    </array>
    <string name="static_init_classes"></string>
    <string name="use_local_qt_libs">1</string>
    <string name="bundle_local_qt_libs">1</string>
    <string name="system_libs_prefix"></string>
</resources>
"@
    $resValues = Join-Path $ApkDir "res/values"
    New-Item -ItemType Directory -Force -Path $resValues | Out-Null
    Set-Content (Join-Path $resValues "libs.xml") $xml -Encoding UTF8 -NoNewline
    Write-Host "Wrote res/values/libs.xml ($($all.Count) libs)." -ForegroundColor Yellow
}

Write-Host "== [1/5] cmake configure ($Abi, $Configuration) ==" -ForegroundColor Cyan
if (-not $SkipConfigure) {
    & $CmakeExe -S $AppDir -B $BuildDir -G Ninja `
        "-DCMAKE_TOOLCHAIN_FILE=$QtBase/android_arm64_v8a/lib/cmake/Qt6/qt.toolchain.cmake" `
        "-DANDROID_ABI=$Abi" `
        "-DANDROID_PLATFORM=android-30" `
        "-DQT_ANDROID_PLATFORM=30" `
        "-DQT_HOST_PATH=$QtHost" `
        "-DQT_BASE=$QtBase" `
        "-DVCPKG_BASE=$VcpkgBase" `
        "-DANDROID_NDK_ROOT=$NdkRoot" `
        "-DQT_ANDROID_SDK_ROOT=$RealSdk" `
        "-DQT_ANDROID_NDK_ROOT=$NdkRoot" `
        "-DQT_ANDROID_BUILD_TOOLS_VERSION=36.0.0" `
        "-DCMAKE_BUILD_TYPE=Release"
    if ($LASTEXITCODE -ne 0) { throw "cmake configure failed" }
}

Write-Host "== [2/5] ninja build ==" -ForegroundColor Cyan
& $CmakeExe --build $BuildDir --target aurelex -j 8
if ($LASTEXITCODE -ne 0) { throw "ninja build failed" }

Write-Host "== [3/5] stage app .so + Qt runtime/QML libs into apk libs ==" -ForegroundColor Cyan
$soName = "libaurelex_$Abi.so"
$soPath = Join-Path $BuildDir $soName
if (-not (Test-Path $soPath)) { throw "built .so not found: $soPath" }
$LibOut = "$ApkDir/libs/$Abi"
New-Item -ItemType Directory -Force -Path $LibOut | Out-Null
Copy-Item $soPath $LibOut -Force
# NOTE (qt-material-ui): androiddeployqt's --no-build path in the aqt carve
# subset logs "Appending dependency: lib/libQt6*" but does NOT physically copy
# the Qt runtime / QML module / plugin libraries into jniLibs. Historically the
# libs dir accumulated them from a stale one-time full deploy, which silently
# broke on a clean checkout (APK with only the app .so -> UnsatisfiedLinkError).
# Stage the complete Qt runtime set explicitly so the APK is self-contained and
# reproducible. Gradle packages this dir via jniLibs.srcDirs = ['libs'].
$KitRoot = if ($Abi -eq "arm64-v8a") { "$QtBase/android_arm64_v8a" }
           elseif ($Abi -eq "x86_64") { "$QtBase/android_x86_64" }
           else { throw "unsupported ABI $Abi" }

# Stage only the Qt libraries the app can actually reach. Staging the kit whole
# shipped 140 libs / 86.32 MB of which 96 / 37.97 MB were never loaded (Qt
# Designer, ShaderTools, the Widgets stack, the VirtualKeyboard, three unused
# Controls styles, the qmldbg/qmllint developer tooling...). The kept set is
# derived from the built app library's DT_NEEDED closure plus the app's own QML
# imports plus a short curated list for the libraries that have no link edge --
# see scripts/derive-native-payload.ps1 and the trim-release-payload change. It
# is derived rather than hand-listed so a Qt upgrade cannot silently re-bloat
# the payload, and so a new `import` in main.qml widens it automatically.
$DeriveScript = Join-Path $RepoRoot "scripts/derive-native-payload.ps1"
if (-not (Test-Path $DeriveScript)) { throw "payload derivation script missing: $DeriveScript" }
$keepNames = @(& $DeriveScript -Abi $Abi -QtBase $QtBase -NdkRoot $NdkRoot -AppLib $soPath -Mode List)
$keep = New-Object 'System.Collections.Generic.HashSet[string]'
foreach ($n in $keepNames) { if ($n -and $n.Trim()) { [void]$keep.Add($n.Trim()) } }
# The derivation must at minimum resolve the app library and the platform
# plugin. If it does not, the filter is broken and shipping "only what was
# derived" would produce an APK that cannot start -- fail here instead.
foreach ($required in @($soName, "libplugins_platforms_qtforandroid_$Abi.so")) {
    if (-not $keep.Contains($required)) { throw "payload derivation did not resolve $required -- refusing to stage a filtered set that cannot start" }
}

$kitCandidates = 0; $kitKept = 0; $kitStaged = 0L; $kitDropped = 0L
foreach ($spec in @(
    @{ Path = "$KitRoot/lib";     Filter = "*.so" },
    @{ Path = "$KitRoot/qml";     Filter = "libqml_*.so";     Recurse = $true },
    @{ Path = "$KitRoot/plugins"; Filter = "libplugins_*.so"; Recurse = $true }
)) {
    $items = @(Get-ChildItem -Path $spec.Path -Filter $spec.Filter -Recurse:$([bool]$spec.Recurse) -File -ErrorAction SilentlyContinue)
    $kitCandidates += $items.Count
    foreach ($i in $items) {
        if ($keep.Contains($i.Name)) {
            Copy-Item -Destination $LibOut -Force -Path $i.FullName
            $kitKept++
            $kitStaged += $i.Length
        } else {
            $kitDropped += $i.Length
        }
    }
}
Write-Host ("   Qt kit: {0} candidates -> kept {1} ({2:N2} MB), dropped {3} ({4:N2} MB)" -f `
    $kitCandidates, $kitKept, ($kitStaged/1MB), ($kitCandidates - $kitKept), ($kitDropped/1MB)) -ForegroundColor DarkGray
# libc++_shared.so ships from the NDK (host-agnostic path in r23c; the host
# sysroot is the pre-r23 location). Try both so the script runs on any host OS.
$cppShared = "$NdkRoot/sources/cxx-stl/llvm-libc++/libs/arm64-v8a/libc++_shared.so"
if (-not (Test-Path $cppShared)) {
    $prebuiltHost = if ($IsWindows) { "windows-x86_64" } else { "linux-x86_64" }
    $cppShared = "$NdkRoot/toolchains/llvm/prebuilt/$prebuiltHost/sysroot/usr/lib/aarch64-linux-android/libc++_shared.so"
}
if (Test-Path $cppShared) { Copy-Item $cppShared $LibOut -Force }

# The carve-subset androiddeployqt does not fill the Qt resource template
# (res/values/libs.xml from <kit>/src/android/templates). Without it the
# runtime lookups in QtLoader.startApp (qt_libs / bundled_libs / load_local_libs)
# are null -> android.content.res.Resources$NotFoundException: String array
# resource ID #0x0 -> "Can't create main activity" -> the app dies on the splash
# screen before any engine code runs. Build.gradle packages apk/res via
# sourceSets.main.res.srcDirs, so generate the file deterministically right after
# the libs are staged (it must mirror exactly what the APK ships).
Write-QtLibResources -ApkDir $ApkDir -Abi $Abi

# Qt Android bindings jars (QtNative etc.) live under <kit>/jar/. androiddeployqt
# in the carve-subset --no-build path does not copy them into apk/libs, so the
# Java compile can't find org.qtproject...QtNative. Stage them into libs/ (the
# build.gradle `implementation fileTree(dir:'libs')` picks them up).
$KitJarDir = "$KitRoot/jar"
if (Test-Path $KitJarDir) {
    Get-ChildItem -Path $KitJarDir -Filter "*.jar" -ErrorAction SilentlyContinue |
        Copy-Item -Destination "$ApkDir/libs/" -Force
}

# The derivation's curated roots have no link edge, so nothing in the kit walk
# would put them back if a filter change ever swept them up. libc++_shared is
# staged by the code path above, so assert it landed; the OpenSSL pair arrives
# later (androiddeployqt, via QT_ANDROID_EXTRA_LIBS) and is asserted after that
# step. The OpenSSL pair is what the remote catalog's TLS needs, and its failure
# mode is invisible until the catalog is opened (see AGENTS.md).
foreach ($edgeLess in @("libc++_shared.so")) {
    if (-not (Test-Path (Join-Path $LibOut $edgeLess))) {
        throw "edge-less run-time library $edgeLess is not staged in $LibOut -- the payload filter must never drop these (see scripts/derive-native-payload.ps1)"
    }
}

Write-Host "== [4/5] androiddeployqt (stage + generate project, --no-build) ==" -ForegroundColor Cyan
$settings = Join-Path $BuildDir "android-aurelex-deployment-settings.json"
# --no-build: stage Qt libs/assets and generate the gradle project, but do NOT
# let androiddeployqt invoke gradle itself (its internal run uses the Unity SDK
# + wrong JDK). We apply overrides, then build with gradle under JDK 17.
& $DeployQt --output $ApkDir --input $settings --no-build

# androiddeployqt regenerates AndroidManifest.xml from its template and does
# not merge the package-source manifest (custom activity / intent-filters /
# Java sources). Re-copy them after the deploy step.
Copy-Item (Join-Path $AppDir "android/AndroidManifest.xml") (Join-Path $ApkDir "AndroidManifest.xml") -Force
# Version stamping for release builds (CI sets AURELEX_VERSION_NAME / _CODE
# from the tag; local builds keep the manifest's 0.0.1 / 1 defaults).
if ($env:AURELEX_VERSION_NAME) {
    $mPath = Join-Path $ApkDir "AndroidManifest.xml"
    $m = Get-Content $mPath -Raw
    $m = $m -replace 'android:versionName="[^"]*"', ('android:versionName="' + $env:AURELEX_VERSION_NAME + '"')
    if ($env:AURELEX_VERSION_CODE) {
        $m = $m -replace 'android:versionCode="[^"]*"', ('android:versionCode="' + $env:AURELEX_VERSION_CODE + '"')
    }
    Set-Content $mPath $m -NoNewline
    Write-Host "Stamped manifest versionName=$env:AURELEX_VERSION_NAME versionCode=$env:AURELEX_VERSION_CODE" -ForegroundColor Yellow
}
if (Test-Path (Join-Path $AppDir "android/src")) {
    $stageSrc = Join-Path $ApkDir "src"
    New-Item -ItemType Directory -Force -Path $stageSrc | Out-Null
    # androiddeployqt may have left stale Java sources from a previous build
    # (e.g. pre-package-flip paths); remove them so only the current tree
    # compiles.
    if (Test-Path (Join-Path $stageSrc "com")) { Remove-Item (Join-Path $stageSrc "com") -Recurse -Force }
    if (Test-Path (Join-Path $stageSrc "aurelex")) { Remove-Item (Join-Path $stageSrc "aurelex") -Recurse -Force }
    if (Test-Path (Join-Path $stageSrc "org")) { Remove-Item (Join-Path $stageSrc "org") -Recurse -Force }
    Copy-Item (Join-Path $AppDir "android/src/*") $stageSrc -Recurse -Force
}
if (Test-Path (Join-Path $AppDir "android/res")) {
    New-Item -ItemType Directory -Force -Path (Join-Path $ApkDir "res") | Out-Null
    Copy-Item (Join-Path $AppDir "android/res/*") (Join-Path $ApkDir "res/") -Recurse -Force
}
# Article asset mirror (engine qrc:/// -> APK assets/). androiddeployqt in the
# carve-subset kit does not always propagate QT_ANDROID_PACKAGE_SOURCE_DIR/assets
# into the gradle staging tree, so copy explicitly.
if (Test-Path (Join-Path $AppDir "android/assets")) {
    New-Item -ItemType Directory -Force -Path (Join-Path $ApkDir "assets") | Out-Null
    Copy-Item (Join-Path $AppDir "android/assets/*") (Join-Path $ApkDir "assets/") -Recurse -Force
}
# QML module source overlay (qt-material-ui). androiddeployqt's createRCC path in
# the aqt carve subset does not reliably stage the imported QML module sources
# (Controls/Material/Templates/Layouts ...) into the APK, and --no-build even
# wipes assets/qml. Qt on Android resolves QML-source modules (QtQuick.Controls
# & styles are QML-based, unlike the compiled QtQuick core) from the qml import
# tree under assets:/qml plus their plugin .so in jniLibs.
#
# Copy only the modules the app reaches, using the SAME derived keep-set as the
# library staging above. Prune per module, not per top-level directory:
# QtQuick/Controls contains Fusion/, Imagine/ and Universal/ as nested modules,
# so copying it with -Recurse would pull the styles this filter exists to drop
# (and leave a dropped library addressable in assets while absent from jniLibs).
# A file is copied when its nearest module directory at or above it is
# reachable, which keeps a reachable module's own non-module subdirectories.
if (Test-Path "$KitRoot/qml") {
    $assetQml = Join-Path $ApkDir "assets/qml"
    $kitQml = Join-Path $KitRoot "qml"
    New-Item -ItemType Directory -Force -Path $assetQml | Out-Null

    # Reachable module directories: those holding a kept plugin library.
    $reachableDirs = New-Object 'System.Collections.Generic.HashSet[string]'
    Get-ChildItem -LiteralPath $kitQml -Recurse -Filter "libqml_*.so" -File -ErrorAction SilentlyContinue |
        Where-Object { $keep.Contains($_.Name) } |
        ForEach-Object { [void]$reachableDirs.Add($_.DirectoryName) }
    # Every module directory, reachable or not. A nested module (Fusion/ under
    # Controls/) is its own module, so it must be able to veto its parent's
    # reachability -- otherwise walking up to the first *reachable* ancestor
    # would re-admit every dropped style.
    $moduleDirs = New-Object 'System.Collections.Generic.HashSet[string]'
    Get-ChildItem -LiteralPath $kitQml -Recurse -Filter "qmldir" -File -ErrorAction SilentlyContinue |
        ForEach-Object { [void]$moduleDirs.Add($_.DirectoryName) }

    $assetFiles = 0; $assetBytes = 0L
    foreach ($f in @(Get-ChildItem -LiteralPath $kitQml -Recurse -File -ErrorAction SilentlyContinue)) {
        # Module plugin libraries are deliberately NOT duplicated here. Measured
        # on device: with every assets/qml/*.so removed, logcat shows the QML
        # engine loading each module plugin from base.apk!/lib/<abi>/ (jniLibs)
        # and the app starts and renders articles normally. They were 0.18 MB
        # after the module filter; the copy only risks the two locations
        # disagreeing.
        if ($f.Extension -eq ".so") { continue }
        # Nearest module directory at or above this file decides, and the walk
        # stops there -- a non-module subdirectory of a reachable module is
        # still that module's content.
        $d = $f.DirectoryName; $owner = $null
        while ($d -and $d.StartsWith($kitQml)) {
            if ($moduleDirs.Contains($d)) { $owner = $d; break }
            if ($d -eq $kitQml) { break }
            $d = Split-Path $d -Parent
        }
        if (-not $owner -or -not $reachableDirs.Contains($owner)) { continue }
        $rel = $f.FullName.Substring($kitQml.Length).TrimStart([IO.Path]::DirectorySeparatorChar, '/')
        $dest = Join-Path $assetQml $rel
        New-Item -ItemType Directory -Force -Path (Split-Path $dest -Parent) | Out-Null
        Copy-Item -LiteralPath $f.FullName -Destination $dest -Force
        $assetFiles++; $assetBytes += $f.Length
    }
    Write-Host ("   assets/qml: {0} of {1} modules reachable, copied {2} files ({3:N2} MB, plugin .so not duplicated)" -f `
        $reachableDirs.Count, $moduleDirs.Count, $assetFiles, ($assetBytes/1MB)) -ForegroundColor DarkGray
}

# The vendored OpenSSL pair is staged by androiddeployqt from
# QT_ANDROID_EXTRA_LIBS, and has no link edge either -- Qt dlopen()s it at TLS
# init. Assert it survived packaging so a filter change can never turn into a
# catalog that reports "TLS initialization failed" while the app looks healthy.
foreach ($tls in @("libcrypto_3.so", "libssl_3.so")) {
    if (-not (Test-Path (Join-Path $LibOut $tls))) {
        throw "vendored TLS library $tls is not staged in $LibOut -- the remote catalog would fail at run time (see scripts/derive-native-payload.ps1)"
    }
}

if ($LASTEXITCODE -ne 0) { throw "androiddeployqt failed" }

Write-Host "== [5/5] gradle overrides + assemble$Configuration ==" -ForegroundColor Cyan
# androiddeployqt regenerates these two files; re-apply the working overrides.
# sdk.dir: the colon is escaped (\:) like the original local default; spaces
# are left as-is (AGP tolerates them).
$sdkDir = if ($env:AURELEX_ANDROID_SDK) { $env:AURELEX_ANDROID_SDK } else { "C:\Program Files (x86)\Android\android-sdk" }
$sdkProp = ($sdkDir -replace '\\', '/') -replace ':', '\:'
Set-Content (Join-Path $ApkDir "local.properties") "sdk.dir=$sdkProp" -NoNewline
$gpPath = Join-Path $ApkDir "gradle.properties"
# aapt2 from AGP 7.4.1's default Maven artifact (7.4.1-8841542) cannot link
# against SDK 36's android.jar, so override aapt2 with the newer binary shipped
# in build-tools 36.0.0. The property key is android.aapt2FromMavenOverride.
$aapt2Name = if ($IsWindows) { "aapt2.exe" } else { "aapt2" }
$Aapt2Exe = (Join-Path $sdkDir "build-tools/36.0.0/$aapt2Name") -replace '\\', '/'
# AGP runs its native toolchain (llvm-strip, llvm-objcopy) out of an NDK it has
# located itself, and the only place it looks is inside the Android SDK
# (<sdk>/ndk/<androidNdkVersion>). Ours is installed outside the SDK tree (see
# $NdkRoot above: C:\Program Files (x86)\Android\AndroidNDK\android-ndk-r23c on a
# dev box, $GITHUB_WORKSPACE/ndk/android-ndk-r23c in CI), so AGP found no NDK at
# all: stripReleaseDebugSymbols logged "Unable to strip the following libraries,
# packaging them as they are:" for every jniLib (shipping the ~36 MB unstripped
# engine library in base/), and extractReleaseNativeSymbolTables produced nothing,
# so the AAB carried no native debug symbols at all. `ndkPath` points AGP at the
# NDK we actually built with; it takes precedence over ndkVersion and carries no
# deprecation warning (the ndk.dir local.properties route logs CXX5106 once per
# library, i.e. 140 lines per build). Forward slashes only: a Groovy
# double-quoted string eats \P / \n style escapes out of a Windows path.
$ndkPathGroovy = ($NdkRoot -replace '\\', '/')
# androiddeployqt in the carve-subset kit may not generate gradle.properties on
# a fresh tree (it exists locally only because a prior run left it behind). If
# absent, write one with our pinned values; otherwise patch the existing file.
if (-not (Test-Path $gpPath)) {
    $qtAndroidDir = if ($env:AURELEX_QT_BASE) { "$($env:AURELEX_QT_BASE)/android_arm64_v8a/./src/android/java" } else { "C:/Qt/6.6.3/android_arm64_v8a/./src/android/java" }
    # .properties treats \x sequences as escapes; use forward slashes only.
    $qtAndroidDir = $qtAndroidDir -replace '\\', '/'
    @"
org.gradle.jvmargs=-Xmx2500m -XX:MaxMetaspaceSize=768m -Dfile.encoding=UTF-8
android.useAndroidX=true
android.aapt2FromMavenOverride=$Aapt2Exe
androidBuildToolsVersion=35.0.0
androidCompileSdkVersion=android-36
androidNdkVersion=23.2.8568313
buildDir=build
qt5AndroidDir=$qtAndroidDir
qtAndroidDir=$qtAndroidDir
qtMinSdkVersion=23
android.suppressUnsupportedCompileSdk=36
qtTargetAbiList=arm64-v8a
qtTargetSdkVersion=36
"@ | Set-Content $gpPath -NoNewline
} else {
    $gp = Get-Content $gpPath -Raw
    $gp = $gp -replace 'androidCompileSdkVersion=android-\d+', 'androidCompileSdkVersion=android-36'
    $gp = $gp -replace 'androidBuildToolsVersion=[\d.]+', 'androidBuildToolsVersion=35.0.0'
    $gp = $gp -replace 'qtTargetSdkVersion=\d+', 'qtTargetSdkVersion=36'
    if ($gp -notmatch 'suppressUnsupportedCompileSdk') {
        $gp = $gp -replace '(qtTargetSdkVersion=\d+)', "`$1`nandroid.suppressUnsupportedCompileSdk=36"
    }
    if ($gp -notmatch 'aapt2FromMavenOverride') {
        $gp = $gp.TrimEnd() + "`nandroid.aapt2FromMavenOverride=$Aapt2Exe`n"
    }
    Set-Content $gpPath $gp -NoNewline
}
# settings.gradle must scope this build away from the repo's settings.gradle.kts
if (-not (Test-Path (Join-Path $ApkDir "settings.gradle"))) {
    Set-Content (Join-Path $ApkDir "settings.gradle") 'rootProject.name = "aurelex"'
}

# For Release builds: inject a signing config. Local builds use the debug
# keystore; CI overrides via AURELEX_KEYSTORE_PATH / _PASSWORD / _ALIAS /
# _KEY_PASSWORD (see .github/workflows/release-qt.yml). When neither the
# env-provided keystore nor the local debug keystore exists (e.g. a CI
# dry-run with no secrets), skip injection so gradle produces an unsigned
# release APK instead of failing on a missing storeFile.
function New-BaseBuildGradle {
    param([string]$NdkPath)
    @"
buildscript {
    repositories { google(); mavenCentral() }
    dependencies { classpath 'com.android.tools.build:gradle:7.4.1' }
}
repositories { google(); mavenCentral() }
apply plugin: 'com.android.application'

dependencies {
    implementation fileTree(dir: 'libs', include: ['*.jar', '*.aar'])
    implementation 'androidx.core:core:1.10.1'
}

android {
    compileSdkVersion androidCompileSdkVersion
    buildToolsVersion androidBuildToolsVersion
    ndkVersion androidNdkVersion
    // The NDK we compiled with, outside the SDK tree AGP searches. Without it
    // AGP locates no toolchain: nothing gets stripped and no native debug
    // symbols are extracted (see the ndkPath note in build.ps1).
    ndkPath "$NdkPath"

    packagingOptions.jniLibs.useLegacyPackaging true

    sourceSets {
        main {
            manifest.srcFile 'AndroidManifest.xml'
            java.srcDirs = [qtAndroidDir + '/src', 'src', 'java']
            aidl.srcDirs = [qtAndroidDir + '/src', 'src', 'aidl']
            res.srcDirs = [qtAndroidDir + '/res', 'res']
            resources.srcDirs = ['resources']
            renderscript.srcDirs = ['src']
            assets.srcDirs = ['assets']
            jniLibs.srcDirs = ['libs']
        }
    }

    lintOptions { abortOnError false }

    aaptOptions { noCompress 'rcc' }

    buildTypes {
        release {
            minifyEnabled false
            // Turn the merged libraries' symbol tables into the AAB's
            // BUNDLE-METADATA/com.android.tools.build.debugsymbols/<abi>/*.so.sym
            // entry, which is what Play symbolicates native crashes from.
            // SYMBOL_TABLE = function names (tombstone-compatible); FULL would
            // add file/line info at ~2x the symbols size.
            ndk { debugSymbolLevel 'SYMBOL_TABLE' }
        }
    }

    defaultConfig {
        resConfigs "en", "ru", "ja"
        minSdkVersion qtMinSdkVersion
        targetSdkVersion qtTargetSdkVersion
        ndk.abiFilters = qtTargetAbiList.split(",")
    }
}
"@
}

$bgPath = Join-Path $ApkDir "build.gradle"
if ($Configuration -eq "Release") {
    $ksPath = ""
    if ($env:AURELEX_KEYSTORE_PATH -and (Test-Path $env:AURELEX_KEYSTORE_PATH)) {
        $ksPath = $env:AURELEX_KEYSTORE_PATH
    } else {
        $localDebug = Join-Path $HOME ".android/debug.keystore"
        if (Test-Path $localDebug) { $ksPath = $localDebug }
    }
    if ($ksPath) {
        $ksPass    = if ($env:AURELEX_KEYSTORE_PASSWORD) { $env:AURELEX_KEYSTORE_PASSWORD } else { "android" }
        $ksAlias   = if ($env:AURELEX_KEY_ALIAS)         { $env:AURELEX_KEY_ALIAS }         else { "androiddebugkey" }
        $ksKeyPass = if ($env:AURELEX_KEY_PASSWORD)      { $env:AURELEX_KEY_PASSWORD }      else { "android" }
        $bg = ""
        if (Test-Path $bgPath) { $bg = Get-Content $bgPath -Raw }
        if ($bg.Trim().Length -eq 0) {
            # The carve-subset androiddeployqt --no-build may not generate
            # build.gradle on a fresh tree. Write a complete one matching the
            # Qt androiddeployqt template (values come from gradle.properties).
            Set-Content $bgPath (New-BaseBuildGradle -NdkPath $ndkPathGroovy) -NoNewline
            $bg = Get-Content $bgPath -Raw
            Write-Host "Wrote complete build.gradle (carve-subset fresh tree)." -ForegroundColor Yellow
        }
        if ($bg -notmatch "signingConfigs") {
            # Insert signing config before the android { } block
            $signBlock = @"

    signingConfigs {
        release {
            storeFile file("$($ksPath -replace '\\', '/')")
            storePassword "$ksPass"
            keyAlias "$ksAlias"
            keyPassword "$ksKeyPass"
        }
    }
"@
            # Insert after "apply plugin: 'com.android.application'" and deps
            $marker = "android {"
            $idx = $bg.IndexOf($marker)
            if ($idx -ge 0) {
                # signingConfigs is AGP extension DSL: declare it inside android { }
                # (project scope fails with "Could not find method signingConfigs()").
                $insertAt = $idx + $marker.Length
                $bg = $bg.Substring(0, $insertAt) + "`n" + $signBlock.TrimStart() + "`n" + $bg.Substring($insertAt)
            }
            # Add signingConfig to the release build type
            $bg = $bg -replace '(buildTypes\s*\{[^}]*release\s*\{)', "`$1`n            signingConfig signingConfigs.release`n"
            Set-Content $bgPath $bg -NoNewline
            Write-Host "Injected release signing config (storeFile=$ksPath)." -ForegroundColor Yellow
        }
    } else {
        Write-Host "No release keystore available; building unsigned release APK." -ForegroundColor Yellow
        if (-not (Test-Path $bgPath)) {
            # Fresh carve-subset tree without androiddeployqt's build.gradle.
            Set-Content $bgPath (New-BaseBuildGradle -NdkPath $ndkPathGroovy) -NoNewline
            Write-Host "Wrote complete unsigned build.gradle (fresh tree)." -ForegroundColor Yellow
        }
    }
} else {
    # Debug (or any non-Release) build. androiddeployqt's carve-subset
    # --no-build path does not generate a build.gradle on a fresh tree; gradle
    # then fails with "Task 'assembleDebug' not found". Write the same complete
    # base build file (no signing config; the debug keystore is applied by AGP
    # automatically for the debug buildType).
    if (-not (Test-Path $bgPath)) {
        Set-Content $bgPath (New-BaseBuildGradle -NdkPath $ndkPathGroovy) -NoNewline
        Write-Host "Wrote complete build.gradle for $Configuration (fresh tree)." -ForegroundColor Yellow
    }
}

# androiddeployqt's own template narrows packaged resources to the English
# config (resConfig "en"). The localization change ships ru/ja alternate
# strings, so widen the kept configs on every run (idempotent patch).
if (Test-Path $bgPath) {
    $bgNow = Get-Content $bgPath -Raw
    if ($bgNow -match 'resConfig\s+"en"') {
        Set-Content $bgPath ($bgNow -replace 'resConfig\s+"en"', 'resConfigs "en", "ru", "ja"') -NoNewline
        Write-Host "Patched resConfig to keep en/ru/ja locales." -ForegroundColor Yellow
    }
}

# Native symbols + stripped shipped libraries, for the AAB's native debug
# symbols payload (Play symbolicates native crashes from it) and for base/
# shipping stripped .so files. Two settings, both required, both re-applied here
# because androiddeployqt regenerates build.gradle on every run:
#
#   ndkPath                        AGP runs llvm-strip / llvm-objcopy out of an
#                                  NDK it located itself, and it only looks
#                                  inside the Android SDK (<sdk>/ndk/<version>).
#                                  Ours lives outside the SDK tree, so without
#                                  this AGP finds no toolchain: every jniLib is
#                                  passed through unstripped and NO symbols are
#                                  extracted at all.
#   ndk.debugSymbolLevel           turns the merged libraries' symbol tables
#      'SYMBOL_TABLE'              into the AAB's
#                                  BUNDLE-METADATA/com.android.tools.build.
#                                  debugsymbols/<abi>/*.so.sym entries.
#
# Idempotent, so it also repairs an androiddeployqt-generated build.gradle left
# behind on a dev machine.
if (Test-Path $bgPath) {
    $bgOut = Get-Content $bgPath -Raw
    $dirty = $false
    if ($bgOut -notmatch '(?m)^\s*ndkPath\s') {
        $bgLines = @(Get-Content $bgPath)
        # Anchor on androiddeployqt's own "ndkVersion androidNdkVersion" line so
        # the setting lands next to its sibling; fall back to the android { }
        # block if a tree's template ever drops it.
        $anchor = -1
        for ($i = 0; $i -lt $bgLines.Count; $i++) {
            if ($bgLines[$i] -match '^\s*ndkVersion\s+androidNdkVersion\s*$') { $anchor = $i; break }
        }
        if ($anchor -lt 0) {
            for ($i = 0; $i -lt $bgLines.Count; $i++) {
                if ($bgLines[$i] -match '^\s*android\s*\{\s*$') { $anchor = $i; break }
            }
        }
        if ($anchor -ge 0) {
            $before = if ($anchor -gt 0) { @($bgLines[0..($anchor - 1)]) } else { @() }
            $after = if ($anchor -lt ($bgLines.Count - 1)) { @($bgLines[($anchor + 1)..($bgLines.Count - 1)]) } else { @() }
            $bgOut = (@($before + "    ndkPath `"$ndkPathGroovy`"" + $after) -join "`n")
            $dirty = $true
            Write-Host "Patched build.gradle with ndkPath ($ndkPathGroovy)." -ForegroundColor Yellow
        } else {
            Write-Warning "build.gradle has no ndkVersion / android { anchor; ndkPath NOT patched (AGP would find no NDK: unstripped libraries, no native debug symbols)."
        }
    }
    if ($bgOut -notmatch 'debugSymbolLevel') {
        $bgOut = $bgOut -replace '(buildTypes\s*\{[^}]*release\s*\{)', "`$1`n            ndk { debugSymbolLevel 'SYMBOL_TABLE' }`n"
        $dirty = $true
        Write-Host "Patched release buildType with ndk debugSymbolLevel SYMBOL_TABLE." -ForegroundColor Yellow
    }
    if ($dirty) { Set-Content $bgPath $bgOut -NoNewline }
}

Push-Location $ApkDir
try {
    # Prefer the wrapper scripts (androiddeployqt stages gradlew.bat + wrapper
    # jar on a full kit); on the carve-subset fresh tree neither exists, so use
    # the gradle distribution from AURELEX_GRADLE_HOME (CI installs it) or the
    # system gradle.
    function Invoke-Gradle([string[]]$Tasks) {
        # Prefer the native launcher for the host OS: the Android Gradle
        # distribution ships BOTH bin/gradle and bin/gradle.bat everywhere, and
        # pwsh on Linux cannot exec a .bat. Preference order — on Windows:
        #   <apk>/gradlew.bat, AURELEX_GRADLE_HOME/bin/gradle.bat,
        #   GRADLE_HOME/bin/gradle.bat, gradle.bat on PATH;
        # on Linux the non-.bat equivalents.
        $isWin = $IsWindows
        foreach ($t in $Tasks) {
            $runners = @()
            $runners += if ($isWin) { ".\gradlew.bat" } else { "./gradlew" }
            foreach ($base in @($env:AURELEX_GRADLE_HOME, $env:GRADLE_HOME)) {
                if ($base) {
                    $runners += (Join-Path $base ("bin/" + $(if ($isWin) { "gradle.bat" } else { "gradle" })))
                }
            }
            $wt = Get-Command $(if ($isWin) { "gradle.bat" } else { "gradle" }) -ErrorAction SilentlyContinue
            if ($wt) { $runners += $wt.Source }

            $runner = $null
            foreach ($cand in $runners) {
                if ($cand -and (Test-Path $cand)) { $runner = $cand; break }
            }
            if (-not $runner) {
                throw "no gradlew.bat, no gradle-wrapper.jar, no gradle on PATH in $ApkDir — cannot run gradle"
            }
            & $runner --no-daemon $t
            if ($LASTEXITCODE -ne 0) { throw "gradle $t failed" }
        }
    }

    $tasks = @($gradleTask)
    if ($Bundle -and $Configuration -eq "Release") {
        # Play upload needs the signed AAB; build it alongside the release APK.
        $tasks += @("bundleRelease")
    }
    Invoke-Gradle $tasks
} finally {
    Pop-Location
}

$configLower = $Configuration.ToLower()
$apkDir2 = "$ApkDir/build/outputs/apk/$configLower"
$apk = Get-ChildItem $apkDir2 -Filter "*.apk" | Select-Object -First 1
if (-not $apk) { throw "APK not produced in $apkDir2" }
Write-Host "== DONE: $($apk.FullName) ($([math]::Round($apk.Length/1MB,1)) MB) ==" -ForegroundColor Green

if ($Bundle -and $Configuration -eq "Release") {
    $aabDir = "$ApkDir/build/outputs/bundle/release"
    $aab = Get-ChildItem $aabDir -Filter "*.aab" | Select-Object -First 1
    if (-not $aab) { throw "AAB not produced in $aabDir (did -Bundle run bundleRelease?)" }
    Write-Host "== AAB: $($aab.FullName) ($([math]::Round($aab.Length/1MB,1)) MB) ==" -ForegroundColor Green
}

if ($Install) {
    $adbName = if ($IsWindows) { "adb.exe" } else { "adb" }
    $adb = "$RealSdk/platform-tools/$adbName"
    & $adb install -r $apk.FullName
    & $adb shell "am start -n org.aurelex.pocket.dictionary/.AurelexActivity"
    Write-Host "Installed + launched." -ForegroundColor Green
}
