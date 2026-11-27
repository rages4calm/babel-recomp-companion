# Mods

> This document describes inherited Babel features. In Companion, optional music
> can also be managed through Soundtrack in the new launcher. Local CompanionAchievements is being
> integrated separately. See [current status](README.md) and [music setup](docs/MSU1.md).

Every mod here is off by default and is switched on from the launcher's
**Mods** page. Nothing taken from a ROM ships with this project: languages,
music and graphics all come from files the player supplies, and the ROM you
play stays the stock USA ROM (the launcher verifies it).

| Package | Feature | What it does |
|---|---|---|
| Languages (`iog.languages`) | Game language | Spanish, French or German text and font from your own *Illusion of Time* ROM |
| Gameplay enhancements (`iog.enhancements`) | Run button | Auto-run: walk to build speed, hold **Y** (or X) to start sooner; or Hold: hold the button with a direction to sprint |
| | Text speed | Normal, Cinematic or Instant; hold the run button to hurry any line |
| | Use key items on the spot | Press A where a key item you carry works and Will uses it, no equipping needed |
| | Red Jewel sparkles | A twinkle over each hidden Red Jewel not found yet, and over the people who would give one |
| | Item hotswapping | Hold **X** and press **L/R** to equip the previous/next item |
| | MSU-1 soundtrack | CD-quality music from an MSU-1 pack |
| | Item stacking | Red Jewels, Herbs and Crystals share one slot, with counters on the inventory screen |
| | Equipped indicator | Frames the equipped item on the inventory screen |
| | New Game Plus | Replay a finished save keeping Will's stats and abilities |
| | Hold to advance dialogue | Keep A/B/Y held to page through dialogue; questions still wait for a press |
| Cheats (`iog.cheats`) | Infinite HP, DP, Stats | Classic cheats with adjustable minimums |
| Apocalypse Gaia (`iog.apocalypse`) | Apocalypse Gaia boss | The restored, unfinished final boss (bring your own patch) |
| Randomizer (`iog.randomizer`) | Randomizer seed | Play an Illusion of Gaia Randomizer (IoGR) seed |
| Graphics effects (`iog.graphics`) | HD scaling | Crisp pixels at any resolution, or smooth redrawn edges (xBR), up to 4K |
| GaiaLabs options (`iog.gaialabs`) | JP content | The Japanese release's Edward Castle, Itory and Great Wall backgrounds, red fountain, church cross, prologue palettes and recoloured Crystal Ring; off by default, the purple Diamond Mine and the JP Viper |
| | Herbs heal fully | A herb refills all of Will's HP |
| | Pyramid portals | Portals lead to the entrance hall's lower area |
| | Pyramid moving floors 2x | The Pyramid's moving floors travel twice as fast |
| *(any data-only package)* | HD graphics | Replacement art, see `snesrecomp/docs/HD_PACKS.md` |

## MSU-1 soundtrack

What you need: an Illusion of Gaia MSU-1 pack, i.e. a folder with the
tracks as `<name>-<N>.pcm` (for example Conn's pack from the Zeldix forum:
`iog_msu1-1.pcm` ... `iog_msu1-31.pcm`).

1. **Do not patch your ROM.** Packs usually come with an `.ips`/`.asm`
   patch (`iog_msu.ips`) for emulators; this port does that job itself and
   needs the stock ROM. Just keep the `.pcm` files together in one folder.
2. Open the launcher, go to **Mods**, enable **Gameplay enhancements ->
   MSU-1 soundtrack** and pick that folder as **MSU-1 pack folder**.
3. Play. Songs the pack has play from it; sound effects stay the game's
   own; any song the pack lacks plays as usual.

For testing without the launcher: `SNESRECOMP_MSU1=/path/to/pack/folder`
(the track name prefix is detected automatically). `IOG_MSU_LOG=1` prints
every song change and the track chosen.

Track numbering follows the existing packs (Conn's pack and GaiaLabs use
the same layout): 1 Title, 2 World, 3 Town (gulls), 4 Dark Space, 5 Dead
Gold Ship, 6 Town (no gulls), 7 Village, 8 Angkor Wat, 9 Castle,
10 Dungeon, 11 Great Wall, 12 Larai Cliffs, 13 Meeting Mother,
14 Shipwreck, 15 Sky Garden, 16 Mu, 17 Pyramid, 18 Boss, 19 Returned
Memory, 20 Final Battle, 21/22 Ending, 23 Lola's Song, 24 Item fanfare,
25 Wind Melody, 26 Memory Melody. Tracks 23-26 play once; the rest loop.

How it works (`src/iog_msu.c`): each song with a track in the pack is
replaced, in memory, by a copy of the game's own silent song, so the sound
chip keeps running the game's driver (sound effects) while the MSU-1 plays
the track; the song change itself is recognised from the game's music loader.

Known limitation: a few cutscenes wait for the music to finish; with a
one-shot MSU-1 track they may continue earlier than in the original.

Not available on the original 3DS / 2DS (a New 3DS has the CPU to spare for
streaming the soundtrack); the option is hidden there.

## Languages

Enable **Languages -> Game language**, choose Español / Français / Deutsch
and select your own ROM of that release (*Illusion of Time*, Spain /
France / Germany) under the feature, or drop it in `languages/` beside the
executable. **Ctrl+L** switches language in game. Untranslated lines fall
back to English.

A few lines have no counterpart in the European releases, such as "Where do
you go?" on the world map and the stone girls. These are translated by hand
(`src/iog_hand_text.inc`). The French and German hand translations are
written without accents.

## Run button, hotswapping, cheats

- **Run**, two styles. *Auto-run* (the default, after andrewclunn's
  *Gaia and Time*): every frame Will actually moves earns a point, or eight
  with the run button (default Y) held; at 120 (two seconds of walking, or
  about a quarter second holding the button) he runs in that direction for
  as long as he keeps moving. Turning sideways keeps the speed; reversing,
  stopping or walking into a wall resets it. *Hold*: hold the run button and
  a direction and Will uses the game's own dash at once.
- **Text speed** (after *Gaia and Time*): *Normal* keeps the game's pacing,
  *Cinematic* types lines that have no pace of their own one letter per frame,
  *Instant* shows every line at once. In Normal and Cinematic, holding the run
  button hurries the line (paced lines at half their delay). It changes only
  the game's per-letter delay ($7E) while a message is up and puts the
  script's value back when it closes.
- **Use key items on the spot** (after *Gaia and Time*, on by default): press
  A where a key item you carry does something and Will uses it: the Prison
  Key, both Incan Statues, the Diamond Block, the Meat on the raft, both Mine
  Keys, the Crystal Ball, the Lift Key, the Palace Key, the Purification
  Stone, the Prayer and Rama's Statues, the Magic Powder, the Tearpot, the
  Mushroom Drops and the Gorgon Flower. No game code is added: for as long as
  A is held the game gets its item button (B) with that item equipped, its
  own item code runs, and the item you had equipped comes back afterwards.
  The spots are the game's own checks (room and tile, read from each item's
  handler). Melodies and hieroglyphs are left to you. It assumes the
  default button type (B is the item button).
- **Red Jewel sparkles** (after *Gaia and Time*, on by default): a twinkle of
  light over each of the sixteen hidden Red Jewels until you pick it up, and
  over Lance (after the party), Ann (the Gorgon Flower trade), the stone girl
  in the Gorgon hut and the snake game in Dao until they have given theirs.
  Where his hack adds a sparkle actor to the game, this draws the light over
  the finished picture: nothing in the game changes, and it shows the same
  in the wide view, its margins and the 4:3 picture. It reads the game's own
  "found" flags, so it disappears the moment the jewel is yours.
- **Hotswapping**: hold X and press L or R to cycle the equipped item
  through the inventory (past either end nothing is equipped). The game's
  item sound confirms it.
- **Cheats**: *Infinite HP* refills HP every frame; *DP* keeps at least the
  chosen amount; *Stats* keeps strength, defense and max HP at least at the
  chosen values (0 leaves one alone). The HUD shows new values when the game
  next redraws it.

These change the game's memory while you play, so they are part of the
netplay mod set: both players need the same selection.

## GaiaLabs options

Options from GaiaLabs' *Illusion of Gaia: Retranslated* patcher
(https://gaiahack.ing, source https://github.com/Azarem/IOGRetranslation),
on the original game. Their defaults follow GaiaLabs; each is a switch on
the launcher's Mods page (GaiaLabs section).

- **JP content**: Edward Castle, Itory and Great Wall backgrounds (with the
  Japanese parallax layers), the red fountain in the Seaside Palace, the
  cross in the church, darker prologue palettes and the recoloured Crystal
  Ring in the inventory; the purple Diamond Mine and the JP Viper (the
  Japanese release's boss sprites) are off by default, as in GaiaLabs. The art is GaiaLabs' module data
  (`i18n/gaialabs-mods.bin`, GPL-3.0), recompressed into the game's own
  format and laid into the ROM image in memory, so the game loads it
  itself: it shows the same in the wide view, its margins and the 4:3
  picture, and the native code runs unchanged. Every byte it replaces is
  checked against the stock ROM first. A change applies the next time the
  room loads.
- **Herbs heal fully**: a herb refills all of Will's HP instead of 8.
- **Pyramid portals: lower hall**: the portals in the Pyramid's rooms take
  you to the lower main area of the entrance hall instead of its top.
- **Pyramid moving floors: 2x**: the Pyramid's moving floors travel twice as
  fast; they cover the same distance and stop in the same place.

GaiaLabs' patches change game code, which the native build cannot take
over; these three do the same to the game's state from the host instead.
Options that overlap this port's own features (map, minimap, widescreen,
walkable world map, run button, text speed) are not taken over. Not yet
available: the title screens, the
shortcuts (Mines to Freejia, Mt. Kress, Angkor Wat), the cut content (Sky
Delivery Man, Blue Journal) and extras (borderless epilogue and adrift text,
Thankful Flower, South Cape return, Freejia slave return, Shira spotlight,
minimal HUD, plain borders) and the Portuguese translation.

## Apocalypse Gaia

The Apocalypse Gaia patch restores the unfinished final boss, fought after
Dark Gaia. It is the work of a member of the Illusion of Gaia Randomizer
community and is **not distributed with this project**: download
`IOG_ApocalypseGaia_12.ips` (v1.2, for the US ROM without header) from the
IoGR community (https://www.iogr.app, Discord linked there).

Tick **Apocalypse Gaia -> Apocalypse Gaia boss** on the Mods page and choose
the `.ips` as **Apocalypse Gaia patch**; untick it to play the original. The
patch is applied in memory only (your ROM file stays stock) and save files
are compatible both ways.

While it is on, the game runs entirely through the interpreter
(`src/iog_ips.c`: compiled code was generated from the stock ROM and would
ignore the patched instructions). Measured on the test route it runs at the
same speed.

## Randomizer

The randomizer mode plays seeds of the **Illusion of Gaia Randomizer**
(IoGR, by DontBaguMe and contributors, https://www.iogr.app): items,
abilities and more shuffled with tested logic, an open world, in-game
trackers and its own goals (see the IoGR README).

1. Make a seed from your own US ROM, either on https://www.iogr.app
   (download the randomized ROM), or locally:
   `python3 tools/randomizer/generate.py <your-us-rom.sfc> --seed 1234`
   (fetches IoGR on first use; needs `pip install bsdiff4 bitstring ips.py`;
   options: `--difficulty`, `--goal`, `--statues`).
2. On the Mods page enable **Randomizer -> Randomizer seed** and choose the
   generated `.sfc`.
3. Play. Disable it to go back to the original game.

The game runs interpreted while a seed is loaded (the compiled code belongs
to the stock ROM). Languages, MSU-1, item stacking, New Game Plus and the
Apocalypse Gaia package stand down (IoGR has its own options for the last
two). **Save files:** a seed uses the same save slots as the original game;
use a separate slot (or back up `saves/save.srm`) and don't continue a
randomizer save with the mode off.

## New Game Plus

With **New Game Plus** on:

1. When the **END** screen has been up a few seconds, press any button, or
   wait a minute. The game asks whether to **save the file as finished**, then
   goes back to the title by itself.
2. Continuing a finished file asks **"Start New Game+?"**:
   - **Yes** starts the journey again in the classroom. Will keeps his max HP,
     strength, defense, abilities and Red Jewel tally; the story, dungeons,
     items and pyramid hieroglyphs are reset.
   - **No** continues the file as it was saved.
3. New Game+ is **harder**: the damage Will takes is doubled in the first round
   and tripled from the second round on.

(The state is the same as the GaiaLabs NewGamePlus patch; the game's own
menus are left stock.)

**Completion** shows in the achievement browser and in the in-game settings. It is worth 100 points:

| Part | Points |
|---|---|
| The 87 rooms whose enemies give a HP/STR/DEF reward | 40 |
| The 50 Red Jewels (given to the Gem Man or held) | 40 |
| The end of the story | 20 |

## Inventory

- **Item stacking**: Red Jewels, Herbs and Crystals keep one inventory slot;
  the inventory screen shows how many you carry. Using one brings out the
  next (still equipped). The extra units are stored in the save file.
  The Jeweler takes every stacked Red Jewel at once, as he does in the
  original game: while his menu is up the jewels are laid out in your free
  slots so his own count takes them and pays each reward tier, and any that
  did not fit are added to his count right after. At 50 jewels he warps you
  to the optional Solid Arm fight on every talk, as in the original.
- **Equipped indicator**: a gold frame marks the equipped item on the
  inventory screen.

## HD graphics

**HD scaling** (Graphics effects package, on by default) keeps the picture
sharp at any window or screen size (720p, 1080p, 4K). It is presentation
only: it never changes how the game plays. Two modes:

- **Sharp pixels**: every SNES pixel is drawn as a solid square block; only
  the single screen pixel on a block's edge is blended, so non-integer sizes
  (e.g. 224 lines on a 1080-line screen) give neither blur nor uneven pixels.
  Works with every renderer (the SDL one needs SDL 3.4 or newer).
- **Smooth edges (xBR)**: the diagonal and curved edges of the art are
  redrawn at the screen's resolution, flat areas stay crisp. Needs
  `[Graphics] OutputMethod = OpenGL` (the default on Switch and Android);
  HD packs and Mode 7 at 4x are already high resolution and are shown sharp.

Off, the picture is scaled as on the original (`LinearFiltering`). Cost: none
measurable (about 285 fps at 1080p on an RTX 4070 SUPER either way).

HD packs replace the art itself. A pack's `fx` lines (tilt-shift, bloom,
vignette, grading) still run on the CPU on the 4x canvas: they blur the
picture and halve the frame rate (58 instead of 125 fps at 1080p measured
with the test pack), so a sharp HD pack should not use them.

See `snesrecomp/docs/HD_PACKS.md`: dump a template from your own game with
`SNESRECOMP_HDPACK_DUMP=<dir>`, redraw it at 1x/2x/4x, and ship it as a
data-only `.snesmod`.

## In-game settings

**Escape** on the keyboard, **ZL + R3** on a pad (rebindable in the
launcher's Hotkeys) opens the settings over the paused game:

- Display: fullscreen (desktop), FPS counter
- Audio: volume
- Illusion of Gaia: HD scaling, language (only those whose ROM you have),
  hold to advance text, text speed, run, use key items on the spot, MSU-1
  soundtrack (next launch)
- System: save states, reset (asks twice), quit (asks twice)

Changes apply at once unless the menu says "applies on the next launch",
and are saved: config.ini for the host's, the mod selection for the game's,
so the launcher shows the same choices.

## Map, achievements and save states

There is no separate Companion menu. Each thing has its own way in:

| What | How |
|---|---|
| Area map | **Start**, wherever the area has a map. Its Back button returns to the game. Where there is no map, Start pauses as it always did. |
| Achievements | The **Achievements** row of the in-game settings, or **I** / **ZL+L3**. Back returns to where you came from. |
| Save state | **Shift+F1–F10**, or **ZL+R** for slot 1. Saving over a state asks first. |
| Load state | **F1–F10**, or **ZL+L** for slot 1. Loading asks first. |
| All save states | **F11**, or **ZL+Start**: the browser with thumbnails. |

Items and Status live on the game's own pause menu (Select), which
scales to the wide view. Each prompt shows the button bound to that
action on your controller, or the key name when no controller is
connected.

**Dual and Flip Grip.** In the settings, *Companion screen* puts a second
screen (Items, Status, Map, Saves, Config) beside the running game:

- **Dual** puts the game and the companion side by side.
- **Flip Grip** and **Flip Grip R** stack them and turn the picture a quarter
  turn, for a console held upright.

In these modes you use the companion by touch while you play. Status shows
live numbers. The menu art is captured again whenever your inventory
changes, which causes a short pause right after you pick something up. The
setting is saved as `[General] CompanionLayout` (`normal`, `dual`, `flip`,
`flip_r`).

**Live map (Dual and Flip Grip).** With the Companion panel beside the
running game, the page list is Items, Status, Map, Saves and Config. The Map
page shows the current area's map around the player and updates as you
move, with the same artwork, fog and exit/chest markers as the paused area
map; a legend names the markers present. Tap R3 (or touch the map) to
switch between the close view and a wider one. Areas without an area map
show "No area map here".

## Hold to advance dialogue

With **Hold to advance dialogue** on, keeping the confirm button (A, B or Y)
held turns dialogue pages one after another (Slow, Normal or Fast). Questions
-- yes/no and every other choice menu -- always wait for a real press: the
game marks a choice menu in RAM ($065C) and nothing is pressed for you then.
It works on the controller input only (the button is let go for one frame at
a steady rhythm), so it behaves the same with run-ahead and netplay.

## Enhanced world map

**Convenience -> Enhanced world map** (on by default, also in the in-game
settings) changes the walkable world map: a higher camera, smoother ground,
pins with names over the places you can travel to, a small minimap, a
clearer "Enter" prompt and control a little sooner after leaving a town.
Turn it off for the original walking view.

## Logs and crash reports (all platforms)

If something goes wrong, send the `logs/` folder that sits beside the game
(`sdmc:/switch/babel-recomp/logs/` on Switch).

| File | Contents |
|---|---|
| `babel-recomp.log` | Debug log of this session, starting with the build and platform. On Switch it sits beside the `.nro`. |
| `previous-session.log` | The session before this one. |
| `crash-latest.log` | The log as it was at the moment of the last crash, with the CPU trace. |
| `crash-YYYYmmdd_HHMMSS.log` | One copy of the log per crash. |
| `crash-latest-report.json` | Machine-readable crash report. |
| `crash_report_*.json` | Machine-readable crash reports. |
| `crash_minidump_*.dmp` | Windows minidump of the crash. |
| `unclean-previous.log` | Left when the last session neither exited nor crashed cleanly, for example after a hang. |

If the folder beside the game is read-only, the logs go to the per-user data
folder instead, and the second line of the log gives the path.
`SNESRECOMP_LOG_FILE=0` keeps the output on the console only.

## Switch: safe boot and crash reports

- Hold **ZL + R3** while the game starts: the shader is cleared and the
  default video output restored (for a shader that leaves the screen black).
- Everything the game reports goes to `babel-recomp.log` beside the `.nro`;
  the previous session's is kept as `logs/previous-session.log`.
- A crash leaves `logs/crash-latest.log` (registers, the last events, and
  how to resolve the addresses against `babel-recomp.elf`); a session that
  hung or was closed from HOME is noted in `logs/unclean-previous.log`.

## Folder layout (all platforms, and the only one on consoles)

Beside the executable (`babel-recomp`, `babel-recomp.exe`, or the folder of
`babel-recomp.nro` on Switch):

- `rom.sfc`: your USA ROM, used without asking.
- `languages/`: your European ROMs (any file name; recognised by content).
- `msu1/`: an MSU-1 pack, used when MSU-1 is on and no folder was chosen.
- `mods/<any name>/`: an unpacked mod (a folder with `manifest.toml`, e.g.
  `mods/modhd/`). It appears on the Mods page like an installed one;
  delete the folder to remove it.
- `shaders/`: RetroArch GLSL shaders (`.glslp` presets and `.glsl`), e.g.
  the contents of RetroArch's `shaders_glsl` pack. On Switch,
  `/retroarch/shaders/shaders_glsl/` is read as well.

## RetroArch shaders

Settings -> DISPLAY -> **Shader** browses the folders above (and
`assets/shaders/`) like RetroArch's own menu; pick a `.glslp` preset or a
single `.glsl`. Shaders need the OpenGL renderer, which choosing one selects.
Multi-pass presets, LUT textures, frame history (`Prev`), float and sRGB
framebuffers, `#pragma parameter` defaults and preset parameter overrides
are supported. HD packs
and the HD scaling option are not combined with a shader (the shader gets
the original 1x picture, as in RetroArch).

On Switch the game asks for desktop OpenGL when a shader is chosen (as
RetroArch does there) and falls back to OpenGL ES 3.0 if it is not
available. Measured with Mesa's shader compiler (the one the Switch uses) on
the 620 presets of RetroArch's official `shaders_glsl` pack: 595 load on
desktop OpenGL and 475 on OpenGL ES (GLSL ES lacks macro token pasting and
other things many presets rely on). The 25 that fail on desktop GL have
errors in the shader itself that NVIDIA's compiler tolerates (gizmo-crt,
the GB Player/SGB "tvout" borders, pal, 2xSaL). RetroArch's `#reference`
presets (what its "Save preset" writes) work, parameter overrides included.

