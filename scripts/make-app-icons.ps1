# Generate the Android launcher icons and the Google Play store icon from the
# single master artwork.
#
#   scripts/make-app-icons.ps1
#
# The master is app/android/icon/aurelex-icon-1024.png (gold "Au" + open book
# on a white background). The script knocks the white background out to a
# transparent foreground, then emits:
#
#   * app/android/res/drawable-<dpi>/ic_launcher_foreground.png
#       adaptive-icon foreground (transparent), logo inside the 66/108 safe zone
#   * app/android/res/mipmap-<dpi>/ic_launcher.png
#       legacy (pre-API-26) launcher icons, logo on white
#   * app/android/icon/play-store-icon-512.png
#       Google Play listing icon, 512x512, flattened on white
#
# Requires ImageMagick 7 (`magick`) on PATH. Re-run after replacing the master.

param(
    [string]$Source,
    [double]$SafeZone = 66.0 / 108.0,
    [double]$LegacyFill = 0.78,
    [double]$PlayFill = 0.72,
    [string]$Background = "#FFFFFF"
)

$ErrorActionPreference = "Stop"

$RepoRoot = Split-Path -Parent $PSScriptRoot
$ResDir   = Join-Path $RepoRoot "app/android/res"
$IconDir  = Join-Path $RepoRoot "app/android/icon"
if (-not $Source) { $Source = Join-Path $IconDir "aurelex-icon-1024.png" }

$magickCmd = Get-Command magick -ErrorAction SilentlyContinue
if (-not $magickCmd) { throw "ImageMagick 7 ('magick') not found on PATH" }
$magick = $magickCmd.Source
if (-not (Test-Path -LiteralPath $Source)) { throw "source icon not found: $Source" }

$tmp = Join-Path ([System.IO.Path]::GetTempPath()) ("aurelex-icons-" + [guid]::NewGuid().ToString("N"))
New-Item -ItemType Directory -Force -Path $tmp | Out-Null

# Adaptive foreground densities (canvas = 108dp) and legacy icon sizes.
$foregroundSizes = [ordered]@{ mdpi = 108; hdpi = 162; xhdpi = 216; xxhdpi = 324; xxxhdpi = 432 }
$legacySizes     = [ordered]@{ mdpi = 48;  hdpi = 72;  xhdpi = 96;  xxhdpi = 144; xxxhdpi = 192 }

function New-Icon {
    param(
        [int]$Canvas,
        [int]$ContentLong,
        [string]$Dest,
        [string]$Background   # $null => keep transparency
    )
    $factor = $ContentLong / $script:LogoLong
    $w = [Math]::Max(1, [int][Math]::Round($script:LogoW * $factor))
    $h = [Math]::Max(1, [int][Math]::Round($script:LogoH * $factor))
    New-Item -ItemType Directory -Force -Path (Split-Path -Parent $Dest) | Out-Null
    if ($Background) {
        & $magick $script:Logo -resize "${w}x${h}" -background $Background -gravity center `
            -extent "${Canvas}x${Canvas}" -alpha remove -alpha off $Dest
    }
    else {
        & $magick $script:Logo -resize "${w}x${h}" -background none -gravity center `
            -extent "${Canvas}x${Canvas}" $Dest
    }
    if ($LASTEXITCODE -ne 0) { throw "failed to write $Dest" }
}

try {
    # Knock the (near-)white background out to transparency. Flood-filling from
    # a corner keeps the gold gradient and anti-aliased edges; the follow-up
    # -opaque pass clears the enclosed counter of the "A".
    $script:Logo = Join-Path $tmp "logo.png"
    & $magick $Source -alpha set -fuzz 15% -fill none -draw "alpha 0,0 floodfill" `
        -fuzz 12% -fill none -opaque white -trim +repage $script:Logo
    if ($LASTEXITCODE -ne 0) { throw "failed to extract the logo from $Source" }

    $dims = (& $magick identify -format "%w %h" $script:Logo) -split '\s+'
    $script:LogoW = [int]$dims[0]
    $script:LogoH = [int]$dims[1]
    $script:LogoLong = [Math]::Max($script:LogoW, $script:LogoH)
    Write-Output "master logo: $($script:LogoW)x$($script:LogoH) (trimmed from $Source)"

    # Legacy vector foreground is replaced by the generated PNGs.
    $oldVector = Join-Path $ResDir "drawable/ic_launcher_foreground.xml"
    if (Test-Path -LiteralPath $oldVector) { Remove-Item -LiteralPath $oldVector -Force }

    foreach ($dpi in $foregroundSizes.Keys) {
        $canvas = $foregroundSizes[$dpi]
        $dest = Join-Path $ResDir "drawable-$dpi/ic_launcher_foreground.png"
        New-Icon -Canvas $canvas -ContentLong ([int][Math]::Round($SafeZone * $canvas)) -Dest $dest
        Write-Output "  drawable-$dpi/ic_launcher_foreground.png  ($canvas x $canvas)"
    }

    foreach ($dpi in $legacySizes.Keys) {
        $size = $legacySizes[$dpi]
        $dest = Join-Path $ResDir "mipmap-$dpi/ic_launcher.png"
        New-Icon -Canvas $size -ContentLong ([int][Math]::Round($LegacyFill * $size)) -Dest $dest -Background $Background
        Write-Output "  mipmap-$dpi/ic_launcher.png  ($size x $size)"
    }

    $play = Join-Path $IconDir "play-store-icon-512.png"
    New-Icon -Canvas 512 -ContentLong ([int][Math]::Round($PlayFill * 512)) -Dest $play -Background $Background
    Write-Output "  icon/play-store-icon-512.png  (512 x 512)"
}
finally {
    Remove-Item -LiteralPath $tmp -Recurse -Force -ErrorAction SilentlyContinue
}

Write-Output "done. adaptive background color: $Background (app/android/res/values/colors.xml)"
