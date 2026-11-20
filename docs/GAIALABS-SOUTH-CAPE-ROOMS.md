# South Cape doors at 1.5× in the GaiaLabs preview

The received-content renderer previously recognized South Cape and a narrower
test configuration of the classroom. Regular door entrances into the classroom
and the other nearby rooms could fall back to a centered guest picture with
unused hardware margins.

The preview now draws the cave and house scenery from the running game's two
Mode 1 layers, including both floors of scene 04. It uses the active floor
bounds so neighboring storage pages stay out of the view. The classroom keeps
its verified exterior mask and accepts the wider camera bounds used by its
regular entrances. All paths use a 598×336 picture at 1.5× with square pixels.
Small rooms retain black space around their authored scenery. Dark Space keeps
its live animated center at the same scale and masks the stale side tiles.

All eleven South Cape door records were exercised across eight destinations.
The routes placed Will by the real door triggers and let the game's loader
perform the transitions. A second set queued the exact door records and tested
both movement axes. It matched 308 sampled guest files with the prior preview.
Seven routes returned with directional input. The cave used a saved-story
flag to skip its introductory narration and then returned with directional
input. Three classroom routes used assisted placement at the exit triggers.
The full output was inspected at each arrival, plus 1920×1080 OpenGL captures
of the classroom, houses, Dark Space and a house-to-town fade and return.
The sampled town view after that return was pixel-identical to batch 005.
The SDL virtual controller opened the local map, remapped a control, closed
the map and resumed the guest. The remapped binding was saved to disk.

Unqualified frames still use the guest picture. Set
`IOG_RECEIVED_SOUTH_CAPE_ROOMS=0` to use the old fallback for the cave, houses
and Dark Space. The previous preview launcher is available for comparison.
The guest CPU still uses the interpreter. Private test receipts are in
`.local/batch-001/visual-fullgame-006`. The preview executable is
`babel-mainv2.exe` with SHA-256
`e0cefeda704eb165033909e7e8553879e89fd874a5131a3b03655be4a42b8b2e`.
