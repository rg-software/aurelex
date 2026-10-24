<#
.SYNOPSIS
    Back up every Aurelex cache folder into a single archive.

.DESCRIPTION
    Launcher for scripts/backup-cache.py (same arguments): traverses every
    ~/.cache/aurelex-* directory and writes ONE archive plus a SHA-256
    sidecar, so there is a single backup unit to store. See
    docs/builds/cache.md ("Backup") and the script's --help.

.EXAMPLE
    pwsh -File scripts/backup-cache.ps1
    pwsh -File scripts/backup-cache.ps1 -Out D:\backups\aurelex-cache.tar -Compress
#>
[CmdletBinding()]
param(
    [string]$Out = "",
    [string[]]$Roots = @(),
    [switch]$Compress
)

$ErrorActionPreference = "Stop"

$args = @()
if ($Out -ne "") { $args += "--out"; $args += $Out }
if ($Roots -ne $null -and $Roots.Count -gt 0) { $args += "--roots"; $args += $Roots }
if ($Compress) { $args += "--compress" }
& python (Join-Path $PSScriptRoot "backup-cache.py") @args
if ($LASTEXITCODE -ne 0) { throw "backup-cache.py failed with exit $LASTEXITCODE" }
