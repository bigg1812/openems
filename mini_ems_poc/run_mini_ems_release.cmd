@echo off
setlocal

set "APP_DIR=%~dp0"
if "%APP_DIR:~-1%"=="\" set "APP_DIR=%APP_DIR:~0,-1%"

set "CONFIG_PATH=%~1"
if "%CONFIG_PATH%"=="" set "CONFIG_PATH=C:\ProgramData\MiniEMS\config.json"

for %%I in ("%CONFIG_PATH%") do set "SITE_DIR=%%~dpI"
if "%SITE_DIR:~-1%"=="\" set "SITE_DIR=%SITE_DIR:~0,-1%"

set "MINI_EMS_EXE=%APP_DIR%\mini_ems.exe"
set "LOG_DIR=%SITE_DIR%\logs"
set "STDOUT_LOG=%LOG_DIR%\mini_ems_stdout.log"

if not exist "%LOG_DIR%" mkdir "%LOG_DIR%"

if not exist "%MINI_EMS_EXE%" (
  echo [%DATE% %TIME%] mini_ems.exe not found at "%MINI_EMS_EXE%" >> "%STDOUT_LOG%"
  exit /b 1
)

if not exist "%CONFIG_PATH%" (
  echo [%DATE% %TIME%] config.json not found at "%CONFIG_PATH%" >> "%STDOUT_LOG%"
  exit /b 1
)

cd /d "%APP_DIR%"

:restart
echo [%DATE% %TIME%] Starting Mini EMS release runtime with "%CONFIG_PATH%" >> "%STDOUT_LOG%"
"%MINI_EMS_EXE%" ^
  --config "%CONFIG_PATH%" ^
  --loop >> "%STDOUT_LOG%" 2>&1

set "EXIT_CODE=%ERRORLEVEL%"
if "%EXIT_CODE%"=="0" exit /b 0

echo [%DATE% %TIME%] Mini EMS release runtime exited with code %EXIT_CODE%; restarting in 5 seconds >> "%STDOUT_LOG%"
timeout /t 5 /nobreak >nul
goto restart
