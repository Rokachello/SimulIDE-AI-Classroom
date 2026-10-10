@echo off
cd /d "%~dp0"
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0zazen-windows.ps1"
if errorlevel 1 echo Priprava ali zagon streznika ni uspel.
pause
