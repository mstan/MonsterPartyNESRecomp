# Build and package the local Windows release without ROMs or player data.
param(
    [string]$Rom = (Join-Path (Split-Path -Parent $PSScriptRoot) 'monsterparty.nes'),
    [string]$BuildDir = 'build-release',
    [string]$OutputDir = (Join-Path (Split-Path -Parent $PSScriptRoot) 'release'),
    [string]$ArchiveName = 'MonsterParty-0.1.1-windows-x64.zip',
    [string]$ReleaseVersion = '0.1.1',
    [switch]$SkipBuild
)
$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
$build = [IO.Path]::GetFullPath($(if ([IO.Path]::IsPathRooted($BuildDir)) { $BuildDir } else { Join-Path $root $BuildDir }))
$out = [IO.Path]::GetFullPath($OutputDir)
if ([IO.Path]::GetFileName($ArchiveName) -ne $ArchiveName) { throw 'ArchiveName must be a filename.' }
$env:TEMP = $env:TMP = Join-Path $build 'tmp'
New-Item -ItemType Directory -Path $env:TEMP -Force | Out-Null
if (-not $SkipBuild) { & (Join-Path $PSScriptRoot 'build.ps1') -Rom $Rom -BuildDir $build -ReleaseVersion $ReleaseVersion }
$cache = Get-Content -LiteralPath (Join-Path $build 'CMakeCache.txt') -Raw
if ($cache -notmatch ('(?m)^NESRECOMP_GAME_VERSION:STRING='+[regex]::Escape($ReleaseVersion)+'\r?$')) {
    throw 'Build version does not match the requested release.'
}
if ($cache -notmatch '(?m)^NESRECOMP_BACKEND:STRING=cycle\r?$' -or
    $cache -notmatch '(?m)^NESRECOMP_ENABLE_TRACE:BOOL=OFF\r?$' -or
    $cache -match '(?m)^NESRECOMP_HEADLESS:BOOL=ON\r?$') { throw 'Expected the non-trace cycle build with launcher UI.' }
foreach ($file in 'MonsterPartyRecomp.exe','SDL2.dll','assets/img/boxart.tga') {
    if (-not (Test-Path -LiteralPath (Join-Path $build $file))) { throw "Missing release dependency: $file" }
}
New-Item -ItemType Directory -Path $out -Force | Out-Null
$stage = Join-Path $out ('stage-'+[guid]::NewGuid().ToString('N'))
New-Item -ItemType Directory -Path $stage | Out-Null
# Stage only explicitly selected release files.
foreach ($file in 'MonsterPartyRecomp.exe','SDL2.dll','msvcp140.dll','vcruntime140.dll','vcruntime140_1.dll',
                 'msvcp140_1.dll','msvcp140_2.dll','concrt140.dll','vccorlib140.dll','msvcp140_atomic_wait.dll','msvcp140_codecvt_ids.dll') {
    $source = Join-Path $build $file
    if (Test-Path -LiteralPath $source) { Copy-Item -LiteralPath $source -Destination $stage }
}
$pythonMatch = [regex]::Match($cache, '(?m)^Python3_EXECUTABLE:[^=]+=([^\r\n]+)')
if (-not $pythonMatch.Success) { throw 'Build cache has no Python interpreter.' }
& $pythonMatch.Groups[1].Value -I (Join-Path $PSScriptRoot 'stage_release.py') --build $build --output $stage --version $ReleaseVersion
if ($LASTEXITCODE) { throw 'Shared release staging failed.' }
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
$qualifiedStage = [IO.Path]::GetFullPath($stage)
if (-not $qualifiedStage.StartsWith($out.TrimEnd('\')+'\') -or [IO.Path]::GetFileName($qualifiedStage) -notlike 'stage-*') { throw 'Unqualified staging cleanup path.' }
Remove-Item -LiteralPath $qualifiedStage -Recurse -Force
