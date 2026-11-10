/* Read-only stock-USA visual records. This is an independently written host
 * data decoder, not a simulation or translation of a guest sort routine.
 * Data layout/coordinates are checked against stock bytes and captures;
 * no game graphics or extracted tables are embedded here. */
#include "iog_visual_objects.h"
#include "snes/ppu.h"

#include <limits.h>
#include <string.h>

static uint16_t Word(const uint8_t *p, unsigned at)
{
    return (uint16_t)(p[at] | (unsigned)p[at + 1] << 8);
}

static bool Overlap(const void *a, size_t an, const void *b, size_t bn)
{
    uintptr_t x = (uintptr_t)a, y = (uintptr_t)b;
    return an && bn && (x <= y ? y - x < an : x - y < bn);
}

static bool Byte(const IogVisualSource *s, uint8_t bank, uint16_t at, uint8_t *v)
{
    if (bank == 0x7e || bank == 0x7f) {
        *v = s->ram[((unsigned)bank - 0x7e) * 0x10000u + at];
        return true;
    }
    if ((bank & 0x40) == 0 && at < 0x8000) return false;
    size_t off = ((size_t)(bank & 0x3f) << 16) | at;
    if (off >= s->rom_size) return false;
    *v = s->rom[off];
    return true;
}

static bool BusWord(const IogVisualSource *s, uint8_t bank, uint16_t at, uint16_t *v)
{
    uint8_t lo, hi;
    if (!Byte(s, bank, at, &lo) || !Byte(s, bank, (uint16_t)(at + 1), &hi)) return false;
    *v = (uint16_t)(lo | (unsigned)hi << 8);
    return true;
}

static bool ActorAddress(unsigned actor)
{
    return actor >= 0x1000 && actor < 0x1fc0 && (actor - 0x1000) % 0x30 == 0;
}

/* Lift the signed 16-bit displacement around the real camera before using
 * host coordinates. Never truncate a part to packed 9-bit OAM coordinates. */
static int32_t WorldPosition(uint16_t raw, uint16_t camera)
{
    unsigned d = (raw - (unsigned)camera) & 0xffff;
    return (int32_t)camera + (d < 0x8000 ? (int32_t)d : (int32_t)d - 0x10000);
}

typedef struct ActorOrder { uint16_t actor, key; } ActorOrder;

static IogVisualStatus Actors(const IogVisualSource *s, ActorOrder *list,
    IogVisualFrame *out)
{
    const uint8_t *ram = s->ram;
    unsigned actor = Word(ram, 0x56), prev = 0, count = 0, n = 0;
    uint8_t visited[kIogVisualMaxActors] = {0};
    while (actor) {
        if (!ActorAddress(actor) || count == kIogVisualMaxActors ||
            visited[(actor - 0x1000) / 0x30] || Word(ram, actor + 4) != prev)
            return kIogVisualMalformedSource;
        visited[(actor - 0x1000) / 0x30] = 1;
        count++;
        unsigned flags = Word(ram, actor + 0x10);
        if (flags & 0x2000) out->hidden_actors++;
        else {
            unsigned y = (Word(ram, actor + 0x16) - Word(ram, 0x68e)) & 0xffff;
            unsigned key = flags & 2 ? 0 : flags & 1 ? 510 : 2 * (255 - (y < 256 ? y : 255));
            /* Head-to-tail insertion keeps the equal-key order produced by
             * the stock reverse-chain bucket's front insertion. */
            unsigned pos = n;
            while (pos && list[pos - 1].key > key) {
                list[pos] = list[pos - 1];
                --pos;
            }
            list[pos].actor = (uint16_t)actor;
            list[pos].key = (uint16_t)key;
            n++;
        }
        prev = actor;
        actor = Word(ram, actor + 6);
    }
    if (Word(ram, 0x58) != prev) return kIogVisualMalformedSource;
    out->actor_count = (uint16_t)count;
    /* n may differ from actor_count because hidden actors have no picture. */
    if (n < kIogVisualMaxActors) list[n].actor = 0;
    return kIogVisualReady;
}

static bool PlayerGraphics(const IogVisualSource *s, unsigned actor,
    uint8_t *bank, uint16_t *base)
{
    unsigned offset;
    if (Word(s->ram, 0x9ae) & 0x8000) {
        offset = Word(s->ram, 0x10000 + actor + 0xe);
        /* The initial contract covers the three ordinary form entries only. */
        if (offset > 12 || offset % 6) return false;
    } else {
        unsigned form = Word(s->ram, 0xad4);
        if (form > 2) return false;
        offset = form * 6;
    }
    return BusWord(s, 0x81, (uint16_t)(0xd974 + offset), base) &&
        Byte(s, 0x81, (uint16_t)(0xd976 + offset), bank);
}

static bool Pixels(const IogVisualSource *s, IogVisualPart *part,
    bool player, uint8_t bank, uint16_t base)
{
    unsigned attr = part->tile_attributes;
    unsigned tile = attr & 0x1ff;
    for (unsigned y = 0; y < part->height; y++) {
        unsigned sy = part->vflip ? part->height - 1 - y : y;
        for (unsigned x = 0; x < part->width; x++) {
            unsigned sx = part->hflip ? part->width - 1 - x : x;
            unsigned row = sy & 7, bit = 7 - (sx & 7), planes[4];
            if (player) {
                /* Each player DMA part copies two adjacent characters in
                 * each of two rows, 16 characters apart in the source sheet. */
                unsigned chr = tile + (sy >> 3) * 16 + (sx >> 3);
                uint16_t addr = (uint16_t)(base + chr * 32 + row * 2);
                uint8_t p[4];
                if (!Byte(s, bank, addr, &p[0]) || !Byte(s, bank, (uint16_t)(addr + 1), &p[1]) ||
                    !Byte(s, bank, (uint16_t)(addr + 16), &p[2]) || !Byte(s, bank, (uint16_t)(addr + 17), &p[3]))
                    return false;
                for (unsigned b = 0; b < 4; b++) planes[b] = p[b];
            } else {
                unsigned chr = (((tile & 255) >> 4) + (sy >> 3)) * 16 +
                    (((tile & 15) + (sx >> 3)) & 15);
                unsigned adr = (tile & 256) ? PPU_objTileAdr2(s->ppu) : PPU_objTileAdr1(s->ppu);
                unsigned at = (adr + chr * 16 + row) & 0x7fff;
                unsigned lo = s->ppu->vram[at], hi = s->ppu->vram[(at + 8) & 0x7fff];
                planes[0] = lo & 255; planes[1] = lo >> 8;
                planes[2] = hi & 255; planes[3] = hi >> 8;
            }
            unsigned color = 0;
            for (unsigned b = 0; b < 4; b++) color |= ((planes[b] >> bit) & 1) << b;
            part->indices[y * part->width + x] = color ? (uint8_t)(128 + part->palette * 16 + color) : 0;
            part->pixels[y * part->width + x] = color ?
                (uint16_t)(0x8000 | (s->ppu->cgram[128 + part->palette * 16 + color] & 0x7fff)) : 0;
        }
    }
    return true;
}

static IogVisualStatus Add(const IogVisualSource *s, IogVisualFrame *out,
    unsigned actor, unsigned frame, unsigned index, uint16_t attr,
    int32_t wx, int32_t wy, unsigned size, bool manual, bool player,
    uint8_t bank, uint16_t base, uint32_t *order)
{
    uint32_t rank = ++*order;
    int64_t x = (int64_t)wx - out->viewport.world_x;
    int64_t y = (int64_t)wy - out->viewport.world_y;
    if (x + size <= 0 || y + size <= 0 || x >= out->viewport.width || y >= out->viewport.height) {
        out->outside_parts++;
        return kIogVisualReady;
    }
    if (out->part_count == kIogVisualMaxParts) return kIogVisualCapacity;
    IogVisualPart *p = &out->parts[out->part_count];
    memset(p, 0, sizeof(*p));
    p->world_x = wx; p->world_y = wy; p->x = (int32_t)x; p->y = (int32_t)y;
    p->actor = (uint16_t)actor; p->animation = (uint16_t)frame; p->source_index = (uint16_t)index;
    p->order = rank; p->tile_attributes = attr; p->width = p->height = (uint8_t)size;
    p->palette = (uint8_t)((attr >> 9) & 7); p->priority = (uint8_t)((attr >> 12) & 3);
    p->math = p->palette >= 4; p->hflip = !!(attr & 0x4000); p->vflip = !!(attr & 0x8000);
    p->manual = manual; p->player = player;
    if (!Pixels(s, p, player, bank, base)) return kIogVisualMalformedSource;
    out->part_count++;
    return kIogVisualReady;
}

IogVisualStatus IogVisualObjectsBuild(const IogVisualSource *s,
    const IogVisualViewport *view, IogVisualFrame *out)
{
    if (!s || !view || !out) return kIogVisualInvalidInput;
    if (Overlap(out, sizeof(*out), s, sizeof(*s)) || Overlap(out, sizeof(*out), view, sizeof(*view)) ||
        Overlap(out, sizeof(*out), s->ram, s->ram_size) || Overlap(out, sizeof(*out), s->rom, s->rom_size) ||
        (s->ppu && Overlap(out, sizeof(*out), s->ppu, sizeof(*s->ppu)))) return kIogVisualInvalidInput;
    out->part_count = out->actor_count = out->hidden_actors = out->outside_parts = 0;
    out->status = kIogVisualInvalidInput; out->scene = 0; out->viewport = *view;
    if (!s->ram || s->ram_size != 0x20000 || !s->rom || s->rom_size != 0x200000 || !s->ppu ||
        !view->width || view->width > 4096 || !view->height || view->height > 512 ||
        view->world_x > INT32_MAX - 4096 || view->world_y > INT32_MAX - 512)
        return out->status;
    if (!s->stock_identity_verified) { out->status = kIogVisualUnsupportedFormat; return out->status; }
    out->scene = Word(s->ram, 0x644);
    if (out->scene != 1 && out->scene != 12) { out->status = kIogVisualUnsupportedScene; return out->status; }
    if ((s->ppu->bgmode & 7) != 1 || PPU_objSize(s->ppu) || PPU_objInterlace(s->ppu) ||
        (Word(s->ram, 0x6ee) & 0x1000)) { out->status = kIogVisualUnsupportedFormat; return out->status; }
    ActorOrder actors[kIogVisualMaxActors] = {{0,0}};
    IogVisualStatus status = Actors(s, actors, out);
    uint32_t order = 0;
    if (status != kIogVisualReady) goto done;
    /* The reader uses a negative-X terminator, not the producer's D8 cursor
     * (which is reset during composition and can be zero on render-only
     * paths). Bound the scan explicitly; an absent sentinel refuses rather
     * than silently truncating clipped source records. */
    bool manual_end = false;
    for (unsigned n = 0; n < 128; n++) {
        unsigned at = 0x13100 + n * 6;
        unsigned x = Word(s->ram, at);
        if (x & 0x8000) { manual_end = true; break; }
        status = Add(s, out, 0, 0, n, Word(s->ram, at + 4), x,
            Word(s->ram, at + 2), 8, true, false, 0, 0, &order);
        if (status != kIogVisualReady) goto done;
    }
    if (!manual_end) { status = kIogVisualCapacity; goto done; }
    for (unsigned n = 0; n < kIogVisualMaxActors && actors[n].actor; n++) {
        unsigned actor = actors[n].actor, ext = 0x10000 + actor;
        uint8_t bank = s->ram[ext + 8], count;
        uint16_t ptr = Word(s->ram, ext + 0xc);
        if (!Byte(s, bank, (uint16_t)(ptr + 8), &count) || !count) { status = kIogVisualMalformedSource; goto done; }
        uint16_t mask = Word(s->ram, actor + 0xe), flags = Word(s->ram, actor + 0x10);
        unsigned blink = (flags & 0x80) && !(flags & 0x10) && (Word(s->ram, ext + 0x28) & 1) ? 0xe00 : 0;
        int32_t ax = WorldPosition(Word(s->ram, actor + 0x14), Word(s->ram, 0x68a));
        int32_t ay = WorldPosition(Word(s->ram, actor + 0x16), Word(s->ram, 0x68e));
        int32_t x0 = ax - (int16_t)Word(s->ram, actor + 0x18);
        int32_t y0 = ay - (int16_t)Word(s->ram, actor + 0x1a) - 1;
        bool player = (flags & 0x8000) != 0;
        uint8_t graphics_bank = 0; uint16_t graphics_base = 0;
        if (player && !PlayerGraphics(s, actor, &graphics_bank, &graphics_base)) { status = kIogVisualUnsupportedFormat; goto done; }
        for (unsigned i = 0; i < count; i++) {
            uint16_t record = (uint16_t)(ptr + 9 + i * 7), attr;
            uint8_t size, xoff, yoff;
            if (!Byte(s, bank, record, &size) ||
                !Byte(s, bank, (uint16_t)(record + 1 + !!(mask & 0x4000)), &xoff) ||
                !Byte(s, bank, (uint16_t)(record + 3 + !!(mask & 0x8000)), &yoff) ||
                !BusWord(s, bank, (uint16_t)(record + 5), &attr)) { status = kIogVisualMalformedSource; goto done; }
            status = Add(s, out, actor, Word(s->ram, actor + 0x28), i,
                (uint16_t)((attr ^ mask) | blink), x0 + xoff, y0 + yoff,
                size & 1 ? 16 : 8, false, player, graphics_bank, graphics_base, &order);
            if (status != kIogVisualReady) goto done;
        }
    }
done:
    out->status = status;
    if (status != kIogVisualReady) out->part_count = 0;
    return status;
}
