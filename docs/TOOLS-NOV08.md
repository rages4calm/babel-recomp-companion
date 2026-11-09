# November 8 tool qualification

Tool refreshes stay beneath ignored `.local/batch-001/native-007/tool-versions`.
They do not change global PATH, tool installations, owner settings or sibling
projects. Official downloads/manifests and checksums are retained privately.

| Tool | Checked selection and reason |
|---|---|
| SNESRecomp | Main remains `e98dc63b474d5469ad984490e04eb0b0496ec62e`, already integrated in batch 006 with Babel's preservation inventory. No newer main revision was available at this check. |
| Managed C/C++ toolchain | [RetroPorting-Toolchains 1.0.14](https://github.com/RetroPortingToolKit/RetroPorting-Toolchains/releases/tag/v1.0.14) matches the installed bundle: Clang 22.1.8, Ninja 1.13.2, bundled CMake 3.31.12. Newer standalone LLVM exists; it is not substituted for the bundle's qualified compiler/sysroot. |
| CMake | Private [4.4.5](https://github.com/Kitware/CMake/releases/tag/v4.4.5), official ZIP checksum verified. The real new candidate configures and builds with it. The managed bundle deliberately pins older CMake for broader compatibility. |
| Python | Private [3.14.10](https://www.python.org/downloads/release/python-31410/), the current maintenance release of the existing interpreter family. Stable 3.15.2 exists; a minor-version migration is separate. Global site/package paths are disabled. |
| pytest | Private 9.2.0 and its five dependencies, downloaded from official PyPI with all six wheel hashes checked. Third-party plugin autoload is disabled. |
| Rust analyzer | Private [Rust 1.99.1](https://github.com/rust-lang/rust/releases/tag/1.99.1), Windows GNU, verified official component manifests/checksums. Debug and release each pass 108 library and 12 analyzer checks. The new graph uses the rebuilt release analyzer through `SNESRECOMP_NATIVE_ANALYZER`. |
| PowerShell | Current application-bundled 7.6.9 runs the actual build script. Legacy Windows PowerShell inherited incompatible module paths in the first attempt; that failed setup remains recorded. |
| RomAtlas | Current main is `a942a3897fcd8e7e335c9c765106c79db39895f9`. Compiled CLI/crate/dependency trees match the retained verified decoder source; intervening atlas/docs/debug-script changes do not require a decoder rebuild. The read-only reference executable remains SHA-256 `376109639e9a2a539f2d47ba8b32898433942869e34b43bc964c06c28d0fdfa6`. |
| Mesen2 MCP | 0.6.0 tag/master remain `a319e226b6d310e2865e44ad3f99a6d6b8a4355d`. Reuse the existing verified private package. No global MCP registration or new external parity claim. |

The new analyzer is SHA-256
`ec1dd9c42b8306c26b8cd5962d49af2e39de073954307ed5bc373b01b297dbf4`;
its source stamp is
`da258fb556f82f7fee1553ac5daf11efc2df97c44fc5102b439ae290cdc1587f`.
The first Rust link attempt lacked the managed sysroot's GCC runtime; the
passing builds use Rust's official self-contained link runtime. The rejected
Python import-site probe and initial build failure are also retained.

`scripts/build_windows.ps1 -CMake <exe>` now accepts an explicit CMake executable.
Its existing `-BuildDirectory` keeps candidate builds below `.local`, leaving
the installed game separate. Qualified absolute paths and environment settings
are in the private `QUALIFIED-TOOLS.json`; they are machine-specific metadata,
not public dependencies or game assets.

Current GaiaLabs/core/baserom/retranslation branches were checked too. Their
public package/source mismatch remains; independently updating packages would
not establish Kassiven's intended dev build. Use the supplied build recipe and
[separate edition identities](GAME-EDITIONS.md) when that build arrives.

Upstream status was refreshed: authored issues #233, #239, #240 and #242 are
closed; [#263](https://github.com/RetroPortingToolKit/snesrecomp/issues/263)
remains open without comments. Timing PRs
[#250](https://github.com/RetroPortingToolKit/snesrecomp/pull/250) and
[#251](https://github.com/RetroPortingToolKit/snesrecomp/pull/251) remain drafts
at the maintainer's previously recorded heads. No duplicate bug report or
unnecessary follow-up message was posted.

The later live aspect diagnostic found a separate screenshot JSON path-escaping
defect. It was independently reproduced with the exact official formatting
call and synthetic inputs, then reported as
[#264](https://github.com/RetroPortingToolKit/snesrecomp/issues/264).
This is a diagnostic API report, not a change to game execution or the deferred
music report.
