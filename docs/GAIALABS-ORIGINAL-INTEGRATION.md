# GaiaLabs features in the Original-based Companion

The Companion uses the verified USA cartridge and its usual renderer, local
scenery map, saves and native dispatch. The private GaiaLabs development build
serves as a reference when a feature needs comparison.

## Retranslated dialogue

The import now covers **1,112 of 1,138** chapter-dialogue declarations in the
pinned [GaiaLabs IOGRetranslation source](https://github.com/Azarem/IOGRetranslation/tree/754d3bfbb0f4452fb33ac0a1c3eb8304ebb0e2cc).
The importer supplies 1,120 candidates. The runtime keeps stock text when
a candidate cannot safely preserve its original script. Batch 031 added 28 replacements,
including returning dialogue, Adrift day titles, part of the Edward's
Castle dialogue and the Dao Snake Panic score response. New formatted
rows can retain verified stock pause, input-wait, palette and live
number commands with their original operands. Plain prose can be wrapped
within verified stock window bounds while retaining script controls.
Returning strings keep the stock choice row count, indentation, and return
instruction for interactive choices. The game still runs its own choice
branches. The 793 previous replacements keep their exact encoded bytes
and virtual addresses. A v33 save made with the translated Dark Space
prompt open resumed on v34 with the same picture and saved game state.
Paired controller replays also checked the expanded Dark Space healing
dialogue and walked back to the Aqueduct. From the same assisted 1 HP
checkpoint, both language modes healed Will to full and produced the same
post-exit picture and sampled game state.

Batch 032 adds 12 replacements, including Dark Space advice, Mu dialogue,
and the Aqueduct countdown. The importer transports known shared print
calls and marker tails separately. The runtime preserves the verified
original call and window setup. It validates stock bytes up to the
marker before relocating a suffix and retains the stock entry points.
All 821 prior payloads retain their bytes and virtual addresses.
An assisted Aqueduct countdown replay showed the new text within the
stock window. A v34 save made during healing dialogue resumed with an
identical picture and game state once back in the Aqueduct.
An assisted source-room setup also exercised the shared print call for
Psycho Dash advice. Both language modes advanced through the same save
prompt and returned to the Aqueduct with matching scene timing and
post-exit pictures.

Batch 033 adds four replacements in Angel Village, Native Village and
the final classroom scene. The verified large stock dialogue boxes can
use their full text width. The timed classroom sequence keeps each
original pause and window-clear or close operation. New entries are
assigned after the previous overlays, preserving all 833 earlier
encoded payloads and virtual addresses. Unsatisfied jump and timing
checks leave the original text in place.
The linked 38,000-frame New Babel-to-END replay reached its checkpoints
at the prior scene times with the expanded pack active. A v35 save
made during the translated Psycho Dash advice resumed and continued to
the Aqueduct with matching picture and sampled guest state.

Batch 034 adds 14 replacements using verified stock dialogue boxes that
stay open across speaker changes. The original speaker opcodes and return
boundaries are preserved. All 837 older overlays keep the same encoded bytes
and virtual addresses, including active text pointers in save states.
The Watermia birthday replay continued from Luke's house to the dock and
back, earning Lance's Letter in both the new and original Neil dialogue
paths. Both had the same room-transition timing. The translated page fit
the stock box at square-pixel 1.5×.

Original v38 adds 25 stock choice responses in Freejia, Angel Village,
Watermia, Euro, Native Village, Angkor Wat, Dao and the Moon Tribe camp.
The existing prompt opens the box, and the results keep its stock clear
command, dimensions and branch. Translation is restricted to verified
call sites. All 851 prior payloads and virtual addresses are preserved.
Three v38 controller replays entered Native Village from the Dao route and
tested the map child's choice at 1.5×. From the same restored position and
declared prerequisite flags, both stock and translated Yes unlocked Angkor.
Translated No left it locked.

v40 adds five dialogue entries with a separate stock interior-marker entry
point. Both entry points share one verified translation and preserve the
stock wait before the marker. It also adds two menu descriptions and ten
prologue cards. Paired 1.5× replays exercised both Inca Queen callers, the
Prayer Statue description and equipping, and the second prologue card.
All 970 prior patch payloads and the five previous overlay banks stayed exact.

Original v41 adds 82 chapter translations across stock manual dialogue,
returning fragments and timed sequences. The reflow keeps the original
speaker and voice commands and checks row limits, choices and wait boundaries.
Paired controller replays through the Angkor Wat entrance and the prison-key
reward exercised two of the new paths. Both reward runs granted the same
key and story flag. Both Dao Snake Panic outcomes displayed their live
score, preserved the correct jewel payout, and exited to Dao on controller
input. All 1,002 v40 patches and its six overlay banks retain their bytes
and addresses.

Original v42 adds 19 chapter translations. It validates the stock caller
before extending ability and Dark Space dialogue and uses the original choice
row layout and branch targets for nine further prompts. Linked controller
replays walked from the world map to the Staring Man in Native Village and
verified both replies. A paired Itory portal replay earned Psycho Dash,
read the tutorial and exited back to Itory. Both runs set the same ability
bit and departed on the same frame. The previous 1,164 patches and all 12
overlay banks remain byte-identical.

Original v43 adds eight more entries. The Jeweler's list keeps its original
reward thresholds and their column alignment. Paired controller replays
opened the list in South Cape with and without the five new labels. The
inherited replies keep the original speaker, input wait and return. Paired
controller replays of Edward's reply reached identical follow-up pictures
after the translated or stock response.

Original v44 adds 28 entries, including spoken replies, marker entry
points, timed cards and jingles. The ability announcement prints the
approved wording while the game continues to read the live ability name
from the original bank. Paired controller replays earned Psycho Dash and
exited Dark Space to Itory on the same frame. The Jeweler reward replay
granted the Herb and set the same reward flag with both text paths.

Two standalone timed boxes grow within the original display area. The
script retains its stock pause operands. Paired epilogue replays advanced
through the same scenes with the new boxes. All 1,191 prior patch payloads
retain their bytes and addresses.

Original v45 adds three ending scripts. The paired replays kept all 35
stock pause operands and reached the credits. The dialogue boxes grow
where the approved text needs more lines. The revised placement leaves
the actors visible and keeps the lower card inside the stock viewport.

Original v46 adds 11 entries, including the Incan statue fanfares, the
Comet opening and the New Babel narration. Gem's translated reply uses the
original live jewel count. Paired controller replays confirmed the Incan
Statue A and Herb rewards, the Babel statue ceremony, and the transitions
into the ending. New Babel uses a taller narration box to fit the longer
text. All 1,224 previous patch records retain their bytes and addresses.

Original v47 adds the Watermia and Euro arrival narration and two replies
that return to an original same-bank branch. The arrival sequences keep
the original waits while fitting the approved text in five visible rows.
Controller checks exercise Kara's travel reply and Neil's No branch
followed by Yes. All 1,235 v46 patches retain their bytes and addresses.

Original v48 adds 41 entries with a different method. Earlier passes fitted
new prose into the stock string's own boxes one rule at a time. The remaining
self-contained dialogues differ from stock mainly in their page breaks and
box sizes, so `scripts/gaia_authored_dialogue.py` keeps the pages, rows and
boxes GaiaLabs authored and transcribes them for the stock renderer:

- Stock opens the box before it selects the speaker, because opening a box
  resets the text colours and voice. The transcription reorders the two and
  selects the speaker again after every box it opens.
- Stock templates `$08`-`$0F` have the same row counts as the GaiaLabs ones.
  The two five-row GaiaLabs templates become explicit boxes. The tall top
  box starts at the stock tile row 6, because rows 0-4 hold the status
  display and closing a box there would erase it.
- Opening a box does not erase the previous one. A box that does not cover
  the open box gets a close first.
- GaiaLabs speaker themes above `$15` do not exist in stock. Olman, the
  vampires and the glass-game player use their stock speaker; place themes
  use the plain narration colours.
- The stock font has no ellipsis tile. A row that passes 26 columns once
  ellipses and names are spelled out is wrapped again, and its box grows by
  the row it needs.

The module carries a model of the stock renderer (box origin and size,
cursor row and column, input waits). Every transcribed string must pass it:
all text inside a box the string opened, no row past the box width, no page
past the box height, and the dialogue ended by `[END]`. Only stock strings
that open their own box and end the dialogue qualify. Strings with entry
markers, jumps, shared print calls, table lookups or a returning terminal
stay with the earlier passes.

Each row carries a signature of the USA bytes it was derived from. The
runtime pass (`src/iog_authored_dialogue.inc`) applies a row only when
those bytes are present, and it follows the cursor again before patching.
It runs after every earlier pass. All 1,239 v47 patches and the bytes of
all 13 overlay banks are unchanged.

The 41 strings were also shown by the running game. Each one was bound in
turn to the Incan Statue A notice, which one button press reaches from a
retained checkpoint, and the text layer was read back from memory while a
virtual controller advanced the pages. All 223 pages appeared in order with
the expected box rectangle and rows at square-pixel 1.5×, and the box was
closed afterwards. That first run found the status-display overlap noted
above. This check exercises the renderer with the exact installed bytes. It
does not replay the 41 scenes themselves, so their surrounding scripts and
actors have not been observed with the new text.

The same batch extends the transcription to 21 strings that share a box
with the script that prints them:

- **Choice prompts.** The script's choice command (COP `$BE`) puts its
  cursor a fixed number of rows below the box origin, and the importer
  reads that number from each call site. GaiaLabs scripts sometimes use a
  different row. The last page is rebuilt so the choices start on the stock
  row: the question keeps the sentences that fit above them, a short
  question leaves a blank row, and earlier sentences get a page of their
  own. An option that continues on a second row keeps the stock row count.
- **Strings that return after a page wait.** The script continues in the box
  the stock string leaves open, so a page shown in another box is followed
  by that stock box and its speaker.
- **Replies printed into the caller's box.** The importer finds the script
  commands (COP `$BF`) that print the string and the string each script
  printed before it. The box is used only when every call site agrees and
  the stock text fits it. The pack row records that box, and text may only
  use its rows or a box that covers it.

Six of the 21 use an inherited box. That box is inferred from the script
bytes; it has not been observed in the scenes. All 62 authored strings
(308 pages) passed the in-game page check on one executable, with a
returning string ended and an inherited box opened for the test. The
choice cursor itself only runs in the real scenes, which have not been
replayed. Adding rows moved the virtual addresses of the 41 strings from
earlier in this batch; the 1,239 v47 patches and their bank bytes are
unchanged.

A third pass adds 14 strings with control flow of their own:

- **A second entry point (9).** Scripts start these strings at the
  beginning or part-way in. The whole string and the entry are transcribed
  separately and each gets its own redirect; the entry starts in the box the
  first part leaves open. Lola's dinner line has only a pause in front of
  its entry, shorter than a redirect, so that pause stays in the ROM.
- **A final same-bank jump (3).** A jump cannot run from an overlay bank.
  The text returns after its last page with the stock box and speaker
  restored, and the original jump then runs from the ROM bank.
- **Replies reached through a choice (2).** A reply's calling box is also
  taken from the prompt whose choice table leads to the script site that
  prints it. This evidence has to agree with the string printed before.

All 76 authored rows passed the in-game page check on one executable: 84
streams with the entries, 390 pages. The same limits apply as above. The
entries, jumps and choice cursors run only in their own scenes, which have
not been replayed.

26 chapter declarations still use stock behavior. Ten of them have nothing
to translate: five are a lone box close that is identical in both versions,
and five are stubs that open a box and jump to an entry point. One more
only widens the Jeweler's list box, which the Jeweler's rows below need.
The other 15 are:

- the Jeweler's menu, deposit reply and list row (`08D0F1`, `08D20F`,
  `08D621`), whose box and cursor belong to the Jeweler's own code;
- three strings built from a table lookup or a shared print call
  (`08EB85`, `08E4A4`, `08ED6D`) and one with raw tiles (`039E1A`);
- three timed sequences where GaiaLabs changed the timeline: Lola's melody
  (`049D29`), the plane jump (`0984B1`) and the epilogue card (`0BDC95`);
- two replies whose calling box could not be proven (`06BE85`, `06BF0A`);
- `0595B4`, whose four authored rows do not fit the three-row box its jump
  target continues in; `07944D`, which changes typing speed inside a row
  that needs wrapping; and `0583E7`, where GaiaLabs added a jump.

The list is in `visual-fullgame-040/dialogue/v50-residual.json`.

### Inventory, room titles and map lettering

Original v41 applies all 124 approved console menu entries and all 64 named
room titles. The 177 empty room-title records stay empty. Stock menu slots
retain their layout and control bytes. Fifteen longer titles use the wider
title box and the short stock Mu slot uses a dictionary entry. Paired mixed
and interpreter runs display the same centered Mu title at 1.5×. Virtual
controller replays opened and closed four inventory details and confirmed
that the correct items equipped.

The pack also includes all 35 indexed world-map sprite strings and ten
prologue cards. Dialogue-only packs still load.

A controller replay from Dao showed the translated title on the same frame
and in the original box while leaving the scenery unchanged. A staged Lift
Key inventory test showed the approved label, equipped the original item ID,
and returned to the prison at the same frame as the stock-label control.
A stock Mode 7 flight showed the translated Freesia caption and reached the
Diamond Mine with the same timing as the Freejia control. Lettering baked
into the map artwork remains as authored in the original ROM.

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

A save state made with translated dialogue open needs the same configured
dialogue pack on the next launch. The build installs that pack before the
first game frame, so a restored text pointer is ready when dialogue resumes.
Live language changes still wait for the current dialogue box to close.

An SDL virtual controller opened and advanced translated dialogue in the
classroom at 1920×1080 with MSU-1 active. The same route used stock text
with the original-language setting and with a refused import.
The previous dialogue pass verified Hamlet's reflowed two-line text
and Kara's three-page conversation from separately assisted Original room
checkpoints. The stock-language test restored the original Hamlet text.
The Watermia arrival replay checks the translated and stock Luke dialogue
and reaches Luke's house in both variants. The stock sound cue remains.
The current build shows both newly translated Neil's Cottage dialogue pages,
with the original pauses and speaker changes. The same virtual-controller
replay with `IOG_LANG=original` shows both original pages.
The v33 Dark Space replay checks both save-prompt options with the
retranslation enabled and with stock text selected. The 1.5× screenshots
show the choices at their original positions. The option to record writes
the same save bytes as stock, and skipping leaves those bytes untouched.

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
The entrance itself now checks the Itory story gate too. A controller regression
with a staged save already inside South Cape's entrance radius reproduced the
old bypass. The new build stays on the map while the gate is closed and enters
South Cape after the flag is set.

For the follow-up, an SDL virtual controller replayed a player's copied map
save into South Cape and moved inside the town. The direction and entry
prompts were checked at 1920×1080 and square-pixel 1.5×. Recovery from a
walking save with missing map data matched the prior build. In paced dummy
audio runs, the same route with the stock soundtrack and with MSU-1 had no
output underflows or dropped samples. MSU-1 began the South Cape track on
entry. Deliberate turbo in the previous build reproduced audible-sample
drops; this check does not establish behavior across physical audio devices.
