/* Read-only stock-USA visual records. This is an independently written host
 * data decoder, not a simulation or translation of a guest sort routine.
 * Data layout/coordinates are checked against stock bytes and captures;
 * no game graphics or extracted tables are embedded here. */
#include "iog_visual_objects.h"
#include "snes/ppu.h"
#include "sha256.h"

#include <limits.h>
#include <stdlib.h>
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

bool IogVisualObjectsSupportsScene(uint16_t scene)
{
    switch (scene) {
    case 0x01: case 0x02: case 0x03: case 0x04: case 0x05:
    case 0x06: case 0x08: case 0x0c: case 0x0d: case 0x0e: case 0x0f: case 0x12:
    case 0x15: case 0x1a: case 0x1c: case 0x1e: case 0x23: case 0x25: case 0x26:
    case 0x27: case 0x28: case 0x29: case 0x2d: case 0x31: case 0x3d:
    case 0x3e: case 0x3f: case 0x40: case 0x41: case 0x42:
    case 0x45: case 0x46: case 0x4c: case 0x4f: case 0x51: case 0x53:
    case 0x55: case 0x61: case 0x62: case 0x64: case 0x67:
    case 0x6d: case 0x6f: case 0x83: case 0x85: case 0x86: case 0x8a:
    case 0x8b: case 0xa7: case 0xb6: case 0xb8: case 0xcc:
    case 0xcd: case 0xce: case 0xdd: case 0xde: case 0xdf:
    case 0xe0: case 0xe1: case 0xe2: case 0xe3: case 0xe5:
    case 0xe6: case 0xe7: case 0xe8: case 0xea:
        return true;
    default:
        /* One explicit developer-survey scene at a time. This does not
         * promote an unknown room into the shipping admission list; all
         * layout, object, ROM and publication guards still apply below. */
        {
            const char *token=getenv("IOG_WORLD_SURVEY_SCENE");
            if(!token || strlen(token)!=2)return false;
            unsigned value=0;
            for(unsigned n=0;n<2;n++) {
                char c=token[n];unsigned digit;
                if(c>='0'&&c<='9')digit=(unsigned)(c-'0');
                else if(c>='a'&&c<='f')digit=(unsigned)(c-'a'+10);
                else if(c>='A'&&c<='F')digit=(unsigned)(c-'A'+10);
                else return false;
                value=value*16+digit;
            }
            return scene<0xF0 && scene==value;
        }
    }
}

/* Lift the signed 16-bit displacement around the real camera before using
 * host coordinates. Never truncate a part to packed 9-bit OAM coordinates. */
static int32_t WorldPosition(uint16_t raw, uint16_t camera)
{
    unsigned d = (raw - (unsigned)camera) & 0xffff;
    /* Supported map cameras fit below 32768. FFFF during a boundary shake
     * denotes -1, not a world sixty-five thousand pixels away. */
    return (int32_t)(int16_t)camera +
        (d < 0x8000 ? (int32_t)d : (int32_t)d - 0x10000);
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
    uint8_t *bank, uint16_t *base, uint16_t lookup)
{
    unsigned offset;
    if (Word(s->ram, 0x9ae) & 0x8000) {
        offset = Word(s->ram, 0x10000 + actor + 0xe);
        /* Stock has nine six-byte body records. Actual retained ability/
         * transformation captures also use rows4,5,6; rows7/8 are currently
         * source-format coverage, not observed execution qualification. */
        if (offset > 48 || offset % 6) return false;
    } else {
        unsigned form = Word(s->ram, 0xad4);
        if (form > 2) return false;
        offset = form * 6;
    }
    return BusWord(s, 0x81, (uint16_t)(lookup + offset), base) &&
        Byte(s, 0x81, (uint16_t)(lookup + 2 + offset), bank);
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

static IogVisualStatus BuildLayout(const IogVisualSource *s,
    const IogVisualViewport *view, IogVisualFrame *out, bool received, uint32_t prefix)
{
    if (!s || !view || !out) return kIogVisualInvalidInput;
    if (Overlap(out, sizeof(*out), s, sizeof(*s)) || Overlap(out, sizeof(*out), view, sizeof(*view)) ||
        Overlap(out, sizeof(*out), s->ram, s->ram_size) || Overlap(out, sizeof(*out), s->rom, s->rom_size) ||
        (s->ppu && Overlap(out, sizeof(*out), s->ppu, sizeof(*s->ppu)))) return kIogVisualInvalidInput;
    out->part_count = out->actor_count = out->hidden_actors = out->outside_parts = 0;
    out->status = kIogVisualInvalidInput; out->scene = 0; out->viewport = *view;
    if (!s->ram || s->ram_size != 0x20000 || !s->rom || s->rom_size != (received ? 0x320000u : 0x200000u) || !s->ppu ||
        !view->width || view->width > 4096 || !view->height || view->height > 512 ||
        view->world_x > INT32_MAX - 4096 || view->world_y > INT32_MAX - 512)
        return out->status;
    if (!received && !s->stock_identity_verified) { out->status = kIogVisualUnsupportedFormat; return out->status; }
    out->scene = Word(s->ram, 0x644);
    if (received ? out->scene != 8 : !IogVisualObjectsSupportsScene(out->scene)) { out->status = kIogVisualUnsupportedScene; return out->status; }
    if ((s->ppu->bgmode & 7) != 1 || PPU_objSize(s->ppu) || PPU_objInterlace(s->ppu) ||
        (!received && (Word(s->ram, 0x6ee) & 0x1000))) { out->status = kIogVisualUnsupportedFormat; return out->status; }
    ActorOrder actors[kIogVisualMaxActors] = {{0,0}};
    IogVisualStatus status = Actors(s, actors, out);
    uint32_t order = prefix;
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
            WorldPosition(Word(s->ram, at + 2), Word(s->ram, 0x68e)),
            8, true, false, 0, 0, &order);
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
        if (player && !PlayerGraphics(s, actor, &graphics_bank, &graphics_base, received ? 0xf179 : 0xd974)) { status = kIogVisualUnsupportedFormat; goto done; }
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


IogVisualStatus IogVisualObjectsBuild(const IogVisualSource *s,
    const IogVisualViewport *view, IogVisualFrame *out)
{
    return BuildLayout(s, view, out, false, 0);
}

/* Identity metadata only. No received code, tables or game assets are embedded.
 * Verify once after loading, then keep the ROM allocation immutable/alive for
 * the lifetime of the returned identity. Never reuse it across ROM reloads. */
static const char *const ReceivedPins[3] = {
    "dded02334752a7122d4db8da4df4aa56d6997c078065e69183865dc23202973f",
    "70485bc087dd11937ebd8794a39b3c76638f135ea873b63bfda0639a943697ad",
    "dec96c815acd857455134a3ce2210678cc98285a62b196d912ae7c352756faa6"
};
static bool DigestMatches(const uint8_t digest[32], const char *pin)
{
    static const char hex[] = "0123456789abcdef";
    for (unsigned i=0;i<32;i++)
        if (hex[digest[i]>>4]!=pin[2*i] || hex[digest[i]&15]!=pin[2*i+1]) return false;
    return true;
}
IogVisualStatus IogVisualReceivedVerify(const uint8_t *rom, size_t size,
    IogVisualReceivedIdentity *identity)
{
    if (!identity || !rom || Overlap(identity,sizeof(*identity),rom,size))
        return kIogVisualInvalidInput;
    memset(identity,0,sizeof(*identity));
    if (size!=0x320000) return kIogVisualIdentityMismatch;
    sha256_compute(rom,size,identity->digests[0]);
    sha256_compute(rom+0x3dafe,118,identity->digests[1]);
    sha256_compute(rom+0x1f179,54,identity->digests[2]);
    for(unsigned i=0;i<3;i++) if(!DigestMatches(identity->digests[i],ReceivedPins[i])) {
        memset(identity,0,sizeof(*identity));return kIogVisualIdentityMismatch;
    }
    identity->rom=rom;identity->rom_size=size;
    return kIogVisualReady;
}

IogVisualStatus IogVisualReceivedBuild(const IogVisualReceivedSource *s,
    const IogVisualViewport *view, IogVisualReceivedFrame *out)
{
    if(!s || !view || !out) return kIogVisualInvalidInput;
    if(Overlap(out,sizeof(*out),s,sizeof(*s)) || Overlap(out,sizeof(*out),view,sizeof(*view)) ||
       Overlap(out,sizeof(*out),s->ram,s->ram_size) ||
       (s->identity && (Overlap(out,sizeof(*out),s->identity,sizeof(*s->identity)) ||
        Overlap(out,sizeof(*out),s->identity->rom,s->identity->rom_size))) ||
       (s->ppu && Overlap(out,sizeof(*out),s->ppu,sizeof(*s->ppu))) ||
       Overlap(out,sizeof(*out),s->staging,s->staging_size) ||
       Overlap(out,sizeof(*out),s->published,s->published_size)) return kIogVisualInvalidInput;
    out->screen_count=0;out->world.part_count=0;out->status=kIogVisualInvalidInput;
    if(!s->ram || s->ram_size!=0x20000 || !s->ppu || !s->identity) return out->status;
    const IogVisualReceivedIdentity *id=s->identity;
    if(!id->rom || id->rom_size!=0x320000) return out->status=kIogVisualIdentityMismatch;
    for(unsigned i=0;i<3;i++) if(!DigestMatches(id->digests[i],ReceivedPins[i]))
        return out->status=kIogVisualIdentityMismatch;
    /* This binding is qualified only for the observed Will classroom. In
     * particular the received0600 direct path and other body records refuse. */
    if(Word(s->ram,0x644)!=8 || Word(s->ram,0xad4)!=0 || (Word(s->ram,0x9ae)&0x8000))
        return out->status=kIogVisualSourceUnqualified;
    if(!s->staging || !s->published || s->staging_size!=544 || s->published_size!=544 ||
       !s->compose_epoch || s->compose_epoch!=s->publication_epoch ||
       memcmp(s->staging,s->published,544)) return out->status=kIogVisualPublicationMismatch;
    unsigned bytes=(Word(s->ram,0x6ee)&0x1000)?Word(s->ram,0xda):0;
    if(bytes>512 || bytes%4 || bytes!=s->observed_direct_bytes)
        return out->status=kIogVisualMalformedSource;
    if(memcmp(s->ram+0x11fc0,s->staging,bytes)) return out->status=kIogVisualPublicationMismatch;
    for(unsigned n=0;n<bytes/4;n++)
        if(((s->staging[512+n/4]>>((n%4)*2))&3)!=2)
            return out->status=kIogVisualMalformedSource;
    IogVisualSource world={s->ram,s->ram_size,id->rom,id->rom_size,s->ppu,false};
    IogVisualStatus status=BuildLayout(&world,view,&out->world,true,bytes/4);
    if(status!=kIogVisualReady) return out->status=status;
    for(unsigned n=0;n<bytes/4;n++) {
        const uint8_t *p=s->ram+0x11fc0+n*4;
        IogVisualPart picture;memset(&picture,0,sizeof(picture));
        picture.tile_attributes=Word(p,2);picture.width=picture.height=16;
        picture.palette=(picture.tile_attributes>>9)&7;picture.priority=(picture.tile_attributes>>12)&3;
        picture.hflip=!!(picture.tile_attributes&0x4000);picture.vflip=!!(picture.tile_attributes&0x8000);
        if(!Pixels(&world,&picture,false,0,0)) {
            out->world.part_count=0;return out->status=kIogVisualMalformedSource;
        }
        IogVisualScreenPart *part=&out->screen[n];
        memset(part,0,sizeof(*part));part->x=p[0];part->y=p[1];part->order=n+1;
        part->tile_attributes=picture.tile_attributes;part->width=part->height=16;
        part->palette=picture.palette;part->priority=picture.priority;
        part->hflip=picture.hflip;part->vflip=picture.vflip;
        memcpy(part->pixels,picture.pixels,sizeof(part->pixels));
        memcpy(part->indices,picture.indices,sizeof(part->indices));
    }
    out->screen_count=(uint16_t)(bytes/4);
    return out->status=kIogVisualReady;
}
