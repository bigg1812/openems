<#
Mini EMS - Smoketest nach einem Release-Update (H7).

Prueft nach einem Update bzw. Neustart, dass die Runtime frisch und gesund
laeuft. Wird von windows\update_release.ps1 aufgerufen, ist aber auch solo
nutzbar.

Geprueft wird:
  1. Frische runtime\health.json: timestamp neuer als der Startzeitpunkt
     (last_cycle_at bleibt als Rueckwaertskompatibilitaet akzeptiert),
     runtime_status = live, status = healthy. Es wird bis -TimeoutSeconds
     gewartet, damit mindestens ein Zyklus nach dem Neustart laufen kann.
  2. /api/status ist erreichbar und meldet die erwartete app_version sowie
     optional den explizit erwarteten api_read_only-Wert.
  3. logs\mini_ems.log enthaelt seit -SinceTime keine neuen ERROR-Zeilen.

Exit-Code 0 = bestanden, 1 = nicht bestanden. Standortdaten werden nur gelesen,
nie veraendert.
#>
[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [string]$ExpectedVersion,

    [string]$SiteDir = "C:\ProgramData\MiniEMS",
    [int]$TimeoutSeconds = 120,
    [datetime]$SinceTime = (Get-Date),
    [string]$StatusUrl = "http://127.0.0.1:8090/api/status",

    # Optionaler erwarteter api_read_only-Wert. Ohne Angabe wird nur Erreichbarkeit geprüft.
    [object]$ExpectReadOnly = $null
)

$ErrorActionPreference = "Stop"

$HealthPath = Join-Path $SiteDir "runtime\health.json"
$LogPath    = Join-Path $SiteDir "logs\mini_ems.log"
$SinceUtc   = $SinceTime.ToUniversalTime()

$errors = New-Object System.Collections.Generic.List[string]

function Convert-IsoToUtc {
    param([string]$Value)
    if (-not $Value) { return $null }
    try {
        return ([datetimeoffset]::Parse($Value)).UtcDateTime
    } catch {
        return $null
    }
}

# --- 1. Frische, gesunde health.json (mit Warten bis Timeout) ----------------
Write-Host "[smoketest] Warte auf frische health.json (max. $TimeoutSeconds s) ..."
$deadline = (Get-Date).AddSeconds($TimeoutSeconds)
$healthOk = $false
$lastReason = "keine health.json gefunden"

while ((Get-Date) -lt $deadline) {
    if (Test-Path $HealthPath) {
        try {
            $health = Get-Content -Path $HealthPath -Raw -Encoding UTF8 | ConvertFrom-Json
        } catch {
            $health = $null
            $lastReason = "health.json nicht lesbar/parsebar"
        }
        if ($health) {
            $lastCycleValue = [string]$health.timestamp
            if (-not $lastCycleValue) {
                $lastCycleValue = [string]$health.last_cycle_at
            }
            $lastCycleUtc = Convert-IsoToUtc $lastCycleValue
            $runtimeStatus = [string]$health.runtime_status
            $status = [string]$health.status
            if (-not $lastCycleUtc) {
                $lastReason = "timestamp/last_cycle_at fehlt oder ist unlesbar"
            } elseif ($lastCycleUtc -le $SinceUtc) {
                $lastReason = "Zykluszeitpunkt ($lastCycleValue) ist nicht neuer als der Startzeitpunkt"
            } elseif ($runtimeStatus -ne "live") {
                $lastReason = "runtime_status ist '$runtimeStatus' (erwartet 'live')"
            } elseif ($status -ne "healthy") {
                $lastReason = "status ist '$status' (erwartet 'healthy')"
            } else {
                $healthOk = $true
                break
            }
        }
    }
    Start-Sleep -Seconds 5
}

if ($healthOk) {
    Write-Host "[smoketest] OK: health.json frisch, runtime_status live, status healthy."
} else {
    $errors.Add("Health nicht bestanden: $lastReason")
}

# --- 2. /api/status erreichbar, app_version + api_read_only pruefen ----------
$expectReadOnlyBool = $null
if ($null -ne $ExpectReadOnly) {
    $expectReadOnlyBool = [bool]$ExpectReadOnly
}

try {
    $statusResponse = Invoke-RestMethod -Uri $StatusUrl -TimeoutSec 15 -UseBasicParsing
} catch {
    $statusResponse = $null
    $errors.Add("/api/status nicht erreichbar unter $StatusUrl ($($_.Exception.Message))")
}

if ($statusResponse) {
    $actualVersion = [string]$statusResponse.app_version.version
    if ($actualVersion -eq $ExpectedVersion) {
        Write-Host "[smoketest] OK: app_version = $actualVersion (wie erwartet)."
    } else {
        $errors.Add("app_version ist '$actualVersion', erwartet '$ExpectedVersion'")
    }

    if ($null -ne $expectReadOnlyBool) {
        $actualReadOnly = [bool]$statusResponse.api_read_only
        if ($actualReadOnly -eq $expectReadOnlyBool) {
            Write-Host "[smoketest] OK: api_read_only = $actualReadOnly (wie konfiguriert)."
        } else {
            $errors.Add("api_read_only ist '$actualReadOnly', konfiguriert/erwartet '$expectReadOnlyBool'")
        }
    }
}

# --- 3. Keine neuen ERROR-Zeilen im Log seit SinceTime ----------------------
if (Test-Path $LogPath) {
    $newErrors = 0
    $sampleError = ""
    foreach ($line in Get-Content -Path $LogPath -Encoding UTF8) {
        if ($line -notmatch '"level":\s*"ERROR"') { continue }
        try {
            $entry = $line | ConvertFrom-Json
        } catch {
            continue
        }
        $entryUtc = Convert-IsoToUtc $entry.timestamp
        if ($entryUtc -and ($entryUtc -gt $SinceUtc)) {
            $newErrors++
            if (-not $sampleError) { $sampleError = [string]$entry.event }
        }
    }
    if ($newErrors -eq 0) {
        Write-Host "[smoketest] OK: keine neuen ERROR-Zeilen im Log seit dem Startzeitpunkt."
    } else {
        $errors.Add("$newErrors neue ERROR-Zeile(n) im Log seit dem Startzeitpunkt (z. B. '$sampleError')")
    }
} else {
    Write-Warning "[smoketest] Logdatei $LogPath nicht gefunden - ERROR-Pruefung uebersprungen."
}

# --- Ergebnis ---------------------------------------------------------------
Write-Host ""
if ($errors.Count -eq 0) {
    Write-Host "[smoketest] BESTANDEN: Mini EMS laeuft frisch und gesund (Version $ExpectedVersion)."
    exit 0
} else {
    Write-Host "[smoketest] NICHT BESTANDEN:" -ForegroundColor Red
    foreach ($e in $errors) {
        Write-Host "  - $e" -ForegroundColor Red
    }
    exit 1
}
