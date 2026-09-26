@echo off
setlocal
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0windows\package_menu.ps1" -PackagePath "%~dp0." %*
set "result=%ERRORLEVEL%"
if not defined CI pause
exit /b %result%
