@echo off
cd /d "%~dp0"
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\review-windows.ps1"
if errorlevel 1 (
  echo Pregled ni uspel. Podrobnosti so v setup.log. Zascite ne izklapljaj.
  pause
  exit /b 1
)
pause
