$ErrorActionPreference = "Stop"

$Root = Resolve-Path (Join-Path $PSScriptRoot "..")
$BackendDist = Join-Path $Root "dist\backend"
$PlaywrightDist = Join-Path $Root "dist\ms-playwright"

Set-Location $Root

if (Get-Command python -ErrorAction SilentlyContinue) {
    $PythonCommand = "python"
} elseif (Get-Command py -ErrorAction SilentlyContinue) {
    $PythonCommand = "py"
} else {
    throw "Python was not found. Install Python 3 or make python/py available on PATH."
}

function Invoke-Python {
    if ($PythonCommand -eq "py") {
        & py -3 @args
    } else {
        & $PythonCommand @args
    }

    if ($LASTEXITCODE -ne 0) {
        throw "Python command failed with exit code ${LASTEXITCODE}: $PythonCommand $args"
    }
}

Invoke-Python -m pip install --upgrade pip
Invoke-Python -m pip install -r "backend\requirements.txt"
Invoke-Python -m pip install pyinstaller

$env:PLAYWRIGHT_BROWSERS_PATH = $PlaywrightDist
Invoke-Python -m playwright install chromium

if (Test-Path $BackendDist) {
    Remove-Item $BackendDist -Recurse -Force
}

Invoke-Python -m PyInstaller "packaging\backend\backend.spec" --noconfirm --clean

Write-Host "Backend built at $BackendDist"
Write-Host "Playwright browsers installed at $PlaywrightDist"
