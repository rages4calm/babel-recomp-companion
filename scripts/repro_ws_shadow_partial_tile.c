/* ROM-free legacy WsShadow native-edge witness for upstream PR #218.
 * Compile with runner/src/snes/ws_shadow.c and runner/src on the include path.
 * Main 66eebe6 intentionally exits 1: fine-scroll phases 1..7 reproduce the
 * missing native-overlap ownership; phase 0 is a passing control. This checks
 * shared helpers, not the complete renderer or the pending PR implementation.
 */
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "snes/ppu.h"
#include "snes/ws_shadow.h"
int snes_frame_counter;
int main(void) {
    Ppu *ppu = calloc(1, sizeof(*ppu));
    if (!ppu) return 2;
    unsigned failures = 0;
    for (unsigned phase = 0; phase < 8; phase++) {
        memset(ppu, 0, sizeof(*ppu));
        ppu->bgmode = 1;
        ppu->bgXsc[0] = 0x11; /* 64x32 tilemap, word base $1000 */
        ppu->hScroll[0] = 120 + phase;
        ppu->vScroll[0] = 288;
        unsigned last = (120 + phase + 255) >> 3;
        unsigned word = 0x1000 + (63 & 31) * 32 + (last & 31) + ((last & 32) ? 0x400 : 0);
        ppu->vram[word] = 0x1111; /* synthetic current native VRAM entry */
        WsShadowReset();
        WsShadowSetWorld(0, 120 + phase, 288);
        WsShadowSetScroll(0, 120 + phase, 288);
        WsShadowFrame(ppu);
        uint16_t captured = 0;
        int found = WsShadowLookupWorldTile(0, last, 63, &captured);
        WsShadowPrefillTile(0, last, 63, 0x2222); /* different CPU-map source */
        int start_x = (int)(last * 8) - (int)(120 + phase);
        uint16_t tile = WsShadowTile(0, start_x, 511, 120 + phase, word, 0x1111);
        /* Whole-cell callers draw native pixels through 255 from this tile.
         * At phase1..7 the last cell is the uncaptured 33rd native cell. */
        unsigned native_pixels = 256u - (unsigned)start_x;
        if (tile != 0x1111) failures++;
        printf("fineX=%u cellStart=%d nativePixels=%u captured=%d result=%04X expectedNative=1111\n",
               phase, start_x, native_pixels, found, tile);
    }
    free(ppu);
    fprintf(stderr, "%u of 8 native-overlap checks failed\n", failures);
    return failures ? 1 : 0;
}
