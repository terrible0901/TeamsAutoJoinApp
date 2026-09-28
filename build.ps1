$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath $PSScriptRoot

$depsRoot = Join-Path $PSScriptRoot '.deps'
if (-not (Test-Path -LiteralPath $depsRoot)) {
    python -m pip install --target $depsRoot -r (Join-Path $PSScriptRoot 'requirements.txt')
    if ($LASTEXITCODE -ne 0) { throw 'Dependency installation failed.' }
}

$env:PYTHONPATH = @(
    $depsRoot,
    (Join-Path $depsRoot 'win32'),
    (Join-Path $depsRoot 'win32\lib'),
    (Join-Path $depsRoot 'pythonwin'),
    (Join-Path $depsRoot 'pywin32_system32')
) -join [IO.Path]::PathSeparator
$env:PATH = (Join-Path $depsRoot 'pywin32_system32') + [IO.Path]::PathSeparator + $env:PATH

python -m PyInstaller --noconfirm --clean --onedir --windowed `
    --name TeamsAutoJoin `
    --distpath release `
    --workpath .build-release `
    --paths $depsRoot `
    --paths (Join-Path $depsRoot 'win32') `
    --paths (Join-Path $depsRoot 'win32\lib') `
    --paths (Join-Path $depsRoot 'pythonwin') `
    --paths (Join-Path $depsRoot 'pywin32_system32') `
    --hidden-import pywinauto `
    --hidden-import pythoncom `
    --hidden-import win32crypt `
    --hidden-import win32gui `
    --hidden-import win32ui `
    --hidden-import win32con `
    --hidden-import six `
    --hidden-import comtypes.gen `
    main.py
if ($LASTEXITCODE -ne 0) { throw 'EXE build failed.' }

Write-Host "Output: $PSScriptRoot\release\TeamsAutoJoin\TeamsAutoJoin.exe"
