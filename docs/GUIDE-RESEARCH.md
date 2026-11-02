# Guide research and coverage plan

Inspected November 2, 2026. The owner supplied the Classic Games Paradise
walkthrough. This document records **guide expectations and proposed tests**;
it does not establish story flags, completed gameplay, native coverage, or
achievement eligibility. Existing [native evidence](NATIVE-BATCH.md) retains its
stated scope. No guide prose, maps, screenshots or game assets were copied into
the project.

## Complete linked guide inventory

The continuation chain contains four parts and ends at Part 4. Its 32 map
anchors resolve to 20 distinct image URLs; all 20 returned HTTP 200 to read-only
HEAD requests. These links provide navigation references, not extracted map
geometry or verified game-state requirements.

| Part | Topics | Linked area/map targets |
|---|---|---|
| [1](https://classicgamesparadise.com/super%20nes/Illusion%20of%20Gaia%20Guide.html) | South Cape; castle/prison; Itory/Moon Tribe; Incan ruins/Castoth; ship/raft; Freejia. | [South Cape](https://classicgamesparadise.com/super%20nes/Illusion%20of%20Gaia/map%20-%20Illusion%20of%20Gaia%20-%20South%20Cape.png), [Edward's Castle](https://classicgamesparadise.com/super%20nes/Illusion%20of%20Gaia/map%20-%20Illusion%20of%20Gaia%20-%20Edward%27s%20Castle.png), [Edward's Prison](https://classicgamesparadise.com/super%20nes/Illusion%20of%20Gaia/map%20-%20Illusion%20of%20Gaia%20-%20Edward%27s%20Prison.png), [Itory Village](https://classicgamesparadise.com/super%20nes/Illusion%20of%20Gaia/map%20-%20Illusion%20of%20Gaia%20-%20Itory%20Village.png), [Larai Cliffs](https://classicgamesparadise.com/super%20nes/Illusion%20of%20Gaia/map%20-%20Illusion%20of%20Gaia%20-%20Larai%20Cliffs.png), [Freejia](https://classicgamesparadise.com/super%20nes/Illusion%20of%20Gaia/map%20-%20Illusion%20of%20Gaia%20-%20Freejia.png) |
| [2](https://classicgamesparadise.com/super%20nes/Illusion%20of%20Gaia%20Guide%202.html) | Diamond Mine; Neil/Nazca; Sky Garden/Viper; Seaside Palace; Mu/Vampires. | [Diamond Mine](https://classicgamesparadise.com/super%20nes/Illusion%20of%20Gaia/map%20-%20Illusion%20of%20Gaia%20-%20Diamond%20Mine.png), [Sky Garden](https://classicgamesparadise.com/super%20nes/Illusion%20of%20Gaia/map%20-%20Illusion%20of%20Gaia%20-%20Sky%20Garden.png), [Seaside Palace](https://classicgamesparadise.com/super%20nes/Illusion%20of%20Gaia/map%20-%20Illusion%20of%20Gaia%20-%20Seaside%20Palace.png), [Mu](https://classicgamesparadise.com/super%20nes/Illusion%20of%20Gaia/map%20-%20Illusion%20of%20Gaia%20-%20Mu.png) |
| [3](https://classicgamesparadise.com/super%20nes/Illusion%20of%20Gaia%20Guide%203.html) | Angel Village; Watermia; Great Wall/Sand Fanger; Euro; Mountain Temple; Native Village/Ankor Wat. | [Angel Village](https://classicgamesparadise.com/super%20nes/Illusion%20of%20Gaia/map%20-%20Illusion%20of%20Gaia%20-%20Angel%20Village.png), [Angel Village Caverns](https://classicgamesparadise.com/super%20nes/Illusion%20of%20Gaia/map%20-%20Illusion%20of%20Gaia%20-%20Angel%20Village%20Caverns.png), [Watermia](https://classicgamesparadise.com/super%20nes/Illusion%20of%20Gaia/map%20-%20Illusion%20of%20Gaia%20-%20Watermia.png), [Great Wall](https://classicgamesparadise.com/super%20nes/Illusion%20of%20Gaia/map%20-%20Illusion%20of%20Gaia%20-%20Great%20Wall.png), [Euro](https://classicgamesparadise.com/super%20nes/Illusion%20of%20Gaia/map%20-%20Illusion%20of%20Gaia%20-%20Euro.png), [Mountain Temple](https://classicgamesparadise.com/super%20nes/Illusion%20of%20Gaia/map%20-%20Illusion%20of%20Gaia%20-%20Mountain%20Temple.png), [Ankor Wat](https://classicgamesparadise.com/super%20nes/Illusion%20of%20Gaia/map%20-%20Illusion%20of%20Gaia%20-%20Ankor%20Wat.png) |
| [4](https://classicgamesparadise.com/super%20nes/Illusion%20of%20Gaia%20Guide%204.html) | Dao; Pyramid/Mummy Queen; Tower of Babel; Dark Gaia. | [Dao](https://classicgamesparadise.com/super%20nes/Illusion%20of%20Gaia/map%20-%20Illusion%20of%20Gaia%20-%20Dao.png), [Pyramid](https://classicgamesparadise.com/super%20nes/Illusion%20of%20Gaia/map%20-%20Illusion%20of%20Gaia%20-%20Pyramid.png), [Tower of Babel](https://classicgamesparadise.com/super%20nes/Illusion%20of%20Gaia/map%20-%20Illusion%20of%20Gaia%20-%20Tower%20of%20Babel.png) |

## Next natural milestones

The following short sequence paraphrases [Part 1](https://classicgamesparadise.com/super%20nes/Illusion%20of%20Gaia%20Guide.html).
Stop after each milestone to record an independent checkpoint.

| Milestone | Guide expectation | What the test must demonstrate |
|---|---|---|
| Depart South Cape | Cave demonstration, home events, royal invitation. | Dialogue completes and travel becomes available without state injection. |
| Castle to cell | Meet Kara and the king; imprisonment follows. | Correct transition, actors, dialogue and input recovery. |
| Leave confinement | Cell event sequence, telekinesis, key equipped and used. | Inventory/equipment operation and the actual door transition. |
| First combat reward | Clear the southern enemy room for a permanent stat gain. | Enemy count reaches zero, reward appears, corresponding stat changes once; revisit does not duplicate it. |
| First Freedan | Melody/switch route reaches Dark Space; longer reach operates a switch. | Transformation, attack range, puzzle response, return path and form persistence. |

Use fresh isolated saves and matched native/interpreter inputs. Record the last
enemy and first reward effect separately; a scene arrival alone cannot identify
a room-clear reward. Capture terrain, actors, HUD/dialogue, inventory and audio,
then compare CPU state/clocks, memory and devices. Running this plan has not been
claimed here.

## Later form and traversal checkpoints

| Guide source | Candidate test gates |
|---|---|
| [Part 1](https://classicgamesparadise.com/super%20nes/Illusion%20of%20Gaia%20Guide.html) | Itory Psycho Dash; Incan form-dependent reach and melody puzzles. |
| [Part 2](https://classicgamesparadise.com/super%20nes/Illusion%20of%20Gaia%20Guide%202.html) | Mine Dark Friar; Sky Garden top/underside routing; Mu Psycho Slider. |
| [Part 3](https://classicgamesparadise.com/super%20nes/Illusion%20of%20Gaia%20Guide%203.html) | Great Wall Spin Dash; Mountain Temple Aura Barrier; Ankor Wat Earthquaker and glasses. |
| [Part 4](https://classicgamesparadise.com/super%20nes/Illusion%20of%20Gaia%20Guide%204.html) | Pyramid Shadow/Aura descent, alternating forms and hieroglyph routes; Babel barrier and return/save opportunity. |

Test each newly obtained ability first in its acquisition context, then at one
obstacle that requires it. Include refusal with the wrong form or absent ability.
Treat visual likeness, menu text, and a written capability bit as different
observations until source and runtime evidence connect them.

## Jewel checkpoints and missability research

These are **candidate timing/choice risks**, not a verified list of permanently
missable jewels:

- [Part 1](https://classicgamesparadise.com/super%20nes/Illusion%20of%20Gaia%20Guide.html): South Cape bell/jar/fisherman, Seth before ship events, seaside-house pot before departure.
- [Part 2](https://classicgamesparadise.com/super%20nes/Illusion%20of%20Gaia%20Guide%202.html): rescued-laborer reward; Sky Garden/Mu side routes.
- [Part 3](https://classicgamesparadise.com/super%20nes/Illusion%20of%20Gaia%20Guide%203.html): Ishtar's comparison-room chest; Watermia gambling/lotus visit; Lance revisit; Ankor side paths.
- [Part 4](https://classicgamesparadise.com/super%20nes/Illusion%20of%20Gaia%20Guide%204.html): Dao minigame; Pyramid side routes; Babel pedestal before final progression.

The four pages are not an audited 50-location checklist. For each candidate,
verify the acquisition event, unique collection state, repeat behavior and last
return opportunity before describing it as permanently missable. Distinguish
jewels held, handed in, and individually collected; a total cannot identify a
specific missing location. Keep future assistance spoiler-controlled and avoid
turning unverified guide hints into achievement conditions.

## Primary-source cross-check

GaiaLabs was checked at commit `f7649eb735aaf19b2cd8f693fdaa6669b3e42711`:

- Its [US scene metadata](https://github.com/Azarem/GaiaLabs/blob/f7649eb735aaf19b2cd8f693fdaa6669b3e42711/GaiaLib/db/us/scenes.json#L1) identifies `01` South Cape, `02` Coastal Cave,
  `06` Will's House and `08` Church. The guide calls the initial building a
  school; retain both naming contexts rather than inventing another scene.
- The [castle sequence](https://github.com/Azarem/GaiaLabs/blob/f7649eb735aaf19b2cd8f693fdaa6669b3e42711/GaiaLib/db/us/scenes.json#L53) lists `0A` castle, `0B` prison and `0C..13`
  aqueduct rooms. These are scene indices, **not RAM addresses or teleport
  recipes**. The metadata does not select the first reward room or Freedan door.
- [`E6` is shared Dark Space](https://github.com/Azarem/GaiaLabs/blob/f7649eb735aaf19b2cd8f693fdaa6669b3e42711/GaiaLib/db/us/scenes.json#L1245). Arriving there cannot prove a form
  unlocked; return destination and entry/story context still matter.
- [Parts metadata](https://github.com/Azarem/GaiaLabs/blob/f7649eb735aaf19b2cd8f693fdaa6669b3e42711/GaiaLib/db/us/parts.json#L2289) identifies a hidden-jewel actor; the
  [reward actors](https://github.com/Azarem/GaiaLabs/blob/f7649eb735aaf19b2cd8f693fdaa6669b3e42711/GaiaLib/db/us/parts.json#L4294) and [table](https://github.com/Azarem/GaiaLabs/blob/f7649eb735aaf19b2cd8f693fdaa6669b3e42711/GaiaLib/db/us/parts.json#L4706) name HP/strength/defense reward actors and
  `reward_table_01AADE`. This supports a source-trace worklist, not a confirmed
  per-jewel flag or new reward event. Existing [observer guards](ACHIEVEMENTS-INTEGRATION.md)
  still require real transition evidence.

The [IoGR project's mechanics documentation](https://github.com/DontBaguMe/IoGR/blob/master/README.md#room-rewards-and-stat-upgrades)
explicitly changes reward distribution; its [other changes](https://github.com/DontBaguMe/IoGR/blob/master/README.md#other-features)
include relocated Dark Spaces and altered form/travel logic. Do not transplant
randomizer prerequisites into stock-guide tests.

## Assisted coverage authorized by the owner

Cheats, teleporting and flag/state preparation may accelerate testing. Each such
run remains **assisted coverage**, even if cheats are later disabled. Preserve a
separate natural route and exclude assisted sessions from ordinary achievement
eligibility. No state edit, teleport or engine change was performed for this
research.

| Assisted target | Prerequisites to establish before execution | What the result may claim |
|---|---|---|
| First reward room | Source-identified room/entry, valid player/camera, uncleared room state, expected enemy roster and baseline stats. Prefer a naturally captured pre-clear state. | Combat/reward transition from that prepared state; not natural prison completion. |
| First transformation | Verified entry context, return scene, required plot/inventory/ability state and functioning player actor. Preserve pre-transformation form. | Transformation and reach puzzle coverage; not natural acquisition. |
| Later traversal/form gate | Paired before/after checkpoints that establish the relevant inventory, capability, puzzle and travel states. | That gate under documented preparation; not the skipped journey. |
| Jewel risk | Known pre-collection state, matching location/plot window and counter baseline. | One collection/choice behavior; not all-jewel completion or permanence by assumption. |

Resolve prerequisites through source references and controlled pre/post runtime
differences. Never guess flag masks, bulk-enable story bits, or warp only by a
scene label. Prefer the game's validated transition path; a raw scene write may
omit camera, spawn, actor/script, music and return-context setup. Hash-bind every
prepared state and edit manifest, use identical preparation on both execution
paths, and preserve failed attempts.

Prefer survivability assistance without maxing reward stats: a capped stat
cannot demonstrate a stat increase. Record each enabled assist and its lifetime.

Assistance does not relax exact PC/M/X/E classification, code-patch exclusions,
WRAM byte-witness requirements, interpreter fallback or device comparisons.
New scenes produce a new discovery profile and candidate cohort; they do not
retroactively extend the qualified South Cape route into a campaign.
