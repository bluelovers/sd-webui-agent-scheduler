<#
.SYNOPSIS
    Standard Python launcher for this extension - the logic behind pyrun.bat.

.DESCRIPTION
    Picks the interpreter, reads .env, keeps a one-day cache and runs python:

        WEBUI_PYTHON (process env or .env)
            -> .cache\webui-python.txt (dated stamp, one calendar day)
            -> upward search for the webui root (webui.bat) and its venv
               (venv, then .venv; gradio must be present)
            -> uv's Python (uv run --no-project python ...)

    Options (first argument):
        --which     print the interpreter on stdout (diagnostics on stderr)
        --refresh   ignore the cache, re-detect and rewrite it
        (none)      print usage and exit 2

    Environment options:
        PYRUN_DOTENV_OVERRIDE=0 (also off / false / no)
            Existing environment variables win over .env instead of the
            default ".env wins" behaviour (python-dotenv override=True).
        PYRUN_DATE_SOURCE        No longer needed here: the date stamp is
            Get-Date -Format yyyyMMdd in-process, i.e. free.

    Why PowerShell: the previous implementation was a batch file. cmd's
    "call :label" search is unreliable in LF-only batch files once they grow
    (pyrun.bat itself started failing with "cannot find the batch label"),
    and cmd also mangles ":search=replace" expansions of empty variables.
    PowerShell parses scripts properly regardless of line endings and has
    none of the % / call / rem quirks, so this file is LF and self-contained.
    pyrun.bat stays as the thin entry point (no labels there either).

    ASCII-only on purpose: Windows PowerShell 5.1 reads a .ps1 without a BOM
    using the ANSI code page, so non-ASCII text could garble. The bilingual
    documentation lives in tests\README.md and AGENTS.md.
#>

$scriptDir = $PSScriptRoot
if ([string]::IsNullOrEmpty($scriptDir)) { $scriptDir = (Get-Location).Path }
$envFile = Join-Path $scriptDir '.env'
$cacheFile = Join-Path $scriptDir '.cache\webui-python.txt'

function Write-Diag {
    # Diagnostics always go to stderr so stdout stays machine-readable
    # (pyrun.bat --which prints only the interpreter path on stdout).
    param([string]$Message)
    [Console]::Error.WriteLine($Message)
}

if ($args.Count -eq 0) {
    Write-Output 'Usage: pyrun.bat [python arguments...]'
    Write-Output '       pyrun.bat --which     print the interpreter that would be used'
    Write-Output '       pyrun.bat --refresh   re-detect the interpreter and update the cache'
    Write-Output 'Option: PYRUN_DOTENV_OVERRIDE=0 let existing env vars win over .env'
    Write-Output '        (default: .env overwrites them; accepts 0 / off / false / no)'
    Write-Output 'Example: pyrun.bat tests\run_tests.py'
    Write-Output 'Example: pyrun.bat -m py_compile scripts\task_scheduler.py'
    exit 2
}

# ---------------------------------------------------------------------------
# .env: parsed here because Python itself never reads it. By default .env
# WINS over variables that already exist (python-dotenv override=True);
# PYRUN_DOTENV_OVERRIDE=0 flips that. The option is read from the process
# environment first, then from .env itself.
# ---------------------------------------------------------------------------
$overrideRaw = [Environment]::GetEnvironmentVariable('PYRUN_DOTENV_OVERRIDE')
if ([string]::IsNullOrWhiteSpace($overrideRaw) -and (Test-Path -LiteralPath $envFile)) {
    $overrideLine = Get-Content -LiteralPath $envFile |
        Where-Object { $_ -match '^\s*PYRUN_DOTENV_OVERRIDE\s*=' } |
        Select-Object -First 1
    if ($overrideLine) { $overrideRaw = ($overrideLine -split '=', 2)[1].Trim() }
}
$dotenvOverride = -not ($overrideRaw -match '^(0|off|false|no)$')

if (Test-Path -LiteralPath $envFile) {
    foreach ($line in (Get-Content -LiteralPath $envFile)) {
        # Comments, blank lines and lines without '=' are skipped; only the
        # first '=' separates key from value, so values may contain '='.
        if ($line -notmatch '^\s*[^#=][^=]*=') { continue }
        $idx = $line.IndexOf('=')
        $key = $line.Substring(0, $idx).Trim()
        if ([string]::IsNullOrEmpty($key)) { continue }
        $alreadySet = [bool][Environment]::GetEnvironmentVariable($key)
        if ($dotenvOverride -or -not $alreadySet) {
            Set-Item -LiteralPath "Env:$key" -Value $line.Substring($idx + 1)
        }
    }
}

# ---------------------------------------------------------------------------
# Interpreter resolution
# ---------------------------------------------------------------------------
function Resolve-Interpreter {
    $today = Get-Date -Format 'yyyyMMdd'

    # 1) explicit override, from the environment or from .env
    if ($env:WEBUI_PYTHON) {
        if (Test-Path -LiteralPath $env:WEBUI_PYTHON) {
            return @{ Path = $env:WEBUI_PYTHON; Source = 'WEBUI_PYTHON (process env or .env)' }
        }
        Write-Diag "[pyrun] WEBUI_PYTHON does not exist, ignoring it: $($env:WEBUI_PYTHON)"
    }

    # 2) cache: line 1 must be today's stamp, line 2 a path that still exists
    if (-not $refresh -and (Test-Path -LiteralPath $cacheFile)) {
        $lines = @(Get-Content -LiteralPath $cacheFile)
        $stamp = ''
        $cached = ''
        if ($lines.Count -ge 1) { $stamp = $lines[0].Trim() }
        if ($lines.Count -ge 2) { $cached = $lines[1].Trim() }
        if ([string]::IsNullOrEmpty($cached)) {
            Write-Diag '[pyrun] cache: no path recorded, rebuilding'
        } elseif ($stamp -ne $today) {
            Write-Diag "[pyrun] cache expired: stamped `"$stamp`", today is `"$today`""
        } elseif (-not (Test-Path -LiteralPath $cached)) {
            Write-Diag '[pyrun] cache: path no longer exists, rebuilding'
        } else {
            return @{ Path = $cached; Source = 'cache (.cache\webui-python.txt)' }
        }
    }

    # 3) walk up to the webui root, then take its in-project venv. gradio must
    #    be present so a tooling-only environment is never picked.
    $dir = $scriptDir
    while ($true) {
        if (Test-Path -LiteralPath (Join-Path $dir 'webui.bat')) { break }
        $parent = Split-Path -Path $dir -Parent
        if ([string]::IsNullOrEmpty($parent) -or $parent -eq $dir) { $dir = $null; break }
        $dir = $parent
    }
    if ($dir) {
        foreach ($venv in @('venv', '.venv')) {
            $candidate = Join-Path $dir (Join-Path $venv 'Scripts\python.exe')
            $gradio = Join-Path $dir (Join-Path $venv 'Lib\site-packages\gradio')
            if ((Test-Path -LiteralPath $candidate) -and (Test-Path -LiteralPath $gradio)) {
                $null = New-Item -ItemType Directory -Force -Path (Split-Path -Path $cacheFile -Parent) -ErrorAction SilentlyContinue
                Set-Content -LiteralPath $cacheFile -Value @($today, $candidate)
                return @{ Path = $candidate; Source = 'search (webui root venv)' }
            }
        }
    }

    return $null
}

$refresh = $false
$action = 'run'
if ($args[0] -eq '--which') { $action = 'which' }
elseif ($args[0] -eq '--refresh') { $action = 'refresh'; $refresh = $true }

$resolved = Resolve-Interpreter

if ($null -eq $resolved) {
    Write-Diag "[pyrun] no webui venv found, using uv's Python."
    if (-not (Get-Command uv -ErrorAction SilentlyContinue)) {
        Write-Diag '[pyrun] uv was not found on PATH. Install uv (https://astral.sh/uv) or set WEBUI_PYTHON in .env.'
        exit 1
    }
    & uv run --no-project python @args
    exit $LASTEXITCODE
}

if ($action -eq 'which' -or $action -eq 'refresh') {
    Write-Diag "[pyrun] source: $($resolved.Source)"
    $mode = if ($dotenvOverride) { '1' } else { '0' }
    Write-Diag "[pyrun] .env override: $mode (1 = .env wins, 0 = existing env wins)"
    Write-Output $resolved.Path
    exit 0
}

& $resolved.Path @args
exit $LASTEXITCODE
