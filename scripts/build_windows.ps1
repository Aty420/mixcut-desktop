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

# Add an installable edition with a real Windows uninstaller. The existing
# Actions artifact paths stay unchanged: put both editions inside the ZIP.
$iscc = Get-Command ISCC.exe -ErrorAction SilentlyContinue
if (-not $iscc) {
    $compiler = @(
        "${env:ProgramFiles(x86)}\Inno Setup 6\ISCC.exe",
        "${env:ProgramFiles}\Inno Setup 7\ISCC.exe",
        "${env:ProgramFiles(x86)}\Inno Setup 7\ISCC.exe"
    ) | Where-Object { Test-Path $_ } | Select-Object -First 1
    if (-not $compiler) {
        choco install innosetup --yes --no-progress
        Check-Exit 'Install Inno Setup'
        $compiler = Get-ChildItem "${env:ProgramFiles(x86)}", "$env:ProgramFiles" -Filter ISCC.exe -Recurse -ErrorAction SilentlyContinue | Select-Object -First 1 -ExpandProperty FullName
    }
} else { $compiler = $iscc.Source }
if (-not $compiler) { throw 'Inno Setup compiler not found.' }
& $compiler scripts/installer.iss
Check-Exit 'Build Windows installer'
if ($env:GITHUB_ACTIONS -eq 'true') {
    & ./scripts/test_installer.ps1 -Compiler $compiler
}

@'
推荐双击 MixCut-Setup.exe 安装，然后从开始菜单打开 MixCut。
安装版支持一键卸载：软件右下角“卸载软件”，或开始菜单“一键卸载 MixCut”。
卸载会删除安装的程序、快捷方式、安装记录，以及已记录的临时转码缓存。
原始素材、已导出视频、组合记录和项目历史会保留。
请先停止任务并关闭其他 MixCut 窗口；旧版项目请在新版中扫描一次以登记缓存位置。
MixCut 文件夹是便携版；直接运行其中的 EXE 不会安装卸载程序。
'@ | Set-Content dist/READ-ME-FIRST.txt -Encoding UTF8
Compress-Archive -Path dist/MixCut, dist/MixCut-Setup.exe, dist/READ-ME-FIRST.txt -DestinationPath dist/MixCut-Windows-x64.zip -Force
$hash = (Get-FileHash dist/MixCut-Windows-x64.zip -Algorithm SHA256).Hash.ToLower()
"$hash  MixCut-Windows-x64.zip" | Out-File dist/SHA256SUMS.txt -Encoding ascii
Write-Host 'Ready: dist/MixCut-Windows-x64.zip (includes MixCut-Setup.exe)'
