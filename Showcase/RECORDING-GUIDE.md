# Illusion of Gaia Companion — recording scenes

Double-click `Scene Picker.exe`, select a scene and press **Play / reset scene**.
The game opens at that scene's checkpoint and you play: there is no scripted
input, no frame limit and no automatic recording.

## How a session works

- Every **Play** makes a new private folder in `Sessions/` (the newest five are
  kept, older ones are deleted). The game files are hard links to `Runtime/`
  (a copy of your installed build, no player data), so a session costs almost
  no disk. Your install, its saves, settings and achievements are never written.
- The checkpoint is copied into the session as state slot 1 and loaded at start
  (Autosave). **F1** returns to it (it asks first). **Play / reset** makes a fresh
  session from the same checkpoint.
- Music: the session points at the MSU-1 pack you imported into the installed
  build (`msu1\companion-packs\…`); nothing is copied. The pack covers 22 songs;
  the others play the original SNES music, as in the game.
- Achievements are recorded in the session's own folder: a throwaway profile.
- Checkpoints were made with the test harness: the story at that point (exact
  story flags), the items of that chapter and maximum life, strength and defence.
  They are not from your own playthrough.

## Settings of every session (the "standard set")

Wide view · HD scaling (smooth) · HD Mode 7 · MSU-1 music · sound on, volume
100 · status display at the screen edges · cheats off · run: hold A (Y button) ·
hold to advance text (Fast) · text speed Normal · radar off · GaiaLabs options as
installed (JP Edward Castle, Itory and Great Wall backgrounds and the other
defaults on; purple Diamond Mine and JP Viper off). A scene's own changes are
listed under *Settings* below and in the picker.

**Window:** a 1600×900 window by default. Tick **Fullscreen 1080p** for
desktop fullscreen on the 1920×1080 display.

## Recording

Use OBS at 1920×1080 / 60 fps (NVENC, Indistinguishable quality). Capture the
game window (Window Capture, or Game Capture in fullscreen) and the game's audio
once (not Desktop Audio and application audio together). Do not use Tab
fast-forward in takes.

Start recording, wait **3 seconds**, act, and keep **3 seconds** after. 20-30 s
for a vista, 40-60 s for a fight is plenty. **Stop OBS before Play / reset** or
before choosing another scene. Keep the picker out of the capture.

Use **Copy video name**, rename the OBS file to it and put it in `Recordings/`.
Raise **Take** for another attempt; keep the extension OBS used (.mkv is fine).

**F9 and F10 are free for OBS** (start / stop recording): the sessions unbind
load and save state slots 9 and 10, which those keys use in the game.

## Controls (keyboard defaults)

| Action | Key |
| --- | --- |
| Move | Arrow keys |
| Attack, talk, confirm (A) | X |
| Cancel (B) | Z |
| Run (Y) | hold A with a direction |
| Area map (Start) | Enter |
| Items (Select) | Right Shift |
| L / R | C / V |
| In-game settings | Esc |
| Back to the scene's start | F1 (asks first) |
| Save state | Shift + F1-F8 |
| Save-state browser / rewind | F11 / F12 |
| Fast forward | Tab |
| Pause / fullscreen | P / Alt+Enter |
| OBS record / stop | F9 / F10 |

A controller works as in your install: LT + Start opens the save-state browser,
LT + L loads slot 1.

## Shot list

| Scene | First take filename | What to capture | Caption | Settings |
| --- | --- | --- | --- | --- |
| 01 — Launcher / PC features | `01_Launcher_Take01.mp4` | Opens your installed Companion launcher. Move slowly through Display (Picture, Scaling), Input and the Controls window, Cheats and Mods, Soundtrack and Achievements; open the Update window to show it, then close it. 3-5 s per page. Do not press Apply, Play or Update. | The Companion Launcher: picture, scaling, controls, mods, soundtrack and updates in one place. | Your installed launcher as it is (not a private copy): leave every setting unchanged. |
| 02 — Edward Castle rampart / wide view | `02_Edward_Castle_Wide_Take01.mp4` | Will stands on the castle rampart under the mountain sky. Wait 3 s for the room title to fade, then walk slowly left to the guard and back right to the wall, 20-30 s. No fighting here. | True widescreen drawn from the game's own scenery: Edward Castle, with the Japanese release's sky (GaiaLabs option). | Standard set: Wide view, HD scaling (smooth), HD Mode 7, MSU-1 music, status display at the edges, cheats off. GaiaLabs JP Edward Castle background on (default). |
| 03 — Great Wall / wide view | `03_Great_Wall_Wide_Take01.mp4` | Will arrives at the left end of the wall walk. Walk right past the gatehouse and along the rampart under the desert sky, 20-30 s; hold A (run) for a stretch. | The Great Wall stretching across the wide view, with the Japanese release's background (GaiaLabs option). | Standard set. GaiaLabs JP Great Wall background on (default). |
| 04 — Sky Garden / wide view | `04_Sky_Garden_Wide_Take01.mp4` | Will stands at the right edge of the Sky Garden's central platform. Walk left along the edge and around the pools, 20-30 s. The skull enemies wander; avoid them or swing at one (X). | Sky Garden: a platform floating over open sky, filling the wide view. | Standard set. |
| 05 — Inca Ruins / Larai Cliff | `05_Inca_Ruins_Wide_Take01.mp4` | Will is at the top right of Larai Cliff beside the giant stone head. Cross the bridge to the left and walk down the cliff paths, 20-30 s. | Inca Ruins in the wide view: more of each area around the original picture, with square pixels. | Standard set. |
| 06 — Diamond Mine / enemies in the wide view | `06_Diamond_Mine_Wide_Take01.mp4` | Will enters the mine at the bottom left; two lizard guards patrol. Walk up between the fences, fight one with X (stand still a moment to show the swing), 30-40 s. | The Diamond Mine, fences and enemies spread across the wide view. | Standard set. |
| 07 — Angkor Wat / path to the main shrine | `07_Angkor_Wat_Wide_Take01.mp4` | Will stands at the gate below the overgrown courtyard. Walk up toward the temple steps, then across the courtyard, 20-30 s. | Angkor Wat's courtyard in the wide view. | Standard set. |
| 08 — Mu / wide view | `08_Mu_Wide_Take01.mp4` | Will stands at the top left of Mu beside the colonnade. Walk right and down past the stone faces and the water, 20-30 s. | The ruins of Mu in the wide view. | Standard set. |
| 09 — Babel Tower / exterior | `09_Babel_Tower_Wide_Take01.mp4` | Will is on Babel Tower's outer walkway beside the winged statue. Walk right along the walkway and up the tower, 20-30 s. | The outside of Babel Tower, arches and walkways across the wide view. | Standard set. |
| 10 — Walkable world map (Mode 7) | `10_World_Map_Walk_Take01.mp4` | Will has just left Freejia onto the world map. Up walks, Left / Right turn: turn slowly to show the horizon, walk toward another place until its name shows, 20-30 s. Do not press X (it would enter a town). | The walkable world map from the GaiaLabs project, its ground drawn by the GPU at window resolution, with a higher camera, place markers and a minimap. | Standard set. Enhanced world map on. |
| 11 — Flight over the ocean (Mode 7) | `11_Ocean_Flight_Mode7_Take01.mp4` | A cutscene: Neil's plane over the ocean after the Sky Garden. Start OBS, press nothing; it plays for about 20 s (the plane flies on, then the scene drops to the sky with parachutes). Stop when it fades. | The flight over the ocean: a Mode 7 scene that reaches the horizon of the wide view, with HD Mode 7. | Standard set. HD Mode 7 on. |
| 12 — Boss / Castoth | `12_Boss_Castoth_Take01.mp4` | Freedan stands in Castoth's chamber; the boss rises after a few seconds. Fight: hit the hands and then the head with X, move between them, 40-60 s. | Boss fight: Castoth, Inca Ruins. | Standard set + Refill HP cheat ON, so a take never ends in a game over (the life bar refills). The checkpoint has maximum life, strength and defence (staged). Achievements pause because of the cheat. |
| 13 — Boss / Vampires | `13_Boss_Vampires_Take01.mp4` | Freedan is at the foot of the Vampires' hall. Walk up until Erik shouts and the Vampires appear, advance their lines with X, then fight, 40-60 s. | Boss fight: the Vampires, Mu. | Standard set + Refill HP cheat ON (the life bar refills). The checkpoint has maximum life, strength and defence (staged). |
| 14 — Boss / Sand Fanger | `14_Boss_Sand_Fanger_Take01.mp4` | Freedan is at the left end of the wall top. Walk right and down the wall to wake Sand Fanger, then fight it in the open, 40-60 s. | Boss fight: Sand Fanger on the Great Wall. | Standard set + Refill HP cheat ON (the life bar refills). The checkpoint has maximum life, strength and defence (staged). |
| 15 — Boss / Mummy Queen | `15_Boss_Mummy_Queen_Take01.mp4` | Freedan enters the Mummy Queen's hall; she descends at once. Fight her with X while moving around the hall, 40-60 s. | Boss fight: the Mummy Queen, Pyramid. | Standard set + Refill HP cheat ON (the life bar refills). The checkpoint has maximum life, strength and defence (staged). |
| 16 — Boss / Solid Arm | `16_Boss_Solid_Arm_Take01.mp4` | Freedan faces Solid Arm. Advance his opening lines with X, then fight from below, stepping left and right, 40-60 s. | Boss fight: Solid Arm. | Standard set + Refill HP cheat ON (the life bar refills). The checkpoint has maximum life, strength and defence (staged). |
| 17 — Final boss / Dark Gaia (Shadow) | `17_Boss_Dark_Gaia_Take01.mp4` | Shadow stands on the comet as Dark Gaia appears. Fight with X, moving around the arena, 40-60 s. Spoiler: the final boss; use sparingly in the edit. | The final battle: Shadow against Dark Gaia. | Standard set + Refill HP cheat ON (the life bar refills). The checkpoint has maximum life, strength and defence (staged). |
| 18 — Dark Space / Will becomes Freedan | `18_Dark_Space_Freedan_Take01.mp4` | Will stands below a Dark Space portal in the Sky Garden. Press Up to step in. Inside, walk left, then up onto the tile in front of the knight statue; press X through the lines (pick the first answer) and watch the transformation, about 30 s in all. | A Dark Space: Gaia's statue turns Will into the dark knight Freedan. | Standard set. |
| 19 — Retranslated text / hold to advance | `19_Retranslation_Text_Take01.mp4` | Will arrives at the right end of the Great Wall and his narration opens at once. Hold X: hold to advance turns each page at reading speed; let go and tap X for single pages, 20-30 s. | The GaiaLabs Retranslation is built in: 1,133 retranslated dialogue entries, menus and room titles. Hold a button to advance text. | Standard set. Hold to advance on at Normal pace (instead of Fast) so each page can be read; text speed Normal. |
| 20 — Area map and radar | `20_Area_Map_Radar_Take01.mp4` | Walk a few steps so the radar in the corner shows, then press Enter (Start) for the area map: C / V zoom, wait 3 s, Z to return. Walk into the courtyard and open it again, 20-30 s. | Area map (Start): a map of the scenery that fills in as you explore, with exits and chests, and a small radar while you play. | Standard set + radar ON. The explored-area records are a private copy of your own (read only), so the map is already partly revealed. |
| 21 — Save states / browser and rewind | `21_Save_States_Rewind_Take01.mp4` | Walk around Mu for 10 s. Press F12 and rewind a few seconds, then resume. Press F11: the browser shows this session's six states (other scenes' places); move through them, load one (confirm), 30-40 s. Shift+F2 saves; F1 returns to the start (asks first). | Save states with a browser and pictures (F11), and rewind (F12); loading and overwriting ask first. | Standard set. Six private states: slot 1 is this scene, slots 2-6 are the castle, Great Wall, Sky Garden, Diamond Mine and Babel checkpoints. |
| 22 — Status display at the screen edges | `22_Edge_Status_Display_Take01.mp4` | Starts with the original centred status display. Walk 5 s, press Esc, choose Status display and switch it to the screen edges, close the menu; walk on and hit a lizard (X) so its life shows at the right, 30-40 s. | Optional status display at the screen edges in the wide view: player life at the left, DP centred, enemy life at the right. | Standard set, but the status display at the edges starts OFF (you switch it on in the in-game settings). |
| 23 — Picture / Original 4:3 | `23_Picture_Original_43_Take01.mp4` | Same rampart as scene 02. Wait 3 s, walk left to the guard and back, 15 s. Record 24 and 25 the same way for a side-by-side. | Original 4:3: the SNES picture. | Picture: Original 4:3 (Wide view off, widescreen off); centred status display (the edge display is a wide-view option). Otherwise the standard set. |
| 24 — Picture / Classic 16:9 | `24_Picture_Classic_169_Take01.mp4` | Same walk as scene 23: wait 3 s, left to the guard and back, 15 s. | Classic 16:9: the older, simpler widescreen. | Picture: Classic 16:9 (Wide view off, widescreen on); centred status display. Otherwise the standard set. |
| 25 — Picture / Wide view | `25_Picture_Wide_View_Take01.mp4` | Same walk as scene 23: wait 3 s, left to the guard and back, 15 s. | Wide view: more of each area around the original picture, with square pixels. | Picture: Wide view; centred status display, so it compares directly with 23 and 24. Otherwise the standard set. |
| 26 — GaiaLabs / Mt. Kress spirit shortcut | `26_GaiaLabs_Kress_Shortcut_Take01.mp4` | Will is on the vine at the top of Mt. Kress. Walk left until he stops beside the spirit, press X, answer Yes, and ride down to the mountain's foot, 20-30 s. | GaiaLabs option: once you have climbed Mt. Kress, a spirit at the top offers to take you back down. | Standard set. GaiaLabs Mt. Kress shortcut on (default). |
| 27 — GaiaLabs / Freejia laborer returns | `27_GaiaLabs_Laborer_Returns_Take01.mp4` | Will stands beside the laborer whose secret he kept. Press Right once to face him, then X; advance his thanks with X until the Red Jewel is given, 20-30 s. | GaiaLabs option: keep the runaway laborer's secret and he later returns to thank you with a Red Jewel. | Standard set. GaiaLabs Freejia laborer return on (default). Story: the laborer was not given away. |
| 28 — GaiaLabs / purple Diamond Mine (JP) | `28_GaiaLabs_JP_Diamond_Mine_Take01.mp4` | Will is in the purple-crystal mine. Walk left past the lizard and along the cave, 20-30 s. | GaiaLabs option: the Japanese release's purple Diamond Mine. | Standard set + GaiaLabs JP purple Diamond Mine ON (off by default). |
| 29 — GaiaLabs / JP Viper | `29_GaiaLabs_JP_Viper_Take01.mp4` | Freedan stands at the foot of a pillar in Viper's sky arena. Walk Up the pillar onto the floating floor; Viper swoops in. Fight with X, 40-60 s. | GaiaLabs option: Viper with the Japanese release's boss sprites. | Standard set + GaiaLabs JP Viper ON (off by default) + Refill HP cheat ON (the life bar refills). The checkpoint has maximum life, strength and defence (staged). |
| 30 — Achievement / Behind the Hedge | `30_Achievement_Hedge_Take01.mp4` | Will stands below Freejia's hedges. Walk Up into the hedge while tapping X until the hidden man speaks; advance his lines with X. The achievement notice appears; keep recording 5 s. Then Esc > Achievements to show it unlocked, 30 s. | Achievements, saved on your PC: a secret unlocks with an in-game notice. | Standard set, no cheats, so achievements record. They go to this session's own folder: a throwaway profile, never your real progress. |

## Editing notes

Captions say only what each feature does. Order suggestion: launcher insert →
vistas (02-09) → world map and flight (10-11) → Dark Space (18) → bosses (12-17,
Dark Gaia last and brief) → map, save states, status display, picture comparison
(20-25) → GaiaLabs options and achievement (26-30). Boss takes use the Refill HP
cheat, so the life bar never empties; do not present those as unassisted play.

Nothing in this folder except `source/`, `scenes.json` and this guide belongs in
the repository: runtime, checkpoints, sessions and videos are ROM-derived or
private. Send only the finished recordings for the edit.

## Maintenance

- `Scene Picker.exe --self-check` checks every checkpoint, the runtime, the ROM
  and the music pack (`picker-self-check.json`).
- After installing a new build: `Scene Picker.exe --build-runtime` copies it into
  `Runtime/`. Checkpoints are save states; if a new build cannot load them they
  must be made again (`.local/batch-001/showcase/stage.py`).
- Rebuild the picker: `dotnet build source -c Release` (it lands in this folder).
