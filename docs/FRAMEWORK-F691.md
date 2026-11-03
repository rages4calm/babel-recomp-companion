# Merged framework integration: f6912cd

November 3, 2026. SNESRecomp merged the reported correctness fixes while the
widescreen/control repair was being verified. The title now incorporates main
`f6912cd74e06eb21329aeb5c929d7f374479db80` instead of
`66eebe6ae415b4fb2607a22e5b12352f612e1bdf`.

This was a changed-file, three-way integration. All 14 upstream-changed files
were inventoried against base/local/upstream before modification. Babel's title
and framework changes were preserved; the vendor tree was not replaced.
Analyzer and RDNMI conflicts were equivalent repairs with different spelling;
the preserved source differences retain Babel's diagnostics, APU observations,
native credit/boundary hooks and interpreter ownership/fallback behavior.

The merged changes cover recursive no-return convergence (#244), default
indexed-indirect bank carry (#243), interrupt-entry I/D flags (#245), selectable
RDNMI ownership (#246) and caller-clocked HVBJOY reads (#247). The cached-pointer
pacing adapter was updated for the corrected code generator while retaining
precharge refusal and a single architectural pointer fetch. The new clocked-read
scope wrappers remain intact.

The additional `cpuReadClocked` field is host scope state outside the frozen
serialized region; it is reset to false. The ordinary state format remains
version 10, and the owner's existing F1 state loads successfully. This does not
waive the separately reported canonical audio-continuation failure. Pending PR
#241's per-clock audio/DSP, DMA and version-11 serialization work was not adopted.

## Verification

- **644 Python checks pass, two existing skips; 12 Rust checks pass.**
- A further 75 title generation/comparator/replay checks pass with 243 subtests.
- The real bridge fixture passes **432 checks in each fused-read mode**;
  interrupt-tail checks pass 27 cases and the CPU bus/latch fixture passes.
- Eight fresh wide executions cover four native/interpreter mechanics pairs.
  CPU/WRAM, device state, full APU/PCM/scheduler state, cycle-bound audio events
  and complete 342×224 output agree. Source-verified projectile, Aura, 8x room
  clear and Mummy outcomes still occur. The prior authentic central crops,
  including partial edge tiles, remain identical.
- Fresh town/classroom/walking/running and direct 4:3 comparisons use the
  current merged-head executable, with full output and current-tier comparisons.
- All 26 mod/music checks run again on that executable. They cover positive HP
  refill, real nonlethal damage, minimum DP, dialogue, run controls, menu/message
  guards, 1x/8x room clears and immediate/delayed/missing-pack song startup.

The only extra test adaptation supplies the newly required **actual** hardware
read classifier and scoped-read helper to a source-extracted fixture, including
nested-scope restoration. Source reads explicitly use UTF-8 on Windows. The
initial dependency/encoding failures remain in private logs. Production wrappers
were not removed or weakened to make the tests pass.

The selected executable SHA-256 is
`00429989aabf5cf2d0d0ee9846fa7a2fd490185237863c5aa587c078b280e8bd`.
The generated program remains the existing, guarded batch-004 cohort. Runtime
integration and generator compatibility checks are not new native coverage or
newly generated game code. All intermediate executable identities and their
receipts remain separate. Owner saves, settings, ROM, bindings and music are
unchanged; no release or new public repository was created.

[Visual/control repair and remaining limits](WIDESCREEN-MODS-005.md).
