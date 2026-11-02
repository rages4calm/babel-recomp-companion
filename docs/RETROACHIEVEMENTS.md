# RetroAchievements policy and this edition

Policy checked against official documentation on November 2, 2026.

## Decision

Use the independent, offline **CompanionAchievements** system for this edition.
Do not enable RetroAchievements account login, service traffic or remote unlock
submission on the assumption that inherited code is approved. Preserve the
original Babel/RetroAchievements/rcheevos attribution and applicable licenses.
The current implementation and verification status of the edition's service
disablement is recorded below; this policy research is not an account/session
test against the service.

CompanionAchievements is a separate local feature with original definitions.
It does not submit RetroAchievements points, copy that service's achievement
set, synchronize accounts or claim certification. Its live game integration is
still pending; see [ACHIEVEMENTS-INTEGRATION.md](ACHIEVEMENTS-INTEGRATION.md).

## What the official rules establish

The official standalone policy expressly states:

> Decompilations, recompilations, and other unofficial ports are not eligible for standalone sets.

It also requires RetroAchievements administrator approval for standalone support;
meeting the published criteria does not guarantee acceptance. Its exception for
developers integrating their own original game is not evidence of permission
for an unofficial Gaia port. Merely selecting Casual mode does not remove the
explicit exclusion of recompilation-based standalone sets.
[Standalone Support](https://docs.retroachievements.org/general/standalone-support.html)

That rule specifically concerns **standalone sets**. It should not be overstated
as a documented ruling on every conceivable custom emulator client reading an
existing console set. The inspected official pages do not establish that Babel
or this fork has been accepted under such a different arrangement. We therefore
choose local achievements rather than assume an exception or test service limits.
[Standalone Support](https://docs.retroachievements.org/general/standalone-support.html)

The official `rc_client` integration guide documents ordinary emulator clients,
unique product/version identification, login, ROM hashing and memory callbacks.
It explains that unrecognized clients can have Hardcore requests demoted to
Casual, and directs developers to RAdmin for Hardcore validation. Successful
HTTP requests or a working Casual client are technical behavior, not evidence
that an unofficial port was approved for standalone support.
[rc_client integration](https://github.com/RetroAchievements/rcheevos/wiki/rc_client-integration)

Hardcore compliance is a separate approval with identity, feature enforcement,
release-history and integrity requirements. Inheriting another client's identity
or circumventing a restriction is not an acceptable route to support. This
edition will not impersonate an approved emulator or bypass service decisions.
[Hardcore Compliance Requirements](https://docs.retroachievements.org/general/hardcore-compliance-requirements.html)

## What inherited Babel code actually does

This is a source inspection, not a login or remote-unlock test. No user account,
token file or credentials were opened, and no integration session was started.

| Source | Observed behavior |
|---|---|
| `snesrecomp/runner/runner.cmake`, `snesrecomp_target_retroachievements` | Compiles vendored rcheevos and network glue into the host; selects WinHTTP on Windows or libcurl where available |
| `snesrecomp/runner/src/achievements/snes_ra.c`, `SnesRa_Init` | Creates a normal `rc_client`, constructs its User-Agent from app name/version plus the rcheevos clause, and explicitly disables Hardcore |
| Same file, `SnesRa_LoadGameFromFile` / `begin_load_game` | Hashes the owner's original ROM using the SNES hashing routine and loads the service's matching console-game achievement data; does not define a new standalone set |
| Same file, `read_memory` | Supplies WRAM and cartridge SRAM to achievement evaluation |
| Same file, login/lifecycle functions | Supports password login, token persistence/login, per-frame processing and remote requests through `ra_http.c` |
| `snesrecomp/runner/src/desktop/host_main.c` | Exposes account controls in the inherited launcher and settings; passes the window title/build version to initialization |
| `src/iog_mods.c`, `src/iog_ngplus.c` and related mode guards | Block some gameplay-altering sessions; those technical guards do not demonstrate policy approval |
| Inherited `MODS.md` | Describes original Illusion of Gaia's service game ID as 945; the source resolves by ROM hash, rather than hard-coding an approval/client registration ID |

No approval record, administrator correspondence or explicit client-registration
evidence was found in the inspected implementation, README/MODS documentation,
workflow files or public upstream issue titles. This is a bounded absence of
evidence, **not proof that the original author never discussed the integration
privately**. The source's Casual-only comments are an implementation rationale;
they are not an administrator decision.

Keep upstream documentation clearly labeled as historical where it describes
RA functionality that this edition does not expose. Keep credited library
notices even when the runtime path is disabled. Any future change to this
decision requires an applicable official policy change or explicit approval
covering this exact project and proposed behavior; server acceptance alone is
insufficient.

## Edition opt-out implementation and checks

The game's CMake sets `SNESRECOMP_DISABLE_RETROACHIEVEMENTS` before constructing
the desktop host. The framework's opt-out branch compiles only
`snes_ra_disabled.c` for that API and returns before adding rcheevos, the HTTP
adapter or a RetroAchievements network backend. The unchanged upstream service
implementation and notices remain available in source history and the tree.

The stub implements every public `SnesRa_*` function. Attempts to enable or log
in remain disabled, and no function reads a token, ROM, username or password,
opens/deletes a file, creates a client or sends a request. The host removes the
RetroAchievements settings section, excludes the inherited account callbacks,
forces legacy parsed enable flags off, and clears the launcher provider after
all profile/title configuration so a later provider cannot expose account UI.

Verification on Windows Clang Release:

- The rebuilt main executable linked successfully.
- A standalone fixture linked all **13** public API functions and passed **9**
  assertions, covering attempts to enable/login, status strings, bounded/null
  output buffers, shutdown and reinitialization. Static inspection also found
  no filesystem, HTTP or rcheevos calls in the disabled implementation.
- The generated Ninja target/command closure contains the disabled source and
  compile flag, with no rcheevos sources, active `snes_ra.c`, `ra_http.c` or
  RetroAchievements backend library. The final PE import table contains no
  WinHTTP or WinINet import.

These checks establish the compiled service opt-out, not a screenshot-based UI
review or gameplay campaign. Other framework features may retain their own
networking code; this is specifically a RetroAchievements service exclusion,
not a claim that the entire executable contains no network functionality.
Compact private verification is in `.local/batch-001/ra-disabled/receipt.json`.
