<#
.SYNOPSIS
    Publish the dictionary catalog: build catalog.json, upload changed dictionary
    files to the permanent release tag, and stage the catalog for commit.

.DESCRIPTION
    The maintainer loop this automates:

      1. Build the dictionaries into a directory (default: dist/).
      2. `build` catalog.json from catalog/source.json + those files, computing
         each file's size and SHA-256.
      3. Compare the built catalog with the LIVE one (GitHub Pages) and upload
         only the files that are new or changed to the permanent release tag.
      4. Stage catalog/catalog.json; commit + push it (the Pages workflow then
         deploys it).

    The dictionary files are uploaded with `gh release upload --clobber`, so the
    release tag (`catalog-data` by default, read from catalog/source.json) must
    never be deleted: the catalog's file URLs point at it.

.PARAMETER Commit
    Also commit catalog/catalog.json (and stage it). Does not push.

.EXAMPLE
    pwsh -File scripts/publish-catalog.ps1
    pwsh -File scripts/publish-catalog.ps1 -FilesDir D:\built -Commit
#>
[CmdletBinding()]
param(
    [string]$FilesDir = "dist",
    [string]$Source = "catalog/source.json",
    [string]$Catalog = "catalog/catalog.json",
    [string]$Repo = "rg-software/aurelex",
    [string]$LiveCatalogUrl = "https://rg-software.github.io/aurelex/catalog/catalog.json",
    [switch]$Commit
)

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
Push-Location $root
try {
    # The permanent tag is part of the catalog's file URLs; read it from source.
    $sourceObj = Get-Content $Source -Raw -Encoding utf8 | ConvertFrom-Json
    $releaseTag = $sourceObj.releaseTag
    if (-not $releaseTag) { throw "catalog/source.json has no releaseTag" }

    Write-Host "== Building $Catalog from $Source + $FilesDir ==" -ForegroundColor Cyan
    python scripts/build-catalog.py build --source $Source --files-dir $FilesDir --out $Catalog
    if ($LASTEXITCODE -ne 0) { throw "build failed" }

    Write-Host "== Validating $Catalog ==" -ForegroundColor Cyan
    python scripts/build-catalog.py validate $Catalog
    if ($LASTEXITCODE -ne 0) { throw "the built catalog is not valid" }

    # Compare against the live catalog so we upload only what changed. If it is
    # unreachable, treat every file as new (the first publish, or Pages down).
    $toUpload = @()
    $tmp = Join-Path $env:TEMP "aurelex-live-catalog.json"
    $haveLive = $false
    try {
        Invoke-WebRequest -UseBasicParsing -Uri $LiveCatalogUrl -OutFile $tmp -TimeoutSec 30
        $haveLive = $true
    } catch {
        Write-Warning "live catalog not reachable ($LiveCatalogUrl); treating all files as new"
    }

    if ($haveLive) {
        $diffJson = python scripts/build-catalog.py diff $tmp --catalog $Catalog --json
        $diffExit = $LASTEXITCODE
        $diff = $diffJson | ConvertFrom-Json
        if ($diffExit -eq 2) {
            Write-Host "Identity violations (do not publish):" -ForegroundColor Red
            $diff.identity_violations | ForEach-Object { Write-Host "  $_" -ForegroundColor Red }
            throw "refusing to publish: a published entry's file was renamed or moved"
        } elseif ($diffExit -ne 0) {
            throw "diff failed"
        }
        if ($diff.new_files) { $toUpload += @($diff.new_files) }
        if ($diff.changed_files) { $toUpload += @($diff.changed_files) }
        Write-Host ("diff: {0} new, {1} changed, {2} unchanged" -f `
            (@($diff.new_files).Count), (@($diff.changed_files).Count), (@($diff.unchanged_files).Count))
    } else {
        $built = Get-Content $Catalog -Raw -Encoding utf8 | ConvertFrom-Json
        $toUpload = @($built.entries | ForEach-Object { $_.files } | ForEach-Object { $_.name })
    }

    if ($toUpload.Count -eq 0) {
        Write-Host "No dictionary files changed." -ForegroundColor Green
    } else {
        Write-Host "== Ensuring release tag '$releaseTag' exists ==" -ForegroundColor Cyan
        gh release view $releaseTag --repo $Repo *> $null
        if ($LASTEXITCODE -ne 0) {
            gh release create $releaseTag --repo $Repo `
                --title "Dictionary data" `
                --notes "Permanent release holding the dictionary files the app catalog references. Never delete this tag: catalog.json points its file URLs at it."
            if ($LASTEXITCODE -ne 0) { throw "could not create release $releaseTag" }
        }

        Write-Host "== Uploading $($toUpload.Count) file(s) to $releaseTag ==" -ForegroundColor Cyan
        foreach ($name in $toUpload) {
            $path = Join-Path $FilesDir $name
            if (-not (Test-Path $path)) { throw "catalog references $name but $path does not exist" }
            Write-Host "  uploading $name"
            gh release upload $releaseTag $path --repo $Repo --clobber
            if ($LASTEXITCODE -ne 0) { throw "upload failed for $name" }
        }
    }

    Write-Host "== Staging $Catalog ==" -ForegroundColor Cyan
    git add $Catalog
    if ($Commit) {
        git commit -m "chore(catalog): publish dictionary catalog"
        Write-Host "Committed. Push to main to deploy the catalog to Pages." -ForegroundColor Green
    } else {
        Write-Host "Staged. Commit and push to deploy the catalog:" -ForegroundColor Yellow
        Write-Host "  git commit -m `"chore(catalog): publish dictionary catalog`" && git push"
    }
} finally {
    Pop-Location
}
