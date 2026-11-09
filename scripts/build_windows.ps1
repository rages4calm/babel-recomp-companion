param([switch]$PrivateAot, [string]$Rom = '', [int]$Jobs = 8, [string]$NativeBatch = '',
      [string]$BuildDirectory = '', [string]$CMake = 'cmake', [string]$NativeEffects = '')
$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path $PSScriptRoot -Parent
$buildRoot = Join-Path $projectRoot 'build'
if ($BuildDirectory) {
    # Qualification candidates must not overwrite the owner's installed binary,
    # mod state or build cache before matched execution has passed.
    $candidateRoot = [IO.Path]::GetFullPath((Join-Path $projectRoot $BuildDirectory))
    $privateRoot = [IO.Path]::GetFullPath((Join-Path $projectRoot '.local')) + [IO.Path]::DirectorySeparatorChar
    if (-not $candidateRoot.StartsWith($privateRoot, [StringComparison]::OrdinalIgnoreCase)) {
        throw 'BuildDirectory must be beneath this project''s ignored .local directory.'
    }
    $buildRoot = $candidateRoot
}
if ($Jobs -lt 1 -or $Jobs -gt 32) { throw 'Jobs must be 1..32.' }
$compilerC = (Get-Command clang -ErrorAction Stop).Source
$compilerCpp = (Get-Command clang++ -ErrorAction Stop).Source
$cmakeExe = (Get-Command -Name $CMake -ErrorAction Stop).Source
$generatedRoot = Join-Path $projectRoot 'src/gen'
$generatedIncludes = Join-Path $projectRoot 'recomp'
if ($NativeBatch) {
    $PrivateAot = $true
    $batchRoot = (Resolve-Path -LiteralPath $NativeBatch).Path
    $generatedRoot = Join-Path $batchRoot 'generated'
    $generatedIncludes = Join-Path $batchRoot 'cfg'
    if (-not (Test-Path -LiteralPath (Join-Path $generatedRoot 'program_manifest.json')) -or
        -not (Test-Path -LiteralPath (Join-Path $generatedIncludes 'funcs.h'))) {
        throw 'NativeBatch requires a completed generated program and its matching cfg/funcs.h.'
    }
    $receiptPath = Join-Path $batchRoot 'generation-receipt.json'
    if (-not (Test-Path -LiteralPath $receiptPath)) { throw 'NativeBatch requires its generation receipt.' }
    $receipt = Get-Content -LiteralPath $receiptPath -Raw | ConvertFrom-Json
    $manifestHash = (Get-FileHash -LiteralPath (Join-Path $generatedRoot 'program_manifest.json') -Algorithm SHA256).Hash.ToLowerInvariant()
    if ($receipt.exit_code -ne 0 -or $receipt.guarded_range_violations.Count -ne 0 -or
        $receipt.manifest_sha256 -ne $manifestHash) {
        throw 'NativeBatch generation failed, violated a fallback guard, or no longer matches its receipt.'
    }
} elseif ($PrivateAot) {
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
$effectsSource = ''
if ($NativeEffects) {
    if (-not $PrivateAot) { throw 'NativeEffects requires a private AOT build.' }
    $effectsRoot = (Resolve-Path -LiteralPath $NativeEffects).Path
    $privateEffectsRoot = [IO.Path]::GetFullPath((Join-Path $projectRoot '.local')) + [IO.Path]::DirectorySeparatorChar
    if (-not $effectsRoot.StartsWith($privateEffectsRoot, [StringComparison]::OrdinalIgnoreCase)) {
        throw 'NativeEffects must stay beneath project .local.'
    }
    $effects = Get-Content -LiteralPath (Join-Path $effectsRoot 'receipt.json') -Raw | ConvertFrom-Json
    if ($effects.source_file -ne 'native_continuations.c') { throw 'Unexpected native effects source name.' }
    $effectsSource = Join-Path $effectsRoot $effects.source_file
    $effectsHash = (Get-FileHash -LiteralPath $effectsSource -Algorithm SHA256).Hash.ToLowerInvariant()
    if ($effectsHash -ne $effects.generated_source_sha256) { throw 'Native effects receipt/source mismatch.' }
    $helperHash = (Get-FileHash -LiteralPath (Join-Path $projectRoot 'snesrecomp/runner/src/snes/interp816.c') -Algorithm SHA256).Hash.ToLowerInvariant()
    $emitterHash = (Get-FileHash -LiteralPath (Join-Path $projectRoot 'snesrecomp/recompiler/v2/native_effects.py') -Algorithm SHA256).Hash.ToLowerInvariant()
    $driverHash = (Get-FileHash -LiteralPath (Join-Path $projectRoot 'scripts/native_effects.py') -Algorithm SHA256).Hash.ToLowerInvariant()
    if ($helperHash -ne $effects.helper_file_sha256 -or $emitterHash -ne $effects.emitter_sha256 -or $driverHash -ne $effects.driver_sha256) {
        throw 'Native effects helper/emitter changed; regenerate before building.'
    }
}
& $cmakeExe -S $projectRoot -B $buildRoot -G Ninja -DCMAKE_BUILD_TYPE=Release `
    "-DCMAKE_C_COMPILER=$compilerC" "-DCMAKE_CXX_COMPILER=$compilerCpp" `
    "-DSNESRECOMP_INTERPRETER_ONLY=$executionMode" `
    "-DIOG_NATIVE_EFFECTS_SOURCE=$effectsSource" `
    "-DIOG_GENERATED_DIR=$generatedRoot" "-DIOG_GENERATED_INCLUDE_DIR=$generatedIncludes"
if ($LASTEXITCODE -ne 0) { throw 'Engine configuration failed.' }
& $cmakeExe --build $buildRoot -j $Jobs
if ($LASTEXITCODE -ne 0) { throw 'Engine build failed.' }
if ($PrivateAot) {
    Write-Output 'Private mixed AOT build: contains ROM-derived code; public packaging will reject it.'
} else {
    Write-Output (Join-Path $buildRoot 'babel-recomp.exe')
}
