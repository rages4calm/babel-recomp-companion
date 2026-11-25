# Illusion of Gaia Companion

A controller-first PC edition of Quintet's SNES adventure, with square-pixel
widescreen, a scenery map that reveals as you explore, and optional MSU-1 music.

[Features](#features) · [Build from source](#build-from-source) ·
[Development status](#development-status) · [Credits](#thanks)

**Windows playtest in development.** Bring your own unmodified
**Illusion of Gaia (USA)** ROM. Maintained by
[Carl Prewitt Jr. / rages4calm](https://github.com/rages4calm), based on
[Babel Recomp](https://github.com/mrOt4/babel-recomp) by mr0ta / mrOt4.

![Watermia's docks in square-pixel widescreen at 1.5×](https://github.com/user-attachments/assets/81a3df72-cc86-41c4-ba7e-5ea2dc49f566)

## Features

- **Widescreen and 1.5×** extend the view with real scenery in supported
  rooms. Fixed compositions keep their original framing at the same scale.
  [Visual coverage and renderer direction](docs/VISUAL-COVERAGE.md)
- **World travel and local maps** combine GaiaLabs' walkable world map
  with Companion's scenery-based area map, explored terrain, discovered
  markers and radar. Locally prepared packs also supply all 1,127 retranslated
  chapter entries, all 124 approved menu strings, and all 64 named room
  titles.
  [GaiaLabs integration](docs/GAIALABS-ORIGINAL-INTEGRATION.md) ·
  [Companion map](docs/MAP-SYSTEM-DIRECTION.md)
- **Companion Launcher** verifies your ROM and exposes display, audio
  and gamepad settings. Its Cheats and Mods panel includes optional 1×–8×
  room-clear rewards. The existing hold-Y run and full remapping remain
  available. [Launcher](companion/README.md) · [Cheats and mods](docs/CHEATS-AND-MODS.md)
- **MSU-1 soundtrack** can be imported from a local ZIP or folder with
  validation. Original SNES audio remains available.
  [Soundtrack setup and credits](docs/MSU1.md)
- **Companion Achievements** has a controller-friendly browser on its own Companion page.
  Local progress is available in the opt-in preview.
  [Achievement integration](docs/ACHIEVEMENTS-INTEGRATION.md)

| Companion radar in Freejia | Walkable world map at South Cape |
| --- | --- |
| ![Freejia street with the Companion area radar in the lower-right corner](https://github.com/user-attachments/assets/9a9be356-f8c2-4117-b952-bc3e8f75e75a) | ![Will standing above South Cape on the expanded Mode 7 world map](https://github.com/user-attachments/assets/bfba1b8c-bd55-42c8-a6d6-d355d04d1560) |

## Development status

Original v44 fixes the Watermia save-load frame and the backdrop seams
in the Diamond Mine elevator and Angel Village annex.
[Visual fixes and controller checks](docs/VISUAL-COVERAGE.md#watermia-save-load-and-finite-room-edges)

Original v41 fixes save-resume framing at square-pixel 1.5× across
tested stock rooms. Campaign-wide visual and retranslation checks continue.
[Visual fixes and controller checks](docs/VISUAL-COVERAGE.md#save-resume-framing-across-the-campaign)

Original v39 fixes the Larai Cliff mist seam and preserves square-pixel 1.5×
through the Changed World map, New Babel and the credits.
[Visual fixes and controller checks](docs/VISUAL-COVERAGE.md#larai-cliff-mist-and-ending-framing)

Original v31 keeps the wider view through Babel's victory effects, the
Ship Dream transitions, and the flight into Sky Garden's Mode 7 crash.
[Visual fixes and controller checks](docs/VISUAL-COVERAGE.md#babel-victory-waves-ship-dream-and-sky-garden-flight)

The Original v27 controller replays verify the linked Solid Arm fight and
return to Babel, the rooftop, both Dark Gaia forms and the ending through
the credits and final school scene. Tests used checkpoint-linked virtual
controller input at square-pixel 1.5×. See the coverage notes for the tested
rooms, inherited stat boosts and fallback checks.
[Latest route verification](docs/VISUAL-COVERAGE.md#solid-arm-through-the-ending)

Fully native execution is a development goal. The default source build
interprets the 65816 instructions from your ROM. The private native build
replaces selected execution paths with qualified native code. SPC700 remains
interpreted. The interpreter, renderer reference path and stock world map
remain available. [Native test results and scope](docs/NATIVE-BATCH-025.md)

## Build from source

Install CMake 3.20 or newer, a C11/C++17 compiler, Python 3 and Ninja or Make.
CMake builds SDL3 when needed.

```sh
git clone https://github.com/rages4calm/babel-recomp-companion.git
cd babel-recomp-companion
cmake -S . -B build -DCMAKE_BUILD_TYPE=Release
cmake --build build --config Release --parallel
```

Run the resulting `babel-recomp` executable and select your USA ROM.
On Windows, the executable is `babel-recomp.exe` and multi-config generators
place it under `build/Release/`. The engine accepts the original 2 MiB USA
image with or without a 512-byte copier header.

For the separate Windows Companion Launcher, build the companion adapter
after preparing its .NET 8 and CompanionLauncher package dependencies.
[Launcher setup](companion/README.md)

The ROM, generated game code, extracted assets, music and saves
come from your own local setup. Keep generated game code and private validation
data out of commits. [Build and toolchain notes](scripts/toolchains/README.md)

## Reporting a problem

Report Companion bugs on the [Illusion of Gaia Companion issue tracker](https://github.com/rages4calm/babel-recomp-companion/issues).
Include the build or commit, the area or scene, what you were doing and your
controller, display and mod settings. Attach any relevant log excerpt with
personal paths removed.

## Babel Recomp foundation

**[Babel Recomp](https://github.com/mrOt4/babel-recomp)** by **mr0ta / mrOt4**
provided the starting port and its original platform integrations. The
original documentation records Babel's platform builds, controls, mods and
hardware results. [Babel documentation](https://github.com/mrOt4/babel-recomp#readme) ·
[Documentación original en castellano](README.es.md)

[![Support mr0ta on Ko-fi](https://ko-fi.com/img/githubbutton_sm.svg)](https://ko-fi.com/mr0ta)

## Thanks

This port stands on the work of many people. Thank you all.

- **[mr0ta / mrOt4](https://github.com/mrOt4)** — original author of
  **[Babel Recomp](https://github.com/mrOt4/babel-recomp)**, the foundation
  of this fork. The Ko-fi link above supports the original author.
- **[CompanionLauncher](https://github.com/rages4calm/companion-launcher)**
  and **[CompanionAchievements](https://github.com/rages4calm/companion-achievements)**
  — shared Companion integrations by Carl Prewitt Jr. and contributors (MIT).

- **[snesrecomp](https://github.com/RetroPortingToolKit/snesrecomp)** — the
  SNES static-recompilation framework this port is built on, by Matthew
  Stanley and the R.A.I.D. community; and its launcher,
  **[recomp-ui](https://github.com/RetroPortingToolKit/recomp-ui)**.
- **[GaiaLabs](https://github.com/Azarem/GaiaLabs)** by Azarem — the Illusion
  of Gaia ROM-hacking toolkit, disassembly and database: symbols, text format,
  and the reference patches behind the run button, New Game+, music transitions
  and more. This port would not exist without these tools.
- **Aleks** ([ALEKS Ultimate NX](https://github.com/Alexgg1014/The-Legend-of-Zelda-A-Link-To-The-Past-Alek-s-Ultimate-NX-Edition))
  — for the dual-screen companion (the Dual and Flip Grip layouts) and for
  their help throughout. Its safe boot, crash reporter and RetroAchievements
  storage were adapted here with permission.
- **EstebanPdN** ([zelda-alttp-3ds](https://github.com/EstebanPdN/zelda-alttp-3ds))
  — the port ALEKS Ultimate NX is built on.
- **Illusion of Gaia Randomizer** — DontBaguMe and contributors
  ([IoGR](https://github.com/DontBaguMe/IoGR), [iogr.app](https://www.iogr.app));
  the **Apocalypse Gaia** patch by a member of that community, and its
  playtesters.
- **MSU-1 pack authors**, in particular **Conn** ([Zeldix forum](https://www.zeldix.net)),
  whose track layout this port follows.
- **Emulation research and code** in snesrecomp:
  [snesrev zelda3](https://github.com/snesrev/zelda3) and
  [smw](https://github.com/snesrev/smw) (the SNES hardware core),
  [LakeSnes](https://github.com/angelo-wf/LakeSnes),
  [snes9x](https://github.com/snes9xgit/snes9x),
  [bsnes](https://github.com/bsnes-emu/bsnes),
  [ares](https://github.com/ares-emulator/ares) (Cx4),
  [SMWDisX](https://github.com/IsoFrieze/SMWDisX) (IsoFrieze),
  [recompiler-rs](https://github.com/perplexes/snesrecomp) (perplexes),
  [ar-recomp](https://github.com/DerrickGold/ar-recomp) (DerrickGold) — see
  [THIRD_PARTY_ATTRIBUTION.md](snesrecomp/THIRD_PARTY_ATTRIBUTION.md).
- **[RetroAchievements](https://retroachievements.org)** and
  **[rcheevos](https://github.com/RetroAchievements/rcheevos)**.
- **[SDL](https://github.com/libsdl-org/SDL)**,
  **[Dear ImGui](https://github.com/ocornut/imgui)** (Omar Cornut),
  **[stb](https://github.com/nothings/stb)** (Sean Barrett), the
  [Lato](https://www.latofonts.com),
  [Noto Sans Symbols 2](https://github.com/notofonts/symbols) and
  [OpenMoji](https://openmoji.org) fonts.
- **Consoles:** [devkitPro](https://github.com/devkitPro) (devkitA64, libnx,
  devkitARM, libctru), Mesa for Switch
  ([danfromtico](https://github.com/danfromtico/mesa-switch),
  [NaGaa95](https://github.com/NaGaa95/mesa-switch)),
  [VitaSDK](https://vitasdk.org),
  [Project_CTR](https://github.com/3DSGuy/Project_CTR) (makerom) and
  [bannertool](https://github.com/diasurgical/bannertool).
- **[RetroArch / libretro](https://github.com/libretro/RetroArch)** — the GLSL
  shader format and `libretro.h`.
- The **zelda3** ports for [3DS](https://github.com/ProbablyRohan/Z3R-3ds)
  (ProbablyRohan) and [Vita](https://github.com/Rinnegatamante/zelda3)
  (Rinnegatamante), whose build choices informed the handheld versions.
- **Quintet / Enix**, for the original *Illusion of Gaia* (1993). All game
  content belongs to its rights holders.
- Everyone who tested builds and sent logs, screenshots and videos.

## License

The source code is under the
[PolyForm Noncommercial License 1.0.0](LICENSE): free to use, study, modify
and share for any non-commercial purpose. The frameworks keep their own
licenses (`snesrecomp/LICENSE`, `recomp-ui/LICENSE`, and the third-party notices
above). None of them covers the game, which is not distributed here.

Donations through Ko-fi are voluntary and are not a sale of the game or of
this software: everything here is free.

*Illusion of Gaia* is a trademark of its respective owners. This project is
not affiliated with or endorsed by Nintendo, Square Enix or Quintet.
