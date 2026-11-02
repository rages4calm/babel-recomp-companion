# Companion edition icons

These are original AI-generated identity assets for this fork, created with
OpenAI's built-in image generation tool on November 2, 2026. They do not use a
ROM, extracted graphics, box art or another person's icon as source artwork.
This addition does not replace Babel's authorship, support link or existing
credits; the original `res/icon.ico` and console identity assets remain intact.

- `gaia-game.png`: transparent golden flute over a blue/purple world orb, with
  a sweeping luminous comet and gold rim. The prompt requested a clear desktop
  game icon with no text, preserving the flute/orb/comet idea.
- `gaia-launcher.png`: matching transparent flute/orb/comet artwork with a
  purple and gold play badge, distinguishing the launcher from the game.
- The PNGs are unchanged copies of the approved generated outputs. Their
  transparency and full square canvases are preserved.

`build_icons.ps1` uses Windows System.Drawing only for format conversion and
full-canvas downsampling. It creates PNG-backed, 32-bit alpha ICO frames at
16, 20, 24, 32, 40, 48, 64, 128 and 256 pixels. It does not crop, recolor,
redesign or reconstruct the art. Rebuild from this directory with:

```powershell
./res/branding/build_icons.ps1
```

`src/babel-recomp.rc` embeds the game ICO as Windows resource 1. The existing
SDL3 Windows backend uses the first embedded icon for its window class.
`companion/Game.Companion.csproj` sets the launcher executable's ApplicationIcon
and embeds the same ICO for the runtime Windows Forms title-bar icon.
