# Generate the Android launcher icons and the Google Play assets from the
# single master artwork.
#
#   scripts/make-app-icons.ps1                    # launcher + Play icon
#   scripts/make-app-icons.ps1 -FeatureGraphic    # ... plus the feature graphic
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
#   * app/android/icon/play-feature-graphic-1024x500.png   (with -FeatureGraphic)
#       Google Play feature graphic: gradient background, mark + wordmark + tagline
#
# Requires ImageMagick 7 (`magick`) on PATH. Re-run after replacing the master.

param(
    [string]$Source,
    [double]$SafeZone = 66.0 / 108.0,
    [double]$LegacyFill = 0.78,
    [double]$PlayFill = 0.72,
    [string]$Background = "#FFFFFF",
    [switch]$FeatureGraphic,
    [string]$FeatureFont = "Montserrat-Regular",
    [string]$FeatureTitle = "Aurelex",
    [string]$FeatureTagline1 = "Offline dictionaries,",
    [string]$FeatureTagline2 = "beautifully fast"
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

function New-FeatureGraphic {
    param([string]$Dest)
    # Capability strip uses an ASCII-safe middot separator so the script is
    # encoding-independent.
    $sep  = " " + [char]0x00B7 + " "
    $cap1 = @("MDX", "DSL", "StarDict") -join $sep
    $cap2 = @("Full-text search", "Audio") -join $sep
    $cmd = @(
        "-size", "1024x500", "-define", "gradient:angle=115", "gradient:#F6ECD0-#FFFFFF",
        "(", $script:Logo, "-resize", "x230", ")",
        "-gravity", "West", "-geometry", "+70+0", "-composite",
        "-gravity", "NorthWest",
        "-font", $FeatureFont, "-fill", "#2C2820", "-pointsize", "120", "-annotate", "+470+100", $FeatureTitle,
        "-fill", "#6E6552", "-pointsize", "34", "-annotate", "+476+270", $FeatureTagline1,
        "-annotate", "+476+316", $FeatureTagline2,
        "-fill", "#A9862B", "-pointsize", "26", "-annotate", "+476+384", $cap1,
        "-annotate", "+476+418", $cap2,
        "-alpha", "remove", "-alpha", "off", "-depth", "8",
        $Dest
    )
    New-Item -ItemType Directory -Force -Path (Split-Path -Parent $Dest) | Out-Null
    & $magick @cmd
    if ($LASTEXITCODE -ne 0) { throw "failed to write $Dest" }
}

try {
    # Knock the near-white background out to transparency. A global white key
    # (rather than a corner flood-fill) also clears enclosed areas such as the
    # counter of the "A", which matters whenever the art sits on a non-white
    # surface (the dark feature-graphic variant, themed icons).
    $script:Logo = Join-Path $tmp "logo.png"
    & $magick $Source -alpha set -fuzz 10% -transparent white -trim +repage $script:Logo
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

    if ($FeatureGraphic) {
        $feature = Join-Path $IconDir "play-feature-graphic-1024x500.png"
        New-FeatureGraphic -Dest $feature
        Write-Output "  icon/play-feature-graphic-1024x500.png  (1024 x 500)"
    }
}
finally {
    Remove-Item -LiteralPath $tmp -Recurse -Force -ErrorAction SilentlyContinue
}

Write-Output "done. adaptive background color: $Background (app/android/res/values/colors.xml)"
