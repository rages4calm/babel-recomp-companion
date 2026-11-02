# Native batch 003

## Independent source research — November 2, 2026

This section is a preparation record. It does not qualify a teleport, ability,
combat encounter, new area or native function. Batch 002's bounded natural and
assisted evidence remains separate; see [the handoff](../HANDOFF.md),
[guide expectations](GUIDE-RESEARCH.md) and [assisted-test rules](ASSISTED-TESTING.md).
Generation, execution and comparison results must identify their own frozen
inputs rather than inherit a result from this area inventory.

### Dependency and overlay check

Live GitHub default-branch heads were unchanged:

| Dependency | Inspected head | Local decision |
|---|---|---|
| [SNESRecomp](https://github.com/RetroPortingToolKit/snesrecomp/commit/66eebe6ae415b4fb2607a22e5b12352f612e1bdf) | `66eebe6ae415b4fb2607a22e5b12352f612e1bdf` | Preserve current vendor and local fixes; no replacement. |
| [RomAtlas](https://github.com/weisserw/romatlas/commit/3d0d1393149491777626f5a8e4461f7c49b2d6df) | `3d0d1393149491777626f5a8e4461f7c49b2d6df` | Retain verified research executable; no runtime integration or rebuild. |
| [GaiaLabs](https://github.com/Azarem/GaiaLabs/commit/f7649eb735aaf19b2cd8f693fdaa6669b3e42711) | `f7649eb735aaf19b2cd8f693fdaa6669b3e42711` | Read pinned metadata/source; no patch application. |

At the initial research checkpoint, before batch 003 implementation edits, the
tracked SNESRecomp tree was compared with the retained exact upstream export:
1,256 files match after CRLF normalization; 31 paths differ, including nine
whitespace-only differences, and six files are local additions. The substantive
overlays include preserved Babel host/runtime policy, disabled RA backend,
analyzer convergence repair, opt-in instruction/region timing, owner-aware
fallback, APU credit/PB-unwind support and state-dump evidence. Tests and the
[timing contract](../snesrecomp/docs/REGION_PACED_TIMING.md) are included. Export
omissions and nested-library pins remain governed by the earlier preservation
receipt; these counts are not an instruction to overwrite the vendor directory.

The RomAtlas executable still matches its recorded SHA-256. A fresh upstream
compare from its recorded revision to the inspected head reports one commit and
170 changed files, all under `atlas/`; no CLI/SNES decoder source changed in
that range. Its recorded Windows external-assembler refusal overlay remains a
research-tool distinction, not a linked game dependency. Eight GaiaLabs source
blobs used here match the pinned Git tree exactly. Private receipts contain
per-file identities; no other project was modified.

### Static area cohort and incoming-entry provenance

The private research index contains 53 candidate scenes and their original-ROM
incoming records, actor lists and reward-table kinds. A 24-record priority plan
uses the teleport owner's accepted `{name, kind, offset, scene}` schema. Offsets
point to actual source records; tuple bytes are not embedded in public recipes.
The plan covers all four [guide parts](GUIDE-RESEARCH.md#complete-linked-guide-inventory).

| Environment family | Priority scene IDs | Intended coverage, subject to prerequisites |
|---|---|---|
| Town/interior baseline | `01`, `03`, `06` | South Cape, two houses; dialogue, actors, camera and return transitions. |
| Castle/prison/aqueduct | `0A`, `0B`, `0C`, `0D`, `10` | Audience/cell context, combat reward and puzzle/item rooms. |
| Itory/Inca | `15`, `1D`, `20`, `21`, `22` | Town, cliffs, corridors and river environments. |
| Mine/Sky Garden/Mu | `3F`, `4D`, `5F` | Dense combat, elevated routing and water-state contexts. |
| Angel/Watermia/Great Wall | `6B`, `78`, `83` | Town actors, dialogue and vertical traversal. |
| Mountain/Angkor | `A1`, `B6` | Dense actors and traversal/puzzle environments. |
| Dao/Pyramid/Babel | `C3`, `CC`, `E0` | Late town, mixed-form puzzle hub and tower context. |

Names/indices come from pinned [US scene metadata](https://github.com/Azarem/GaiaLabs/blob/f7649eb735aaf19b2cd8f693fdaa6669b3e42711/GaiaLib/db/us/scenes.json), not inferred room names. The wider index also includes paired Garden surfaces, reward-bearing rooms and boss environments. Missing ordinary incoming records for some boss scenes are explicitly unresolved; no synthetic entry was invented.

The pinned [struct definitions](https://github.com/Azarem/GaiaLabs/blob/f7649eb735aaf19b2cd8f693fdaa6669b3e42711/GaiaLib/db/us/structs.json) describe `scene_warp` as four bytes followed by the same typed payload as [COP 26](https://github.com/Azarem/GaiaLabs/blob/f7649eb735aaf19b2cd8f693fdaa6669b3e42711/GaiaLib/db/us/copdef.json): byte, word, word, byte, word. The [type reader](https://github.com/Azarem/GaiaLabs/blob/f7649eb735aaf19b2cd8f693fdaa6669b3e42711/GaiaLib/Rom/Extraction/TypeParser.cs) establishes little-endian, same-bank near pointers. A bounded read of the verified original USA image decoded 546 ordinary warp records; empty-list aliases and reserved inventory-scene handling are recorded separately. The schema alone does not name rectangle fields or establish active-game transition readiness; those semantics belong to the teleport owner's independent source/runtime trace.

Actor records were classified through the pinned `enemy`/`actor` discriminator
and header references. Counts describe table entries, not a live enemy roster:
story conditions can suppress actors. For example, `0C` has three enemy-class
records and stock reward kind 1, making it a source-backed HP-reward candidate.
That does not prove a natural clear or identify when its reward actor executes.

### Form, inventory and story prerequisites

The [item dictionary example](https://github.com/Azarem/GaiaLabs/blob/f7649eb735aaf19b2cd8f693fdaa6669b3e42711/GaiaPacker/Patches/ItemDictionary.asm)
provides named item IDs for research, including keys, melodies, statues, glasses,
Aura and the ring. It does not establish that inserting an item also establishes
the corresponding plot, capability, equipment or puzzle state. The
[teleporter example](https://github.com/Azarem/GaiaLabs/blob/f7649eb735aaf19b2cd8f693fdaa6669b3e42711/GaiaPacker/Patches/Teleporter.asm)
explicitly requires adding a modified Dark Space actor; its destination/context
table is patch documentation, not an installed stock teleport API.
`scene_meta`/`scene_actors` transform files are also patch rules, not independent
stock-state truth. No GaiaLabs implementation was copied into the engine.

| Candidate class | Evidence still required before a recipe can claim the mechanic |
|---|---|
| Will traversal abilities | Witnessed acquisition/capability state, correct form, relevant obstacle, and before/after action. |
| Freedan and reach/attack abilities | Valid Dark Space entry/return context, transformation state, and an actual form-dependent interaction. |
| Shadow/Aura and Pyramid routes | Verified form/item/capability relationship and puzzle/travel state, followed by the real descent/interaction. |
| Boss or story-specific room | Encounter-enabled actors and preceding event/puzzle state; rendering a boss room alone is not a boss encounter. |
| Room-clear reward | Unset clear state, live roster, baseline stat headroom and the actual clear/reward transition. |

Exact ability/story flag masks are **not established by this metadata audit**.
Use a source-verified event or matching witnessed checkpoint; do not fill that
gap with random flags. Report static arrival, assisted movement, assisted combat,
ability interaction and natural progression as separate evidence. Preserve every
injected field, checkpoint identity and failed readiness probe.

### Native promotion boundary

Each admitted area needs a complete, loss-free discovery capture from the
selected interpreter reference, with ROM/build/config identities and exact
PC/M/X/E contexts. Preserve code-patch exclusions and mutable-WRAM fallback.
Scene/actor tables do not make internal labels callable native roots or prove
native closure. New emitted candidates still require compilation and matched
execution/device/render comparisons; candidate counts cannot replace observed
native execution. Assistance must remain sticky in eligibility/provenance.

Private research evidence is under `.local/batch-001/native-003/research/`:
`dependency-heads.json`, overlay/source verification receipts,
`area-cohort.json` and `teleport-scene-warp-plan.json`. No ROM, extracted game
assembly, prepared state or guide asset is published with this note.

### Expanded-graph structural check

The 23 selected `collection-left-f8-reference` assisted-area profiles contain
11,541 observed PC/M/X/E contexts. Against the frozen `expanded-v2/generated`
manifest (`858c125d1b895005462324eb5e3a54a92722e42680ce3ef2c71e529847b4bc5f`),
RomAtlas and the framework decoder agree on opcode and instruction length for
8,192 checked contexts: 4,888 new independent decodes and 3,304 reused checks
whose tool, decoder, ROM identity and original bytes still match. There were
zero decode mismatches. This sample represents 99.8726% of recorded interpreted
instruction hits and 151 of 154 unique observed transfer-target contexts.

The three remaining transfer targets are mutable WRAM mirrors of `$0402`;
12 observed WRAM instruction contexts lack a historical byte witness in these
inputs and remain outside cartridge-source verification. Across all observed
contexts, the graph classifies 415 as exact eligible AOT entries, 44 as exact
LLE-only entries, 4,590 as internal labels only and 6,492 as having no exact
entry or label. These are structural classifications, not executed native
coverage, callable-context proof, timing parity or campaign qualification.

Private receipt: `research/structural-expanded.json` and its companion log under
the batch directory. The verified stock ROM and read-only research executable
retain the identities documented in [the RomAtlas plan](ROMATLAS-PLAN.md).



## Selected implementation and execution

Batch 003 is route-qualified partial native execution. The selected private
executable is SHA-256 `6e3abd83b0fa57ec3708ab893e5e60a502d0fcd3c42ea988b47cc804c405fc7a`.
Its graph is `expanded-v3/generated/program_manifest.json`, SHA-256
`858c125d1b895005462324eb5e3a54a92722e42680ce3ef2c71e529847b4bc5f`;
`expanded-v4` identifies the final runtime/evidence revision of that graph.
It has **231 profile roots, 952 variants, 877 eligible candidates and 75 LLE
variants**. These are structural counts, not executed-function coverage.
All **6,460 explicit PC/alias guards** remain; reset/NMI, boot polling, mutable
actor/OAM and changing WRAM stubs still use interpretation.

The cohort combines a fresh selected-build residual and 23 area captures.
Three historical profiles seed analysis with their original identities and
separate costs. The strict loader rejects incomplete captures, loss counters,
nonfinite numbers and mixed current build identities; it does not relabel old
profiles or sum overlapping historical costs into current coverage. Generation
used the owned Windows Job Object, 4 GiB/300 seconds, 1,024 instructions and
12,000 nodes. It finished in 12.38 seconds with about 229 MiB peak commit and
zero guarded-range violations. See [residual planning](NATIVE-003-PLANNING.md).

The main mechanism is conservative cached-pointer pacing across six addressing
modes and eight accumulator/load/store operations. Low-WRAM preview guards run
before guest mutation; accepted instructions fetch each pointer once through
the paced bus, retain 24-bit indexing carry and reject device/word-wrap cases.
Dispatch, software interrupts and unsupported operations retain fallback.
The opt-in [timing contract](../snesrecomp/docs/REGION_PACED_TIMING.md) records
its limits. Default source builds remain interpreter-only.

| Matched case | Frames per tier | Observed native CPU cycles | Result |
|---|---:|---:|---|
| Cold boot, classroom dialogue/movement, South Cape, 4:3 | 6,000 | 34,243,529 / 255,149,254 (**13.4210%**) | Pass |
| Same cold route, 16:9 | 6,000 | 37,900,137 / 270,357,536 (**14.0185%**) | Pass |
| 23 source-backed area entries, all four guide parts | 600 each | **10.3480%–20.9685%** by case | All pass |
| Continuous original portal/statue sequence to Freedan / Shadow | 2,000 each | **7.5103% / 7.6786%** | Both pass |
| Original form roundtrips, returning to Ankor / Pyramid | 3,000 each | **10.0215% / 10.3572%** | Both pass |
| Original inventory open/close in Aqueduct / Babel | 400 / 260 | Recorded per-case, not campaign coverage | Both pass |

The cold route's previous shares were 6.2645% / 6.3244%. The new executable's
forced interpreter also matches the retained F8 reference for both aspects and
all 23 area scripts. All 62 runs above have complete, zero-loss captures.
These 36,460 frames per tier are separate, partly overlapping fixtures; they
are not one continuous campaign.

Comparisons require identical CPU/WRAM rows, CPU/master totals, complete
memory/PPU/frame snapshots, DMA/PPU journals, serialized SPC/RAM/DSP/PCM-ring and
scheduler/port-queue state, and full final rendered output. Both the previous
`samples` contract and the stronger new `cycles` contract pass all these cases.
The latter binds every row of an event-time `.apu-clock.tsv` sidecar to its
unchanged raw `.apu.tsv` row and requires identical executed APU cycles for
SPC events. CPU events retain full host-frame/beam stamps; SPC event order,
port/value, DSP sample and executed cycle all remain exact. SPC host-frame/beam
stamps describe when batched catch-up logged the event, not an independent
hardware timestamp. Raw differences remain in every receipt. Neither mode is
a bus-phase/hardware oracle; strict raw-byte mode remains the default.

### Audio failure and correction

Expanded v2 and v3 are **failed** receipts. Their CPU, rendering and saved audio
state matched, but retained SPC events sometimes received different host-frame
tags. Adding boundary flushes alone did not resolve it. The deeper mismatch was
that native credit skipped extended-mode absolute scheduling markers while
interpretation retained them. The final callback matches the interpreted
predicate and applies the existing batch threshold at completed instruction
boundaries, including paired returns. Absolute flushing synchronizes and clears
the marker without relative double-credit. The new event-time APU clock proves
the final SPC sequence at cycle resolution rather than inferring it from a
32-clock DSP sample. Earlier failures were not changed to passes.

### Teleport readiness and assistance

The old South Cape seed was still waiting in the scene-title input loop at
`83:DA8A..DAA4` with `$00B4=$00E0`. Dismiss the banner with real input before
writing the original request. `$0656/$0657/$0660/$0661` are processed controller
input here. They are not camera fields. Do not clear arbitrary story flags.

The stock warp writer also installs `$0AF4/$0AF6` return context from the
original bank-81 row plus four. For incoming flags bit 7, it installs
`$0AF0/$0AF2` and clears that bit in effective flags. Then supply the original
`$064C..0653` tuple and pending `$0642`; let the loader set `$0644` itself.
[scripts/gaia_transition_fixture.py](../scripts/gaia_transition_fixture.py)
checks the owner ROM, reads reviewed incoming rows, records writes and hashes,
waits for request consumption, and requires changed visible terrain/player/HP.
The directional dismissal avoids accidental item-use dialogue after arrival.
The former failed pending-only requests remain failed.

The 23 cases cover houses, castle/prison, Aqueduct, Itory, Inca, Mine, Sky Garden,
Mu, Angel Village, Watermia, Great Wall, Mountain Temple, Ankor, Dao, Pyramid and
Babel. Infinite HP is explicit in both tiers. Net coordinate movement was
witnessed in 11 cases; source-declared enemy entry ranges executed in 12. This
is not proof of hits, kills, room clears or normal story access. Special Garden
and Great Wall entry attempts that exited or waited remain failed; ordinary
incoming alternatives were verified instead.

Freedan uses Ankor's actual context-1 Dark Space portal. Shadow uses Pyramid's
context-1 portal plus one explicit original unlock bit, `$0A16` bit `$10`.
Fixtures position the player at source-derived spatial triggers and execute
original dialogue, animation and resource loading. They never poke the form
selector, player script or resource jobs. Babel's context-0 portal heals and
cannot supply the transformation; that failed attempt remains recorded.
See [form contracts](NATIVE-003-FORMS.md). These are checkpoint-linked assisted
mechanics, not naturally earned forms, ability use or achievement evidence.

### Tests, reproduction and next boundary

- 665 Python tests passed, two existing compiler-path skips, 163 subtests.
- Pointer differential fixtures execute 864 cases against actual `interp816`,
  plus refusal/ownership tests and the existing direct pacing cases.
- Actual boundary/credit fixtures cover nested ownership, null hooks,
  subthreshold/zero/equal thresholds, and absolute flushing without relative
  double-credit. Comparator policy: 33 tests.
- Independent current-source C contracts: 432 bridge checks per fused-read
  mode, 27 interrupt-tail checks and the CPU bus/latch fixture passed.
- Actual SPC event-clock capture and state-export fixtures pass, including
  unavailable-clock refusal, delayed export, wrapped history, producer changes,
  and allocation/open/write/close cleanup. Forty direct audio-history/clock
  processes across all four history modes pass. The PowerShell matrix also
  passes after its test-only failure switch was corrected to treat an empty
  environment value as disabled. Earlier wrapper failures remain recorded;
  production audio behavior was not changed by that fixture correction.

```powershell
./scripts/build_windows.ps1 -NativeBatch .local/batch-001/native-003/expanded-v3 -Jobs 2
# Retained fallback in that same private executable:
$env:SNESRECOMP_INTERPRET_ALL = '1'
# Clear it to allow native execution again:
Remove-Item Env:SNESRECOMP_INTERPRET_ALL
python scripts/gaia_transition_fixture.py --self-test
```

Run the fixture scripts with immutable copied inputs in fresh private output
directories, then compare with `scripts/compare_native_runs.py REF CANDIDATE
--devices --apu-state --apu-clock cycles --output private-report.json`.
Private plans, original tuples, checkpoints and generated game code stay ignored.
Proof index: `.local/batch-001/native-003/selected-v4-proof-index.json`; natural
comparisons, `teleport/expanded-v4-summary.json`, `expanded-v4-cycle-summary.json`,
`teleport/forms-v4-summary.json`, `teleport/forms-roundtrip-v4-summary.json`
and `teleport/inventory-v4-summary.json`.

Remaining boundaries include true attack/hit/kill/reward sequences, earned
abilities, puzzles, bosses, natural story progression, wider area checks and a
hardware/reference oracle. An observed repeated controller-remap path still
needs investigation before the ambiguous attack stimuli can count as combat.
No new movement feature or broad random flag sweep was added. Physical audio,
controllers, non-Windows gameplay and campaign completion remain unqualified.
