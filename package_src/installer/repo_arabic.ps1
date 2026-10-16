# R.E.P.O. Arabic localization - installer / uninstaller
# Windows PowerShell 5.1+, no administrator rights needed (Steam game folders are user-writable).
# Adds 3 text files to REPO_Data\StreamingAssets\Localizations (the game's official override mechanism)
# and patches the embedded Arabic font bytes in sharedassets0.assets in place (same length, hash-checked,
# original bytes backed up and restored on uninstall). Never touches save data (AppData\LocalLow).
param(
  [ValidateSet('Install', 'Uninstall', 'Status')] [string]$Action = 'Install',
  [string]$GamePath,
  [switch]$Force,   # allow an unrecognised game version (advanced)
  [switch]$Quiet    # no dialogs (used for automated tests)
)
$ErrorActionPreference = 'Stop'
$PkgRoot = Split-Path $PSScriptRoot -Parent
$Manifest = Get-Content (Join-Path $PkgRoot 'manifest.json') -Raw -Encoding UTF8 | ConvertFrom-Json
$LogDir = Join-Path $env:LOCALAPPDATA 'REPO_Arabic'
New-Item -ItemType Directory -Force $LogDir | Out-Null
$LogFile = Join-Path $LogDir 'install.log'
$StateName = 'REPO_Arabic.install.json'
$Files = @('HUD.tsv', 'Menu.tsv', 'Game.tsv')

function Log([string]$m) {
  $line = '{0}  {1}' -f (Get-Date -Format 'yyyy-MM-dd HH:mm:ss'), $m
  Add-Content -Path $LogFile -Value $line -Encoding UTF8
  Write-Host $m
}
function Show([string]$msg, [string]$kind = 'Info') {
  if ($Quiet) { return }
  Add-Type -AssemblyName System.Windows.Forms
  $icon = if ($kind -eq 'Error') { 'Error' } elseif ($kind -eq 'Warn') { 'Warning' } else { 'Information' }
  [System.Windows.Forms.MessageBox]::Show($msg, 'تعريب R.E.P.O.', 'OK', $icon, 'Button1',
    ([System.Windows.Forms.MessageBoxOptions]::RtlReading -bor [System.Windows.Forms.MessageBoxOptions]::RightAlign)) | Out-Null
}
function Ask([string]$msg) {
  if ($Quiet) { return $true }
  Add-Type -AssemblyName System.Windows.Forms
  $r = [System.Windows.Forms.MessageBox]::Show($msg, 'تعريب R.E.P.O.', 'YesNo', 'Question', 'Button2',
    ([System.Windows.Forms.MessageBoxOptions]::RtlReading -bor [System.Windows.Forms.MessageBoxOptions]::RightAlign))
  return $r -eq 'Yes'
}
function Sha([string]$p) { (Get-FileHash -Algorithm SHA256 -LiteralPath $p).Hash.ToUpperInvariant() }
function Fail([string]$msg) { Log "ERROR: $msg"; Show "$msg`n`nالسجل: $LogFile" 'Error'; exit 1 }

function Find-Game {
  $candidates = New-Object System.Collections.Generic.List[string]
  $steam = $null
  foreach ($k in 'HKCU:\Software\Valve\Steam', 'HKLM:\SOFTWARE\WOW6432Node\Valve\Steam', 'HKLM:\SOFTWARE\Valve\Steam') {
    try { $v = Get-ItemProperty -Path $k -ErrorAction Stop; if ($v.SteamPath) { $steam = $v.SteamPath } elseif ($v.InstallPath) { $steam = $v.InstallPath } } catch {}
    if ($steam) { break }
  }
  if ($steam) {
    $steam = $steam -replace '/', '\'
    $candidates.Add((Join-Path $steam 'steamapps\common\REPO'))
    $vdf = Join-Path $steam 'steamapps\libraryfolders.vdf'
    if (Test-Path -LiteralPath $vdf) {
      foreach ($m in [regex]::Matches((Get-Content -LiteralPath $vdf -Raw), '"path"\s+"([^"]+)"')) {
        $candidates.Add((Join-Path ($m.Groups[1].Value -replace '\\\\', '\') 'steamapps\common\REPO'))
      }
    }
  }
  foreach ($c in $candidates) { if (Test-Path -LiteralPath (Join-Path $c 'REPO.exe')) { return $c } }
  return $null
}
function Pick-Folder {
  if ($Quiet) { return $null }
  Add-Type -AssemblyName System.Windows.Forms
  $d = New-Object System.Windows.Forms.FolderBrowserDialog
  $d.Description = 'اختر مجلد لعبة R.E.P.O. (المجلد الذي يحتوي على REPO.exe)'
  if ($d.ShowDialog() -eq 'OK') { return $d.SelectedPath }
  return $null
}

try {
  Log "==== $Action  (package v$($Manifest.version)) ===="
  if (-not $GamePath) { $GamePath = Find-Game }
  if (-not $GamePath) {
    Show 'لم أجد مجلد اللعبة تلقائيًا. اختر مجلد R.E.P.O. في النافذة التالية.'
    $GamePath = Pick-Folder
  }
  if (-not $GamePath) { Fail 'لم يتم اختيار مجلد اللعبة. لم يتغير شيء.' }
  $GamePath = (Resolve-Path -LiteralPath $GamePath).Path
  Log "Game folder: $GamePath"
  $exe = Join-Path $GamePath 'REPO.exe'
  $asm = Join-Path $GamePath 'REPO_Data\Managed\Assembly-CSharp.dll'
  $locDir = Join-Path $GamePath 'REPO_Data\StreamingAssets\Localizations'
  if (-not (Test-Path -LiteralPath $exe) -or -not (Test-Path -LiteralPath $asm) -or -not (Test-Path -LiteralPath $locDir)) {
    Fail "هذا المجلد ليس مجلد R.E.P.O. صالحًا:`n$GamePath"
  }
  $statePath = Join-Path $locDir $StateName
  $state = $null
  if (Test-Path -LiteralPath $statePath) { $state = Get-Content -LiteralPath $statePath -Raw -Encoding UTF8 | ConvertFrom-Json }

  if ($Action -eq 'Status') {
    if ($state) { Log "Installed: v$($state.version) on $($state.date)"; Show "التعريب مثبت (الإصدار $($state.version))." }
    else { Log 'Not installed'; Show 'التعريب غير مثبت في هذا المجلد.' }
    exit 0
  }

  if ($Action -eq 'Install') {
    $asmHash = Sha $asm
    Log "Assembly-CSharp.dll SHA256: $asmHash"
    $supported = $Manifest.supported | Where-Object { $_.assembly_csharp_sha256 -eq $asmHash }
    if (-not $supported) {
      $msg = "إصدار اللعبة المثبت غير مدعوم من هذه النسخة من التعريب.`n" +
             "الإصدارات المدعومة: $(($Manifest.supported | ForEach-Object { $_.game_version }) -join '، ')`n`n" +
             'غالبًا تم تحديث اللعبة. ابحث عن نسخة أحدث من التعريب. لم يتغير شيء.'
      if (-not $Force) { Fail $msg }
      Log 'WARNING: unsupported version, continuing because -Force was given'
    } else { Log "Supported game version: $($supported.game_version)" }

    # ---- font patch: overwrite the embedded Arabic font bytes in sharedassets0.assets in place ----
    $fontPatched = $false; $fontBackup = $null
    if ($Manifest.font_patch) {
      $fp = $Manifest.font_patch
      $target = Join-Path $GamePath ($fp.target -replace '/', '\')
      if (-not (Test-Path -LiteralPath $target)) { Fail "لم أجد ملف اللعبة $($fp.target)." }
      $th = Sha $target
      Log "$($fp.target) SHA256: $th"
      if ($th -eq $fp.patched_file_sha256) {
        Log 'Font patch already applied'; $fontPatched = $true
        if ($state) { $fontBackup = $state.font_backup }
      } elseif ($th -eq $fp.original_file_sha256) {
        $region = [IO.File]::ReadAllBytes((Join-Path $PkgRoot 'files\font_region.bin'))
        $sha256 = [Security.Cryptography.SHA256]::Create()
        if (([BitConverter]::ToString($sha256.ComputeHash($region)) -replace '-', '') -ne $fp.region_sha256) { Fail 'ملف الخط في الحزمة تالف. أعد تنزيل الحزمة.' }
        try { $fs = [IO.File]::Open($target, 'Open', 'ReadWrite', 'None') }
        catch { Fail 'ملف اللعبة مستخدم حاليًا. أغلق اللعبة ثم أعد المحاولة. لم يتغير شيء.' }
        try {
          $orig = New-Object byte[] ([int]$fp.length)
          $fs.Position = [int64]$fp.offset
          [void]$fs.Read($orig, 0, $orig.Length)
          if (([BitConverter]::ToString($sha256.ComputeHash($orig)) -replace '-', '') -ne $fp.original_region_sha256) { throw 'original region hash mismatch' }
          $fontBackup = '_REPO_Arabic_font_backup.bin'
          $bpath = Join-Path $locDir $fontBackup
          [IO.File]::WriteAllBytes($bpath, $orig)
          if ((Sha $bpath) -ne $fp.original_region_sha256) { throw 'backup verification failed' }
          $fs.Position = [int64]$fp.offset
          $fs.Write($region, 0, $region.Length)
          $fs.Flush()
        } catch {
          $fs.Close(); Fail ("تعذر تطبيق الخط، ولم يتغير ملف اللعبة: " + $_.Exception.Message)
        }
        $fs.Close()
        if ((Sha $target) -ne $fp.patched_file_sha256) {
          # roll back from the verified backup
          $fs = [IO.File]::Open($target, 'Open', 'ReadWrite', 'None'); $fs.Position = [int64]$fp.offset
          $fs.Write($orig, 0, $orig.Length); $fs.Close()
          Fail 'فشل التحقق بعد تطبيق الخط، وأُعيد الملف إلى أصله.'
        }
        $fontPatched = $true
        Log 'Font patch applied and verified'
      } else {
        Fail ("ملف اللعبة $($fp.target) لا يطابق الإصدار المدعوم (ربما حُدّثت اللعبة أو عُدّلت بأداة أخرى). " +
              'تحقق من ملفات اللعبة عبر Steam ثم أعد المحاولة. لم يتغير شيء.')
      }
    }

    $prevOurs = @{}
    if ($state) { foreach ($f in $state.files) { $prevOurs[$f.name] = $f.sha256 } }
    $ourHashes = @{}
    foreach ($f in $Manifest.payload) { $ourHashes[$f.name] = $f.sha256 }

    # back up any foreign override files (another translation or mod) before replacing them
    $backupDir = $null
    $backups = @()
    if ($state -and $state.backup_dir) { $backupDir = $state.backup_dir; $backups = @($state.backups) }
    foreach ($n in $Files) {
      $dst = Join-Path $locDir $n
      if (-not (Test-Path -LiteralPath $dst)) { continue }
      $h = Sha $dst
      $isOurs = ($prevOurs[$n] -eq $h) -or ($ourHashes[$n] -eq $h)
      if ($isOurs) { continue }
      if (-not $backupDir) { $backupDir = '_backup_REPO_Arabic_' + (Get-Date -Format 'yyyyMMdd_HHmmss') }
      $bdir = Join-Path $locDir $backupDir
      New-Item -ItemType Directory -Force $bdir | Out-Null
      Copy-Item -LiteralPath $dst -Destination (Join-Path $bdir $n) -Force
      if ((Sha (Join-Path $bdir $n)) -ne $h) { Fail "فشل التحقق من النسخة الاحتياطية للملف $n. لم يتغير شيء." }
      $backups += [pscustomobject]@{ name = $n; sha256 = $h }
      Log "Backed up existing $n ($h) -> $backupDir"
    }

    $installed = @()
    foreach ($f in $Manifest.payload) {
      $src = Join-Path $PkgRoot ('files\Localizations\' + $f.name)
      if ((Sha $src) -ne $f.sha256) { Fail "ملف التعريب $($f.name) في الحزمة تالف أو معدل. أعد تنزيل الحزمة." }
      $dst = Join-Path $locDir $f.name
      Copy-Item -LiteralPath $src -Destination $dst -Force
      if ((Sha $dst) -ne $f.sha256) { Fail "فشل التحقق بعد نسخ $($f.name)." }
      $installed += [pscustomobject]@{ name = $f.name; sha256 = $f.sha256 }
      Log "Installed $($f.name)"
    }
    $newState = [pscustomobject]@{
      package = 'REPO_Arabic'; version = $Manifest.version; date = (Get-Date -Format 's')
      game_assembly_sha256 = $asmHash; files = $installed; backup_dir = $backupDir; backups = $backups
      font_patched = $fontPatched; font_backup = $fontBackup
    }
    [IO.File]::WriteAllText($statePath, ($newState | ConvertTo-Json -Depth 5), (New-Object Text.UTF8Encoding $false))
    $verb = if ($state) { 'تم تحديث التعريب' } else { 'تم تثبيت التعريب' }
    Log "$Action OK"
    Show "$verb بنجاح (الإصدار $($Manifest.version)).`n`nشغّل اللعبة من Steam كالمعتاد. التعريب يحل محل اللغة الإنجليزية، فإذا ظهرت لغة أخرى فاختر English.`n`nللإزالة: شغّل Uninstall_Arabic.cmd"
    exit 0
  }

  if ($Action -eq 'Uninstall') {
    if (-not $state) {
      # fall back: remove files only if they are byte-identical to this package's files
      $removed = 0
      foreach ($f in $Manifest.payload) {
        $dst = Join-Path $locDir $f.name
        if ((Test-Path -LiteralPath $dst) -and ((Sha $dst) -eq $f.sha256)) { Remove-Item -LiteralPath $dst -Force; $removed++; Log "Removed $($f.name)" }
      }
      if ($removed -eq 0) { Log 'Nothing to uninstall'; Show 'التعريب غير مثبت في هذا المجلد. لم يتغير شيء.'; exit 0 }
      Show 'تمت إزالة التعريب.'; exit 0
    }
    # ---- restore the original font bytes first (only if the file is exactly our patched version) ----
    if ($state.font_patched -and $Manifest.font_patch) {
      $fp = $Manifest.font_patch
      $target = Join-Path $GamePath ($fp.target -replace '/', '\')
      $bpath = Join-Path $locDir $state.font_backup
      $th = Sha $target
      if ($th -eq $fp.patched_file_sha256) {
        if (-not (Test-Path -LiteralPath $bpath) -or (Sha $bpath) -ne $fp.original_region_sha256) {
          Fail 'النسخة الاحتياطية للخط مفقودة أو تالفة. استخدم "التحقق من سلامة ملفات اللعبة" في Steam لاستعادة الملف الأصلي.'
        }
        $orig = [IO.File]::ReadAllBytes($bpath)
        try { $fs = [IO.File]::Open($target, 'Open', 'ReadWrite', 'None') }
        catch { Fail 'ملف اللعبة مستخدم حاليًا. أغلق اللعبة ثم أعد المحاولة. لم يتغير شيء.' }
        try { $fs.Position = [int64]$fp.offset; $fs.Write($orig, 0, $orig.Length); $fs.Flush() } finally { $fs.Close() }
        if ((Sha $target) -ne $fp.original_file_sha256) { Fail 'فشل التحقق بعد استعادة الخط الأصلي. استخدم "التحقق من سلامة ملفات اللعبة" في Steam.' }
        Log 'Original font restored and verified'
      } elseif ($th -eq $fp.original_file_sha256) {
        Log 'Font already original (e.g. restored by Steam)'
      } else {
        Log "WARNING: $($fp.target) changed since install (game update?); font left as is"
      }
      if (Test-Path -LiteralPath $bpath) { Remove-Item -LiteralPath $bpath -Force }
    }

    $kept = @()
    foreach ($f in $state.files) {
      $dst = Join-Path $locDir $f.name
      if (-not (Test-Path -LiteralPath $dst)) { continue }
      if ((Sha $dst) -eq $f.sha256) { Remove-Item -LiteralPath $dst -Force; Log "Removed $($f.name)" }
      else {
        $keep = Ask "الملف $($f.name) تم تعديله بعد التثبيت. هل تريد حذفه رغم ذلك؟"
        if ($keep) { Remove-Item -LiteralPath $dst -Force; Log "Removed modified $($f.name) (user confirmed)" }
        else { $kept += $f.name; Log "Kept modified $($f.name)" }
      }
    }
    if ($state.backup_dir) {
      $bdir = Join-Path $locDir $state.backup_dir
      foreach ($b in $state.backups) {
        $bf = Join-Path $bdir $b.name; $dst = Join-Path $locDir $b.name
        if (-not (Test-Path -LiteralPath $bf)) { Log "WARNING: backup $($b.name) missing"; continue }
        if (Test-Path -LiteralPath $dst) { Log "WARNING: $($b.name) exists, backup not restored over it"; continue }
        Copy-Item -LiteralPath $bf -Destination $dst
        if ((Sha $dst) -ne $b.sha256) { Fail "فشل التحقق من استرجاع $($b.name)." }
        Remove-Item -LiteralPath $bf -Force
        Log "Restored $($b.name) from backup"
      }
      if ((Test-Path -LiteralPath $bdir) -and -not (Get-ChildItem -LiteralPath $bdir -Force)) { Remove-Item -LiteralPath $bdir -Force }
    }
    Remove-Item -LiteralPath $statePath -Force
    Log 'Uninstall OK'
    $extra = if ($kept) { "`n`nتُركت هذه الملفات المعدلة كما هي: $($kept -join '، ')" } else { '' }
    Show "تمت إزالة التعريب وأُعيدت اللعبة إلى حالتها السابقة.$extra"
    exit 0
  }
} catch {
  Fail ("حدث خطأ غير متوقع: " + $_.Exception.Message)
}
