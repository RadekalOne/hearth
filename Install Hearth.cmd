@echo off
setlocal
start "" /wait powershell.exe -NoProfile -ExecutionPolicy Bypass -STA -WindowStyle Hidden -File "%~dp0installer\windows\Install-Hearth.ps1"
