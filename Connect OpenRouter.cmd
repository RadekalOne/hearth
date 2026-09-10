@echo off
setlocal
start "" /wait powershell.exe -NoProfile -ExecutionPolicy Bypass -STA -WindowStyle Hidden -File "%~dp0installer\windows\Connect-OpenRouter.ps1"
