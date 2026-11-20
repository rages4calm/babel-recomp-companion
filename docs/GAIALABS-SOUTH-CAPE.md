# South Cape at 1.5× in the GaiaLabs preview

The earlier South Cape footage was from the Original build. Its renderer
already supported town. The GaiaLabs preview uses different map data and a
separate renderer that previously admitted only classroom scene 08 for Mode 1.
When it reached South Cape, it centered the 384×224 guest picture in the
598×336 output. The preview also defaulted to enabling the renderer while
requiring an explicit setting to start its sprite publication observer.

The preview now admits the verified received town layout. It reads both aligned
5×4-page scenery layers from the running game and draws their original tiles
with the current palette, color math and published objects. The old camera
bound still controls the guest. It no longer limits which authored scenery the
wider picture can show. The painter resolves wrapped scroll registers against
the camera coordinates and clips to the received map allocation.

Town, world travel and the fallback use the same 598×336 output at 1.5×.
Scenery uses one output sample per source pixel. Verified dim fade frames can
render through both the town and Mode 7 paths. Unsupported or incomplete frames
still use the centered guest picture at the same scale.
`IOG_RECEIVED_SOUTH_CAPE=0` forces that fallback in town. The previous preview
launcher is also retained.

Three actual 1920×1080 OpenGL captures were inspected at town arrival, during
the town exit fade and after return to the world map. The round trip uses a
retained world-map checkpoint and normal movement inputs. It includes 368
expanded town frames and matches all 75 sampled guest fields from the previous
preview. The test uses the launcher defaults, without an override to start the
observer. The explicit fallback passes the same comparison and still keeps the
598×336 output. The preview uses nearest filtering.

Seven Original South Cape comparison routes match the retained guest
snapshots and CPU traces. Controller navigation passed in both Original and
the GaiaLabs preview with an SDL virtual controller. The received
configuration and observer checks passed after rebuilding. The camera can
reframe to fit the authored town edge while pixel scale stays fixed. Other
unqualified received rooms may still show borders.

Private evidence is under `.local/batch-001/visual-fullgame-005`. The corrected
preview binary is `babel-mainv4.exe`, SHA-256
`84b03bc450608b533969c9a96c11a849d30178ac254a7e8cd7877bb6013b71de`.
