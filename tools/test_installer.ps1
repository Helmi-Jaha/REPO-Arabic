# Automated installer tests against a TEST COPY of the game (never the real Steam folder). No GUI.
# Usage: powershell -ExecutionPolicy Bypass -File tools\test_installer.ps1 -Game <test copy folder> [-Package <package folder>]
param(
  [Parameter(Mandatory = $true)] [string]$Game,
  [string]$Package = (Join-Path (Split-Path $PSScriptRoot -Parent) 'package\REPO_Arabic_v1.1.1')
)
$ErrorActionPreference = 'Stop'
if ($Game -like '*steamapps*') { throw 'refusing to test on the real game folder; make a copy first' }
$loc = Join-Path $Game 'REPO_Data\StreamingAssets\Localizations'
$sa = Join-Path $Game 'REPO_Data\sharedassets0.assets'
$ps1 = Join-Path $Package 'installer\repo_arabic.ps1'
$manifest = Get-Content (Join-Path $Package 'manifest.json') -Raw -Encoding UTF8 | ConvertFrom-Json
$fp = $manifest.font_patch
$results = New-Object System.Collections.Generic.List[string]
$fail = 0
function Check([string]$name, [bool]$ok) { $script:results.Add(('{0}  {1}' -f $(if ($ok) { 'PASS' } else { 'FAIL' }), $name)); if (-not $ok) { $script:fail++ } }
function Run([string]$action, [string]$path) {
  $p = Start-Process powershell.exe -ArgumentList "-NoProfile -ExecutionPolicy Bypass -File `"$ps1`" -Action $action -GamePath `"$path`" -Quiet" -Wait -PassThru -WindowStyle Hidden
  return $p.ExitCode
}
function Sha($p) { (Get-FileHash -Algorithm SHA256 -LiteralPath $p).Hash }
function Ours { foreach ($f in $manifest.payload) { $d = Join-Path $loc $f.name; if (-not (Test-Path $d) -or (Sha $d) -ne $f.sha256) { return $false } }; return $true }
function NoneOurs { foreach ($f in $manifest.payload) { if (Test-Path (Join-Path $loc $f.name)) { return $false } }; return $true }
$backup = Join-Path $loc '_REPO_Arabic_font_backup.bin'

if ((Sha $sa) -ne $fp.original_file_sha256) { throw 'test copy sharedassets0.assets must be the original file before testing' }
foreach ($n in 'HUD.tsv', 'Menu.tsv', 'Game.tsv', 'REPO_Arabic.install.json') { Remove-Item (Join-Path $loc $n) -ErrorAction SilentlyContinue }

Check 'T1 install exit 0' ((Run Install $Game) -eq 0)
Check 'T1 translation files installed' (Ours)
Check 'T1 font patched (file hash)' ((Sha $sa) -eq $fp.patched_file_sha256)
Check 'T1 font backup verified' ((Test-Path $backup) -and (Sha $backup) -eq $fp.original_region_sha256)
Check 'T2 reinstall exit 0' ((Run Install $Game) -eq 0)
Check 'T2 font patched exactly once' ((Sha $sa) -eq $fp.patched_file_sha256)
Check 'T3 uninstall exit 0' ((Run Uninstall $Game) -eq 0)
Check 'T3 translation files removed' (NoneOurs)
Check 'T3 original font restored' ((Sha $sa) -eq $fp.original_file_sha256)
Check 'T3 backup removed' (-not (Test-Path $backup))

$foreign = Join-Path $loc 'Menu.tsv'
Set-Content $foreign "MAIN.PRIVATE_GAME`tother translation" -Encoding UTF8; $fh = Sha $foreign
Check 'T4 install over foreign file exit 0' ((Run Install $Game) -eq 0)
Check 'T4 uninstall exit 0' ((Run Uninstall $Game) -eq 0)
Check 'T4 foreign file restored byte-identical' ((Test-Path $foreign) -and (Sha $foreign) -eq $fh)
Remove-Item $foreign

$fake = Join-Path $env:TEMP 'repo_fake_game'
Remove-Item $fake -Recurse -Force -ErrorAction SilentlyContinue
New-Item -ItemType Directory -Force (Join-Path $fake 'REPO_Data\Managed'), (Join-Path $fake 'REPO_Data\StreamingAssets\Localizations') | Out-Null
Set-Content (Join-Path $fake 'REPO.exe') 'x'; Set-Content (Join-Path $fake 'REPO_Data\Managed\Assembly-CSharp.dll') 'other build'
Check 'T5 unsupported version refused' ((Run Install $fake) -eq 1)
Check 'T5 nothing written' (-not (Get-ChildItem (Join-Path $fake 'REPO_Data\StreamingAssets\Localizations')))
Remove-Item $fake -Recurse -Force
Check 'T6 non-game folder refused' ((Run Install $env:TEMP) -eq 1)

$results
"failures: $fail"
exit $fail
