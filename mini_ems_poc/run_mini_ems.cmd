@echo off
setlocal
set "PROJECT_DIR=%~dp0"
if "%PROJECT_DIR:~-1%"=="\" set "PROJECT_DIR=%PROJECT_DIR:~0,-1%"
cd /d "%PROJECT_DIR%"

if not exist "%PROJECT_DIR%\logs" mkdir "%PROJECT_DIR%\logs"

set "MINI_EMS_PYTHON=%PROJECT_DIR%\.venv\Scripts\python.exe"

if not exist "%MINI_EMS_PYTHON%" (
  echo Python executable not found at "%MINI_EMS_PYTHON%" >> "%PROJECT_DIR%\logs\mini_ems_stdout.log"
  exit /b 1
)

:restart
echo [%DATE% %TIME%] Starting Mini EMS runtime >> "%PROJECT_DIR%\logs\mini_ems_stdout.log"
"%MINI_EMS_PYTHON%" ^
  "%PROJECT_DIR%\mini_ems.py" ^
  --config "%PROJECT_DIR%\config.json" ^
  --loop >> "%PROJECT_DIR%\logs\mini_ems_stdout.log" 2>&1

set "EXIT_CODE=%ERRORLEVEL%"
if "%EXIT_CODE%"=="0" exit /b 0

echo [%DATE% %TIME%] Mini EMS runtime exited with code %EXIT_CODE%; restarting in 5 seconds >> "%PROJECT_DIR%\logs\mini_ems_stdout.log"
timeout /t 5 /nobreak >nul
goto restart
