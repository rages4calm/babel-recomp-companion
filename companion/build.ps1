param([string]$CompanionRoot = '', [switch]$Test)
$ErrorActionPreference = 'Stop'
if (-not $CompanionRoot) { $CompanionRoot = Join-Path (Split-Path (Split-Path $PSScriptRoot -Parent) -Parent) 'CompanionLauncher' }
$env:COMPANION_LAUNCHER_FEED = Join-Path (Resolve-Path -LiteralPath $CompanionRoot).Path 'packages'
if (-not (Test-Path -LiteralPath (Join-Path $env:COMPANION_LAUNCHER_FEED 'Companion.Launcher.Core.0.2.0.nupkg'))) {
    throw 'Build CompanionLauncher 0.2.0 packages first.'
}
dotnet restore (Join-Path $PSScriptRoot 'Game.Companion.csproj') --locked-mode
if ($LASTEXITCODE -ne 0) { throw 'Companion restore failed.' }
dotnet build (Join-Path $PSScriptRoot 'Game.Companion.csproj') -c Release --no-restore --nologo
if ($LASTEXITCODE -ne 0) { throw 'Companion build failed.' }
if ($Test) {
    dotnet restore (Join-Path $PSScriptRoot 'tests/Gaia.Companion.Tests.csproj') --locked-mode
    if ($LASTEXITCODE -ne 0) { throw 'Companion test restore failed.' }
    dotnet run --project (Join-Path $PSScriptRoot 'tests/Gaia.Companion.Tests.csproj') -c Release --no-restore
    if ($LASTEXITCODE -ne 0) { throw 'Companion adapter tests failed.' }
    dotnet run --project (Join-Path $PSScriptRoot 'tests/Gaia.Companion.Tests.csproj') -c Release --no-restore -- --soundtrack-tests
    if ($LASTEXITCODE -ne 0) { throw 'Soundtrack importer tests failed.' }
    dotnet run --project (Join-Path $PSScriptRoot 'tests/Gaia.Companion.Tests.csproj') -c Release --no-restore -- --activation
    if ($LASTEXITCODE -ne 0) { throw 'Native soundtrack activation tests failed.' }
    dotnet run --project (Join-Path $PSScriptRoot 'tests/Gaia.Companion.Tests.csproj') -c Release --no-restore -- --mods-tests
    if ($LASTEXITCODE -ne 0) { throw 'Native mod settings tests failed.' }
}
