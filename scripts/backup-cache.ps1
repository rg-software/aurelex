<#
.SYNOPSIS
    Back up every Aurelex cache folder into a single archive.

.DESCRIPTION
    The builder caches live under several top-level directories
    (~/.cache/aurelex-kaikki, ~/.cache/aurelex-bilingual, ...), which is
    correct per the shared-cache convention but awkward to back up as
    several sync-library roots. This script traverses all of them and
    produces ONE archive file plus a SHA-256 sidecar, so there is a single
    backup unit to store.

    The big blobs (the bulk audio tar, the kaikki snapshots) are already
    compressed, so the default is a plain .tar (no recompression: minutes
    instead of an hour of CPU for ~zero bytes saved). Pass -Compress for a
    .tar.gz when the cache is small enough for gzip to matter.

    Restore is the inverse one-liner (see docs/builds/cache.md). Nothing is
    ever deleted or modified by this script.

.PARAMETER Out
    Archive path to write. Default:
    "$HOME/aurelex-cache-backup-<yyyy-MM-dd>.tar" (or .tar.gz with -Compress).

.PARAMETER Roots
    Cache roots to include. Default: every "$HOME/.cache/aurelex-*" directory
    that exists, so a future cache folder is picked up automatically.

.PARAMETER Compress
    Gzip the archive (slower, smaller). Default is store-only .tar.

.EXAMPLE
    pwsh -File scripts/backup-cache.ps1
    pwsh -File scripts/backup-cache.ps1 -Compress -Out D:\backups\aurelex-cache.tar.gz
#>
[CmdletBinding()]
param(
    [string]$Out = "",
    [string[]]$Roots = @(),
    [switch]$Compress
)

$ErrorActionPreference = "Stop"

$homeCache = Join-Path $HOME ".cache"
if (-not $Roots -or $Roots.Count -eq 0) {
    $Roots = Get-ChildItem -Directory -Path (Join-Path $homeCache "aurelex-*") `
        | ForEach-Object { $_.FullName }
}
if (-not $Roots -or $Roots.Count -eq 0) {
    throw "no Aurelex cache folders found under $homeCache"
}
foreach ($r in $Roots) {
    if (-not (Test-Path $r -PathType Container)) {
        throw "cache root does not exist: $r"
    }
}

if ([string]::IsNullOrEmpty($Out)) {
    $stamp = Get-Date -Format "yyyy-MM-dd"
    $ext = if ($Compress) { "tar.gz" } else { "tar" }
    $Out = Join-Path $HOME "aurelex-cache-backup-$stamp.$ext"
}

# Sizes first, so the run states what it is about to pack.
$total = 0
foreach ($r in $Roots) {
    $size = (Get-ChildItem -Recurse -Force -File -Path $r `
        | Measure-Object -Property Length -Sum).Sum
    if ($null -eq $size) { $size = 0 }
    $total += $size
    Write-Host ("  {0,-60} {1,12:N0} bytes" -f $r, $size)
}
Write-Host ("total: {0:N0} bytes in {1} root(s)" -f $total, $Roots.Count)

# One archive, paths stored relative to ~/.cache so a restore lands back
# where the builders look. bsdtar ships with Windows 10+.
$rel = $Roots | ForEach-Object {
    $u = $_.TrimEnd('\', '/')
    if ($u.StartsWith($homeCache, [StringComparison]::OrdinalIgnoreCase)) {
        $u.Substring($homeCache.Length).TrimStart('\', '/')
    } else {
        throw "cache root $u is outside $homeCache; pass explicit -Roots within one parent or back it up separately"
    }
}
$tarArgs = @("-cf", $Out, "-C", $homeCache) + $rel
if ($Compress) {
    # -z must precede -f for bsdtar/GNU tar alike.
    $tarArgs = @("-czf", $Out, "-C", $homeCache) + $rel
}
Write-Host "== writing $Out ==" -ForegroundColor Cyan
& tar $tarArgs
if ($LASTEXITCODE -ne 0) { throw "tar failed with exit $LASTEXITCODE" }

$hash = (Get-FileHash -Algorithm SHA256 -Path $Out).Hash.ToLowerInvariant()
Set-Content -Path "$Out.sha256" -Value "$hash  $(Split-Path $Out -Leaf)" -NoNewline
Write-Host "wrote $Out"
Write-Host "sha256: $hash"
