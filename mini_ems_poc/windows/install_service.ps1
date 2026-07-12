<#
    DEPRECATED – NICHT VERWENDEN.

    Dieses Skript ist ein alter Windows-Dienst-Wrapper und NICHT der unterstuetzte
    Betriebspfad. Die Mini-EMS-Runtime ist konsolenbasiert; der produktive Start
    laeuft ueber den geplanten Task:
      - Git-Checkout:   windows/install_task.ps1              + run_mini_ems.cmd
      - Release-Paket:  windows/install_task.ps1 -Mode release + run_mini_ems_release.cmd
    Siehe MINI_EMS_ANLEITUNG.md, HOSTING_SICHERHEIT.md (Teil 3/4) und UPDATE_WARTUNG.md.

    Die Datei bleibt nur als Referenz erhalten. Der Default-PythonPath unten
    (C:\Python39) ist veraltet und wird bewusst nicht gepflegt.
#>
param(
    [string]$ServiceName = "MiniEmsPoC",
    [string]$PythonPath = "C:\Python39\python.exe",
    [string]$ProjectDir = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path,
    [string]$SiteDir = "C:\ProgramData\MiniEMS"
)

# Legacy helper for a true Windows service wrapper.
# The current mini_ems.py runtime is console-based, so the supported
# production start path is install_task.ps1 + run_mini_ems.cmd.

$scriptPath = Join-Path $ProjectDir "mini_ems.py"

if (-not (Test-Path $scriptPath)) {
    throw "mini_ems.py not found at $scriptPath"
}
if (-not (Test-Path $PythonPath)) {
    throw "Python executable not found at $PythonPath"
}

$binaryPath = "`"$PythonPath`" `"$scriptPath`" --site-dir `"$SiteDir`" --loop"

if (-not (Get-Service -Name $ServiceName -ErrorAction SilentlyContinue)) {
    New-Service `
        -Name $ServiceName `
        -BinaryPathName $binaryPath `
        -DisplayName $ServiceName `
        -Description "Mini EMS proof-of-concept runtime" `
        -StartupType Automatic
} else {
    Write-Host "Service '$ServiceName' already exists. Updating it."
}

sc.exe failure $ServiceName reset= 86400 actions= restart/5000/restart/5000/restart/5000 | Out-Null
sc.exe failureflag $ServiceName 1 | Out-Null
# Run as LocalSystem so the service can access the per-user Python installation
# and project files without having to grant access to LocalService explicitly.
sc.exe config $ServiceName obj= "LocalSystem" | Out-Null

Write-Host "Service '$ServiceName' created or updated."
Write-Host "This service path is not the recommended runtime for mini_ems.py."
Write-Host "Use windows/install_task.ps1 for the supported production start path."
