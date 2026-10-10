@echo off
rem ============================================================================
rem run_tests_uv.bat - Run the Agent Scheduler test suite through uv.
rem
rem Usage:
rem     tests\run_tests_uv.bat
rem     It can also be double-clicked, or called from any working directory by
rem     its full path; it switches to the extension root by itself.
rem
rem Environment variables:
rem     WEBUI_PYTHON             Optional explicit interpreter; when set it wins
rem                               over the automatic search below.
rem     AGENT_SCHEDULER_TEST_DIR Directory for test artifacts (default: system temp).
rem
rem How the interpreter is found (no hard-coded absolute paths):
rem     1. WEBUI_PYTHON, if defined.
rem     2. Walk upward from this extension folder until a directory that contains
rem        webui.bat is found - the webui root hosting this extension - and take
rem        its in-project virtual environment: venv\Scripts\python.exe first,
rem        .venv\Scripts\python.exe second. Only a venv that provides gradio is
rem        accepted, so a tooling-only venv next to the real one is never picked.
rem     3. Otherwise let uv use its own Python.
rem
rem Design notes:
rem     1. The unit tests only need the Python standard library: gradio and the
rem        sd-webui runtime are NOT required. The logger used by the tested modules
rem        lives in agent_scheduler\log.py (standard library only) instead of
rem        helpers.py, which is what keeps them importable without webui.
rem        A webui venv is still preferred when it can be found, so the suite runs
rem        under the same interpreter as the app; otherwise uv's own Python is used.
rem     2. uv only selects the interpreter and runs the suite. In --no-project mode
rem        it installs nothing and writes no .venv / uv.lock into the repo, so the
rem        git status stays clean. --no-sync is omitted on purpose: alongside
rem        --no-project it only produces a "has no effect" warning.
rem     3. The exit code is the test result: 0 = all passed, 1 = a failure or an
rem        unusable environment.
rem     4. This file is ASCII-only on purpose. cmd decodes a batch file with the
rem        OEM code page (cp950 / GBK here), so UTF-8 Chinese in comments would
rem        garble the console and can even make cmd mis-parse the lines. The
rem        bilingual documentation lives in tests\README.md and AGENTS.md.
rem     5. Keep redirection characters (angle brackets, pipes) out of rem lines:
rem        cmd parses them even on comment lines and would create stray files.
rem ============================================================================

setlocal

rem Switch to the extension root (this file lives in tests\), so it works both
rem when double-clicked and from any working directory.
pushd "%~dp0.."

rem --- 1. Make sure uv is available --------------------------------------------
where uv >nul 2>&1
if errorlevel 1 goto :no_uv

rem --- 2. Pick the interpreter ---------------------------------------------------
rem Precedence: WEBUI_PYTHON, then an upward search, then uv's own Python.
set "PY=%WEBUI_PYTHON%"
if defined PY goto :py_ready

rem Start at the extension root and walk up to the drive root.
for %%I in ("%~dp0..") do set "CAND=%%~fI"

:search_up
rem webui.bat marks a webui root; only there do we look for an in-project venv.
if exist "%CAND%\webui.bat" goto :webui_root
for %%I in ("%CAND%\..") do set "NEXT=%%~fI"
if /I "%NEXT%"=="%CAND%" goto :use_uv_python
set "CAND=%NEXT%"
goto :search_up

:webui_root
rem Classic venv first, uv-style .venv second; require gradio in the same venv so
rem a tooling-only environment (e.g. one created only for ruff/black) is skipped.
if exist "%CAND%\venv\Scripts\python.exe" if exist "%CAND%\venv\Lib\site-packages\gradio" set "PY=%CAND%\venv\Scripts\python.exe"
if defined PY goto :py_ready
if exist "%CAND%\.venv\Scripts\python.exe" if exist "%CAND%\.venv\Lib\site-packages\gradio" set "PY=%CAND%\.venv\Scripts\python.exe"
if defined PY goto :py_ready
goto :use_uv_python

:use_uv_python
rem The suite is standard-library-only, so any Python will do when no webui venv
rem can be found (first run on a fresh machine, or a bare checkout).
echo [run-tests] no webui venv found, using uv's own Python.
uv run --no-project tests\run_tests.py
goto :done

:py_ready
if not exist "%PY%" goto :bad_interpreter
rem Capture uv's exit code (the test result) before popd.
echo [run-tests] interpreter: %PY%
uv run --no-project --python "%PY%" tests\run_tests.py

:done
set "RC=%ERRORLEVEL%"
popd
endlocal & exit /b %RC%

:no_uv
echo [run-tests] ERROR: uv was not found on PATH.
echo             Get it from https://astral.sh/uv, then re-run this script.
popd
endlocal & exit /b 1

:bad_interpreter
echo [run-tests] ERROR: WEBUI_PYTHON does not exist:
echo             %PY%
popd
endlocal & exit /b 1
