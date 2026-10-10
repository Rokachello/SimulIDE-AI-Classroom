@echo off
cd /d "%~dp0"
set SIMULIDE_DATA=%LOCALAPPDATA%\SimulIDE-AI-V0.2\classroom-data
"%LOCALAPPDATA%\SimulIDE-AI-V0.2\server-runtime312\python.exe" app.py backup
if errorlevel 1 echo Najprej pripravi streznik z ZAZENI-SERVER.cmd.
pause
