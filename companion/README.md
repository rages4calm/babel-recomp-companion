# Gaia Companion launcher integration

This Windows adapter consumes **CompanionLauncher 0.2.0** packages. The shared
Windows Forms shell is reused directly; it is not copied or redesigned per game.
Babel Recomp by **mr0ta / mrOt4**, all upstream contributors and their credits
remain the foundation of this edition. See the repository README and licenses.
The shared launcher is MIT licensed, copyright Carl Prewitt Jr. and contributors:
[source and license](https://github.com/rages4calm/companion-launcher).

## Build and run

Requires .NET 8 desktop runtime and a .NET SDK to build. Build the sibling
CompanionLauncher packages first, then from this repository:

```powershell
./companion/build.ps1 -Test
# Or use -CompanionRoot C:/path/to/CompanionLauncher
./companion/bin/Release/net8.0-windows/illusion-of-gaia.Companion.exe
```

The local package source uses `COMPANION_LAUNCHER_FEED`; the build script resolves
it from `-CompanionRoot` or the sibling checkout. Versions and dependency hashes
are pinned in `packages.lock.json`. This does not install or edit the shared SDK.

On **Game**, select an existing Babel executable and your own USA ROM, then Apply.
Play verifies SHA-256 after stripping an optional 512-byte copier header and passes
the ROM through structured `--rom` arguments. It never imports game bytes into
the repository or launcher preferences. Direct Play uses `--no-launcher`.
**Babel tools and remapping** uses `--launcher` for existing mod management,
controller/keyboard remapping and optional-mode setup. The selected ROM is still
the clean supported base image; optional patched-mode inputs belong in Babel.

## Settings and owner data

- Display, master audio and gamepad options read and update the executable's
  existing `config.ini`. Changed fields are merged while retaining comments,
  unrecognized keys, `[KeyMap]` and selected-controller data.
- Native config values are authoritative. In-game edits appear when Revert
  reloads or the launcher is reopened. Apply detects edits since the last read
  and asks the user to Revert instead of replacing newer native settings.
- On a fresh engine with no `config.ini`, launch once before editing native
  options, then Revert. The engine initializes its complete defaults; the adapter
  refuses to create a partial file that would suppress those defaults.
- Selecting a different executable reloads that installation's settings. The
  preceding installation's options are not copied over it.
- HD Mode 7 controls the shared pipeline's `Mode7Enabled`, preserving the current
  `Mode7Scale` and `Mode7Supersample`. Legacy `EnhancedMode7` is retained untouched
  for HD-pack compatibility. VSync supports Off, On and the current Adaptive mode,
  including native boolean/numeric spellings. Restart after applying graphics
  changes so the presenter can be selected consistently.
- Native writes use atomic replacement; a later preference-write failure restores
  the prior native bytes. This is not a power-loss transaction across both files.
- Launcher-only paths and launch destination live under local application data
  `CompanionGames/illusion-of-gaia/original/original/unseeded`. Set
  `COMPANION_DATA_ROOT` for an isolated test profile. Saves, ROMs, keybinds, mods,
  MSU-1 packs and achievements stay in their existing native locations.

In-game shortcuts remain Babel's: **Esc / LT+R3** settings, **I / LT+L3** companion,
**F11 / LT+Start** states, **Tab / LT+RT** fast forward. LT means the left trigger
(ZL on Nintendo, L2 on PlayStation). Default SNES keys and full shortcuts remain
documented in the upstream README. This batch does not reimplement full remapping,
ROM import, mod management, live achievements or Resume. **Soundtrack** in the
sidebar opens the optional-music window: download in your browser, import a
ZIP/folder, inspect verified installed packs, then select imported or original
audio for the next game launch. It uses Babel's native mod selection.

## Optional music investigation

EarthBound's `Companion/MsuDownloader.cs` already provides HTTPS sources, bounded
size checks, per-file checksums, retries, cancellation and temporary-file commit.
Its soundtrack catalog and URLs are EarthBound-specific and cannot safely be
reused for Gaia. A later Gaia importer should reuse that pattern with a reviewed
Gaia catalog and licensing/provenance. This edition now includes that Gaia
hash catalog and a bounded, cancellable local importer. The Download button
opens the source provider in the browser; it does not perform an unverified
background transfer. Music bytes are never bundled. See
[MSU-1 setup and credits](../docs/MSU1.md). Babel's original SNES fallback remains
in the engine, including when a selected optional pack has moved or disappeared.

## Verification

`./companion/build.ps1 -Test` builds the adapter and runs isolated synthetic
settings tests. They cover native settings/alias precedence, unknown-key and
binding preservation, stale writes, rollback, invalid configs, invalid ROMs and
unqualified Resume rejection. An optional read-only owner-ROM check also verifies
header normalization and structured launch plans:

```powershell
$env:COMPANION_LAUNCHER_FEED = 'C:/path/to/CompanionLauncher/packages'
dotnet run --project companion/tests -c Release -- --rom 'C:/path/to/your.sfc'
```

`--smoke-test <fresh-directory>` on the launcher renders every declared page and
checks draft navigation, disabled Play with unapplied changes and Revert. These
checks do not launch a game or certify gameplay, controller hardware or another OS.

For a bounded real-engine launch through the adapter (fresh output directory required):

```powershell
dotnet run --project companion/tests -c Release -- --engine 'C:/path/to/build/babel-recomp.exe' --rom 'C:/path/to/your.sfc' --output 'C:/path/to/fresh-smoke'
```

This copies the verified interpreter-only executable and staged resources to the
fresh output, creates an isolated config, then uses `BuildLaunchPlan` to run 60
frames with dummy SDL video/audio. It records a frame, exit status and unchanged
owner-file hashes. This is process handoff and boot evidence, not a playthrough.
