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

    $libDir = Join-Path $ApkDir "libs\$Abi"
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
    $resValues = Join-Path $ApkDir "res\values"
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
$LibOut = "$ApkDir\libs\$Abi"
New-Item -ItemType Directory -Force -Path $LibOut | Out-Null
Copy-Item $soPath $LibOut -Force
# NOTE (qt-material-ui): androiddeployqt's --no-build path in the aqt carve
# subset logs "Appending dependency: lib/libQt6*" but does NOT physically copy
# the Qt runtime / QML module / plugin libraries into jniLibs. Historically the
# libs dir accumulated them from a stale one-time full deploy, which silently
# broke on a clean checkout (APK with only the app .so -> UnsatisfiedLinkError).
# Stage the complete Qt runtime set explicitly so the APK is self-contained and
# reproducible. Gradle packages this dir via jniLibs.srcDirs = ['libs'].
$KitRoot = if ($Abi -eq "arm64-v8a") { "$QtBase\android_arm64_v8a" }
           elseif ($Abi -eq "x86_64") { "$QtBase\android_x86_64" }
           else { throw "unsupported ABI $Abi" }
Get-ChildItem -Path "$KitRoot\lib" -Filter "*.so" -ErrorAction SilentlyContinue |
    Copy-Item -Destination $LibOut -Force
Get-ChildItem -Path "$KitRoot\qml" -Recurse -Filter "libqml_*.so" -ErrorAction SilentlyContinue |
    Copy-Item -Destination $LibOut -Force
Get-ChildItem -Path "$KitRoot\plugins" -Recurse -Filter "libplugins_*.so" -ErrorAction SilentlyContinue |
    Copy-Item -Destination $LibOut -Force
# libc++_shared.so ships from the NDK sysroot, not the Qt kit.
$cppShared = "$NdkRoot\toolchains\llvm\prebuilt\windows-x86_64\sysroot\usr\lib\aarch64-linux-android\libc++_shared.so"
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
$KitJarDir = "$KitRoot\jar"
if (Test-Path $KitJarDir) {
    Get-ChildItem -Path $KitJarDir -Filter "*.jar" -ErrorAction SilentlyContinue |
        Copy-Item -Destination "$ApkDir\libs\" -Force
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
Copy-Item (Join-Path $AppDir "android\AndroidManifest.xml") (Join-Path $ApkDir "AndroidManifest.xml") -Force
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
if (Test-Path (Join-Path $AppDir "android\src")) {
    $stageSrc = Join-Path $ApkDir "src"
    New-Item -ItemType Directory -Force -Path $stageSrc | Out-Null
    # androiddeployqt may have left stale Java sources from a previous build
    # (e.g. pre-package-flip paths); remove them so only the current tree
    # compiles.
    if (Test-Path (Join-Path $stageSrc "com")) { Remove-Item (Join-Path $stageSrc "com") -Recurse -Force }
    if (Test-Path (Join-Path $stageSrc "aurelex")) { Remove-Item (Join-Path $stageSrc "aurelex") -Recurse -Force }
    Copy-Item (Join-Path $AppDir "android\src\*") $stageSrc -Recurse -Force
}
if (Test-Path (Join-Path $AppDir "android\res")) {
    New-Item -ItemType Directory -Force -Path (Join-Path $ApkDir "res") | Out-Null
    Copy-Item (Join-Path $AppDir "android\res\*") (Join-Path $ApkDir "res\") -Recurse -Force
}
# Article asset mirror (engine qrc:/// -> APK assets/). androiddeployqt in the
# carve-subset kit does not always propagate QT_ANDROID_PACKAGE_SOURCE_DIR/assets
# into the gradle staging tree, so copy explicitly.
if (Test-Path (Join-Path $AppDir "android\assets")) {
    New-Item -ItemType Directory -Force -Path (Join-Path $ApkDir "assets") | Out-Null
    Copy-Item (Join-Path $AppDir "android\assets\*") (Join-Path $ApkDir "assets\") -Recurse -Force
}
# QML module source overlay (qt-material-ui). androiddeployqt's createRCC path in
# the aqt carve subset does not reliably stage the imported QML module sources
# (Controls/Material/Templates/Layouts ...) into the APK, and --no-build even
# wipes assets/qml. Qt on Android resolves QML-source modules (QtQuick.Controls
# & styles are QML-based, unlike the compiled QtQuick core) from the qml import
# tree under assets:/qml plus their plugin .so in jniLibs. Copy the kit's whole
# qml tree deterministically so the Material UI modules import at runtime.
if (Test-Path "$KitRoot\qml") {
    New-Item -ItemType Directory -Force -Path (Join-Path $ApkDir "assets\qml") | Out-Null
    Copy-Item (Join-Path $KitRoot "qml\*") (Join-Path $ApkDir "assets\qml\") -Recurse -Force
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
androidBuildToolsVersion=35.0.0
androidCompileSdkVersion=android-34
androidNdkVersion=23.2.8568313
buildDir=build
qt5AndroidDir=$qtAndroidDir
qtAndroidDir=$qtAndroidDir
qtMinSdkVersion=23
qtTargetAbiList=arm64-v8a
qtTargetSdkVersion=33
"@ | Set-Content $gpPath -NoNewline
} else {
    $gp = Get-Content $gpPath -Raw
    $gp = $gp -replace 'androidCompileSdkVersion=android-\d+', 'androidCompileSdkVersion=android-34'
    $gp = $gp -replace 'androidBuildToolsVersion=[\d.]+', 'androidBuildToolsVersion=35.0.0'
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
        release { minifyEnabled false }
    }

    defaultConfig {
        resConfig "en"
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
        $localDebug = Join-Path $env:USERPROFILE ".android\debug.keystore"
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
            Set-Content $bgPath (New-BaseBuildGradle) -NoNewline
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
        if (-not (Test-Path $bgPath)) {
            # Fresh carve-subset tree without androiddeployqt's build.gradle.
            Set-Content $bgPath (New-BaseBuildGradle) -NoNewline
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
        Set-Content $bgPath (New-BaseBuildGradle) -NoNewline
        Write-Host "Wrote complete build.gradle for $Configuration (fresh tree)." -ForegroundColor Yellow
    }
}

Push-Location $ApkDir
try {
    # Prefer the wrapper scripts (androiddeployqt stages gradlew.bat + wrapper
    # jar on a full kit); on the carve-subset fresh tree neither exists, so use
    # the gradle distribution from AURELEX_GRADLE_HOME (CI installs it) or the
    # system gradle.
    if (Test-Path ".\gradlew.bat") {
        & ".\gradlew.bat" --no-daemon $gradleTask
    } elseif ($env:AURELEX_GRADLE_HOME -and (Test-Path (Join-Path $env:AURELEX_GRADLE_HOME "bin\gradle.bat"))) {
        & (Join-Path $env:AURELEX_GRADLE_HOME "bin\gradle.bat") --no-daemon $gradleTask
    } elseif ($env:GRADLE_HOME -and (Test-Path (Join-Path $env:GRADLE_HOME "bin\gradle.bat"))) {
        & (Join-Path $env:GRADLE_HOME "bin\gradle.bat") --no-daemon $gradleTask
    } else {
        $wt = Get-Command "gradle.bat" -ErrorAction SilentlyContinue
        if ($wt) {
            & $wt.Source --no-daemon $gradleTask
        } else {
            throw "no gradlew.bat, no gradle-wrapper.jar, no gradle on PATH in $ApkDir — cannot run gradle"
        }
    }
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
    & $adb shell "am start -n aurelex.android/.AurelexActivity"
    Write-Host "Installed + launched." -ForegroundColor Green
}
