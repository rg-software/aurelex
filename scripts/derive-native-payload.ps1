<#
.SYNOPSIS
  Derive the set of native libraries a release artifact actually needs.

.DESCRIPTION
  The build used to stage the whole Qt kit: every *.so in <kit>/lib, every
  libqml_*.so under <kit>/qml, and every libplugins_*.so under <kit>/plugins.
  Measured on arm64-v8a that is 140 libraries / 86.32 MB packaged, of which
  96 libraries / 37.97 MB are never loaded. This script derives the reachable
  subset so app/build.ps1 can stage only that.

  The kept set is the transitive DT_NEEDED closure over an explicit root list.
  A pure closure is NOT sufficient -- two classes of library have no link edge
  and would be wrongly dropped:

    1. QML modules. QtQuick.Controls.Material is not linked; the QML engine
       finds it through a `plugin` line in its qmldir. Material's qmldir also
       says `import QtQuick.Controls.Basic auto`, so Basic's style plugin and
       impl are reachable only through that chain -- which is why this script
       follows `depends`/import lines in qmldir rather than trusting DT_NEEDED
       alone.

    2. Libraries loaded with no link edge at all. libcrypto_3.so / libssl_3.so
       are dlopen'd by Qt at TLS init (see AGENTS.md: Qt's Android TLS is the
       OpenSSL backend and dlopen()s the vendored libs, wired in through
       QT_ANDROID_EXTRA_LIBS). A pure closure reports them DEAD. Shipping
       without them reproduces the exact failure the vendoring exists to
       prevent: a build that looks healthy and only fails when the remote
       catalog is opened. libc++_shared.so is injected the same way.

  The QML module roots are read from the app's own QML imports, so adding an
  `import` to main.qml widens the payload automatically rather than requiring a
  hand edit here. Only the genuinely edge-less libraries are curated, and each
  carries its justification below.

.EXAMPLE
  pwsh -File scripts/derive-native-payload.ps1
  Prints kept/dropped with sizes. Reviewable in a commit.

.EXAMPLE
  pwsh -File scripts/derive-native-payload.ps1 -Mode List
  Prints just the kept library names, one per line, for build.ps1 to consume.

.EXAMPLE
  pwsh -File scripts/derive-native-payload.ps1 -Mode Json
  Emits {"keep":[...],"drop":[...]} for the release pipeline assertion.
#>
[CmdletBinding()]
param(
    [string]$Abi        = "arm64-v8a",
    [string]$QtBase     = $(if ($env:AURELEX_QT_BASE) { $env:AURELEX_QT_BASE } else { "C:\Qt\6.6.3" }),
    [string]$NdkRoot    = $(if ($env:AURELEX_NDK_ROOT) { $env:AURELEX_NDK_ROOT } else { "C:\Program Files (x86)\Android\AndroidNDK\android-ndk-r23c" }),
    [string]$AppLib,
    [string]$AppQml     = "app/main.qml",
    [ValidateSet("Derive", "List", "Json")]
    [string]$Mode       = "Derive"
)

$ErrorActionPreference = "Stop"
$RepoRoot = Split-Path -Parent $PSScriptRoot

if (-not $AppLib) { $AppLib = Join-Path $RepoRoot "build-qtquick/libaurelex_$Abi.so" }

# ---------------------------------------------------------------- toolchain --

function Get-Readelf {
    $prebuilt = if ($IsWindows) { "windows-x86_64" } else { "linux-x86_64" }
    $exe = Join-Path $NdkRoot "toolchains/llvm/prebuilt/$prebuilt/bin/llvm-readelf.exe"
    if (-not (Test-Path $exe)) { $exe = Join-Path $NdkRoot "toolchains/llvm/prebuilt/$prebuilt/bin/llvm-readelf" }
    if (-not (Test-Path $exe)) { throw "llvm-readelf not found under $NdkRoot -- the NDK is required (set AURELEX_NDK_ROOT)" }
    $exe
}

# <name> -> absolute path, for every library the kit offers.
function Get-KitIndex {
    # Qt names the kit dir android_arm64_v8a (underscore), not the ABI name.
    $kitRoot = Join-Path $QtBase ("android_" + ($Abi -replace '-', '_'))
    if (-not (Test-Path $kitRoot)) { throw "Qt kit not found: $kitRoot (set AURELEX_QT_BASE)" }
    $index = @{}
    Get-ChildItem -LiteralPath (Join-Path $kitRoot "lib")     -Filter "*.so"           -File -EA SilentlyContinue |
        ForEach-Object { $index[$_.Name] = $_.FullName }
    Get-ChildItem -LiteralPath (Join-Path $kitRoot "qml")     -Recurse -Filter "libqml_*.so"     -File -EA SilentlyContinue |
        ForEach-Object { $index[$_.Name] = $_.FullName }
    Get-ChildItem -LiteralPath (Join-Path $kitRoot "plugins") -Recurse -Filter "libplugins_*.so" -File -EA SilentlyContinue |
        ForEach-Object { $index[$_.Name] = $_.FullName }
    $index
}

function Get-DTNeeded {
    param([string]$Path, [string]$Readelf)
    # Filter on NEEDED: `readelf -d` also prints SONAME in brackets, and a
    # library's SONAME is its own file name -- an unfiltered parse therefore
    # makes every library look like it links itself.
    $out = @()
    foreach ($line in (& $Readelf -d $Path 2>$null)) {
        if ($line -match '\(NEEDED\)' -and $line -match '\[(.+?)\]') { $out += $Matches[1] }
    }
    $out
}

# ------------------------------------------------------- QML import module --

# Map a QML module name to the kit directory that holds it. Qt's layout puts
# QtQuick/Controls/Material under qml/QtQuick/Controls/Material, so the module
# name is the path.
function Get-ModuleDir {
    param([string]$KitRoot, [string]$Module)
    Join-Path $KitRoot ("qml/" + ($Module -replace '\.', '/'))
}

# Follow a module's own imports: the `depends`/`import` lines in its qmldir AND
# the `import` statements in its .qml sources. The second source is not optional:
# QtQuick.Controls.Material/ApplicationWindow.qml does `import QtQuick.Window`,
# and QtQuick.Window's qmldir never mentions it -- so a qmldir-only closure
# drops that module and the app dies at startup with
# `Type ApplicationWindow unavailable` /
# `module "QtQuick.Window" is not installed`.
function Get-ModuleImports {
    param([string]$Dir)
    $mods = @()
    $q = Join-Path $Dir "qmldir"
    if (Test-Path $q) {
        foreach ($line in (Get-Content $q -EA SilentlyContinue)) {
            if ($line -match '^\s*depends\s+([A-Za-z][\w.]*)')      { $mods += $Matches[1]; continue }
            if ($line -match '^\s*import\s+([A-Za-z][\w.]*)')       { $mods += $Matches[1]; continue }
        }
    }
    # .qml sources in this module directory only -- a nested module directory
    # (Controls/Basic, Controls/Material) is its own node in the closure.
    foreach ($qml in @(Get-ChildItem -LiteralPath $Dir -Filter "*.qml" -File -EA SilentlyContinue)) {
        foreach ($line in (Get-Content $qml.FullName -EA SilentlyContinue)) {
            if ($line -match '^\s*import\s+([A-Za-z][\w.]*)') { $mods += $Matches[1] }
        }
    }
    $mods
}

# ------------------------------------------------ curated edge-less roots ----

# Every entry here is a library with no DT_NEEDED path from the app. Keep the
# list short and keep each entry's justification -- if one of these ever grows a
# real link edge, delete it from this list rather than leaving a stale entry.
$CURATED_ROOTS = @(
    # dlopen'd by Qt at TLS init (AGENTS.md: Qt's Android TLS is the OpenSSL
    # backend and dlopen()s the vendored libs via QT_ANDROID_EXTRA_LIBS). No
    # link edge exists, so a pure closure calls these dead -- and shipping
    # without them fails only when the remote catalog is opened.
    'libcrypto_3.so'
    'libssl_3.so'
    # Injected by the build, not linked: build.ps1 copies it from the NDK.
    'libc++_shared.so'
)

# Run-time plugins the app needs but cannot reach by DT_NEEDED: the platform
# plugin, the WebView bridge, the TLS backends, and the image formats /
# SVG icon engine. The image formats are deliberate: dictionaries embed JPEG,
# GIF, ICO and SVG artwork that the article path renders through QImage, so
# dropping them trades a working feature for ~0.87 MB.
$PLUGIN_ROOTS = @(
    'libplugins_platforms_qtforandroid'
    'libplugins_webview_qtwebview_android'
    'libplugins_tls_qopensslbackend'
    'libplugins_tls_qcertonlybackend'
    'libplugins_networkinformation_qandroidnetworkinformation'
    'libplugins_imageformats_qsvg'
    'libplugins_imageformats_qgif'
    'libplugins_imageformats_qico'
    'libplugins_imageformats_qjpeg'
    'libplugins_iconengines_qsvgicon'
)

# ------------------------------------------------------------------ derive --

$Readelf = Get-Readelf
$KitRoot = Join-Path $QtBase ("android_" + ($Abi -replace '-', '_'))
$index   = Get-KitIndex

if (-not (Test-Path $AppLib)) {
    throw "app library not found: $AppLib -- build it first (cmake --build <dir> --target aurelex)"
}

# The app library is the root of the link closure but is not a kit library, so
# add it to the index under its own name.
$index[(Split-Path $AppLib -Leaf)] = $AppLib

# Neither are the vendored/injected libraries, which build.ps1 stages from
# outside the kit: the OpenSSL pair from app/openssl/<abi>/ (tracked in git, see
# AGENTS.md) and libc++_shared.so from the NDK. Without these in the candidate
# set they are silently "dropped" -- and they have no link edge, so nothing else
# would put them back.
$vendoredDir = Join-Path $RepoRoot "app/openssl/$Abi"
Get-ChildItem -LiteralPath $vendoredDir -Filter "*.so" -File -EA SilentlyContinue |
    ForEach-Object { $index[$_.Name] = $_.FullName }

$cppShared = Join-Path $NdkRoot "sources/cxx-stl/llvm-libc++/libs/$Abi/libc++_shared.so"
if (-not (Test-Path $cppShared)) {
    $prebuilt = if ($IsWindows) { "windows-x86_64" } else { "linux-x86_64" }
    $cppShared = Join-Path $NdkRoot "toolchains/llvm/prebuilt/$prebuilt/sysroot/usr/lib/$Abi/libc++_shared.so"
}
if (Test-Path $cppShared) {
    $index["libc++_shared.so"] = $cppShared
} else {
    Write-Warning "libc++_shared.so not found under the NDK -- it will not be kept"
}

# --- assertion 1 (design Context): libQt6Widgets must NOT be kept.
# It is reachable only from libplugins_styles_qandroidstyle, a widget-based
# Controls style plugin that a Qt Quick app never loads. It is NOT in
# $PLUGIN_ROOTS, so the closure must leave it out. If a future kit ever links it
# from something we do keep, this assertion fires and the derivation's answer
# has legitimately changed -- investigate before editing the list.
$widgets = "libQt6Widgets_$Abi.so"
if ($index.ContainsKey($widgets)) {
    foreach ($p in $PLUGIN_ROOTS) {
        if (-not $index.ContainsKey("$p`_$Abi.so")) { continue }
        $need = Get-DTNeeded $index["$p`_$Abi.so"] $Readelf
        if ($need -contains $widgets) {
            Write-Warning "ASSERTION CHANGED: $p links $widgets, which is in the kit. The qandroidstyle widget plugin is now reachable -- review PLUGIN_ROOTS."
        }
    }
}

# --- assertion 2 (design Context): libQt6ShaderTools must NOT be kept.
# No library in the staged set has it in DT_NEEDED (checked across the whole
# kit), and no app QML uses ShaderEffect. If this ever fires, a kit change made
# it reachable and it should stay.
$shader = "libQt6ShaderTools_$Abi.so"
if ($index.ContainsKey($shader)) {
    foreach ($k in $index.Keys) {
        if ((Get-DTNeeded $index[$k] $Readelf) -contains $shader) {
            Write-Warning "ASSERTION CHANGED: $k links $shader. Something now needs ShaderTools -- review whether it should be packaged."
        }
    }
}

# QML module roots, read from the app's own imports and closed transitively over
# both qmldir declarations and .qml `import` statements (see
# Get-ModuleImports). A module enters the closure because the app imports it, or
# because a module already in the closure does.
$qmlFile = Join-Path $RepoRoot $AppQml
if (-not (Test-Path $qmlFile)) { throw "app QML not found: $qmlFile" }

$modules = New-Object System.Collections.Generic.List[string]
$queue2  = New-Object System.Collections.Queue
foreach ($line in (Get-Content $qmlFile)) {
    if ($line -match '^\s*import\s+([A-Za-z][\w.]*)') { [void]$queue2.Enqueue($Matches[1]) }
}
while ($queue2.Count -gt 0) {
    $m = $queue2.Dequeue()
    if ($modules.Contains($m)) { continue }
    [void]$modules.Add($m)
    $dir = Get-ModuleDir $KitRoot $m
    if (-not (Test-Path $dir)) { continue }   # app-local module, not the kit's
    foreach ($dep in (Get-ModuleImports $dir)) {
        if (-not $modules.Contains($dep)) { [void]$queue2.Enqueue($dep) }
    }
}

$roots = New-Object System.Collections.Generic.List[string]
$roots.Add((Split-Path $AppLib -Leaf))                       # link closure root
foreach ($m in $modules) {                                   # QML modules
    $dir = Get-ModuleDir $KitRoot $m
    if (-not (Test-Path $dir)) { Write-Warning "no kit module dir for '$m'"; continue }
    Get-ChildItem -LiteralPath $dir -Filter "libqml_*.so" -File -EA SilentlyContinue |
        ForEach-Object { $roots.Add($_.Name) }
}
foreach ($p in $PLUGIN_ROOTS)   { $roots.Add("$p`_$Abi.so") }   # run-time plugins
foreach ($c in $CURATED_ROOTS)  { $roots.Add($c) }                # dlopen'd / injected

# Walk the closure.
$seen = @{}
$queue = New-Object System.Collections.Queue
foreach ($r in $roots) { if ($index.ContainsKey($r)) { $queue.Enqueue($r) } }
while ($queue.Count -gt 0) {
    $n = $queue.Dequeue()
    if ($seen.ContainsKey($n)) { continue }
    $seen[$n] = $true
    if (-not $index.ContainsKey($n)) { continue }
    foreach ($d in (Get-DTNeeded $index[$n] $Readelf)) {
        if ($index.ContainsKey($d) -and -not $seen.ContainsKey($d)) { $queue.Enqueue($d) }
    }
}

$keep = @(); $drop = @(); $kBytes = 0L; $dBytes = 0L
foreach ($k in ($index.Keys | Sort-Object)) {
    $len = (Get-Item -LiteralPath $index[$k]).Length
    if ($seen.ContainsKey($k)) { $keep += $k; $kBytes += $len } else { $drop += $k; $dBytes += $len }
}

switch ($Mode) {
    "List" { $keep | ForEach-Object { $_ }; return }
    "Json" {
        [pscustomobject]@{ abi = $Abi; keep = $keep; drop = $drop } |
            ConvertTo-Json -Depth 3 -Compress
        return
    }
}

"MOST RECENT QML imports read from $AppQml : $($modules -join ', ')"
""
"candidate (kit + app): {0,4} libs {1,8:N2} MB" -f $index.Count, ((($index.Keys | ForEach-Object { (Get-Item -LiteralPath $index[$_]).Length }) | Measure-Object -Sum).Sum/1MB)
"KEEP    (reachable):  {0,4} libs {1,8:N2} MB" -f $keep.Count, ($kBytes/1MB)
"DROP    (dead):       {0,4} libs {1,8:N2} MB" -f $drop.Count, ($dBytes/1MB)
""
"curated roots kept (no link edge -- verify these stay):"
foreach ($c in $CURATED_ROOTS) {
    "    {0,-24} {1}" -f $c, $(if ($keep -contains $c) { "KEPT" } else { "*** DROPPED ***" })
}
""
"largest dropped:"
$drop | Sort-Object { -(Get-Item -LiteralPath $index[$_]).Length } | Select-Object -First 20 |
    ForEach-Object { "    {0,7:N2} MB  {1}" -f ((Get-Item -LiteralPath $index[$_]).Length/1MB), $_ }