@echo off
rem ============================================================================
rem date_stamp.bat - Stable ASCII date stamp: yyyyMMdd (e.g. 20261010).
rem
rem Usage:
rem     date_stamp.bat              print the stamp on stdout, nothing else
rem     date_stamp.bat --verbose    also report the winning tier on stderr
rem
rem Tiers, first usable hit wins:
rem     1. powershell -NoProfile -Command "Get-Date -Format yyyyMMdd"
rem     2. bash -c "date --iso-8601"   (dashes are stripped afterwards)
rem     3. cmd's own %DATE%            (no external command, always present)
rem PYRUN_DATE_SOURCE=bash or bat starts the chain later (ps = full chain,
rem the default); unknown values keep the default.
rem
rem Failure safety - a missing command or a broken shell costs only the next
rem tier, never an abort:
rem     1. every tier's output is captured TOGETHER with stderr (2^>^&1) and is
rem        accepted only after validation, so error text such as "'powershell'
rem        is not recognized ..." is dropped instead of leaking into the stamp
rem        or onto stdout;
rem     2. validation means: exactly 8 characters, all of them digits. Anything
rem        else (empty output, a localized date, a stack trace) is rejected;
rem     3. tier 3 takes %DATE%, keeps its first 10 characters (this drops the
rem        localized weekday wherever it sits) and removes the separators, so
rem        it still yields yyyyMMdd on the common locale formats;
rem     4. nothing is ever redirected to NUL; diagnostics go to stderr only
rem        with --verbose (plus one line when every tier failed).
rem All three tiers print the same yyyyMMdd shape, so switching tiers between
rem runs does not invalidate yesterday's cache stamp.
rem
rem Design notes: this file is ASCII-only and carries no redirection
rem characters on rem lines - cmd decodes a .bat with the OEM code page
rem (cp950 / GBK) and parses rem lines too.
rem ============================================================================
setlocal EnableExtensions DisableDelayedExpansion

set "VERBOSE="
if /I "%~1"=="--verbose" set "VERBOSE=1"

rem Source selection: ps (default) keeps the full chain, bash / bat skip tiers.
set "SRC=ps"
if /I "%PYRUN_DATE_SOURCE%"=="bash" set "SRC=bash"
if /I "%PYRUN_DATE_SOURCE%"=="bat" set "SRC=bat"

set "STAMP="
set "TIER="

if /I "%SRC%"=="bat" goto :tier_bat
if /I "%SRC%"=="bash" goto :tier_bash

rem --- Tier 1: PowerShell (fixed format, locale independent) -----------------
rem stderr is merged into stdout on purpose: the validator then throws away
rem any error line, so a missing or blocked powershell is silent and harmless.
for /f "tokens=1" %%S in ('powershell -NoProfile -Command "Get-Date -Format yyyyMMdd" 2^>^&1') do call :accept_8 "%%S"
if defined STAMP (
    set "TIER=powershell"
    goto :report
)
if defined VERBOSE 1>&2 echo [date_stamp] tier 1 powershell failed or missing

:tier_bash
for /f "tokens=1" %%S in ('bash -c "date --iso-8601" 2^>^&1') do call :accept_iso "%%S"
if defined STAMP (
    set "TIER=bash"
    goto :report
)
if defined VERBOSE 1>&2 echo [date_stamp] tier 2 bash failed or missing

:tier_bat
call :from_pct_date
if defined STAMP (
    set "TIER=cmd %DATE%"
    goto :report
)
rem Unreachable in practice: %DATE% always exists. Kept as a safety net.
1>&2 echo [date_stamp] no date source produced a usable stamp
exit /b 1

:report
if defined VERBOSE 1>&2 echo [date_stamp] tier: %TIER% -^> %STAMP%
echo %STAMP%
exit /b 0

rem ===========================================================================
rem Validators: every candidate goes through :validate, which accepts only an
rem exactly-8-digit token. STAMP is written once, by the first tier to pass.
rem ===========================================================================
:accept_8
set "CAND=%~1"
goto :validate

:accept_iso
rem ISO date (yyyy-mm-dd): drop the dashes, then use the same validation.
set "CAND=%~1"
set "CAND=%CAND:-=%"
goto :validate

:validate
if defined STAMP exit /b 0
if "%CAND%"=="" exit /b 0
rem Length must be exactly 8: no tail beyond 8 chars, and 8 chars must cover it.
if not "%CAND:~8%"=="" exit /b 0
if not "%CAND:~0,8%"=="%CAND%" exit /b 0
rem Every character must be a digit. Each substitution is guarded: cmd mangles
rem a ":search=replace" expansion of an EMPTY variable (it would leave junk
rem such as "7=" behind), which would reject a perfectly valid stamp as soon
rem as the residue became empty halfway through the chain.
set "S=%CAND%"
if defined S set "S=%S:0=%"
if defined S set "S=%S:1=%"
if defined S set "S=%S:2=%"
if defined S set "S=%S:3=%"
if defined S set "S=%S:4=%"
if defined S set "S=%S:5=%"
if defined S set "S=%S:6=%"
if defined S set "S=%S:7=%"
if defined S set "S=%S:8=%"
if defined S set "S=%S:9=%"
if defined S exit /b 0
set "STAMP=%CAND%"
exit /b 0

rem ===========================================================================
rem Tier 3: derive yyyyMMdd from %DATE%. The weekday (localized, possibly
rem non-ASCII) sits either before or after the date, so keeping the first 10
rem characters of the space-stripped value always keeps a part that changes
rem daily, and removing the separators turns yyyy/M/d into yyyyMMdd.
rem ===========================================================================
:from_pct_date
set "CAND=%date: =%"
if defined CAND set "CAND=%CAND:~0,10%"
if defined CAND set "CAND=%CAND:/=%"
if defined CAND set "CAND=%CAND:-=%"
if defined CAND set "CAND=%CAND:.=%"
call :validate
rem Last resort: a locale whose %DATE% does not reduce to 8 digits still gets
rem a daily-changing string rather than no stamp at all (TTL stays correct,
rem the interpreter path check keeps guarding a moved venv).
if not defined STAMP set "STAMP=%CAND%"
exit /b 0
