<# Einfache Bedienung des geprueften Windows-Pakets. Im Pruefmodus keine Anlage. #>
[CmdletBinding()]
param(
    [ValidateSet("Menu", "Check", "Install", "Rollback")]
    [string]$Mode = "Menu",
    [string]$PackagePath = (Split-Path -Parent $PSScriptRoot)
)

$ErrorActionPreference = "Stop"
$PackagePath = [IO.Path]::GetFullPath($PackagePath).TrimEnd('\')
$UpdateScript = Join-Path $PackagePath "windows\update_release.ps1"
$Binary = Join-Path $PackagePath "mini_ems.exe"

function Invoke-UpdateScript {
    param([string[]]$Arguments)
    & powershell.exe -NoProfile -ExecutionPolicy Bypass -File $UpdateScript @Arguments
    if ($LASTEXITCODE -ne 0) { throw "Paket- oder Update-Pruefung fehlgeschlagen (Exit $LASTEXITCODE)." }
}

function Test-Package {
    Invoke-UpdateScript -Arguments @("-VerifyOnly", "-PackagePath", $PackagePath)
    $site = Join-Path $env:TEMP ("MiniEMS-Paketcheck-" + [guid]::NewGuid().ToString("N"))
    try {
        & $Binary --site-dir $site --once
        if ($LASTEXITCODE -ne 0) { throw "Der simulierte Start ist fehlgeschlagen (Exit $LASTEXITCODE)." }
        $health = Get-Content -LiteralPath (Join-Path $site "runtime\health.json") -Raw -Encoding UTF8 | ConvertFrom-Json
        if ($health.status -ne "healthy" -or $health.storage_status -ne "ok" -or -not $health.cycle_id) {
            throw "Der simulierte Zyklus meldet keinen gesunden Lauf."
        }
        Write-Host "Paketpruefung bestanden. Der IPC-Standort wurde nicht veraendert." -ForegroundColor Green
    } finally {
        if (Test-Path -LiteralPath $site) { Remove-Item -LiteralPath $site -Recurse -Force }
    }
}

function Assert-Administrator {
    $identity = [Security.Principal.WindowsIdentity]::GetCurrent()
    $principal = New-Object Security.Principal.WindowsPrincipal($identity)
    if ($principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) { return }
    Write-Host "Windows fragt jetzt nach Administratorrechten."
    $arguments = "-NoProfile -ExecutionPolicy Bypass -File `"$PSCommandPath`" -Mode $Mode -PackagePath `"$PackagePath`""
    $child = Start-Process -FilePath powershell.exe -Verb RunAs -ArgumentList $arguments -Wait -PassThru
    if ($child.ExitCode -ne 0) { throw "Die Aktion im Administratorfenster ist fehlgeschlagen (Exit $($child.ExitCode))." }
    Write-Host "Die Aktion im Administratorfenster ist abgeschlossen." -ForegroundColor Green
    exit 0
}

try {
    if (-not (Test-Path -LiteralPath $UpdateScript -PathType Leaf) -or
        -not (Test-Path -LiteralPath $Binary -PathType Leaf)) {
        throw "Das Paket ist unvollstaendig. Bitte das ganze ZIP entpacken."
    }
    if ($Mode -eq "Menu") {
        $version = (Get-Content -LiteralPath (Join-Path $PackagePath "VERSION") -Encoding UTF8 |
            Where-Object { $_ -like "version=*" } | Select-Object -First 1) -replace '^version=', ''
        Write-Host "Mini EMS $version"
        Write-Host "1  Paket ohne Anlagenzugriff pruefen"
        Write-Host "2  Version auf diesem IPC installieren"
        Write-Host "3  Vorherige Version wiederherstellen"
        Write-Host "0  Beenden"
        $choice = Read-Host "Auswahl"
        $Mode = switch ($choice) { "1" { "Check" } "2" { "Install" } "3" { "Rollback" } default { "Exit" } }
    }
    switch ($Mode) {
        "Check" { Test-Package }
        "Install" {
            Assert-Administrator
            if (-not (Test-Path -LiteralPath "C:\Program Files\MiniEMS\mini_ems.exe") -or
                -not (Get-ScheduledTask -TaskName "MiniEmsPoCRelease" -ErrorAction SilentlyContinue)) {
                throw "Auf diesem Rechner ist kein Mini-EMS-Release-Task installiert. Dieses Menue aktualisiert nur bestehende IPC-Installationen."
            }
            Test-Package
            $answer = Read-Host "Mini EMS wird kurz gestoppt und aktualisiert. Jetzt installieren? (J/n)"
            if ($answer -ne "J") { Write-Host "Abgebrochen. Der IPC wurde nicht aktualisiert."; break }
            Invoke-UpdateScript -Arguments @("-PackagePath", $PackagePath)
            Write-Host "Update bestanden. Version und Health wurden geprueft." -ForegroundColor Green
        }
        "Rollback" {
            Assert-Administrator
            $answer = Read-Host "Vorherige Anwendungsversion wiederherstellen? (J/n)"
            if ($answer -ne "J") { Write-Host "Abgebrochen."; break }
            Invoke-UpdateScript -Arguments @("-Rollback")
            Write-Host "Vorherige Anwendungsversion wiederhergestellt und geprueft." -ForegroundColor Green
        }
    }
    exit 0
} catch {
    Write-Host "Mini EMS: $($_.Exception.Message)" -ForegroundColor Red
    exit 1
}
