# GaiaLabs features in the Original-based Companion

The Companion uses the verified USA cartridge and its usual renderer, local
scenery map, saves and native dispatch. The private GaiaLabs development build
serves as a reference when a feature needs comparison.

## Retranslated dialogue

The first import covers **632 of 1,138** chapter-dialogue replacements in the
pinned [GaiaLabs IOGRetranslation source](https://github.com/Azarem/IOGRetranslation/tree/754d3bfbb0f4452fb33ac0a1c3eb8304ebb0e2cc).
The importer produces 862 candidate entries. The runtime accepts 632 that
have a known stock text window and fit its dimensions. Entries that need
choice tables, relocated pointers, a new font, or unverified script commands
continue to use the original text. This pass covers dialogue. Menus, sprite
lettering and the remaining chapter lines still need integration.

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

An SDL virtual controller opened and advanced translated dialogue in the
classroom at 1920×1080 with MSU-1 active. The same route used stock text
with the original-language setting and with a refused import.

## World map and widescreen

The Original destination menu now extends its verified Mode 7 map band at
square-pixel 1.5×. The menu and its scanline transition retain the original
center picture. `IOG_WORLD_MAP_SPLIT=0` restores the prior centered view.
The Freejia town renderer also preserves the original animated background
phase across the wider view.

Controller input selected South Cape and completed the Original Mode 7
journey. Freejia movement was checked along both axes. The controller also
opened and closed the Companion local map with the dialogue pack active.

GaiaLabs' walkable world map is still pending. Building that module alone
relocates game sections, so its output is a reference for integration.
All fifteen stock travel menu destinations matched the module's target
parameters. Its four additional destinations and progression rules still
need verification through the Original game's scene loader.
