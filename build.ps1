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

$previousDiagFile = $env:TEAMS_AUTOJOIN_DIAG_FILE
try {
    $env:TEAMS_AUTOJOIN_DIAG_FILE = Join-Path $PSScriptRoot ('.build-release\self-test-' + [guid]::NewGuid().ToString('N') + '.txt')
    $check = Start-Process -FilePath (Join-Path $PSScriptRoot 'release\TeamsAutoJoin\TeamsAutoJoin.exe') `
        -ArgumentList '--self-test' -WindowStyle Hidden -PassThru
    if (-not $check.WaitForExit(30000)) {
        Stop-Process -Id $check.Id
        throw 'Packaged EXE self-test timed out. The build is not ready to use.'
    }
    $check.Refresh()
    if ($check.ExitCode -ne 0 -or -not (Test-Path -LiteralPath $env:TEAMS_AUTOJOIN_DIAG_FILE)) {
        throw "Packaged EXE self-test failed. Check $env:TEAMS_AUTOJOIN_DIAG_FILE"
    }
    if ((Get-Content -LiteralPath $env:TEAMS_AUTOJOIN_DIAG_FILE -Raw).Trim() -ne 'OK') {
        throw "Packaged EXE self-test failed. Check $env:TEAMS_AUTOJOIN_DIAG_FILE"
    }
} finally {
    $env:TEAMS_AUTOJOIN_DIAG_FILE = $previousDiagFile
}

Write-Host "Output: $PSScriptRoot\release\TeamsAutoJoin\TeamsAutoJoin.exe"
