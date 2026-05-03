$ErrorActionPreference = "Stop"

$Root = Resolve-Path (Join-Path $PSScriptRoot "..")
$BackendDist = Join-Path $Root "dist\backend"
$PlaywrightDist = Join-Path $Root "dist\ms-playwright"

Set-Location $Root

python -m pip install -r "backend\requirements.txt"
python -m pip install pyinstaller

$env:PLAYWRIGHT_BROWSERS_PATH = $PlaywrightDist
python -m playwright install chromium

if (Test-Path $BackendDist) {
    Remove-Item $BackendDist -Recurse -Force
}

pyinstaller "packaging\backend\backend.spec" --noconfirm --clean

Write-Host "Backend built at $BackendDist"
Write-Host "Playwright browsers installed at $PlaywrightDist"
