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
    [switch]$SkipConfigure,
    [switch]$Install
)

$ErrorActionPreference = "Stop"

$RepoRoot   = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
$ExpDir     = $PSScriptRoot
$BuildDir   = Join-Path $RepoRoot "build-qtquick"
$ApkDir     = Join-Path $BuildDir "apk"

$QtBase     = "C:\Qt\6.6.3"
$QtHost     = "C:\Qt\6.6.3\msvc2019_64"
$VcpkgBase  = "C:\vcpkg"
$NdkRoot    = "C:\Program Files (x86)\Android\AndroidNDK\android-ndk-r23c"
$RealSdk    = "C:\Program Files (x86)\Android\android-sdk"
$UnitySdk   = "C:\Program Files\Unity\Hub\Editor\6000.0.62f1\Editor\Data\PlaybackEngines\AndroidPlayer\SDK"
$Jdk17      = "C:\Program Files\Unity\Hub\Editor\6000.0.62f1\Editor\Data\PlaybackEngines\AndroidPlayer\OpenJDK"
$CmakeExe   = "$UnitySdk\cmake\3.22.1\bin\cmake.exe"
$DeployQt   = "$QtHost\bin\androiddeployqt.exe"

if (-not (Test-Path $CmakeExe)) { throw "cmake not found at $CmakeExe" }
if (-not (Test-Path $DeployQt)) { throw "androiddeployqt not found at $DeployQt" }

$env:JAVA_HOME         = $Jdk17
$env:ANDROID_SDK_ROOT  = $RealSdk
$env:ANDROID_HOME      = $RealSdk
$env:ANDROID_NDK_ROOT  = $NdkRoot

Write-Host "== [1/5] cmake configure ($Abi) ==" -ForegroundColor Cyan
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
if ($LASTEXITCODE -ne 0) { throw "androiddeployqt failed" }

Write-Host "== [5/5] gradle overrides + assembleDebug ==" -ForegroundColor Cyan
# androiddeployqt regenerates these two files; re-apply the working overrides.
Set-Content (Join-Path $ApkDir "local.properties") "sdk.dir=C\:/Program Files (x86)/Android/android-sdk" -NoNewline
$gpPath = Join-Path $ApkDir "gradle.properties"
$gp = Get-Content $gpPath -Raw
$gp = $gp -replace 'androidCompileSdkVersion=android-\d+', 'androidCompileSdkVersion=android-34'
$gp = $gp -replace 'androidBuildToolsVersion=[\d.]+', 'androidBuildToolsVersion=35.0.0'
Set-Content $gpPath $gp -NoNewline
# settings.gradle must scope this build away from the repo's settings.gradle.kts
if (-not (Test-Path (Join-Path $ApkDir "settings.gradle"))) {
    Set-Content (Join-Path $ApkDir "settings.gradle") 'rootProject.name = "aurelex-exp"'
}

Push-Location $ApkDir
try {
    & ".\gradlew.bat" --no-daemon assembleDebug
    if ($LASTEXITCODE -ne 0) { throw "gradle assembleDebug failed" }
} finally {
    Pop-Location
}

$apk = Get-ChildItem "$ApkDir\build\outputs\apk\debug" -Filter "*.apk" | Select-Object -First 1
if (-not $apk) { throw "APK not produced" }
Write-Host "== DONE: $($apk.FullName) ($([math]::Round($apk.Length/1MB,1)) MB) ==" -ForegroundColor Green

if ($Install) {
    $adb = "$RealSdk\platform-tools\adb.exe"
    & $adb install -r $apk.FullName
    & $adb shell "am start -n com.aurelex.experiment/org.qtproject.qt.android.bindings.QtActivity"
    Write-Host "Installed + launched." -ForegroundColor Green
}