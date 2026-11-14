#ifndef IOG_MAP_DISCOVERY_H
#define IOG_MAP_DISCOVERY_H
#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>

enum { kIogMapDiscoveryMaxSide=256, kIogMapDiscoveryBytes=8192 };
typedef struct IogMapDiscoveryIdentity {
    uint8_t content_sha256[32],layout_sha256[32];
    uint32_t floor_id;
} IogMapDiscoveryIdentity;
typedef struct IogMapDiscovery {
    IogMapDiscoveryIdentity identity;
    uint16_t width,height;
    uint8_t explored[kIogMapDiscoveryBytes];
} IogMapDiscovery;

/* Pure host state. The caller defines world-cell resolution and identities;
 * neither ROM layout, line of sight nor guest RAM is inferred here. */
bool IogMapDiscoveryInit(IogMapDiscovery *map,unsigned width,unsigned height,
    const IogMapDiscoveryIdentity *identity);
bool IogMapDiscoveryIsRevealed(const IogMapDiscovery *map,int x,int y);
/* Visibility is REQUIRED, one nonzero byte per permitted cell. Circle is only
 * a range limit, not a substitute for caller-provided occlusion/LOS. The center
 * is not automatically revealed when visibility marks it hidden. */
bool IogMapDiscoveryReveal(IogMapDiscovery *map,int center_x,int center_y,
    unsigned radius,const uint8_t *visibility,size_t visibility_bytes,
    size_t visibility_stride,size_t *new_cells);
size_t IogMapDiscoveryEncodedSize(const IogMapDiscovery *map);
/* Portable LE v1, strict dimensions/content/layout/floor binding, CRC32 damage
 * detection (not authentication). Decode failure leaves destination unchanged.
 * Serialize buffers must not overlap the input object. */
bool IogMapDiscoverySerialize(const IogMapDiscovery *map,uint8_t *output,
    size_t capacity,size_t *written);
bool IogMapDiscoveryDeserialize(IogMapDiscovery *destination,const uint8_t *input,
    size_t bytes,const IogMapDiscoveryIdentity *expected_identity,
    unsigned expected_width,unsigned expected_height);
#endif
