# GaiaLabs Retranslation data

Three files in this folder are generated from the GaiaLabs Illusion of Gaia
Retranslation project by Azarem and contributors:

- `gaialabs-dialogue.tsv`: the retranslated script, laid out for this port.
- `gaialabs-world-map.bin`: the collision map for the walkable world map.
- `gaialabs-mods.bin`: the art, palettes and parallax tables of the JP content
  options (Edward Castle, Itory and Great Wall backgrounds, the red fountain,
  the church cross, the Diamond Mine and prologue palettes), recompressed for
  the game's own loader (the GaiaLabs options package on the Mods page).

Source: https://github.com/Azarem/IOGRetranslation at revision
`754d3bfbb0f4452fb33ac0a1c3eb8304ebb0e2cc` (dialogue and world map) and
`1bedfbad97203df8557e45953225706798f1bb1d` (options).

All three files are distributed under the GNU General Public License, version 3
(`GPL-3.0.txt` in this folder), the license of that project. The scripts that
generate them are in this port's repository:
`scripts/import_gaialabs_dialogue.py`, `scripts/gaia_authored_dialogue.py`,
`scripts/import_gaialabs_world_map.py` and `scripts/build_gaialabs_mods.py`.

All credit for the retranslation belongs to GaiaLabs and its contributors.
These files are separate works from the game program, which has its own
license. Delete `gaialabs-dialogue.tsv` to play with the original English
text; delete `gaialabs-world-map.bin` to use the original destination menu;
delete `gaialabs-mods.bin` (or turn the options off) for the North American art.
