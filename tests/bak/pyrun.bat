@echo off
rem ============================================================================
rem pyrun.bat (legacy) - the original all-in-batch Python launcher.
rem
rem Superseded by pyrun.bat + pyrun.ps1 in the extension root and kept here
rem for reference only. Current usage, interpreter precedence and .env
rem handling are documented in pyrun.ps1.
rem ============================================================================
setlocal EnableExtensions DisableDelayedExpansion

if "%~1"=="" goto :usage

set "SCRIPT_DIR=%~dp0"
set "ENV_FILE=%SCRIPT_DIR%.env"
set "CACHE_FILE=%SCRIPT_DIR%.cache\webui-python.txt"

rem --- 1. Read .env (.env wins by default; PYRUN_DOTENV_OVERRIDE flips it) -----
call :init_dotenv_override
if exist "%ENV_FILE%" call :read_env

rem --- 2. Commands that only inspect the interpreter --------------------------
if /I "%~1"=="--which" goto :which
if /I "%~1"=="--refresh" goto :refresh

rem --- 3. Pick the interpreter, then run the requested python arguments -------
call :resolve_python
if not defined PY goto :uv_python
"%PY%" %*
exit /b %ERRORLEVEL%

rem ===========================================================================
rem Command handlers
rem ===========================================================================
:which
call :resolve_python
if not defined PY (
    1>&2 echo [pyrun] no webui venv found; uv's Python would be used as fallback.
    exit /b 1
)
rem Diagnostics go to stderr, stdout carries only the interpreter path.
1>&2 echo [pyrun] source: %PY_SOURCE%
1>&2 echo [pyrun] .env override: %DOTENV_APPLY% (1 = .env wins, 0 = existing env wins)
echo %PY%
exit /b 0

:refresh
set "REFRESH=1"
call :resolve_python
if not defined PY (
    1>&2 echo [pyrun] no webui venv found; uv's Python would be used as fallback.
    exit /b 1
)
1>&2 echo [pyrun] source: %PY_SOURCE%
1>&2 echo [pyrun] .env override: %DOTENV_APPLY% (1 = .env wins, 0 = existing env wins)
echo %PY%
exit /b 0

:usage
echo Usage: pyrun.bat [python arguments...]
echo        pyrun.bat --which     print the interpreter that would be used
echo        pyrun.bat --refresh   re-detect the interpreter and update the cache
echo Option: PYRUN_DOTENV_OVERRIDE=0 let existing env vars win over .env
echo         (default: .env overwrites them; accepts 0 / off / false / no)
echo Option: PYRUN_DATE_SOURCE=bat skip powershell and bash for the cache date
echo         (default ps: powershell, then bash, then %DATE%; see date_stamp.bat)
echo Example: pyrun.bat tests\run_tests.py
echo Example: pyrun.bat -m py_compile scripts\task_scheduler.py
exit /b 2

rem ===========================================================================
rem Interpreter resolution: WEBUI_PYTHON -^> .env -^> cache -^> upward search
rem ===========================================================================
:resolve_python
set "PY="
set "PY_SOURCE="

if defined WEBUI_PYTHON set "PY=%WEBUI_PYTHON%"
if defined PY if not exist "%PY%" (
    1>&2 echo [pyrun] WEBUI_PYTHON does not exist, ignoring it: %PY%
    set "PY="
    set "PY_SOURCE="
)
if defined PY (
    set "PY_SOURCE=WEBUI_PYTHON (process env or .env)"
    exit /b 0
)

rem The cache is only consulted when it was not explicitly invalidated.
if "%REFRESH%"=="1" goto :search_upward
call :read_cache
if defined PY (
    set "PY_SOURCE=cache (.cache\webui-python.txt)"
    exit /b 0
)

:search_upward
rem Start at this script's folder and walk up to the drive root.
for %%I in ("%SCRIPT_DIR%.") do set "CAND=%%~fI"

:search_up
rem webui.bat marks a webui root; only there do we look for an in-project venv.
if exist "%CAND%\webui.bat" goto :webui_root
for %%I in ("%CAND%\..") do set "NEXT=%%~fI"
if /I "%NEXT%"=="%CAND%" goto :no_webui_root
set "CAND=%NEXT%"
goto :search_up

:webui_root
rem Classic venv first, uv-style .venv second; require gradio in the same venv
rem so a tooling-only environment (e.g. one created only for ruff/black) is skipped.
if exist "%CAND%\venv\Scripts\python.exe" if exist "%CAND%\venv\Lib\site-packages\gradio" set "PY=%CAND%\venv\Scripts\python.exe"
if defined PY goto :cache_python
if exist "%CAND%\.venv\Scripts\python.exe" if exist "%CAND%\.venv\Lib\site-packages\gradio" set "PY=%CAND%\.venv\Scripts\python.exe"
if defined PY goto :cache_python
goto :no_webui_root

:cache_python
set "PY_SOURCE=search (webui root venv)"
call :get_today
rem No stamp means no trustworthy TTL: skip writing rather than store a cache
rem that could never expire correctly (the search is cheap either way).
if not defined TODAY exit /b 0
if not exist "%SCRIPT_DIR%.cache" mkdir "%SCRIPT_DIR%.cache"
rem Line 1 = date stamp (the one-day lifetime), line 2 = interpreter path.
>"%CACHE_FILE%" echo %TODAY%
>>"%CACHE_FILE%" echo %PY%
exit /b 0

rem ===========================================================================
rem Today's stamp (yyyyMMdd). Taken from date_stamp.bat, which tries
rem powershell, then bash, then %DATE%, so the value is a fixed ASCII string
rem whatever the locale and whatever is installed; all its tiers print the
rem same shape, so switching tiers never invalidates a fresh cache.
rem When date_stamp.bat is missing or fails, the very same %DATE% derivation
rem is repeated here as the last resort.
rem Called only when the cache is read or written: a run answered by
rem WEBUI_PYTHON never pays for the date (powershell alone costs ~300 ms).
rem ===========================================================================
:get_today
set "TODAY="
if exist "%SCRIPT_DIR%date_stamp.bat" (
    for /f "tokens=1" %%S in ('call "%SCRIPT_DIR%date_stamp.bat"') do if not defined TODAY set "TODAY=%%S"
)
if defined TODAY exit /b 0
rem %DATE% = "date weekday" or "weekday date": keep the first 10 characters
rem of the space-stripped value (drops the localized weekday wherever it is),
rem then the separators, to match date_stamp.bat tier 3. Every substitution is
rem guarded because cmd mangles expansions of empty variables.
set "TODAY=%date: =%"
if defined TODAY set "TODAY=%TODAY:~0,10%"
if defined TODAY set "TODAY=%TODAY:/=%"
if defined TODAY set "TODAY=%TODAY:-=%"
if defined TODAY set "TODAY=%TODAY:.=%"
exit /b 0

rem ===========================================================================
rem Cache reader: line 1 must be today's stamp, line 2 a path that still
rem exists. Anything else (missing file, old one-line format from a previous
rem version, expired stamp, deleted venv) leaves PY unset so the caller
rem redoes the upward search and rewrites the file; failures never break the
rem launcher, they only cost one search.
rem ===========================================================================
:read_cache
set "C_STAMP="
set "C_PY="
if not exist "%CACHE_FILE%" exit /b 0
for /f "usebackq delims=" %%L in ("%CACHE_FILE%") do (
    if defined C_STAMP (
        if not defined C_PY set "C_PY=%%L"
    ) else (
        set "C_STAMP=%%L"
    )
)
if not defined C_PY (
    1>&2 echo [pyrun] cache: no path recorded, rebuilding
    exit /b 0
)
call :get_today
if not defined TODAY exit /b 0
if not "%C_STAMP%"=="%TODAY%" (
    1>&2 echo [pyrun] cache expired: stamped "%C_STAMP%", today is "%TODAY%"
    exit /b 0
)
if not exist "%C_PY%" (
    1>&2 echo [pyrun] cache: path no longer exists, rebuilding
    exit /b 0
)
set "PY=%C_PY%"
exit /b 0

:no_webui_root
set "PY="
exit /b 0

rem ===========================================================================
rem uv's Python: only used when no webui venv could be found
rem ===========================================================================
:uv_python
echo [pyrun] no webui venv found, using uv's Python.
uv run --no-project python %*
set "RC=%ERRORLEVEL%"
if %RC% geq 9009 echo [pyrun] uv was not found on PATH. Install uv (https://astral.sh/uv) or set WEBUI_PYTHON in .env.
exit /b %RC%

rem ===========================================================================
rem .env reader: KEY=VALUE lines, "#" starts a comment, blank lines are skipped.
rem By default every key overwrites the environment (".env wins", the
rem python-dotenv override=True behaviour); when the caller opted out with
rem PYRUN_DOTENV_OVERRIDE=0 only keys that are still unset get applied
rem (override=False).
rem ===========================================================================
:read_env
for /f "usebackq eol=# tokens=1,* delims==" %%A in ("%ENV_FILE%") do (
    if not "%%A"=="" (
        if "%DOTENV_APPLY%"=="1" (
            set "%%A=%%B"
        ) else if not defined %%A (
            set "%%A=%%B"
        )
    )
)
exit /b 0

rem ===========================================================================
rem PYRUN_DOTENV_OVERRIDE: 1 (default) = .env wins, 0 = existing env wins.
rem Read from the process environment first, then from .env itself, so the
rem option can be set either way; accepted falsy spellings: 0 / off / false / no.
rem ===========================================================================
:init_dotenv_override
set "DOTENV_OVERRIDE_OPT="
if defined PYRUN_DOTENV_OVERRIDE set "DOTENV_OVERRIDE_OPT=%PYRUN_DOTENV_OVERRIDE%"
if not defined DOTENV_OVERRIDE_OPT if exist "%ENV_FILE%" (
    for /f "usebackq eol=# tokens=1,* delims==" %%A in ("%ENV_FILE%") do (
        if /I "%%A"=="PYRUN_DOTENV_OVERRIDE" set "DOTENV_OVERRIDE_OPT=%%B"
    )
)
set "DOTENV_APPLY=1"
if /I "%DOTENV_OVERRIDE_OPT%"=="0" set "DOTENV_APPLY=0"
if /I "%DOTENV_OVERRIDE_OPT%"=="off" set "DOTENV_APPLY=0"
if /I "%DOTENV_OVERRIDE_OPT%"=="false" set "DOTENV_APPLY=0"
if /I "%DOTENV_OVERRIDE_OPT%"=="no" set "DOTENV_APPLY=0"
exit /b 0
