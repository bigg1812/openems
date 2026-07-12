<#
Build a Mini EMS release package on Windows (H2 – IPC release artifact).

Same PyInstaller spec as build_release.sh, so the macOS/Linux verification build
and the Windows IPC build share one source of truth. Produces a one-dir package
under packaging\dist\mini_ems\ (mini_ems.exe + resources + VERSION +
SHA256SUMS + RELEASE_HINWEISE.md).

site.sqlite and all operational data (data\, logs\, runtime\) are NEVER part of
the package. The runtime receives only the site directory; configuration is
created and revised through the UI-backed site store.

Prerequisites: a Python >= 3.10 interpreter with PyInstaller installed
(pip install pyinstaller). Pass -Python to select the interpreter.
#>
[CmdletBinding()]
param(
    [string]$Version = $(if ($env:MINI_EMS_VERSION) { $env:MINI_EMS_VERSION } else { "" }),
    [string]$Python = "python"
)

$ErrorActionPreference = "Stop"

# Version is a required, explicit input (schema JJJJ.MM.n). No silently ageing
# default: a stale hard-coded version is a reproducibility trap.
if (-not $Version) {
    Write-Host "[build] FEHLER: Version fehlt. Aufruf mit -Version JJJJ.MM.n (z. B. 2026.07.1) oder `$env:MINI_EMS_VERSION setzen." -ForegroundColor Red
    exit 2
}

$ScriptDir  = Split-Path -Parent $MyInvocation.MyCommand.Definition
$ProjectDir = Split-Path -Parent $ScriptDir
$Spec       = Join-Path $ScriptDir "mini_ems.spec"
$WorkDir    = Join-Path $ScriptDir "build"
$DistDir    = Join-Path $ScriptDir "dist"
$ReleaseDir = Join-Path $DistDir "mini_ems"

Write-Host "[build] project : $ProjectDir"
Write-Host "[build] python  : $Python"
Write-Host "[build] version : $Version"

# Fresh build, but only under packaging\ (never touch the repo build\ dir).
if (Test-Path $WorkDir) { Remove-Item -Recurse -Force $WorkDir }
if (Test-Path $DistDir) { Remove-Item -Recurse -Force $DistDir }

Write-Host "[build] running PyInstaller ..."
& $Python -m PyInstaller `
    --noconfirm `
    --clean `
    --distpath $DistDir `
    --workpath $WorkDir `
    $Spec
if ($LASTEXITCODE -ne 0) { throw "PyInstaller failed with exit code $LASTEXITCODE" }

if (-not (Test-Path $ReleaseDir)) {
    throw "Expected release dir not found: $ReleaseDir"
}

# --- VERSION file: semver + build date + git commit hash --------------------
$BuildDate = (Get-Date).ToUniversalTime().ToString("yyyy-MM-ddTHH:mm:ssZ")
$GitCommit = (& git -C $ProjectDir rev-parse --short=12 HEAD 2>$null)
if (-not $GitCommit) { $GitCommit = "unknown" }
& git -C $ProjectDir diff --quiet HEAD 2>$null
if ($LASTEXITCODE -ne 0) { $GitCommit = "$GitCommit+dirty" }
$Platform = "Windows-$env:PROCESSOR_ARCHITECTURE"
@(
    "version=$Version",
    "build_date=$BuildDate",
    "git_commit=$GitCommit",
    "platform=$Platform"
) | Set-Content -Path (Join-Path $ReleaseDir "VERSION") -Encoding ascii
Write-Host "[build] wrote VERSION ($Version, $GitCommit)"

# --- Release launcher + notes: package vs. site data ------------------------
Copy-Item (Join-Path $ProjectDir "run_mini_ems_release.cmd") (Join-Path $ReleaseDir "run_mini_ems_release.cmd") -Force
Copy-Item (Join-Path $ScriptDir "RELEASE_HINWEISE.md") (Join-Path $ReleaseDir "RELEASE_HINWEISE.md") -Force
Copy-Item (Join-Path $ProjectDir "windows") (Join-Path $ReleaseDir "windows") -Recurse -Force

# --- CHANGELOG snapshot into the package (repo CHANGELOG is NOT rewritten) ---
# The [Unreleased] heading becomes the versioned snapshot heading in the copy
# that ships with the package. The repo CHANGELOG.md stays manual maintenance.
$RepoChangelog = Join-Path $ProjectDir "CHANGELOG.md"
$ReleaseDate = (Get-Date).ToUniversalTime().ToString("yyyy-MM-dd")
if (Test-Path $RepoChangelog) {
    $changelogLines = Get-Content -Path $RepoChangelog
    # Non-empty check: at least one bullet between [Unreleased] and the next "## [".
    $inBlock = $false
    $hasEntry = $false
    foreach ($line in $changelogLines) {
        if ($line -match '^## \[Unreleased\]') { $inBlock = $true; continue }
        if ($inBlock -and $line -match '^## \[') { $inBlock = $false }
        if ($inBlock -and $line -match '^[-*] ') { $hasEntry = $true }
    }
    if (-not $hasEntry) {
        Write-Warning "[Unreleased] in CHANGELOG.md ist leer - Paket-Changelog ohne neue Eintraege."
    }
    $snapshot = $changelogLines | ForEach-Object {
        if ($_ -match '^## \[Unreleased\]') { "## [$Version] - $ReleaseDate" } else { $_ }
    }
    Set-Content -Path (Join-Path $ReleaseDir "CHANGELOG.md") -Value $snapshot -Encoding utf8
    Write-Host "[build] wrote CHANGELOG.md snapshot ($Version, $ReleaseDate)"
} else {
    Write-Warning "CHANGELOG.md nicht gefunden unter $RepoChangelog"
}

# --- SHA256SUMS over every release file (excluding the sums file itself) -----
$SumsFile = Join-Path $ReleaseDir "SHA256SUMS"
if (Test-Path $SumsFile) { Remove-Item -Force $SumsFile }
$Files = Get-ChildItem -Path $ReleaseDir -Recurse -File |
    Where-Object { $_.Name -ne "SHA256SUMS" } |
    Sort-Object FullName
$Lines = foreach ($f in $Files) {
    $hash = (Get-FileHash -Path $f.FullName -Algorithm SHA256).Hash.ToLower()
    # Path relative to the release root, forward slashes, "<hash>  ./<path>".
    $rel = $f.FullName.Substring($ReleaseDir.Length).TrimStart('\','/').Replace('\','/')
    "$hash  ./$rel"
}
Set-Content -Path $SumsFile -Value $Lines -Encoding ascii
Write-Host "[build] wrote SHA256SUMS over $($Files.Count) files"

Write-Host "[build] done -> $ReleaseDir"
Get-ChildItem -Name $ReleaseDir
