param(
    [string]$TaskName = "MiniEmsPoC",
    [string]$ProjectDir = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path,
    [string]$PythonPath = "C:\Users\ENGIE_NL_STUTTGART\AppData\Local\Programs\Python\Python312\python.exe",
    [bool]$StartNow = $true
)

$ErrorActionPreference = "Stop"

$cmdPath = Join-Path $ProjectDir "run_mini_ems.cmd"
$venvDir = Join-Path $ProjectDir ".venv"
$venvPython = Join-Path $venvDir "Scripts\python.exe"

if (-not (Test-Path $cmdPath)) {
    throw "run_mini_ems.cmd not found at $cmdPath"
}

try {
    if (-not (Test-Path $PythonPath)) {
        throw "Python executable not found at $PythonPath"
    }

    if (-not (Test-Path $venvPython)) {
        Write-Host "Creating project venv at $venvDir"
        & $PythonPath -m venv --clear $venvDir
    }

    if (-not (Test-Path $venvPython)) {
        throw "Project venv was not created at $venvPython"
    }

    $action = New-ScheduledTaskAction `
        -Execute "cmd.exe" `
        -Argument "/c `"$cmdPath`"" `
        -WorkingDirectory $ProjectDir

    $trigger = New-ScheduledTaskTrigger -AtStartup

    $principal = New-ScheduledTaskPrincipal `
        -UserId "NT AUTHORITY\SYSTEM" `
        -LogonType ServiceAccount `
        -RunLevel Highest

    $settings = New-ScheduledTaskSettingsSet `
        -StartWhenAvailable `
        -MultipleInstances IgnoreNew `
        -RestartCount 999 `
        -RestartInterval (New-TimeSpan -Minutes 1) `
        -AllowStartIfOnBatteries `
        -DontStopIfGoingOnBatteries `
        -ExecutionTimeLimit ([TimeSpan]::Zero)

    Register-ScheduledTask `
        -TaskName $TaskName `
        -Action $action `
        -Trigger $trigger `
        -Principal $principal `
        -Settings $settings `
        -Force | Out-Null

    if ($StartNow) {
        Start-ScheduledTask -TaskName $TaskName
    }

    Get-ScheduledTask -TaskName $TaskName | Select-Object TaskName,State | Format-Table -AutoSize
    Get-ScheduledTaskInfo -TaskName $TaskName | Select-Object LastRunTime,LastTaskResult,NextRunTime,NumberOfMissedRuns | Format-List

    Write-Host "Scheduled task '$TaskName' created and started."
} catch {
    throw "Failed to install scheduled task '$TaskName'. Run PowerShell as Administrator. $($_.Exception.Message)"
}
