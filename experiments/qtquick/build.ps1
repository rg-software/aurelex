# Aurelex Qt experiment / port build script.
# One command: cmake configure -> ninja -> stage .so -> androiddeployqt ->
# gradle overrides -> gradle assembleDebug.
#
# Toolchain facts (proven 2026-09-02, see openspec/changes/qt-quick-frontend/design.md):
# - Qt android kits: C:\Qt\6.6.3\android_arm64_v8a (+ android_x86_64, host msvc2019_64)
# - ANDROID_PLATFORM=android-30 (NDK r23c caps at 33; carve needs iconv >= 28,
#   pthread_cond_clockwait >= 30)
# - NDK bionic sysroot include needed for iconv.h
# - Gradle must run under JDK 17 (AGP 7.4.1 + JDK 21 -> D8 NPE); Unity ships 17.0.9
# - aapt2 needs compileSdk android-34 + buildTools 35.0.0 (AGP 7.4.1 ceiling)
# - androiddeployqt regenerates local.properties/gradle.properties -> re-apply overrides
# - Qt has no qt_add_apk_target in the aqt carve subset -> package via androiddeployqt

param(
    [string]$Abi = "arm64-v8a",
    [ValidateSet("Debug", "Release")]
    [string]$Configuration = "Debug",
    [switch]$SkipConfigure,
    [switch]$Install
)

$ErrorActionPreference = "Stop"

$RepoRoot   = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
$ExpDir     = $PSScriptRoot
$BuildDir   = Join-Path $RepoRoot "build-qtquick"
$ApkDir     = Join-Path $BuildDir "apk"

# Local defaults assume the Unity-2025 install layout; CI overrides via env.
$QtBase     = if ($env:AURELEX_QT_BASE)     { $env:AURELEX_QT_BASE }     else { "C:\Qt\6.6.3" }
$QtHost     = if ($env:AURELEX_QT_HOST)     { $env:AURELEX_QT_HOST }     else { "$QtBase\msvc2019_64" }
$VcpkgBase  = if ($env:AURELEX_VCPKG_BASE)  { $env:AURELEX_VCPKG_BASE }  else { "C:\vcpkg" }
$NdkRoot    = if ($env:AURELEX_NDK_ROOT)    { $env:AURELEX_NDK_ROOT }    else { "C:\Program Files (x86)\Android\AndroidNDK\android-ndk-r23c" }
$RealSdk    = if ($env:AURELEX_ANDROID_SDK) { $env:AURELEX_ANDROID_SDK } else { "C:\Program Files (x86)\Android\android-sdk" }
$Jdk17      = if ($env:AURELEX_JDK17)       { $env:AURELEX_JDK17 }       else { "C:\Program Files\Unity\Hub\Editor\6000.0.62f1\Editor\Data\PlaybackEngines\AndroidPlayer\OpenJDK" }
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

Write-Host "== [1/5] cmake configure ($Abi, $Configuration) ==" -ForegroundColor Cyan
if (-not $SkipConfigure) {
    & $CmakeExe -S $ExpDir -B $BuildDir -G Ninja `
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
& $CmakeExe --build $BuildDir --target aurelex_exp -j 8
if ($LASTEXITCODE -ne 0) { throw "ninja build failed" }

Write-Host "== [3/5] stage .so into apk libs ==" -ForegroundColor Cyan
$soName = "libaurelex_exp_$Abi.so"
$soPath = Join-Path $BuildDir $soName
if (-not (Test-Path $soPath)) { throw "built .so not found: $soPath" }
New-Item -ItemType Directory -Force -Path "$ApkDir\libs\$Abi" | Out-Null
Copy-Item $soPath "$ApkDir\libs\$Abi\" -Force

Write-Host "== [4/5] androiddeployqt (stage + generate project, --no-build) ==" -ForegroundColor Cyan
$settings = Join-Path $BuildDir "android-aurelex_exp-deployment-settings.json"
# --no-build: stage Qt libs/assets and generate the gradle project, but do NOT
# let androiddeployqt invoke gradle itself (its internal run uses the Unity SDK
# + wrong JDK). We apply overrides, then build with gradle under JDK 17.
& $DeployQt --output $ApkDir --input $settings --no-build

# androiddeployqt regenerates AndroidManifest.xml from its template and does
# not merge the package-source manifest (custom activity / intent-filters /
# Java sources). Re-copy them after the deploy step.
Copy-Item (Join-Path $ExpDir "android\AndroidManifest.xml") (Join-Path $ApkDir "AndroidManifest.xml") -Force
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
if (Test-Path (Join-Path $ExpDir "android\src")) {
    New-Item -ItemType Directory -Force -Path (Join-Path $ApkDir "src") | Out-Null
    Copy-Item (Join-Path $ExpDir "android\src\*") (Join-Path $ApkDir "src\") -Recurse -Force
}
if (Test-Path (Join-Path $ExpDir "android\res")) {
    New-Item -ItemType Directory -Force -Path (Join-Path $ApkDir "res") | Out-Null
    Copy-Item (Join-Path $ExpDir "android\res\*") (Join-Path $ApkDir "res\") -Recurse -Force
}
# Article asset mirror (engine qrc:/// -> APK assets/). androiddeployqt in the
# carve-subset kit does not always propagate QT_ANDROID_PACKAGE_SOURCE_DIR/assets
# into the gradle staging tree, so copy explicitly.
if (Test-Path (Join-Path $ExpDir "android\assets")) {
    New-Item -ItemType Directory -Force -Path (Join-Path $ApkDir "assets") | Out-Null
    Copy-Item (Join-Path $ExpDir "android\assets\*") (Join-Path $ApkDir "assets\") -Recurse -Force
}

# Qt VirtualKeyboard: androiddeployqt plans the VK dependencies but silently
# skips staging them (observed with --no-build on the carve-subset kit). Stage
# them manually: libs + the QML modules under assets/qml (Qt resolves QML
# imports from assets on Android; main.cpp adds assets:/qml to the import
# paths).
$VkLibDir = "$QtBase\android_arm64_v8a\lib"
$VkQmlSrc = "$QtBase\android_arm64_v8a\qml\QtQuick\VirtualKeyboard"
if (Test-Path $VkQmlSrc) {
    foreach ($lib in @(
        "libQt6VirtualKeyboard_arm64-v8a.so",
        "libQt6VirtualKeyboardSettings_arm64-v8a.so",
        "libQt6Svg_arm64-v8a.so",
        "libQt6QuickLayouts_arm64-v8a.so",
        "libQt6LabsFolderListModel_arm64-v8a.so",
        "libqml_QtQuick_VirtualKeyboard_qtvkbplugin_arm64-v8a.so",
        "libqml_QtQuick_VirtualKeyboard_Settings_qtvkbsettingsplugin_arm64-v8a.so")) {
        $candidates = @(
            (Join-Path $VkLibDir $lib),
            "$QtBase\android_arm64_v8a\plugins\platforminputcontexts\$lib",
            "$QtBase\android_arm64_v8a\qml\QtQuick\VirtualKeyboard\$lib")
        $src = $candidates | Where-Object { Test-Path $_ } | Select-Object -First 1
        if ($src) { Copy-Item $src "$ApkDir\libs\$Abi\" -Force }
        else { Write-Host "  note: $lib not in kit (skipped)" -ForegroundColor DarkYellow }
    }
    # Settings/Styles plugin .so live inside the qml module dir
    Get-ChildItem $VkQmlSrc -Recurse -Filter "lib*.so" | ForEach-Object {
        Copy-Item $_.FullName "$ApkDir\libs\$Abi\" -Force
    }
    # QML module -> assets. VirtualKeyboard + its dependency modules
    # (Window/Layouts/labs.folderlistmodel are imported by Keyboard.qml).
    $qmlAssetRoot = "$ApkDir\assets\qml"
    New-Item -ItemType Directory -Force -Path "$qmlAssetRoot\QtQuick" | Out-Null
    foreach ($dir in @(
        "$QtBase\android_arm64_v8a\qml\QtQuick\VirtualKeyboard",
        "$QtBase\android_arm64_v8a\qml\QtQuick\Window",
        "$QtBase\android_arm64_v8a\qml\QtQuick\Layouts",
        "$QtBase\android_arm64_v8a\qml\Qt\labs\folderlistmodel")) {
        $name = Split-Path $dir -Leaf
        $parent = Split-Path (Split-Path $dir) -Leaf
        $dst = if ($parent -eq "labs") { "$qmlAssetRoot\Qt\labs\$name" } else { "$qmlAssetRoot\QtQuick\$name" }
        if (Test-Path $dst) { Remove-Item $dst -Recurse -Force }
        New-Item -ItemType Directory -Force -Path $dst | Out-Null
        Copy-Item "$dir\*" $dst -Recurse -Force
        # QML plugin .so must live in libs/<abi> for the class loader; the
        # qmldir "plugin" lines dlopen them from there at import time.
        Get-ChildItem $dst -Recurse -Filter "*.so" | ForEach-Object {
            Copy-Item $_.FullName "$ApkDir\libs\$Abi\" -Force
        }
        Get-ChildItem $dst -Recurse -Filter "*.so" | Remove-Item -Force
    }
}
if ($LASTEXITCODE -ne 0) { throw "androiddeployqt failed" }

Write-Host "== [5/5] gradle overrides + assemble$Configuration ==" -ForegroundColor Cyan
# androiddeployqt regenerates these two files; re-apply the working overrides.
# sdk.dir: the colon is escaped (\:) like the original local default; spaces
# are left as-is (AGP tolerates them).
$sdkDir = if ($env:AURELEX_ANDROID_SDK) { $env:AURELEX_ANDROID_SDK } else { "C:\Program Files (x86)\Android\android-sdk" }
Set-Content (Join-Path $ApkDir "local.properties") "sdk.dir=$($sdkDir -replace ':', '\:')" -NoNewline
$gpPath = Join-Path $ApkDir "gradle.properties"
$gp = Get-Content $gpPath -Raw
$gp = $gp -replace 'androidCompileSdkVersion=android-\d+', 'androidCompileSdkVersion=android-34'
$gp = $gp -replace 'androidBuildToolsVersion=[\d.]+', 'androidBuildToolsVersion=35.0.0'
Set-Content $gpPath $gp -NoNewline
# settings.gradle must scope this build away from the repo's settings.gradle.kts
if (-not (Test-Path (Join-Path $ApkDir "settings.gradle"))) {
    Set-Content (Join-Path $ApkDir "settings.gradle") 'rootProject.name = "aurelex-exp"'
}

# For Release builds: inject a signing config. Local builds use the debug
# keystore; CI overrides via AURELEX_KEYSTORE_PATH / _PASSWORD / _ALIAS /
# _KEY_PASSWORD (see .github/workflows/release-qt.yml). When neither the
# env-provided keystore nor the local debug keystore exists (e.g. a CI
# dry-run with no secrets), skip injection so gradle produces an unsigned
# release APK instead of failing on a missing storeFile.
if ($Configuration -eq "Release") {
    $ksPath = ""
    if ($env:AURELEX_KEYSTORE_PATH) {
        $ksPath = $env:AURELEX_KEYSTORE_PATH
    } else {
        $localDebug = Join-Path $env:USERPROFILE ".android\debug.keystore"
        if (Test-Path $localDebug) { $ksPath = $localDebug }
    }
    if ($ksPath) {
        $ksPass    = if ($env:AURELEX_KEYSTORE_PASSWORD) { $env:AURELEX_KEYSTORE_PASSWORD } else { "android" }
        $ksAlias   = if ($env:AURELEX_KEY_ALIAS)         { $env:AURELEX_KEY_ALIAS }         else { "androiddebugkey" }
        $ksKeyPass = if ($env:AURELEX_KEY_PASSWORD)      { $env:AURELEX_KEY_PASSWORD }      else { "android" }
        $bgPath = Join-Path $ApkDir "build.gradle"
        $bg = Get-Content $bgPath -Raw
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
                # Insert the signing configs right before android {
                $bg = $bg.Substring(0, $idx).TrimEnd() + "`n`n" + $signBlock.TrimStart() + "`n" + $bg.Substring($idx)
            }
            # Add signingConfig to the release build type
            $bg = $bg -replace '(buildTypes\s*\{[^}]*release\s*\{)', "`$1`n            signingConfig signingConfigs.release"
            Set-Content $bgPath $bg -NoNewline
            Write-Host "Injected release signing config (storeFile=$ksPath)." -ForegroundColor Yellow
        }
    } else {
        Write-Host "No release keystore available; building unsigned release APK." -ForegroundColor Yellow
    }
}

Push-Location $ApkDir
try {
    & ".\gradlew.bat" --no-daemon $gradleTask
    if ($LASTEXITCODE -ne 0) { throw "gradle $gradleTask failed" }
} finally {
    Pop-Location
}

$configLower = $Configuration.ToLower()
$apkDir2 = "$ApkDir\build\outputs\apk\$configLower"
$apk = Get-ChildItem $apkDir2 -Filter "*.apk" | Select-Object -First 1
if (-not $apk) { throw "APK not produced in $apkDir2" }
Write-Host "== DONE: $($apk.FullName) ($([math]::Round($apk.Length/1MB,1)) MB) ==" -ForegroundColor Green

if ($Install) {
    $adb = "$RealSdk\platform-tools\adb.exe"
    & $adb install -r $apk.FullName
    & $adb shell "am start -n com.aurelex.experiment/.ExperimentActivity"
    Write-Host "Installed + launched." -ForegroundColor Green
}
