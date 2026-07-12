@echo off
setlocal

set "APP_DIR=%~dp0"
if "%APP_DIR:~-1%"=="\" set "APP_DIR=%APP_DIR:~0,-1%"

set "SITE_DIR=%~1"
if "%SITE_DIR%"=="" set "SITE_DIR=C:\ProgramData\MiniEMS"

rem Upgrade-Kompatibilitaet: Der bisher registrierte Task uebergibt als erstes
rem Argument noch C:\ProgramData\MiniEMS\config.json. Fuer genau diesen alten
rem Aufruf wird einmalig nur der Elternordner als neuer Standortordner genutzt.
if /I "%~x1"==".json" (
  for %%I in ("%~1") do set "SITE_DIR=%%~dpI"
)
if "%SITE_DIR:~-1%"=="\" set "SITE_DIR=%SITE_DIR:~0,-1%"

set "MINI_EMS_EXE=%APP_DIR%\mini_ems.exe"
set "LOG_DIR=%SITE_DIR%\logs"
set "STDOUT_LOG=%LOG_DIR%\mini_ems_stdout.log"

if not exist "%LOG_DIR%" mkdir "%LOG_DIR%"

if not exist "%MINI_EMS_EXE%" (
  echo [%DATE% %TIME%] mini_ems.exe not found at "%MINI_EMS_EXE%" >> "%STDOUT_LOG%"
  exit /b 1
)

cd /d "%APP_DIR%"

:restart
echo [%DATE% %TIME%] Starting Mini EMS release runtime with site dir "%SITE_DIR%" >> "%STDOUT_LOG%"
"%MINI_EMS_EXE%" ^
  --site-dir "%SITE_DIR%" ^
  --loop >> "%STDOUT_LOG%" 2>&1

set "EXIT_CODE=%ERRORLEVEL%"
if "%EXIT_CODE%"=="0" exit /b 0

echo [%DATE% %TIME%] Mini EMS release runtime exited with code %EXIT_CODE%; restarting in 5 seconds >> "%STDOUT_LOG%"
timeout /t 5 /nobreak >nul
goto restart
