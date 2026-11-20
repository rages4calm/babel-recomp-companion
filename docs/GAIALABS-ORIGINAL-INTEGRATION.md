# GaiaLabs features in the Original-based Companion

The Companion uses the verified USA cartridge and its usual renderer, local
scenery map, saves and native dispatch. The private GaiaLabs development build
serves as a reference when a feature needs comparison.

## Retranslated dialogue

The import now covers **728 of 1,138** chapter-dialogue replacements in the
pinned [GaiaLabs IOGRetranslation source](https://github.com/Azarem/IOGRetranslation/tree/754d3bfbb0f4452fb33ac0a1c3eb8304ebb0e2cc).
The importer produces 862 candidates. The runtime accepts 728 with known
stock windows. The earlier pass added 14 shorter-box entries and 50 entries
with stock-matched speaker changes. The current pass accepts 32 more by
retaining the original leading sound-effect command and operand. The
previously accepted 696 dialogue payloads are byte-identical. Entries requiring
choice tables, relocated pointers, a new font, or unverified commands still
use the original text. Menu and sprite lettering are pending.

The text uses the Original localization overlay. Start with a local Git
checkout containing the pinned revision, then generate a pack into the
project's ignored directory.

```powershell
python scripts/import_gaialabs_dialogue.py <local-retranslation-checkout> .local/gaialabs-dialogue.tsv
$env:IOG_GAIALABS_DIALOGUE = (Resolve-Path .local/gaialabs-dialogue.tsv).Path
```

The runtime selects the pack when it is available and no language is
explicitly selected. It also recognizes `i18n/gaialabs-dialogue.tsv` beside
the executable. Use `IOG_LANG=original` or `IOG_GAIALABS_DIALOGUE=0` for
stock dialogue. Keep generated packs private. Credits for the retranslation
remain with GaiaLabs and contributors in the pinned source.

An SDL virtual controller opened and advanced translated dialogue in the
classroom at 1920×1080 with MSU-1 active. The same route used stock text
with the original-language setting and with a refused import.
The previous dialogue pass verified Hamlet's reflowed two-line text
and Kara's three-page conversation from separately assisted Original room
checkpoints. The stock-language test restored the original Hamlet text.
The Watermia arrival replay checks the translated and stock Luke dialogue
and reaches Luke's house in both variants. The stock sound cue remains.

## World map and widescreen

The Original destination menu now extends its verified Mode 7 map band at
square-pixel 1.5×. The menu and its scanline transition retain the original
center picture. `IOG_WORLD_MAP_SPLIT=0` restores the prior centered view.
The Freejia town renderer also preserves the original animated background
phase across the wider view.

Controller input selected South Cape and completed the Original Mode 7
journey. Freejia movement was checked along both axes. The controller also
opened and closed the Companion local map with the dialogue pack active.

### Walkable travel

The Original build uses the GaiaLabs collision data and pace for walking.
Left and Right turn the camera. Up walks forward, Down walks backward, and
the SNES B button enters the nearby named destination. The game uses its own
map art, travel sprite, progression flags and scene loader. The local scenery
map and radar are separate from this view.

The map gives the direction of an available destination while walking and
shows the entry button once within range. SNES B is the bottom face button
on the default controller layout. Turbo defaults to keyboard Tab. The
L2+R2 controller chord is available for an explicit custom binding.

Build the collision data from a local checkout of the pinned GaiaLabs source.

```powershell
python scripts/import_gaialabs_world_map.py <local-retranslation-checkout> .local/gaialabs-world-map.bin
$env:IOG_WALKABLE_MAP_DATA = (Resolve-Path .local/gaialabs-world-map.bin).Path
```

`IOG_WALKABLE_MAP=0` restores the Original destination menu. Missing or
invalid collision data also falls back. The integration uses the fifteen
stock menu destinations and the locations available at each story stage.
A save made while walking returns through the stock menu's Quit destination
if loaded with the feature disabled or the collision data unavailable.
GaiaLabs' four additional entrances and airplane travel are outside this
first pass. The Original scripted journeys retain their existing behavior.

Controller replays used the Original Itory exit, then walked back into Itory
and traveled to South Cape in separate routes at square-pixel 1.5×. The South
Cape test starts from a staged checkpoint with the relevant story flag set.
An otherwise matching run with the flag clear verified the route stays blocked.
The translated dialogue and MSU-1 were both active for the successful routes.

For the follow-up, an SDL virtual controller replayed a player's copied map
save into South Cape and moved inside the town. The direction and entry
prompts were checked at 1920×1080 and square-pixel 1.5×. Recovery from a
walking save with missing map data matched the prior build. In paced dummy
audio runs, the same route with the stock soundtrack and with MSU-1 had no
output underflows or dropped samples. MSU-1 began the South Cape track on
entry. Deliberate turbo in the previous build reproduced audible-sample
drops; this check does not establish behavior across physical audio devices.
