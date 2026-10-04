# Convert device screenshots into Play-ready phone screenshots.
#
#   scripts/make-store-screenshots.ps1 -Captures <dir>      # e.g. a temp dir of screencaps
#   scripts/make-store-screenshots.ps1 -Captures <dir> -Check
#
# Input: PNG captures from `adb exec-out screencap -p`, named `NN-<slug>.png`.
# The numeric prefix is the Play gallery order (hero first), so re-ordering the
# gallery means renaming the captures, not editing this script.
#
# Output: app/android/store-listing/screenshots/NN-<slug>.png at 1080x1920.
#
# Why the numbers: Play wants phone screenshots between 320 and 3840 px per
# side, at 16:9 or 9:16. A modern phone is 1080x2400 (20:9), which Play rejects,
# so the capture is scaled by exactly 0.8 to 864x1920 (9:16, no distortion) and
# centred on a 1080x1920 canvas. The canvas gradient matches the Play feature
# graphic (see make-app-icons.ps1), so the gallery and the feature graphic share
# a background.
#
# The rounded corners and soft shadow are presentation, not deception: the
# screenshot is the real device screen, unmodified, at 80% scale.

param(
    [Parameter(Mandatory)]
    [string]$Captures,

    [string]$Dest,

    # Gradient behind the device screen; keep in step with make-app-icons.ps1.
    [string]$GradientFrom = "#FBF4E4",
    [string]$GradientTo   = "#FFFFFF",

    # Output the plan (and the resulting gallery order) without writing files.
    [switch]$Check
)

$ErrorActionPreference = "Stop"

$RepoRoot = Split-Path -Parent $PSScriptRoot
if (-not $Dest) { $Dest = Join-Path $RepoRoot "app/android/store-listing/screenshots" }

$magickCmd = Get-Command magick -ErrorAction SilentlyContinue
if (-not $magickCmd) { throw "ImageMagick 7 ('magick') not found on PATH" }
$magick = $magickCmd.Source

if (-not (Test-Path -LiteralPath $Captures)) { throw "captures directory not found: $Captures" }

# Sorted by name so the NN- prefix defines the gallery order. Note the distinct
# variable: $Captures is typed [string], so assigning the file array back to it
# would coerce the array to one string.
$shots = @(Get-ChildItem -LiteralPath $Captures -Filter *.png -File | Sort-Object Name)
if ($shots.Count -eq 0) { throw "no PNG captures in $Captures" }

Write-Output "Play gallery order ($($shots.Count) screenshots):"
foreach ($s in $shots) { Write-Output "  $($s.Name)" }

if ($Check) {
    Write-Output "`n-Check: nothing written."
    return
}

$tmp = Join-Path ([System.IO.Path]::GetTempPath()) ("aurelex-shots-" + [guid]::NewGuid().ToString("N"))
New-Item -ItemType Directory -Force -Path $tmp | Out-Null

try {
    $canvas = Join-Path $tmp "canvas.png"
    $shadow = Join-Path $tmp "shadow.png"
    $body   = Join-Path $tmp "body.png"
    $mask   = Join-Path $tmp "mask.png"

    # Soft shadow: blurred rounded rectangle, warm near-black at 30%.
    & $magick -size 920x1980 xc:none -fill "rgba(90,74,40,0.30)" `
        -draw "roundrectangle 28,14,891,1965,52,52" -blur 0x16 $shadow
    # Rounded-corner mask for the screen itself.
    & $magick -size 864x1920 xc:black -fill white `
        -draw "roundrectangle 0,0,863,1919,44,44" $mask
    & $magick -size 1080x1920 "gradient:$GradientFrom-$GradientTo" $canvas

    New-Item -ItemType Directory -Force -Path $Dest | Out-Null

    foreach ($s in $shots) {
        $out = Join-Path $Dest $s.Name

        & $magick $s.FullName -resize 864x1920 $body
        if ($LASTEXITCODE -ne 0) { throw "failed to resize $($s.Name)" }
        & $magick $body $mask -alpha off -compose CopyOpacity -composite $body
        # -strip drops the timestamp/metadata chunks ImageMagick would otherwise
        # write, so re-running this script on the same capture is byte-identical
        # and a diff of the committed assets shows a real visual change only.
        & $magick $canvas $shadow -geometry +80+0 -composite $body -geometry +108+0 -composite -strip $out
        if ($LASTEXITCODE -ne 0) { throw "failed to write $out" }

        $dims = (& $magick identify -format "%w %h" $out) -split "\s+"
        $kb   = [int]((Get-Item $out).Length / 1KB)
        $ok   = if ($dims[0] -eq 1080 -and $dims[1] -eq 1920) { "ok" } else { "WRONG SIZE" }
        Write-Output ("  {0,-34} {1}x{2}  {3,4} KB  {4}" -f $s.Name, $dims[0], $dims[1], $kb, $ok)
    }

    # Prune anything this run did not write. Re-ordering the gallery means
    # renaming captures; without this, the old NN- names survive as
    # byte-identical orphans, which is how a duplicate ends up committed and then
    # uploaded as an extra gallery entry.
    $keep    = @($shots | ForEach-Object { $_.Name })
    $orphans = @(Get-ChildItem -LiteralPath $Dest -Filter *.png -File |
                 Where-Object { $_.Name -notin $keep })
    foreach ($o in $orphans) {
        Remove-Item -LiteralPath $o.FullName -Force
        Write-Output "  removed stale output: $($o.Name)"
    }
}
finally {
    Remove-Item -LiteralPath $tmp -Recurse -Force -ErrorAction SilentlyContinue
}