# Optional MSU-1 music

The Companion soundtrack panel imports music separately from the game package.
Original SNES music works offline; an optional pack is not required to play.
The importer never changes the ROM or applies an IPS patch. Babel already
provides the Gaia music integration.

## Obtain and import a pack

The catalog identifies **Illusion of Gaia Orchestra by JUD6MENT** from the
[Zeldix project listing](https://www.zeldix.net/t1604-illusion-of-gaiatime-gaia-trilogy-ii),
which links the author's [MEGA download](https://mega.nz/file/6OpyGLIQ#uE3VHjqVNrR-hQjOt1wpknC-1-TT8YQkwRwLbSzAtW0).
The launcher opens that download in the browser; complete the provider's download,
then choose **Import ZIP**. This is browser-assisted download followed by local
import. The launcher does not claim to have downloaded a pack it has not fetched.
An existing extracted pack can instead be selected with **Import folder**.

The verified owner-supplied archive has these properties:

| Property | Value |
|---|---|
| ZIP filename | `Illusion of Gaia Orchestra by JUD6MENT.zip` |
| ZIP size | 671,551,176 bytes |
| ZIP SHA-256 | `c9fd1df5590bdeabe411c238d9a7fbb8295b0fefc7ca7cf68ff47da6492604dc` |
| PCM tracks | 28: tracks 1–27 and 31 |
| PCM bytes | 747,852,148 |
| Included credits | `Artist Track Credit Link.docx` (17,357 bytes) |

The public [hash catalog](../companion/soundtrack-catalog.json) contains track
numbers, sizes, loop points and SHA-256 hashes. It contains no music or extracted
game content. Recognition requires the exact cataloged track set and the original
credit document; another valid pack is labeled as a custom pack.

Import streams and verifies the source, which stays unchanged. Progress and
cancellation remain available. Only a complete pack is published under:

```text
<game-folder>/msu1/companion-packs/<content-hash>/
    gaia-1.pcm ... gaia-31.pcm     only the tracks supplied by this pack
    Artist Track Credit Link.docx
    soundtrack-import.json
```

The pack's original filename prefix is normalized to `gaia`; track numbering and
audio bytes stay unchanged. Reimporting identical data reuses the verified pack.
A conflicting or corrupted existing folder is reported without replacing it.
Cancellation or a validation failure rolls back only that import's temporary
staging directory. Existing packs, saves and other user files are preserved.
Imported tracks are rehashed before the launcher offers them for activation.

## Native selection and fallback

Selecting imported music updates Babel's native mod selection, then takes effect
on the next game launch. Selecting original music disables the MSU-1 feature and
keeps the imported pack for later use. Launcher and Babel tools share that native
selection; there is no separate hidden soundtrack mode.

The native state is `<game-folder>/mods/preloaded/state.toml`. Its MSU selection
uses the existing `iog.enhancements` package and `iog.msu1` plugin:

```toml
[[package]]
id = "iog.enhancements"
version = "1.0.0"

[[feature]]
package_id = "iog.enhancements"
id = "msu1"
enabled = true

[[resource]]
package_id = "iog.enhancements"
feature_id = "msu1"
id = "pack"
path = "<absolute-containing-folder>"
```

These are explanatory entries, not a replacement state file. Other mods and
options must survive any update. The mod runtime derives `SNESRECOMP_MSU1` from
the selected folder; setting that environment variable alone does not activate
Gaia's music plugin.

`src/iog_msu.c` retains original S-SMP music for songs absent from the pack.
Script-waited one-shots (tracks 23–26) deliberately keep their original audio so
story events receive the game's completion signals. Sound effects remain the
game's own. Randomizer mode disables this stock-address music integration.
These are inherited engine rules; a short title/intro audio check does not
qualify every song transition or a complete campaign.

## Validation and credits

Each imported PCM must have an `MSU1` header, nonempty aligned 16-bit stereo
samples and a loop point within its sample frames. Import rejects duplicate
paths/tracks, mixed pack prefixes, traversal/absolute ZIP paths, links/junctions,
invalid numbering and oversized data. Limits are 31 tracks, 256 MiB per file,
2 GiB total expanded source data and 4,096 source entries. Custom packs receive
format/hash verification; only matching catalog bytes receive the JUD6MENT
catalog identity. Patches and ROM files are never imported.

JUD6MENT assembled the orchestral set. Its supplied credit document names
thepsynergist, Plasma3Music Remixes, JD Harding, Steven Morris, Sour Jovis,
Orchestral Fantasy, The Noble Demon, DJ Super Raveman and Fenix Ark Angelus,
with track/source links. Track 4 is credited to the original game's OST.
The document also links the
[maintained track-credit sheet](https://docs.google.com/spreadsheets/d/1TUK-GxtOSf6kJ-TWsNF3L6ZnLCizJu7vkhcvFCdL1n4/edit).
The importer preserves that document unchanged inside the local pack. Babel's
credits to Conn, GaiaLabs, MSU-1 contributors and original game rights holders
remain applicable. Music and the supplied credit document are not included in
Companion source or release packages.

Run the synthetic backend checks with:

```powershell
dotnet run --project companion/tests/Gaia.Companion.Tests.csproj -- --soundtrack-tests
```

The focused suite covers ZIP/folder imports, actual symlink rejection where the
OS allows creating one, malformed headers/loops/alignment, duplicate/traversal
paths, size caps, source preservation, corruption, conflicting installed data,
idempotence and cancellation rollback. Real owner-pack import and engine/audio
checks are separate receipts; synthetic PCM is not soundtrack playback proof.

The November 2 runtime check exercised four isolated, paced 900-frame boots:
the imported orchestral pack, a missing selected folder, a partial synthetic
pack without title track 1, and original audio. All delivered samples to SDL's
dummy audio device and captured a frame. The full pack activated 22 music
replacements and started title track 1. A saved missing folder initially blocked
boot; the optional-resource path now falls back without changing the saved
selection. This is activation/sample-delivery evidence, not speaker-output,
all-song transition, save-state restoration or campaign certification.
