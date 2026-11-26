# GaiaLabs Retranslation data

Two files in this folder are generated from the GaiaLabs Illusion of Gaia
Retranslation project by Azarem and contributors:

- `gaialabs-dialogue.tsv`: the retranslated script, laid out for this port.
- `gaialabs-world-map.bin`: the collision map for the walkable world map.

Source: https://github.com/Azarem/IOGRetranslation at revision
`754d3bfbb0f4452fb33ac0a1c3eb8304ebb0e2cc`.

Both files are distributed under the GNU General Public License, version 3
(`GPL-3.0.txt` in this folder), the license of that project. The scripts that
generate them are in this port's repository:
`scripts/import_gaialabs_dialogue.py`, `scripts/gaia_authored_dialogue.py`
and `scripts/import_gaialabs_world_map.py`.

All credit for the retranslation belongs to GaiaLabs and its contributors.
These files are separate works from the game program, which has its own
license. Delete `gaialabs-dialogue.tsv` to play with the original English
text; delete `gaialabs-world-map.bin` to use the original destination menu.
