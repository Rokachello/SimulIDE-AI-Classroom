@echo off
cd /d "%~dp0"
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0server\zazen-windows.ps1"
if errorlevel 1 echo Priprava ali zagon streznika ni uspel. Podrobnosti so v setup.log.
pause
