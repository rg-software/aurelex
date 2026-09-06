# Extract and compile the app's Qt translation catalogs.
#
#   scripts/update-translations.ps1          # extract + compile
#   scripts/update-translations.ps1 -NoCompile  # extract only (.ts)
#
# Runs the host kit's lupdate.exe (app/main.qml + C++ sources) and lrelease.exe,
# honoring AURELEX_QT_BASE / AURELEX_QT_HOST like app/build.ps1. Different
# languages than the default ja/ru can be passed:
#
#   scripts/update-translations.ps1 -Languages @("ru")
#
# Catalogs live in app/i18n/aurelex.<lang>.ts (sources) and the compiled
# aurelex_<lang>.qm (embedded via app/i18n.qrc, loaded at startup by main.cpp).

param(
    [string[]]$Languages = @("ru", "ja"),
    [switch]$NoCompile
)

$ErrorActionPreference = "Stop"

$RepoRoot = Split-Path -Parent $PSScriptRoot
$AppDir   = Join-Path $RepoRoot "app"
$I18nDir  = Join-Path $AppDir "i18n"

# Local defaults assume the Unity-2025 install layout; CI overrides via env.
$QtBase = if ($env:AURELEX_QT_BASE) { $env:AURELEX_QT_BASE } else { "C:\Qt\6.6.3" }
$QtHost = if ($env:AURELEX_QT_HOST) { $env:AURELEX_QT_HOST } else { "$QtBase\msvc2019_64" }

$Lupdate  = Join-Path $QtHost "bin\lupdate.exe"
$Lrelease = Join-Path $QtHost "bin\lrelease.exe"

if (-not (Test-Path -LiteralPath $Lupdate)) {
    throw "lupdate not found at $Lupdate (set AURELEX_QT_BASE/AURELEX_QT_HOST)"
}
if (-not $NoCompile -and -not (Test-Path -LiteralPath $Lrelease)) {
    throw "lrelease not found at $Lrelease (set AURELEX_QT_BASE/AURELEX_QT_HOST)"
}

New-Item -ItemType Directory -Force -Path $I18nDir | Out-Null

# QML + C++ sources scanned for qsTr()/tr().
$Sources = @(
    (Join-Path $AppDir "main.qml"),
    (Join-Path $AppDir "main.cpp"),
    (Join-Path $AppDir "EngineController.cpp"),
    (Join-Path $AppDir "EngineController.hpp"),
    (Join-Path $AppDir "ArticleServer.cpp"),
    (Join-Path $AppDir "ArticleServer.hpp")
) | Where-Object { Test-Path -LiteralPath $_ }

$TsFiles = $Languages | ForEach-Object { Join-Path $I18nDir "aurelex.$_.ts" }

# -no-obsolete drops strings no longer present in the sources.
& $Lupdate @Sources -ts @TsFiles -no-obsolete
if ($LASTEXITCODE -ne 0) {
    throw "lupdate failed with exit code $LASTEXITCODE"
}

if (-not $NoCompile) {
    foreach ($Language in $Languages) {
        $TsFile = Join-Path $I18nDir "aurelex.$Language.ts"
        $QmFile = Join-Path $I18nDir "aurelex_$Language.qm"
        & $Lrelease $TsFile -qm $QmFile
        if ($LASTEXITCODE -ne 0) {
            throw "lrelease failed for $TsFile with exit code $LASTEXITCODE"
        }
    }
}

Write-Host "Translation catalogs updated: $($TsFiles -join ', ')"
if (-not $NoCompile) {
    $QmFiles = $Languages | ForEach-Object { Join-Path $I18nDir "aurelex_$_.qm" }
    Write-Host "Compiled: $($QmFiles -join ', ')"
}