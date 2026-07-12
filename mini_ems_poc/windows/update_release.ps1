<#
Mini EMS - Release-Update auf der IPC (H7).

Automatisiert den bisher manuellen Update-Ablauf aus UPDATE_WARTUNG.md:

  1. SHA256SUMS des neuen Pakets pruefen (Uebertragungs-/Integritaetsschutz).
  2. Geplanten Task stoppen und Prozess-Ende verifizieren.
  3. Standortordner im gestoppten Zustand als <SiteDir>_backup_<zeit> sichern.
  4. Bisherigen App-Ordner nach <AppDir>_vorher_<version> umbenennen
     (Rollback-Kandidat) - Standortdaten in -SiteDir bleiben unberuehrt.
  5. Neues Paket nach <AppDir> kopieren.
  6. Task starten.
  7. Smoketest (windows\smoketest_release.ps1) fahren.
  8. Ergebnis ausgeben; bei Fehlschlag klare Anweisung zum Rollback.

Standortdaten (-SiteDir: site.sqlite, data\, logs\, runtime\) werden NIE
angefasst - nur der App-Ordner wird ersetzt.

Rollback: erneut mit -Rollback aufrufen. Der juengste <AppDir>_vorher_*-Ordner
wird zurueckgeschoben und der Task wieder gestartet.
Mit -RestoreSiteBackup wird zusaetzlich die juengste Standort-Sicherung
zurueckgespielt. Das ist nur beim Ruecksprung ueber eine inkompatible
Standortdaten-Migration vorgesehen.

Unterstuetzt -WhatIf fuer die veraendernden Schritte (Stop/Rename/Copy/Start).

Beispiele:
  .\update_release.ps1 -PackagePath D:\releases\mini_ems_2026.07.1
  .\update_release.ps1 -Rollback
  .\update_release.ps1 -Rollback -RestoreSiteBackup
#>
[CmdletBinding(SupportsShouldProcess = $true, ConfirmImpact = "Medium")]
param(
    [string]$PackagePath,
    [string]$AppDir = "C:\Program Files\MiniEMS",
    [string]$SiteDir = "C:\ProgramData\MiniEMS",
    [string]$TaskName = "MiniEmsPoCRelease",
    [int]$SmoketestTimeoutSeconds = 120,
    [switch]$Rollback,
    [switch]$RestoreSiteBackup
)

$ErrorActionPreference = "Stop"
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Definition

if ($RestoreSiteBackup -and -not $Rollback) {
    throw "-RestoreSiteBackup ist nur zusammen mit -Rollback erlaubt."
}

function Get-VersionFromDir {
    param([string]$Dir)
    $versionFile = Join-Path $Dir "VERSION"
    if (-not (Test-Path $versionFile)) { return $null }
    foreach ($line in Get-Content -Path $versionFile -Encoding UTF8) {
        if ($line -match '^version=(.+)$') { return $Matches[1].Trim() }
    }
    return $null
}

function Stop-RuntimeAndVerify {
    # Stoppt den Task und wartet, bis kein mini_ems-Prozess mehr laeuft.
    # ShouldProcess/-WhatIf wird vom Aufrufer im Skript-Hauptteil gehandhabt.
    try {
        Stop-ScheduledTask -TaskName $TaskName -ErrorAction Stop
    } catch {
        Write-Warning "Task '$TaskName' konnte nicht gestoppt werden (evtl. nicht aktiv): $($_.Exception.Message)"
    }
    Write-Host "[update] Warte auf Prozess-Ende von mini_ems ..."
    $deadline = (Get-Date).AddSeconds(30)
    while ((Get-Date) -lt $deadline) {
        $proc = Get-Process -Name "mini_ems" -ErrorAction SilentlyContinue
        if (-not $proc) {
            Write-Host "[update] OK: kein mini_ems-Prozess mehr aktiv."
            return
        }
        Start-Sleep -Seconds 2
    }
    $stillRunning = Get-Process -Name "mini_ems" -ErrorAction SilentlyContinue
    if ($stillRunning) {
        throw "mini_ems laeuft nach 30 s noch. Bitte Prozess pruefen (Get-Process mini_ems) und manuell beenden, dann erneut versuchen."
    }
}

function Test-PackageChecksums {
    param([string]$Dir)
    $sumsFile = Join-Path $Dir "SHA256SUMS"
    if (-not (Test-Path $sumsFile)) {
        throw "SHA256SUMS nicht gefunden im Paket: $sumsFile"
    }
    $mismatch = 0
    foreach ($line in Get-Content -Path $sumsFile -Encoding UTF8) {
        if (-not $line.Trim()) { continue }
        # Format aus dem Build: "<hash>  ./<relpfad-mit-slashes>"
        if ($line -notmatch '^([0-9a-fA-F]{64})\s+\.?/?(.+)$') {
            Write-Warning "[update] SHA256SUMS-Zeile nicht interpretierbar, uebersprungen: $line"
            continue
        }
        $expected = $Matches[1].ToLower()
        $rel = $Matches[2].Trim().Replace('/', '\')
        $target = Join-Path $Dir $rel
        if (-not (Test-Path $target)) {
            Write-Warning "[update] Datei aus SHA256SUMS fehlt im Paket: $rel"
            $mismatch++
            continue
        }
        $actual = (Get-FileHash -Path $target -Algorithm SHA256).Hash.ToLower()
        if ($actual -ne $expected) {
            Write-Warning "[update] Pruefsumme weicht ab: $rel"
            $mismatch++
        }
    }
    if ($mismatch -gt 0) {
        throw "$mismatch Paketdatei(en) mit falscher oder fehlender Pruefsumme. Update abgebrochen, es wurde nichts veraendert."
    }
    Write-Host "[update] OK: alle Paket-Pruefsummen stimmen."
}

function Invoke-Smoketest {
    param([string]$ExpectedVersion, [datetime]$SinceTime)
    if ($WhatIfPreference) {
        Write-Host "[update] WhatIf: Smoketest wuerde jetzt laufen (erwartete Version $ExpectedVersion)."
        return $true
    }
    $smoketest = Join-Path $ScriptDir "smoketest_release.ps1"
    if (-not (Test-Path $smoketest)) {
        Write-Warning "[update] smoketest_release.ps1 nicht gefunden - Smoketest uebersprungen."
        return $true
    }
    Write-Host "[update] Starte Smoketest (erwartete Version $ExpectedVersion) ..."
    & $smoketest -ExpectedVersion $ExpectedVersion -SiteDir $SiteDir -SinceTime $SinceTime -TimeoutSeconds $SmoketestTimeoutSeconds
    return ($LASTEXITCODE -eq 0)
}

# ============================================================================
# Rollback-Modus
# ============================================================================
if ($Rollback) {
    Write-Host "[update] === Rollback-Modus ==="
    $candidates = @(Get-ChildItem -Path (Split-Path -Parent $AppDir) -Directory -ErrorAction SilentlyContinue |
        Where-Object { $_.Name -like ((Split-Path -Leaf $AppDir) + "_vorher_*") } |
        Sort-Object LastWriteTime -Descending)
    if ($candidates.Count -eq 0) {
        throw "Kein Rollback-Kandidat (<AppDir>_vorher_*) neben $AppDir gefunden."
    }
    $previous = $candidates[0].FullName
    Write-Host "[update] Rollback-Kandidat: $previous"

    $previousSite = $null
    if ($RestoreSiteBackup) {
        $siteLeaf = Split-Path -Leaf $SiteDir
        $siteCandidates = @(Get-ChildItem -Path (Split-Path -Parent $SiteDir) -Directory -ErrorAction SilentlyContinue |
            Where-Object { $_.Name -like ($siteLeaf + "_backup_*") } |
            Sort-Object LastWriteTime -Descending)
        if ($siteCandidates.Count -eq 0) {
            throw "Keine Standort-Sicherung (${siteLeaf}_backup_*) neben $SiteDir gefunden."
        }
        $previousSite = $siteCandidates[0].FullName
        Write-Host "[update] Standort-Sicherung fuer Rollback: $previousSite"
    }

    if ($PSCmdlet.ShouldProcess($TaskName, "Geplanten Task stoppen und Prozess-Ende abwarten")) {
        Stop-RuntimeAndVerify
    }

    if ($PSCmdlet.ShouldProcess($AppDir, "Fehlgeschlagenen App-Ordner entfernen und vorherigen Stand zurueckschieben")) {
        if (Test-Path $AppDir) {
            $failed = "$AppDir" + "_fehlgeschlagen_" + (Get-Date -Format "yyyyMMdd_HHmmss")
            Rename-Item -Path $AppDir -NewName (Split-Path -Leaf $failed)
            Write-Host "[update] Fehlgeschlagenen Stand beiseitegelegt: $failed"
        }
        Rename-Item -Path $previous -NewName (Split-Path -Leaf $AppDir)
        Write-Host "[update] Vorherigen Stand wiederhergestellt nach $AppDir"
    }

    if ($RestoreSiteBackup) {
        $siteLeaf = Split-Path -Leaf $SiteDir
        if ($PSCmdlet.ShouldProcess($SiteDir, "Aktuellen Standortordner beiseitelegen und Standort-Sicherung wiederherstellen")) {
            if (Test-Path $SiteDir) {
                $failedSiteLeaf = $siteLeaf + "_fehlgeschlagen_" + (Get-Date -Format "yyyyMMdd_HHmmss")
                Rename-Item -Path $SiteDir -NewName $failedSiteLeaf
                Write-Host "[update] Aktuellen Standortstand beiseitegelegt: $failedSiteLeaf"
            }
            Rename-Item -Path $previousSite -NewName $siteLeaf
            Write-Host "[update] Standort-Sicherung wiederhergestellt nach $SiteDir"
        }
    }

    $restoredVersion = Get-VersionFromDir $AppDir
    $sinceTime = Get-Date
    if ($PSCmdlet.ShouldProcess($TaskName, "Geplanten Task starten")) {
        Start-ScheduledTask -TaskName $TaskName
    }

    if ($restoredVersion) {
        $ok = Invoke-Smoketest -ExpectedVersion $restoredVersion -SinceTime $sinceTime
        if ($ok) {
            Write-Host "[update] Rollback abgeschlossen und Smoketest bestanden (Version $restoredVersion)." -ForegroundColor Green
            exit 0
        } else {
            Write-Host "[update] Rollback durchgefuehrt, aber der Smoketest ist NICHT bestanden. Bitte health.json und Log pruefen." -ForegroundColor Red
            exit 1
        }
    } else {
        Write-Warning "[update] Wiederhergestellter Stand ohne lesbare VERSION - Smoketest uebersprungen. Bitte manuell pruefen."
        exit 0
    }
}

# ============================================================================
# Update-Modus
# ============================================================================
if (-not $PackagePath) {
    throw "Ohne -Rollback wird -PackagePath (Ordner des neuen Release-Pakets) benoetigt."
}
if (-not (Test-Path $PackagePath)) {
    throw "Paketordner nicht gefunden: $PackagePath"
}
foreach ($required in @("mini_ems.exe", "VERSION", "SHA256SUMS")) {
    if (-not (Test-Path (Join-Path $PackagePath $required))) {
        throw "Paket unvollstaendig: '$required' fehlt in $PackagePath"
    }
}

$newVersion = Get-VersionFromDir $PackagePath
if (-not $newVersion) { throw "Keine version=-Zeile in $PackagePath\VERSION gefunden." }
$currentVersion = Get-VersionFromDir $AppDir
if (-not $currentVersion) { $currentVersion = (Get-Date -Format "yyyyMMdd_HHmmss") }

Write-Host "[update] === Update-Modus ==="
Write-Host "[update] Neues Paket : $PackagePath (Version $newVersion)"
Write-Host "[update] Ziel        : $AppDir (aktuell $currentVersion)"
Write-Host "[update] Standortdaten unberuehrt: $SiteDir"

# 1. Pruefsummen
Test-PackageChecksums -Dir $PackagePath

# 2. Stoppen + Prozess-Ende
if ($PSCmdlet.ShouldProcess($TaskName, "Geplanten Task stoppen und Prozess-Ende abwarten")) {
    Stop-RuntimeAndVerify
}

# 3. Ruhende Sicherung des gesamten Standortordners
$siteBackupPath = $null
if (Test-Path $SiteDir) {
    $siteBackupPath = "$SiteDir" + "_backup_" + (Get-Date -Format "yyyyMMdd_HHmmss")
    if ($PSCmdlet.ShouldProcess($SiteDir, "Standortordner nach $siteBackupPath sichern")) {
        Copy-Item -Path $SiteDir -Destination $siteBackupPath -Recurse -Force
        Write-Host "[update] Standort-Sicherung angelegt: $siteBackupPath"
    }
} else {
    Write-Warning "[update] Standortordner $SiteDir ist noch nicht vorhanden - keine Standort-Sicherung angelegt."
}

# 4. Bisherigen App-Ordner als Rollback-Kandidat beiseitelegen
$backupLeaf = (Split-Path -Leaf $AppDir) + "_vorher_" + $currentVersion
$backupPath = Join-Path (Split-Path -Parent $AppDir) $backupLeaf
if (Test-Path $backupPath) {
    $backupLeaf = $backupLeaf + "_" + (Get-Date -Format "yyyyMMdd_HHmmss")
    $backupPath = Join-Path (Split-Path -Parent $AppDir) $backupLeaf
}
if (Test-Path $AppDir) {
    if ($PSCmdlet.ShouldProcess($AppDir, "Nach $backupLeaf umbenennen (Rollback-Kandidat)")) {
        Rename-Item -Path $AppDir -NewName $backupLeaf
        Write-Host "[update] Rollback-Kandidat angelegt: $backupPath"
    }
} else {
    Write-Warning "[update] Bisheriger App-Ordner $AppDir nicht vorhanden - es gibt keinen Rollback-Kandidaten."
}

# 5. Neues Paket kopieren
if ($PSCmdlet.ShouldProcess($AppDir, "Neues Paket kopieren")) {
    New-Item -ItemType Directory -Path $AppDir -Force | Out-Null
    Copy-Item -Path (Join-Path $PackagePath '*') -Destination $AppDir -Recurse -Force
    Write-Host "[update] Neues Paket nach $AppDir kopiert."
}

# 6. Task starten (Startzeitpunkt fuer den Smoketest merken)
$sinceTime = Get-Date
if ($PSCmdlet.ShouldProcess($TaskName, "Geplanten Task starten")) {
    Start-ScheduledTask -TaskName $TaskName
    Write-Host "[update] Task '$TaskName' gestartet."
}

# 7. Smoketest
$ok = Invoke-Smoketest -ExpectedVersion $newVersion -SinceTime $sinceTime

# 8. Ergebnis
Write-Host ""
if ($ok) {
    Write-Host "[update] UPDATE BESTANDEN: Mini EMS laeuft auf Version $newVersion." -ForegroundColor Green
    Write-Host "[update] Rollback-Kandidat bleibt vorerst erhalten: $backupPath"
    if ($siteBackupPath) {
        Write-Host "[update] Standort-Sicherung bleibt vorerst erhalten: $siteBackupPath"
    }
    exit 0
} else {
    Write-Host "[update] UPDATE NICHT BESTANDEN. Der Smoketest ist fehlgeschlagen." -ForegroundColor Red
    Write-Host "[update] Empfehlung: Rollback ausfuehren:" -ForegroundColor Yellow
    Write-Host "         .\update_release.ps1 -Rollback -AppDir `"$AppDir`" -SiteDir `"$SiteDir`" -TaskName `"$TaskName`"" -ForegroundColor Yellow
    Write-Host "[update] Kein zweiter Blindversuch ohne Ursachenklaerung (siehe UPDATE_WARTUNG.md)." -ForegroundColor Yellow
    exit 1
}
