@echo off
title Tape
cd /d "%~dp0"
if not exist "tape\__main__.py" goto notunzipped
powershell -NoProfile -ExecutionPolicy Bypass -File "launcher\start.ps1"
if errorlevel 1 pause
exit /b

:notunzipped
echo.
echo   Tape needs to be unzipped before it can run.
echo.
echo   1. Close this window.
echo   2. Right-click the Tape zip file and choose "Extract All".
echo   3. Open the new Tape folder and double-click "Start Tape" again.
echo.
pause
