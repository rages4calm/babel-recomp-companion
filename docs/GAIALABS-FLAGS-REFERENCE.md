# GaiaLabs flag analysis reference

Inspected November 11, 2026 from links supplied by the GaiaLabs team through the
owner. This records upstream research and future test inputs, not new Companion
gameplay execution, native coverage or GaiaLabs runtime compatibility.

Pinned repository: `Azarem/gaia-iog-baserom` at
`5a9ba4b1a43af3b9abe85b7fa271ac900961777e`. This does not replace the older
source identity used by completed native batches or select a patched build.

## Sources and checked structure

- [Generated flag reference](https://github.com/Azarem/gaia-iog-baserom/blob/5a9ba4b1a43af3b9abe85b7fa271ac900961777e/artifacts/flags.json): 916 semantic entries across 687 indexed bits and 910 named aliases. Generated from the US database and flag inventory.
- [US flag database](https://github.com/Azarem/gaia-iog-baserom/blob/5a9ba4b1a43af3b9abe85b7fa271ac900961777e/db-us/flags.json): 687 index records, with multiple scene-specific meanings where needed.
- [Mesen2 results](https://github.com/Azarem/gaia-iog-baserom/tree/5a9ba4b1a43af3b9abe85b7fa271ac900961777e/plans/extracted-audit/mesen2-results): reports, closures, checkpoint index, tool issues and separate harness/specification/raw directories. Only selected text reports were fetched; no checkpoints, ROMs, raw captures or scripts were run.

Private read-only snapshots, hashes and receipts are under
`.local/batch-001/native-018/gaialabs-flags-20261111/`. The generated JSON SHA-256
is `26237ecc0ca2f953e77a31dce035daed4a3fd01f3d0ef391500a3875636bc5c6`;
the database SHA-256 is
`6150118f17b9e100e793ed8084a8d03d1dcc36ede6a8a18c3a3395ae93660b08`.

Checked both files' index/meaning counts, every indexed WRAM address and mask,
and every generated named lookup. All agree internally. This is metadata
consistency, not independent execution of their semantic claims.

| Upstream grade | Meaning records |
|---|---:|
| VERIFIED-RUNTIME | 178 |
| VERIFIED-STATIC | 603 |
| INFERRED | 130 |
| UNKNOWN | 1 |
| Unset | 4 |

These are counts of meanings, not distinct bits. All 178 runtime records carry
upstream ROM label `O`; individual report identities and intervention scope still
need checking. Only 53 meanings have nonempty `requires` arrays. Empty prerequisites
must not be interpreted as proof that arbitrary flag edits form a valid setup.

## Applying the reference

For indexed flag `n`, the declared convention is WRAM byte
`0x0A00 + (n >> 3)`, mask `1 << (n & 7)`. Resolve by scene, domain, save/dungeon
lifecycle and ROM identity as well as by index or name.

| Domain | Useful distinction |
|---|---|
| D1, scene scratch, 0–15 | Scene-dependent meanings; scene loads clear the scratch word. The inventory overlay temporarily saves/clears/restores it. |
| D2, story/world, 16–255 | Persistent event state, with documented exceptions and script clear sites. |
| D3, event/death actions, 256–511 | Event-block application, separate from enemy kill bits and rewards. |
| D4, chests/hidden jewels, 512–767 | Collected state; hidden and chest subranges differ. |
| D5, scene-clear reward, 768–1023 | Reward already claimed, distinct from defeating the enemies. |
| D6, enemy kills, 1024–1279 | Shared enemy-number bits can survive ordinary room transitions; dungeon/reset lifecycle matters. |
| D7, boss rewards/abilities | Boss reward bookkeeping and ability unlocks are separate state. |

D8 non-bitfield gates and D9 scene-meta gates are also documented domains; they
are not additional indexed bit ranges to feed through that address formula.

Concrete cross-check: `sc_school_lesson_done` is index 16 (`$0010`), byte `$0A02`,
mask `$01`, scoped to scene `$08`. It matches our existing classroom observation.
The same index also has a boot-logo meaning in scene `$FB`; a global unscoped
label would be misleading.

Use this to plan controlled boss/reward/chest/ability cases and locate their
actual writers. Set setup-only state consistently on both comparison branches;
keep the tested defeat, collection or reward outcome driven by real gameplay.
Preserve existing mixed/reference fallback and all failed receipts.

## Mesen2 report cautions that affect future fixtures

- [Tool issues T-74/T-77](https://github.com/Azarem/gaia-iog-baserom/blob/5a9ba4b1a43af3b9abe85b7fa271ac900961777e/plans/extracted-audit/mesen2-results/tool-issues.md): a requested target scene, or a cleared transition field alone, does not prove that scene's actors and simulation are ready. The later harness criterion includes 12 consecutive `$36` advances and main-loop entry `$80:80B5`; dismiss the scene banner and bind observations to fresh source/checkpoint identity. This is an external harness observation to cross-check, not a replacement transition API.
- [A1](https://github.com/Azarem/gaia-iog-baserom/blob/5a9ba4b1a43af3b9abe85b7fa271ac900961777e/plans/extracted-audit/mesen2-results/A1_flag_write_census_20261030.md) and [A2](https://github.com/Azarem/gaia-iog-baserom/blob/5a9ba4b1a43af3b9abe85b7fa271ac900961777e/plans/extracted-audit/mesen2-results/A2_flag_read_census_20261030.md): stock-ROM labels coexist with assisted form, ability and transition writes. A census is not a naturally played campaign or proof of every boss/reward outcome.
- [S1](https://github.com/Azarem/gaia-iog-baserom/blob/5a9ba4b1a43af3b9abe85b7fa271ac900961777e/plans/extracted-audit/mesen2-results/S1_20261110.md): distinguish transformed extracted input assembly from raw stock instructions. This reinforces the input-mask caveat already recorded in our developer notes.
- [V1](https://github.com/Azarem/gaia-iog-baserom/blob/5a9ba4b1a43af3b9abe85b7fa271ac900961777e/plans/extracted-audit/mesen2-results/V1_20261110.md): script wait counters count owning-runner passes, which are not universally one-per-frame. Its audio analysis also distinguishes the scene BGM/restore ID `$06F2` from the song currently playing. Keep these clocks and playback evidence separate in timing and MSU tests, including the deferred clubhouse report.
- [R3](https://github.com/Azarem/gaia-iog-baserom/blob/5a9ba4b1a43af3b9abe85b7fa271ac900961777e/plans/extracted-audit/mesen2-results/R3_20261110.md): static reference/reachability findings do not make unused/debug paths natural gameplay roots or establish runtime coverage.
- [Tool issues](https://github.com/Azarem/gaia-iog-baserom/blob/5a9ba4b1a43af3b9abe85b7fa271ac900961777e/plans/extracted-audit/mesen2-results/tool-issues.md): inspect the precise tool, version and report before adopting harness assumptions. Upstream issue notes alone are not a newly reproduced Companion or SNESRecomp bug.

Live actor-list membership matters: freed actor slots may retain old bytes.
Do not classify an actor as alive merely from plausible values in an old slot.
These notes identify future checks; they do not revoke or broaden completed
batch receipts without a reproduced contradiction.

The reviewed stock `O` identity matches our original USA ROM: SHA-1
`38de0c84dd2bc3bdfc0a3d7ab0220c79b70887c3`, SHA-256
`32adc048fd89228a4310c03df243e83de7d436cdb2460b4cc83ade20d359b2bd`.
Stock ROM identity does not remove a probe's disclosed state/flag/VRAM edits.
Nine selected reports total 280,693 bytes; per-file identities and detailed
review remain private beside the flag snapshot. Later closure-ledger summaries
are leads to their underlying reports, not raw evidence independently reviewed
here. No upstream harness or Lua code was executed.

Credit GaiaLabs and the analysis contributors for the database and experiments.
Preserve the project's existing Quintet, Babel mr0ta/mrOt4 and upstream credits.
