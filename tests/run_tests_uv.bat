@echo off
rem ============================================================================
rem run_tests_uv.bat - Run the test suite from the extension root.
rem
rem Usage:
rem     tests\run_tests_uv.bat
rem     Also works double-clicked, or called from any working directory.
rem
rem This file only switches to the extension root and calls pyrun.bat.
rem Interpreter selection lives in pyrun.ps1, test details in tests\README.md.
rem Exit code: 0 = all passed, non-zero = a failure.
rem ============================================================================

setlocal

rem Switch to the extension root (this file lives in tests\).
pushd "%~dp0.."

call pyrun.bat tests\run_tests.py

rem Capture the launcher's exit code (the test result) before popd.
set "RC=%ERRORLEVEL%"
popd
endlocal & exit /b %RC%
