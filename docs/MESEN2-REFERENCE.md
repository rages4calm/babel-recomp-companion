# Mesen2 external-reference readiness

Verified November 8, 2026. This checks that the developer-recommended reference
emulator can be controlled privately for later comparisons. It does **not**
establish agreement between Mesen and Gaia Companion, a playable route, native
coverage, hardware accuracy, or compatibility with the newer retranslation.

## Source and runtime identity

- Developer recommendation: [Azarem/mesen2-mcp](https://github.com/Azarem/mesen2-mcp).
- Download: [official Windows x64 v0.6.0 release](https://github.com/Azarem/mesen2-mcp/releases/tag/v0.6.0).
- ZIP SHA-256: `ad0c14df069335278a1e9a632164348a5d27f364c95ebacadf15ef19872246ab`,
  matched against the release's published checksum before execution.
- Inspected release tag commit: `a319e226b6d310e2865e44ad3f99a6d6b8a4355d`.
  This differs from the older `master` identity recorded in the developer notes.
- The running MCP server identified itself as `mesen2-csharp-mcp` **0.6.0**,
  using MCP protocol `2024-11-05`, and listed **81 tools**.

The release binary is not a locally reproduced source build. Download identity,
inspected source identity and observed server identity are recorded separately.
Mesen and this fork retain their authorship and GPL notices; no emulator source
or binary was added to Companion's public source or linked into the game.

## Private portable operation

The reference runtime and results remain under the ignored
`.local/batch-001/native-006/mesen2-mcp/` directory. No global MCP registration
or Codex configuration was changed.

The inspected `ConfigManager.HomeFolder` chooses a portable home when
`settings.json` exists beside `Program.ExePath`. That path is the process's
main executable. Therefore this check runs the private **MesenMcpHost.exe**
apphost directly, with a fresh `{}` settings file beside it. Starting the DLL
through a global `dotnet.exe` would select a different executable directory and
must not be assumed to provide the same isolation.

The successful host log explicitly reports the private runtime directory as
the native dependency/home location. Its defaults disable video, audio and
live input devices; none of those opt-ins was enabled. The subprocess also
uses private application-data paths and an explicit private results directory.
No GUI or computer-control session was used.

## Executed bounded check

Through a temporary newline-delimited stdio JSON-RPC client, the probe:

1. Initialized the server and enumerated its tools.
2. Loaded the owner's clean USA ROM read-only and checked reported identity:
   2,097,152 bytes, HiROM/FastROM, CRC32 `1c3848c0`, SHA-1
   `38de0c84dd2bc3bdfc0a3d7ab0220c79b70887c3`.
3. Paused, read CPU/PPU/timing state and a bounded 32-byte WRAM range.
4. Advanced exactly three frames, then repeated the state and WRAM probes.
5. Stopped the emulator and confirmed the owned process exited with code zero.

The step returned `done`, frame count advanced **1 to 4**, and the observed
master-clock difference was **1,072,104** (three 357,368-clock frames). CPU
execution progressed. Fifteen independent readiness checks passed, including
ROM identity, bounded stepping, portable-home confirmation and clean shutdown.

ROM SHA-256 remained unchanged. The private settings file and the checked
default Documents/Mesen2 settings path were unchanged. Runtime-created save
and debugger directories stayed within the private portable home. No owner
state was loaded or saved, and no owner game settings were modified.

Loading started part of the original boot before the explicit pause. This is
not a synchronized reset checkpoint. A later differential test must match the
exact ROM/profile, reset or checkpoint, inputs, guest execution points and
timing—not compare these three frames with an arbitrary Companion snapshot.

## Reproduction and private receipts

The private probe is retained at
`.local/batch-001/native-006/mesen2-mcp/probe_stdio.py` and accepts a fresh
`--attempt probe-NNN` directory. Its command starts the apphost with only
`--mcp-results-dir=<private absolute path>`; the remaining exchanges are stdio
`initialize`, `tools/list` and the documented `tools/call` requests.

`probe-001/` retains the complete request/response transcript, tool schemas,
stderr, runtime/file hashes, receipt and independent checks. Source hashes for
the portable-home/transport implementation are in
`isolation-source-identity.json`; download verification is in
`download-receipt.json`. These files contain private runtime observations and
must not be published as part of the source or release.

Keep the temporary process stopped between probes. Broader native/reference
comparison and retranslation testing remain separate work.
