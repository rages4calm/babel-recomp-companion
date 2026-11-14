# Enhanced map and radar direction

Owner-approved November 13, 2026. This is a product contract, not a claim that
the features below are implemented or that the received dev build enables every
GaiaLabs module.

The main game includes GaiaLabs' map foundation, alongside its Retranslation
and approved expanded room maps. Preserve all GaiaLabs and collaborator credits.
The enhanced map is built-in content, not a separate edition or patch selector.

## Approved experience

- A full map screen with smooth zooming/panning, readable markers and controls
  suitable for keyboard/mouse and gamepad.
- An optional compact minimap/radar HUD; follow the player without obscuring
  action, dialogue or the game HUD.
- Persistent exploration/discovery tracking and an understandable distinction
  between explored and unknown areas.
- Render a clean overview from actual map artwork/layers for the large map,
  with a simplified readable layout presentation for the compact radar. These
  views share discovery and marker state; do not just shrink the game window
  with its HUD, transient effects and unrelated sprites baked into the image.
- Player, exit, unopened-chest, enemy, Dark Space and other qualified
  point-of-interest markers, with useful visibility filters.
- Keep the default view readable and spoiler-conscious. Additional information
  can be requested without filling the normal view with every marker.

Use their existing game logic/data where appropriate, then improve the native
presentation. Do not add launcher switches or placeholder map controls before
the underlying functionality works.

## What the inspected GaiaLabs source establishes

The inspected `minimap-v2` source describes player, chest, enemy, Dark Space and
exit markers; unopened chests consult game state. Separate dungeon-map and
world-map facilities exist. The developer also states that minimap/world-map
functionality is part of the newer baserom.

Its compact minimap classifies the actual room collision layer into simplified
floor/wall colors; it does not shrink the scenery artwork. Our large-map decoder
instead uses actual foreground map cells, character graphics and palettes.
The clean radar and artwork view share the same exploration mask.

Persistent discovered-area/fog-of-war behavior has not yet been established in
the received binary. Confirm it before deciding whether to reuse it or supply
native tracking. A module's source presence does not prove it was enabled in
this particular developer build.

## Correctness and integration

Keep discovery and marker state bound to the actual content identity and room
layout. Story-dependent versions, floors, warps and changed maps must not share
an incorrectly merged exploration mask. Save and restore it with the appropriate
game/content profile; never write discovery data into undocumented guest RAM.

Reflect real chest/exit/enemy state rather than showing stale or guessed icons.
Hide undiscovered geometry instead of revealing the entire room immediately.
Markers obey discovery/visibility rules too, so secret chests and enemies do
not reveal hidden areas through the default view. Discovery persists across
save/load; the exact reveal radius/visibility policy must be playtested.
Treat secret information deliberately instead of revealing the complete game
through the default radar. Renderer-only observation must not wake enemies or
change collision, quest flags or gameplay visibility.

The first native helpers and packet-based map preview are documented in
[the full-game batch](VISUAL-FULLGAME-001.md). Camera-rectangle diagnostic masks
are not earned exploration or optical line of sight. Likewise, zero collision
is only an unobstructed-cell diagnostic; slopes, water, ledges and occupied cells
need more precise radar classification. The runtime bindings remain unfinished.

Qualify transitions, room changes, load/rewind, menu/dialogue overlap, viewport
resizing and both input styles. Include source provenance and explicit runtime
evidence; native UI graphics alone do not establish native game logic.
