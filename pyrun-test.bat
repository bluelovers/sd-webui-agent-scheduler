@echo off
setlocal
pushd "%~dp0"
call "%~dp0pyrun.bat" "%~dp0tests/run_tests.py" %*
set "RC=%ERRORLEVEL%"
popd
endlocal & exit /b %RC%
