#ifndef IOG_MAP_RUNTIME_H
#define IOG_MAP_RUNTIME_H
#include "iog_map_view.h"
#include "snes/ppu.h"

typedef struct IogMapRuntime IogMapRuntime;
typedef struct IogMapRuntimeRect {unsigned x,y,width,height;} IogMapRuntimeRect;
typedef struct IogMapRuntimeFrame {
    const uint8_t *ram;
    size_t ram_bytes; /* complete131072-byte snapshot, including static flags */
    const Ppu *ppu;
    uint8_t content_sha256[32];
    uint16_t scene;
    IogMapRuntimeRect authored;
    int camera_x,camera_y,player_x,player_y; /* world pixels, not packed OAM */
    /* Caller verifies content/profile and authored layout. Zero flags address
     * selects bank7F's page from $06AA (normally $0000). Dual-layer geometry
     * also validates/uses the page at $06AC and linear layer1 map overlay.
     * Any different profile must validate these Original-format tables. */
    bool profile_verified;
    /* Opt in only after verifying the Original-format cached ROM asset pointers
     * at $0678/$067B/$067E/$0681 against this content ROM. This preserves the
     * authored coordinate-space journal across scripted door/tile edits.
     * False retains strict snapshot-content identity for unqualified profiles. */
    bool stable_source_identity;
    /* Caller proves both scenery planes share world coordinates. Never enable
     * for independently scrolling skies/parallax. Uses real Mode1 BG priority. */
    bool aligned_secondary_source;
    uint32_t static_flags_address;
} IogMapRuntimeFrame;
typedef struct IogMapRuntimeStatus {
    bool frame_valid,storage_available;
    uint16_t scene;
    IogMapRuntimeRect authored;
    int player_cell_x,player_cell_y;
    unsigned grid_width,grid_height,cell_world_pixels,atlas_cell_pixels;
    size_t explored_cells;
    uint8_t layout_sha256[32];
    uint32_t floor_id;
    uint64_t accepted_frames,persistent_writes,persistent_loads;
    const char *reason;
} IogMapRuntimeStatus;

/* Existing UTF-8 saves directory required; only its own nonlinked child
 * "maps" is created. At most8 fog states and one16MiB atlas are retained.
 * Call from one host thread; no guest RAM/PPU writes or state-load rollback.
 */
IogMapRuntime *IogMapRuntimeCreate(const char *existing_saves_directory);
void IogMapRuntimeDestroy(IogMapRuntime *runtime);
bool IogMapRuntimeFlush(IogMapRuntime *runtime);
/* NULL/unsupported input hides the current view immediately. Exploration uses
 * camera-limited radius8 reachability through ZERO static-collision cells;
 * adjacent blocking cells are revealed but never traversed. Special/sloped
 * classes remain conservatively blocked. Unexplained static/live-grid mismatch
 * refuses the frame (proven F0 actor occupancy, including an unchanged static
 * low nibble, is exempt; the underlying static barrier still governs reveal).
 * This is not optical line of sight. */
bool IogMapRuntimeUpdate(IogMapRuntime *runtime,const IogMapRuntimeFrame *frame);
void IogMapRuntimeGetStatus(const IogMapRuntime *runtime,IogMapRuntimeStatus *status);
/* Borrowed pointers remain valid until Update/Destroy. Artwork is lazily built
 * at step2 (8 atlas pixels/16-world-pixel cell), refreshed at most every30
 * accepted frames; room/layout/character-bank/map/definition changes force a
 * fresh atlas immediately. */
bool IogMapRuntimeGetViewSource(IogMapRuntime *runtime,IogMapViewSource *source);
bool IogMapRuntimeDraw(IogMapRuntime *runtime,uint8_t *destination,size_t bytes,
    size_t stride,unsigned width,unsigned height,const IogMapViewSettings *settings);
#endif
