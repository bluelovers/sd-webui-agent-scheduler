@echo off
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0pyrun.ps1" %*
set "RC=%ERRORLEVEL%"
if %RC% equ 9009 1>&2 echo [pyrun] powershell was not found on PATH, cannot launch pyrun.ps1.
exit /b %RC%
