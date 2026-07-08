param(
    [ValidateSet("checkout", "release")]
    [string]$Mode = "checkout",
    [string]$TaskName = "",
    [string]$ProjectDir = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path,
    [string]$PythonPath = "python",
    [string]$AppDir = "C:\Program Files\MiniEMS",
    [string]$ConfigPath = "C:\ProgramData\MiniEMS\config.json",
    [string]$LauncherPath = "",
    [bool]$StartNow = $true
)

$ErrorActionPreference = "Stop"

function Resolve-ExecutablePath {
    param(
        [Parameter(Mandatory = $true)]
        [string]$PathOrCommand
    )

    if (Test-Path $PathOrCommand) {
        return (Resolve-Path $PathOrCommand).Path
    }

    $command = Get-Command $PathOrCommand -ErrorAction SilentlyContinue
    if ($null -ne $command) {
        return $command.Source
    }

    throw "Executable not found: $PathOrCommand"
}

if (-not $TaskName) {
    if ($Mode -eq "release") {
        $TaskName = "MiniEmsPoCRelease"
    } else {
        $TaskName = "MiniEmsPoC"
    }
}

try {
    if ($Mode -eq "release") {
        if (-not $LauncherPath) {
            $LauncherPath = Join-Path $AppDir "run_mini_ems_release.cmd"
        }
        $exePath = Join-Path $AppDir "mini_ems.exe"

        if (-not (Test-Path $LauncherPath)) {
            throw "Release launcher not found at $LauncherPath"
        }
        if (-not (Test-Path $exePath)) {
            throw "mini_ems.exe not found at $exePath"
        }
        if (-not (Test-Path $ConfigPath)) {
            throw "Config file not found at $ConfigPath"
        }
        if (-not (Test-Path $AppDir)) {
            throw "App directory not found at $AppDir"
        }

        $cmdPath = (Resolve-Path $LauncherPath).Path
        $workingDirectory = (Resolve-Path $AppDir).Path
        $actionArgument = "/c `"`"$cmdPath`" `"$ConfigPath`"`""
        Write-Host "Installing release task '$TaskName'"
        Write-Host "  launcher : $cmdPath"
        Write-Host "  config   : $ConfigPath"
    } else {
        $cmdPath = Join-Path $ProjectDir "run_mini_ems.cmd"
        $venvDir = Join-Path $ProjectDir ".venv"
        $venvPython = Join-Path $venvDir "Scripts\python.exe"

        if (-not (Test-Path $cmdPath)) {
            throw "run_mini_ems.cmd not found at $cmdPath"
        }

        $resolvedPython = Resolve-ExecutablePath $PythonPath

        if (-not (Test-Path $venvPython)) {
            Write-Host "Creating project venv at $venvDir"
            & $resolvedPython -m venv --clear $venvDir
        }

        if (-not (Test-Path $venvPython)) {
            throw "Project venv was not created at $venvPython"
        }

        $cmdPath = (Resolve-Path $cmdPath).Path
        $workingDirectory = (Resolve-Path $ProjectDir).Path
        $actionArgument = "/c `"`"$cmdPath`"`""
        Write-Host "Installing checkout task '$TaskName'"
        Write-Host "  launcher : $cmdPath"
        Write-Host "  python   : $resolvedPython"
    }

    $action = New-ScheduledTaskAction `
        -Execute "cmd.exe" `
        -Argument $actionArgument `
        -WorkingDirectory $workingDirectory

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

    if ($StartNow) {
        Write-Host "Scheduled task '$TaskName' created and started."
    } else {
        Write-Host "Scheduled task '$TaskName' created. Start it with: Start-ScheduledTask -TaskName `"$TaskName`""
    }
} catch {
    throw "Failed to install scheduled task '$TaskName'. Run PowerShell as Administrator. $($_.Exception.Message)"
}
