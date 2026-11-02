# Stock form and ability prerequisites

This is source research for assisted native fixtures, not a form/gameplay
qualification. The source is the verified bare USA ROM, read without changes,
joined to pinned [GaiaLabs metadata](ROMATLAS-PLAN.md) at
`f7649eb735aaf19b2cd8f693fdaa6669b3e42711`. The bounded framework decoder
used exact COP argument sizes from that metadata and tracked REP/SEP; this is
not another independent RomAtlas check. Private source excerpts, hashes and
frame-specific observations are in `.local/batch-001/native-003/forms/`.

The later [batch 003 execution record](NATIVE-BATCH-003.md) separately qualifies
assisted original Freedan/Shadow transformations and returns to Ankor/Pyramid.
It does not qualify naturally earned abilities or form-dependent puzzles.

## Form state is not a complete startup recipe

| Field | Meaning |
|---|---|
| WRAM word `$0AD4` | Current form: 0 Will, 1 Freedan, 2 Shadow. |
| WRAM word `$0AA2` | Learned ability bits listed below. |
| WRAM word `$0AAC` | DarkSpace availability/entry context, not current form. |
| WRAM word `$0AB2` | Saved valid DarkSpace context after Gaia startup; `$0AAC` is cleared. |

Changing `$0AD4` alone bypasses animation, palette/resource work, sprite setup,
Shadow's companion actor and control restoration. It is unsuitable evidence
that an original form actually initialized correctly. Babel's New Game Plus
code separately clears `$0AD4` while retaining ability state, consistent with
these fields having different responsibilities.

The stock Gaia interaction installs an original script on the real player
actor, resets its wait counter and sets the transformation control bit.
Those scripts begin with the original animation setup, including COP `$8E`
selector 5; the COP handler records `$0AC8`, selects sprite data and requests
the original graphics update through `$09AE` bit `$8000`. The scripts run
their animation waits and original COP `$3B` resource job before restoring
normal play. Do not replace this sequence with a form-number write.

| Transition | Original script execution address | COP `$3B` job selector |
|---|---|---|
| Will → Freedan | `$88:F235` or its dialogue-confirmation variant `$88:F26E` | `$0C` |
| Shadow → Freedan | `$88:F2A3` | `$0C` |
| Freedan → Will | `$88:F37D` | `$0B` |
| Shadow → Will | `$88:F3B1` | `$0B` |
| Will → Shadow | `$88:F5F9` | `$6C` |
| Freedan → Shadow | `$88:F63C` | `$6C` |

The exact ordering matters. For example, Will → Freedan starts its job before
committing form 1 after later animations; Shadow → Freedan commits form 1
before a yield and the job. Will/Freedan → Shadow also creates the original
`$82:B20E` companion actor before committing form 2. All use shared completion
`$88:F6D3`, which restores player script `$82:C3C8`, resets actor wait/motion
fields, adjusts actor flags and clears the transformation control bit. This
table identifies stock paths; directly installing one outside its DarkSpace
caller/resource context has not been qualified.

## Portal context and the corrected Babel boundary

The stock actor constructor at physical `$03:CF38..CF50` interprets the third
scene-record byte. When its low bit is set, it shifts the byte right once
before storing actor field `$0E`. The portal saves this value in field `$24`
before reusing `$0E`; its trigger child retains the saved value. Entry copies
it to `$0AAC`. Gaia startup at `$88:D7AB` saves contexts below 4 in `$0AB2`,
clears `$0AAC`, and dispatches the appropriate room behavior.

Consequently, record byte `$01` means context **0**, `$03` means context **1**,
and `$05` means context **2**. The initial inference that Babel's `$01` record
meant context 1 was incorrect. Both the constructor and existing WRAM snapshots
show that Babel's portal has saved context 0. Its successful DarkSpace visit
and failed Freedan-pad attempt must remain distinct; the failed attempt does
not demonstrate a renderer, loader or transformation bug. There is no Freedan
statue in that context.

The existing Pyramid Main and Ankor Courtyard snapshots instead show saved
context 1 in the original portal and trigger child. These are appropriate
next candidates. Do not force `$0AAC` or edit the current form to conceal an
incorrect portal choice.

## Source-backed assisted recipe

Use fixture-owned settled area checkpoints from the
[assisted area batch](NATIVE-BATCH-003.md), with identical setup for mixed-native
and forced-interpreter runs. The following coordinates are decimal and are
derived from original COP predicates plus existing actor snapshots, not guessed
map positions. Each write, its old value and its source/snapshot hash must be
recorded by the fixture owner.

1. Load the selected private checkpoint, dismiss its original title/banner
   through real input and verify the player pointer, current scene and settled
   loader state. Read the portal's actual script and saved context; require 1.
2. For **Ankor Courtyard**, the observed portal is at `(1064, 800)`. For
   **Pyramid Main**, it is at `(456, 896)`. Stock COP `$44` requires
   `portalX - 16 < playerX <= portalX + 16` and
   `portalY < playerY <= portalY + 16`. Safe centers are respectively
   `(1064, 808)` and `(456, 904)`. Reach them through input, or explicitly
   record a fixture-only position teleport to those source-derived points.
   Use the observed player pointer plus `$14/$16`, not an assumed actor slot.
3. The original trigger also checks `$09EC` bit `$0080` and tests raw Up input
   via COP `$40` mask `$0801`. With the trigger ready, press Up and let the
   original portal/scene pipeline run. Do not invent a destination tuple or
   patch a player script. Verify actual DarkSpace scene `$E6`, dismiss its
   title, and observe Gaia startup before requiring `$0AB2 == 1`.
4. In context 1 while Will, the **Freedan pad** has
   `48 < x <= 80`, `168 < y <= 184`; center `(64, 176)`.
   The **Shadow pad** has `176 < x <= 208` with the same y bounds;
   center `(192, 176)`. These are original COP `$45` spatial triggers, not an
   assumed A-button interaction. Its handler compares player x and `y - 8`
   to the encoded tile rectangle.
5. For Shadow, the original interaction at `$88:F3EA` additionally requires
   story flag `$B4`: byte `$0A16`, mask `$10`. The stock setter is Dao Neil's
   event at physical `$08:A5C3`. If absent, an authorized assisted fixture may
   OR only that bit while preserving the byte's other bits, explicitly labeling
   the story change. Let the stock introduction, choices and transformation
   finish. A flag write does not prove the Dao event was played.
6. Require the expected `$0AD4` value, restored player main/control state,
   visible correct sprites and matched memory/PPU/APU/output evidence. Then
   leave through the original exit and exercise the form in the chosen area.
   Save a new private form checkpoint only after this sequence succeeds.

The source-derived centers are ready for fixture use, but exact input timing,
complete transformations and form-specific play still need runtime receipts.
The research itself did not run an engine or modify a checkpoint. A generic
area-runner pass must not be accepted as a successful transformation when
`$0AD4` remains unchanged.

## Ability and equipment prerequisites

The original reward dispatcher at physical `$09:A42B` selects by DarkSpace
return scene `$0B12`. Its handlers test and OR these exact bits into `$0AA2`:

| Ability | Form | Mask | Return scene | Stock grant operation |
|---|---|---|---|---|
| Psycho Dash | Will | `$0001` | `$15`, Itory | `$09:A484` |
| Psycho Slider | Will | `$0002` | `$62`, Mu | `$09:A58F` |
| Spin Dash | Will | `$0004` | `$86`, Great Wall | `$09:A633` |
| Dark Friar | Freedan | `$0010` | `$42`, Diamond Mine | `$09:A511` |
| Aura Barrier | Freedan | `$0020` | `$A7`, Mountain Temple | `$09:A78A` |
| Earthquaker | Freedan | `$0040` | `$B8`, Ankor Wat | `$09:A6E9` |

These locations agree with the walkthrough's
[Itory route](https://classicgamesparadise.com/super%20nes/Illusion%20of%20Gaia%20Guide.html),
[Diamond Mine and Mu route](https://classicgamesparadise.com/super%20nes/Illusion%20of%20Gaia%20Guide%202.html),
and [Great Wall, Mountain Temple and Ankor route](https://classicgamesparadise.com/super%20nes/Illusion%20of%20Gaia%20Guide%203.html).
Source masks are authoritative for fixtures; guide location names are not
proof that a particular teleported checkpoint earned an ability.

The six known bits combine to `$0077`. Assisted ability setup should OR only
the requested known bits into the observed word, preserving unrelated bits;
do not fill the word with `$FFFF`. A learned-bit assertion is not an exercised
ability. Capture the charge/projectile, slide, spin, barrier or landing effect
under the correct form and comparable original controls. No movement rate or
running behavior needs modification.

Shadow's **Aura is an inventory item**, type `$24`, rather than another bit in
this ability word. The pinned GaiaLabs
[item dictionary](https://raw.githubusercontent.com/Azarem/GaiaLabs/f7649eb735aaf19b2cd8f693fdaa6669b3e42711/GaiaPacker/Patches/ItemDictionary.asm)
names it; the original Pyramid reward path at `$09:A81B` checks/grants that
item. Inventory is the 16 bytes `$0AB4..0AC3`; equipped slot and equipped type
are words `$0AC4/$0AC6`, also used by Babel's existing inventory adapter.
Prefer the original award and inventory menu. If a fixture supplies the item,
use an observed empty slot, preserve other inventory and equip it through the
real menu so the slot/type state agrees. Label the supplied item separately
from a naturally earned reward.

The [Pyramid guide](https://classicgamesparadise.com/super%20nes/Illusion%20of%20Gaia%20Guide%204.html)
specifically uses Shadow with Aura equipped at designated floor-drop locations.
Neither granting the item nor transforming proves that terrain interaction;
it requires its own bounded matched execution. All assisted form, ability and
story setup stays separate from natural progression and achievement evidence.
