@echo off
rem run_all_checks.bat -- Windows wrapper that invokes the PowerShell script
rem Usage:
rem   run_all_checks.bat
rem   run_all_checks.bat -SkipBenchmarks
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0run_all_checks.ps1" %*
exit /b %ERRORLEVEL%
