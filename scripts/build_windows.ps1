param([switch]$PrivateAot, [string]$Rom = '', [int]$Jobs = 8)
$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path $PSScriptRoot -Parent
$buildRoot = Join-Path $projectRoot 'build'
if ($Jobs -lt 1 -or $Jobs -gt 32) { throw 'Jobs must be 1..32.' }
$compilerC = (Get-Command clang -ErrorAction Stop).Source
$compilerCpp = (Get-Command clang++ -ErrorAction Stop).Source
if ($PrivateAot) {
    if (-not $Rom) { throw 'Private AOT generation requires -Rom pointing to your own supported USA image.' }
    $Rom = (Resolve-Path -LiteralPath $Rom).Path
    $romIdentity = @{}
    Get-Content -LiteralPath (Join-Path $projectRoot 'rom_identity.txt') | ForEach-Object {
        if ($_ -match '^\s*(\w+)\s*=\s*([^#]+)') { $romIdentity[$matches[1]] = $matches[2].Trim().Trim('"') }
    }
    python (Join-Path $projectRoot 'snesrecomp/snesrecomp_cli.py') generate --rom $Rom `
        --cfg-dir (Join-Path $projectRoot 'recomp') --out-dir (Join-Path $projectRoot 'src/gen') `
        --funcs-h (Join-Path $projectRoot 'recomp/funcs.h') --project-root $projectRoot `
        --expected-crc32 $romIdentity.expected_crc32 --expected-sha256 $romIdentity.expected_sha256
    if ($LASTEXITCODE -ne 0) { throw 'Private generation failed.' }
}
$executionMode = if ($PrivateAot) { 'OFF' } else { 'ON' }
cmake -S $projectRoot -B $buildRoot -G Ninja -DCMAKE_BUILD_TYPE=Release `
    "-DCMAKE_C_COMPILER=$compilerC" "-DCMAKE_CXX_COMPILER=$compilerCpp" `
    "-DSNESRECOMP_INTERPRETER_ONLY=$executionMode"
if ($LASTEXITCODE -ne 0) { throw 'Engine configuration failed.' }
cmake --build $buildRoot -j $Jobs
if ($LASTEXITCODE -ne 0) { throw 'Engine build failed.' }
if ($PrivateAot) {
    Write-Output 'Private mixed AOT build: contains ROM-derived code; public packaging will reject it.'
} else {
    Write-Output (Join-Path $buildRoot 'babel-recomp.exe')
}
