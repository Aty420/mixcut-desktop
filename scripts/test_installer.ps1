param([Parameter(Mandatory=$true)][string]$Compiler)
$ErrorActionPreference = 'Stop'
# Unique product identity and explicit fixture state: never touch a developer's
# installed MixCut or normal per-user data while validating the installer.
$token = [guid]::NewGuid().ToString('N')
$qaRoot = Join-Path $env:TEMP "MixCut-uninstall-test-$token"
$qaApp = Join-Path $qaRoot 'Installed App'
$qaState = Join-Path $qaRoot "MixCut-uninstall-test-$token"
$qaOutput = Join-Path $qaRoot 'Output'
New-Item $qaRoot -ItemType Directory | Out-Null
& $Compiler "/DProductId=MixCut.QA.$token" '/DSetupName=MixCut-QA-Setup' "/DStatePath=$qaState" scripts/installer.iss
if ($LASTEXITCODE -ne 0) { throw 'QA installer compile failed.' }
function Run-And-Check([string]$File, [string[]]$Arguments) {
    # Keep diagnostics outside the install folder so uninstall can remove it.
    $log = Join-Path $qaRoot ((Split-Path $File -Leaf) + '.log')
    $process = Start-Process -FilePath $File -ArgumentList ($Arguments + @('/LOG="' + $log + '"')) -PassThru
    if (-not $process.WaitForExit(180000)) {
        $process.Kill()
        if (Test-Path $log) { Get-Content $log -Tail 100 | Write-Host }
        throw "Installer test timed out: $File"
    }
    if ($process.ExitCode -ne 0) {
        if (Test-Path $log) { Get-Content $log -Tail 100 | Write-Host }
        throw "Installer test failed: $File ($($process.ExitCode))"
    }
}

Run-And-Check (Join-Path (Get-Location) 'dist/MixCut-QA-Setup.exe') @('/VERYSILENT','/SUPPRESSMSGBOXES','/NORESTART',('/DIR="' + $qaApp + '"'),'/NOICONS')
if (-not (Test-Path "$qaApp/unins000.exe")) { throw 'Missing installed uninstaller.' }
$env:MIXCUT_QA_STATE = $qaState
$env:MIXCUT_QA_OUTPUT = $qaOutput
@'
import os, sqlite3
from pathlib import Path
state=Path(os.environ['MIXCUT_QA_STATE']); state.mkdir(parents=True)
output=Path(os.environ['MIXCUT_QA_OUTPUT']); output.mkdir()
work=output/'.mixcut-work-crash'; work.mkdir()
(work/('clip_'+'a'*64+'.mp4')).write_bytes(b'cached')
(output/'keep-video.mp4').write_bytes(b'user-owned')
with sqlite3.connect(state/'usage.sqlite3') as db:
    db.execute('CREATE TABLE paths (kind TEXT,path TEXT,PRIMARY KEY(kind,path))')
    db.execute('INSERT INTO paths VALUES (?,?)',('output',str(output)))
'@ | python -
if ($LASTEXITCODE -ne 0) { throw 'Could not create cache fixture.' }
Set-Content "$qaApp/user-file.txt" 'Preserve this user file.'
Run-And-Check "$qaApp/unins000.exe" @('/VERYSILENT','/SUPPRESSMSGBOXES','/NORESTART')
# Native uninstaller self-removal is asynchronous after its copied stub exits.
for ($attempt = 0; $attempt -lt 20 -and (Test-Path "$qaApp/unins000.exe"); $attempt++) { Start-Sleep -Milliseconds 250 }
foreach ($path in @("$qaApp/MixCut.exe", "$qaApp/unins000.exe", "$qaApp/_internal", "$qaApp/mixcut-install.ini", $qaState, "$qaOutput/.mixcut-work-crash")) {
    if (Test-Path $path) { throw "Uninstall left an owned file: $path" }
}
if (-not (Test-Path "$qaApp/user-file.txt") -or -not (Test-Path "$qaOutput/keep-video.mp4")) { throw 'Uninstall deleted user data.' }
$regPath = "HKCU:\Software\Microsoft\Windows\CurrentVersion\Uninstall\MixCut.QA.${token}_is1"
if (Test-Path $regPath) { throw 'Uninstall registration remained.' }
Remove-Item $qaRoot -Recurse -Force
Remove-Item dist/MixCut-QA-Setup.exe
Remove-Item Env:MIXCUT_QA_STATE, Env:MIXCUT_QA_OUTPUT
Write-Host 'Installer/uninstaller/cache preservation checks passed.'

