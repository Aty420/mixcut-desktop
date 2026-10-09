param([switch]$SkipInstall)
$ErrorActionPreference = 'Stop'
Set-Location (Split-Path $PSScriptRoot -Parent)
if (-not $IsWindows -and $env:OS -ne 'Windows_NT') { throw 'Build this package on Windows.' }

function Check-Exit([string]$Step) {
    if ($LASTEXITCODE -ne 0) { throw "$Step failed (exit $LASTEXITCODE)." }
}

if (-not $SkipInstall) {
    python -m pip install -r requirements-build.txt
    Check-Exit 'Install dependencies'
}
python -m unittest discover -s tests -v
Check-Exit 'Source tests'
python -m PyInstaller --noconfirm --clean --windowed --onedir --name MixCut --collect-all imageio_ffmpeg --copy-metadata imageio-ffmpeg main.py
Check-Exit 'PyInstaller'

Copy-Item README.md, USER_GUIDE.md, THIRD_PARTY.md, LICENSE -Destination dist/MixCut
python scripts/collect_notices.py
Check-Exit 'Collect dependency notices'

# Windowed EXEs cannot reliably stream console output; verify explicit result files.
$report = Join-Path (Get-Location) 'smoke-engine.json'
Remove-Item $report -ErrorAction SilentlyContinue
$engine = Start-Process -FilePath dist/MixCut/MixCut.exe -ArgumentList @('--self-test', ('"' + $report + '"')) -PassThru
if (-not $engine.WaitForExit(180000)) { $engine.Kill(); throw 'Packaged engine test timed out.' }
if ($engine.ExitCode -ne 0 -or -not (Test-Path $report)) { throw 'Packaged engine test failed.' }
$result = Get-Content $report -Raw -Encoding UTF8 | ConvertFrom-Json
if (-not $result.ok) { throw 'Packaged video rendering test failed.' }

$uiReport = Join-Path (Get-Location) 'smoke-ui.txt'
Remove-Item $uiReport -ErrorAction SilentlyContinue
$ui = Start-Process -FilePath dist/MixCut/MixCut.exe -ArgumentList @('--smoke-ui', ('"' + $uiReport + '"')) -PassThru
if (-not $ui.WaitForExit(60000)) { $ui.Kill(); throw 'Packaged GUI test timed out.' }
if ($ui.ExitCode -ne 0 -or -not (Test-Path $uiReport)) { throw 'Packaged GUI startup test failed.' }

Compress-Archive -Path dist/MixCut -DestinationPath dist/MixCut-Windows-x64.zip -Force
$hash = (Get-FileHash dist/MixCut-Windows-x64.zip -Algorithm SHA256).Hash.ToLower()
"$hash  MixCut-Windows-x64.zip" | Out-File dist/SHA256SUMS.txt -Encoding ascii
Write-Host 'Ready: dist/MixCut-Windows-x64.zip'
