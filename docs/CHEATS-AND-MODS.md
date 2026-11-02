# Cheats and Mods

Open **Cheats and Mods** in the Companion launcher's sidebar. Apply or Revert
the main launcher's drafts first and close the game before editing launcher mod
settings. During play, use the game's settings overlay for live supported changes.

The panel reads the actual installed catalog and native
`mods/preloaded/state.toml`. It preserves unrelated features, options, soundtrack
selection, controller mappings and saves. Unsupported catalog entries are disabled.
Apply merges changes atomically and refuses stale settings after an external or
in-game edit; Revert reloads the current file.

| Control | Behavior |
|---|---|
| Infinite HP | Refill positive current HP to the current maximum; a death already under way is not revived. |
| Minimum DP | Maintain a chosen Dark Power balance, 0–999, when enabled. |
| Room-clear rewards | Original 1x or 2x–8x for newly earned, source-verified room-clear stat rewards. HP remains capped at 40; strength and defense at 99. Stats Boost, New Game+, randomizer and Apocalypse Gaia retain original rewards. |
| Minimum stats | Keep selected minimum strength, defense and maximum HP. Zero leaves a stat unchanged. Turning the feature off does not undo stats the game already saved. |
| Item stacking | Combine Red Jewels, Herbs and Crystals into one inventory slot each. |
| Equipped item | Draw an equipped-item frame in the original inventory. |
| Quick item selection | Existing hotswap feature; its configured modifier is preserved. |
| Hold dialogue | Existing hold-to-advance feature; its configured speed and fresh-press questions are preserved. |

Cheats disable local achievement eligibility for the session. The Red Jewel
all-50 action stays in the in-game menu; the launcher does not modify saves to
grant jewels. More specialized mods remain available through Babel tools.

Movement and the existing run-button selection are preserved. Gaia has no new XP
multiplier here: the reward rate operates on its room-clear stat system.

Synthetic native-settings checks cover independent fields, native option strings,
effective disabled rates, BOM/CRLF/comments, existing run/MSU selections, stale
writes, unsupported catalogs, invalid rates, duplicate records and a real running
process gate. They do not certify gameplay effects; runtime qualification belongs
to the engine's matched route/fixture evidence.
