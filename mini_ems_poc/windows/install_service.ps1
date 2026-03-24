param(
    [string]$ServiceName = "MiniEmsPoC",
    [string]$PythonPath = "C:\Python39\python.exe",
    [string]$ProjectDir = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
)

$configPath = Join-Path $ProjectDir "config.json"
$scriptPath = Join-Path $ProjectDir "mini_ems.py"

if (-not (Test-Path $configPath)) {
    throw "config.json not found at $configPath"
}
if (-not (Test-Path $scriptPath)) {
    throw "mini_ems.py not found at $scriptPath"
}
if (-not (Test-Path $PythonPath)) {
    throw "Python executable not found at $PythonPath"
}

$config = Get-Content $configPath -Encoding UTF8 | ConvertFrom-Json
$binaryPath = "`"$PythonPath`" `"$scriptPath`" --config `"$configPath`" --loop"

if (Get-Service -Name $ServiceName -ErrorAction SilentlyContinue) {
    throw "Service '$ServiceName' already exists."
}

New-Service `
    -Name $ServiceName `
    -BinaryPathName $binaryPath `
    -DisplayName $ServiceName `
    -Description "Mini EMS proof-of-concept runtime" `
    -StartupType Automatic

sc.exe failure $ServiceName reset= 86400 actions= restart/5000/restart/5000/restart/5000 | Out-Null
sc.exe failureflag $ServiceName 1 | Out-Null
sc.exe config $ServiceName obj= "NT AUTHORITY\LocalService" | Out-Null

$outboundRule = "$ServiceName BACnet Outbound"
$inboundRule = "$ServiceName BACnet Inbound"

New-NetFirewallRule `
    -DisplayName $outboundRule `
    -Direction Outbound `
    -Action Allow `
    -Protocol UDP `
    -Program $PythonPath `
    -RemoteAddress $config.network.controller_ip `
    -RemotePort $config.network.controller_port | Out-Null

New-NetFirewallRule `
    -DisplayName $inboundRule `
    -Direction Inbound `
    -Action Allow `
    -Protocol UDP `
    -Program $PythonPath `
    -LocalAddress $config.network.local_ip `
    -LocalPort $config.network.local_port `
    -RemoteAddress $config.network.controller_ip | Out-Null

Write-Host "Service '$ServiceName' created."
Write-Host "Run 'Start-Service $ServiceName' after validating config.json."
