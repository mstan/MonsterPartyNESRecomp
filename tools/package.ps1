# Build and package the local Windows release without ROMs or player data.
param(
    [string]$Rom = (Join-Path (Split-Path -Parent $PSScriptRoot) 'monsterparty.nes'),
    [string]$BuildDir = 'build-release',
    [string]$OutputDir = (Join-Path (Split-Path -Parent $PSScriptRoot) 'release'),
    [string]$ArchiveName = 'MonsterParty-windows-x64.zip',
    [switch]$SkipBuild
)
$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
$build = [IO.Path]::GetFullPath($(if ([IO.Path]::IsPathRooted($BuildDir)) { $BuildDir } else { Join-Path $root $BuildDir }))
$out = [IO.Path]::GetFullPath($OutputDir)
if ($build -match '^C:' -or $out -match '^C:') { throw 'Release output and staging must be on non-C: storage.' }
if ([IO.Path]::GetFileName($ArchiveName) -ne $ArchiveName) { throw 'ArchiveName must be a filename.' }
$env:TEMP = $env:TMP = Join-Path $build 'tmp'
New-Item -ItemType Directory -Path $env:TEMP -Force | Out-Null
if (-not $SkipBuild) { & (Join-Path $PSScriptRoot 'build.ps1') -Rom $Rom -BuildDir $build }
$cache = Get-Content -LiteralPath (Join-Path $build 'CMakeCache.txt') -Raw
if ($cache -notmatch '(?m)^NESRECOMP_BACKEND:STRING=cycle\r?$' -or
    $cache -notmatch '(?m)^NESRECOMP_ENABLE_TRACE:BOOL=OFF\r?$' -or
    $cache -match '(?m)^NESRECOMP_HEADLESS:BOOL=ON\r?$') { throw 'Expected the non-trace cycle build with launcher UI.' }
foreach ($file in 'MonsterPartyRecomp.exe','SDL2.dll','assets/img/boxart.tga') {
    if (-not (Test-Path -LiteralPath (Join-Path $build $file))) { throw "Missing release dependency: $file" }
}
New-Item -ItemType Directory -Path $out -Force | Out-Null
$stage = Join-Path $out ('stage-'+[guid]::NewGuid().ToString('N'))
New-Item -ItemType Directory -Path $stage | Out-Null
# Retain staging for review; it contains no player data and is outside the ZIP.
foreach ($file in 'MonsterPartyRecomp.exe','SDL2.dll','msvcp140.dll','vcruntime140.dll','vcruntime140_1.dll',
                 'msvcp140_1.dll','msvcp140_2.dll','concrt140.dll','vccorlib140.dll','msvcp140_atomic_wait.dll','msvcp140_codecvt_ids.dll') {
    $source = Join-Path $build $file
    if (Test-Path -LiteralPath $source) { Copy-Item -LiteralPath $source -Destination $stage }
}
Copy-Item -LiteralPath (Join-Path $build 'assets') -Destination (Join-Path $stage 'assets') -Recurse
New-Item -ItemType Directory -Path (Join-Path $stage 'mods') | Out-Null
Copy-Item -LiteralPath (Join-Path $root 'mods/preloaded/packages') -Destination (Join-Path $stage 'mods/packages') -Recurse
$licenses = @{
    'NESRecomp-LICENSE.txt' = (Join-Path $root 'nesrecomp/LICENSE')
    'SDL2-COPYING.txt' = (Join-Path $root 'nesrecomp/runner/external/SDL2/COPYING.txt')
    'ImGui-LICENSE.txt' = (Join-Path $root 'recomp-ui/src/third_party/imgui/LICENSE.txt')
    'recomp-ui-LICENSE.txt' = (Join-Path $root 'recomp-ui/LICENSE')
    'Fonts-NOTICE.md' = (Join-Path $root 'recomp-ui/assets/common/fonts/NOTICE.md')
    'Images-NOTICE.md' = (Join-Path $root 'recomp-ui/assets/common/img/NOTICE.md')
    'OFL-1.1.txt' = (Join-Path $root 'assets/licenses/OFL-1.1.txt')
    'Artwork-SOURCE.txt' = (Join-Path $root 'assets/SOURCE.txt')
}
New-Item -ItemType Directory -Path (Join-Path $stage 'licenses') | Out-Null
foreach ($name in $licenses.Keys) { Copy-Item -LiteralPath $licenses[$name] -Destination (Join-Path $stage "licenses/$name") }
Copy-Item -LiteralPath (Join-Path $root 'WIDESCREEN.md') -Destination $stage
$readme = @'
Monster Party

Select your original Monster Party (USA) ROM in the launcher. No ROM is included.
The supported payload CRC32 is 02B9E7C2 (MMC1, 128 KiB PRG).

Arrow keys: movement. Z: A. X: B. Enter: START. Backslash: SELECT.
Escape: menu. Controls and gamepads can be configured in recomp-ui.
F8/F9: save/load execution snapshot. Snapshots are specific to this build.
Keep the game's passwords for persistent progress.

Adaptive widescreen is optional under Display. Fit follows the window shape.
Original enemy spawning/culling is the default. See WIDESCREEN.md for details.

'@
[IO.File]::WriteAllText((Join-Path $stage 'README.txt'),$readme.Replace("`r`n","`n"),[Text.UTF8Encoding]::new($false))
$forbidden = @(Get-ChildItem -LiteralPath $stage -Recurse -File | Where-Object {
    $_.Extension -in '.nes','.fds','.sav','.srm','.state','.cycstate','.log','.dmp','.route','.ram' -or
    $_.Name -in 'rom.cfg','config.ini','keybinds.ini','debug.ini','state.toml' -or
    $_.FullName -match 'psx\.enhancement\.(cd-speed|fast-loading)'
})
if ($forbidden.Count) { throw 'Forbidden ROM, player, development data or loading mod in staging.' }
$zip = Join-Path $out $ArchiveName
if (Test-Path -LiteralPath $zip) { throw "Archive already exists: $zip; choose a new ArchiveName." }
Compress-Archive -Path (Join-Path $stage '*') -DestinationPath $zip
Add-Type -AssemblyName System.IO.Compression.FileSystem
$archive = [IO.Compression.ZipFile]::OpenRead($zip)
try {
    $entryNames = @($archive.Entries | ForEach-Object { $_.FullName.Replace('\','/') })
    if ($entryNames -match '(^|/)(state\.toml|config\.ini|rom\.cfg)$|\.(nes|fds|sav|srm|cycstate|state|log|dmp)$|psx\.enhancement\.(cd-speed|fast-loading)') {
        throw 'Forbidden entry in the final release archive.'
    }
    if (-not ($entryNames -match '(^|/)assets/img/boxart\.tga$')) { throw 'Missing launcher artwork in archive.' }
} finally { $archive.Dispose() }
Get-FileHash -LiteralPath $zip -Algorithm SHA256 | Format-List
Write-Output "Created $zip"
Write-Output "Staging retained at $stage"
