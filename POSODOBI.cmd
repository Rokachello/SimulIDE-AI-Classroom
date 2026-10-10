@echo off
cd /d "%~dp0"
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\posodobi.ps1"
if errorlevel 1 (
  echo Posodobitev ali gradnja ni uspela. Podrobnosti so v setup.log.
  pause
  exit /b 1
)
echo Posodobitev in gradnja sta koncani. Za odpiranje uporabi ZAZENI.cmd.
pause
