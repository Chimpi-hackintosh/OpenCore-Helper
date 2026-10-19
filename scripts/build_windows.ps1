$ErrorActionPreference = 'Stop'
$taskRoot = Split-Path -Parent $PSScriptRoot
Set-Location $taskRoot
if (-not (Test-Path '.venv/Scripts/python.exe')) {
    py -3.12 -m venv .venv
    if ($LASTEXITCODE -ne 0) { throw 'Could not create Python environment' }
}
$taskPython = Join-Path $taskRoot '.venv/Scripts/python.exe'
& $taskPython -m pip install -r requirements-dev.txt
if ($LASTEXITCODE -ne 0) { throw 'Dependency installation failed' }
& $taskPython -m pytest -q
if ($LASTEXITCODE -ne 0) { throw 'Tests failed' }
& $taskPython scripts/build_windows.py @args
if ($LASTEXITCODE -ne 0) { throw 'Build failed' }
