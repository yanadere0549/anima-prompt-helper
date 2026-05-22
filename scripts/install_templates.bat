@echo off
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0install_templates.ps1" %*
