param()
# Apply the Aurelex deviation patches to the engine/ submodule working tree.
# Contract per AGENTS.md: never edit engine/ in place permanently - each build
# (local or CI) starts from a clean submodule and applies patches/ on top.
$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $PSScriptRoot
$engine = Join-Path $root "engine"

$patches = Get-ChildItem (Join-Path $root "patches") -Filter "*.patch" -ErrorAction SilentlyContinue
if (-not $patches) {
    Write-Output "no patches to apply"
    exit 0
}

foreach ($patch in $patches) {
    Write-Output "applying $($patch.Name)"
    Push-Location $engine
    try {
        git apply --check (Join-Path $root "patches\$($patch.Name)")
        git apply (Join-Path $root "patches\$($patch.Name)")
    }
    finally {
        Pop-Location
    }
}

Write-Output "patches applied to engine/ (working tree only; not committed)"