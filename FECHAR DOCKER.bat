@echo off
title Fechar Docker
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0fechar-docker.ps1"
echo.
pause
