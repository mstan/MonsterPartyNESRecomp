# Configure and build the cycle backend with MSVC + the VS-bundled CMake/Ninja.
# Does not launch the game.
param(
    [string]$Rom = (Join-Path (Split-Path -Parent $PSScriptRoot) 'monsterparty.nes'),
    [string]$BuildDir = 'build',
    [switch]$Trace,
    [switch]$Headless,
    [switch]$Clean,
    [string[]]$CMakeArgs = @()
)
$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
$build = if ([IO.Path]::IsPathRooted($BuildDir)) { $BuildDir } else { Join-Path $root $BuildDir }
$vs = 'C:\Program Files\Microsoft Visual Studio\2022\Community'
$cmake = "$vs\Common7\IDE\CommonExtensions\Microsoft\CMake\CMake\bin\cmake.exe"
$ninja = "$vs\Common7\IDE\CommonExtensions\Microsoft\CMake\Ninja"
$python = (Get-Command python -ErrorAction SilentlyContinue).Source
if (-not $python -or $python -match 'WindowsApps|msys|devkitPro|pyenv|.bat$') {
    $python = "$env:LOCALAPPDATA\Programs\Python\Python312\python.exe"
}
Import-Module "$vs\Common7\Tools\Microsoft.VisualStudio.DevShell.dll"
Enter-VsDevShell -VsInstallPath $vs -SkipAutomaticLocation -DevCmdArguments '-arch=x64 -host_arch=x64' | Out-Null
$env:PATH = "$ninja;$env:PATH"
if ($Clean -and (Test-Path -LiteralPath $build)) { Remove-Item -LiteralPath $build -Recurse -Force }
$traceValue = if ($Trace) { 'ON' } else { 'OFF' }
$configure = @('-S', $root, '-B', $build, '-G', 'Ninja', '-DCMAKE_BUILD_TYPE=Release',
    '-DCMAKE_C_COMPILER=cl', '-DCMAKE_CXX_COMPILER=cl', "-DNESRECOMP_ROM=$((Resolve-Path -LiteralPath $Rom).Path)",
    "-DPython3_EXECUTABLE=$python", "-DNESRECOMP_ENABLE_TRACE:BOOL=$traceValue")
if ($Headless) { $configure += '-DNESRECOMP_HEADLESS=ON' }
$ErrorActionPreference = 'Continue'
& $cmake @($configure + $CMakeArgs) 2>&1 | ForEach-Object { "$_" }
if ($LASTEXITCODE) { throw "configure failed ($LASTEXITCODE)" }
& $cmake --build $build --parallel 6 2>&1 | ForEach-Object { "$_" }
if ($LASTEXITCODE) { throw "build failed ($LASTEXITCODE)" }
