@echo off
cd /d "%~dp0"
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\zazeni.ps1"
if errorlevel 1 (
  echo Zagon ni uspel. Podrobnosti so v setup.log.
  pause
  exit /b 1
)
