/* Experimental received-content classroom picture. Original Babel credits and
 * GaiaLabs contributor/license notices remain with the project. No game data is
 * embedded; this host decoder never changes guest CPU, RAM, ROM or hardware
 * registers. Overlay capture bindings are host presentation state only. */
#include "iog_received_world.h"
#include "common_cpu_infra.h"
#include "iog_received_observer.h"
#include "iog_visual_objects.h"
#include "iog_world_pixels.h"
#include "iog_world_view.h"
#include "sha256.h"
#include "snes/cart.h"
#include "snes/ppu.h"
#include "snes/snes.h"
#include <math.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
extern Snes *g_snes;
extern Ppu *g_ppu;
enum { Width = 598, Height = 336, Chunk = 224 };
static struct {
  bool initialized, enabled, valid, complete;
  int width, height, frame;
  const char *reason;
  FILE *audit;
  uint8_t ram[131072], registers[225][PPU_SAVESTATE_REGS_SIZE];
  uint16_t palettes[225][256];
  uint32_t vram_writes, oam_writes;
  Ppu base, picture;
  IogVisualReceivedSource source;
  IogVisualReceivedFrame visual;
  IogWorldView view;
  PpuExtraObject objects[512];
  uint16_t object_rows[512][16];
  uint32_t output[Width * Height], row[256], ui[384 * 224];
  int left, right, top, bottom;
  uint8_t exterior[48 * 16];
} s;
static unsigned Word(const uint8_t *r, unsigned a) {
  return r[a] | (unsigned)r[a + 1] << 8;
}
static int Clamp(int v, int lo, int hi) {
  return v < lo ? lo : v > hi ? hi : v;
}
bool IogReceivedWorldEnabled(void) {
  if (!s.initialized) {
    s.initialized = true;
    const char *t = getenv("IOG_RECEIVED_WORLD_RENDERER");
    s.enabled = t && !strcmp(t, "1");
    const char *a = getenv("IOG_RECEIVED_WORLD_AUDIT");
    if (s.enabled && a && *a)
      s.audit = fopen(a, "wb");
  }
  return s.enabled;
}
void IogReceivedWorldGeometry(int dw, int dh, int *w, int *h) {
  (void)dw;
  (void)dh;
  if (!IogReceivedWorldEnabled())
    return;
  const char *t = getenv("IOG_RECEIVED_WORLD_EXTENT");
  bool one = t && !strcmp(t, "1");
  *w = one ? 384 : Width;
  *h = one ? 224 : Height;
  s.width = *w;
  s.height = *h;
}
static void Detach(Ppu *p) {
  p->renderBuffer = (uint8_t *)s.row;
  p->renderPitch = 256 * 4;
  p->renderVram = NULL;
  p->hdLookup = NULL;
  p->hdCtx = NULL;
  p->hdFrame = NULL;
  p->hdCapture = NULL;
  p->hiresBuffer = NULL;
  p->hdEmissive = NULL;
  p->widescreenLineEnhancer = NULL;
  p->widescreenLineEnhancerContext = NULL;
  p->extraObjects = NULL;
  p->extraObjectCount = 0;
  p->renderFlags = 0;
  PpuClearOverlayBindings(p);
  PpuClearOverlayCaptures(p);
  PpuSetExtraSpace(p, 0);
  PpuSetWidescreenHudSplit(p, 0, 0, 0);
  for (unsigned i = 0; i < 256; i += 2)
    p->oam[i] = 0xF000;
  memset(p->highOam, 0, 32);
  p->wsOamFullXOn = 0;
  p->wsOamMotionGraceOn = 0;
}
/* The matching public widescreen map's boundary filler is metatile110:
 * all370 instances connect to the map boundary and carry solid collisionF.
 * This is source-cell topology, not a rendered-color key or image crop.
 * Exact map-payload identity refuses future changed layouts until reviewed. */
static bool Exterior(void) {
  static const uint8_t pin[32] = {
      0x48, 0x2b, 0x8c, 0x27, 0xf0, 0x5a, 0xd6, 0xa5, 0x57, 0x62, 0x6d,
      0x7f, 0x8a, 0xa1, 0x18, 0x42, 0xc5, 0xc9, 0x9d, 0xee, 0x6c, 0x6e,
      0xf1, 0x48, 0x49, 0x5d, 0xa5, 0xce, 0x15, 0x8b, 0xb3, 0xbe};
  uint8_t digest[32];
  sha256_compute(s.ram + 0xa000, 768, digest);
  if (memcmp(pin, digest, 32))
    return false;
  unsigned queue[768], head = 0, tail = 0;
  memset(s.exterior, 0, sizeof(s.exterior));
  for (unsigned y = 0; y < 16; y++)
    for (unsigned x = 0; x < 48; x++) {
      unsigned idx = y * 48 + x, source = (x / 16) * 256 + y * 16 + x % 16;
      if ((!x || x == 47 || !y || y == 15) && s.ram[0xa000 + source] == 110) {
        s.exterior[idx] = 1;
        queue[tail++] = idx;
      }
    }
  while (head < tail) {
    unsigned idx = queue[head++], x = idx % 48, y = idx / 48;
    int neighbors[4] = {(int)idx - 1, (int)idx + 1, (int)idx - 48,
                        (int)idx + 48};
    for (unsigned n = 0; n < 4; n++) {
      int z = neighbors[n];
      if ((n == 0 && !x) || (n == 1 && x == 47) || (n == 2 && !y) ||
          (n == 3 && y == 15))
        continue;
      unsigned nx = (unsigned)z % 48, ny = (unsigned)z / 48,
               source = nx / 16 * 256 + ny * 16 + nx % 16;
      if (!s.exterior[z] && s.ram[0xa000 + source] == 110) {
        s.exterior[z] = 1;
        queue[tail++] = (unsigned)z;
      }
    }
  }
  if (tail != 370)
    return false;
  for (unsigned n = 0; n < tail; n++) {
    unsigned x = queue[n] % 48, y = queue[n] / 48,
             source = x / 16 * 256 + y * 16 + x % 16;
    if ((s.ram[0x1c000 + source] & 15) != 15)
      return false;
  }
  return true;
}
void IogReceivedWorldBeginRaster(void) {
  if (!IogReceivedWorldEnabled())
    return;
  s.frame++;
  s.valid = s.complete = false;
  s.reason = "unpaired_or_unqualified";
  memset(s.ui, 0, sizeof(s.ui));
  if (!IogReceivedObserverPicture(&s.source))
    return;
  if (memcmp(g_ppu->oam, s.source.published, 512) ||
      memcmp(g_ppu->highOam, s.source.published + 512, 32)) {
    s.reason = "current_publication_mismatch";
    return;
  }
  if (PPU_forcedBlank(g_ppu) || PPU_brightness(g_ppu) != 15 ||
      Word(s.source.ram, 0x644) != 8 || (g_ppu->bgmode & 7) != 1 ||
      PPU_objInterlace(g_ppu) || g_ppu->frameInterlace || (g_ppu->mosaic >> 4))
    return;
  memcpy(s.ram, g_snes->ram, sizeof(s.ram));
  s.base = *g_ppu;
  s.vram_writes = g_ppu->vramWriteCount;
  s.oam_writes = g_ppu->oamWriteCount;
  /* These are authored bounds, not the entire map allocation. Native384
   * reveals64 each side of the legacy256 camera window; clip that envelope
   * to the actual768x256 map. Spare storage beyond it stays black. */
  if (Word(s.ram, 0x692) != 768 || Word(s.ram, 0x696) != 256 ||
      Word(s.ram, 0x694) != 768 || Word(s.ram, 0x698) != 512 ||
      Word(s.ram, 0x69e) != 0xa000 || Word(s.ram, 0x6a0) != 0xc000 ||
      Word(s.ram, 0x6ae) != 0x2000 || Word(s.ram, 0x6b0) != 0x2800) {
    s.reason = "map_layout";
    return;
  }
  if (!Exterior()) {
    s.reason = "exterior_map_identity";
    return;
  }
  int camera = (int16_t)Word(s.source.ram, 0x68a),
      cy = (int16_t)Word(s.source.ram, 0x68e),
      physical = (s.ram[0x6ee] >> 7) & 1;
  if ((g_ppu->hScroll[physical] & 1023) != (camera & 1023) ||
      (g_ppu->vScroll[physical] & 1023) != (cy & 1023)) {
    s.reason = "camera_publication";
    return;
  }
  int l = Word(s.ram, 0x6d6), r = Word(s.ram, 0x6da), t = Word(s.ram, 0x6d8),
      b = Word(s.ram, 0x6de);
  if (l != 0 || r != 512 || t != 0 || b != 256) {
    s.reason = "authored_window";
    return;
  }
  s.left = Clamp(l - 64, 0, 768);
  s.right = Clamp(r + 64, 0, 768);
  s.top = t;
  s.bottom = b;
  if (!IogWorldViewCompute(camera, cy, s.right, s.bottom, (uint16_t)s.width,
                           (uint16_t)s.height, &s.view)) {
    s.reason = "world_view";
    return;
  }
  IogVisualViewport view = {s.view.world_x, s.view.world_y, (uint16_t)s.width,
                            (uint16_t)s.height};
  if (IogVisualReceivedBuild(&s.source, &view, &s.visual) != kIogVisualReady) {
    s.reason = "visual_records";
    return;
  }
  if (!PpuBindOverlaySurface(g_ppu, kPpuOverlaySource_Bg3, (uint8_t *)s.ui,
                             384 * 4) ||
      !PpuSetOverlayCapture(g_ppu, kPpuOverlaySource_Bg3, -64, 0, 384, 224,
                            0)) {
    s.reason = "bg3_capture";
    return;
  }
  s.valid = true;
  s.reason = "awaiting_raster";
}
void IogReceivedWorldCaptureLine(int line) {
  if (!s.enabled || !s.valid || line < 0 || line > 224)
    return;
  if ((g_ppu->bgmode & 7) != 1 || g_ppu->vramWriteCount != s.vram_writes ||
      g_ppu->oamWriteCount != s.oam_writes || g_ppu->frameInterlace ||
      (g_ppu->mosaic >> 4) ||
      memcmp(s.ram + 0x644, g_snes->ram + 0x644, 0xbe) ||
      memcmp(s.ram + 0x2000, g_snes->ram + 0x2000, 0x1000) ||
      memcmp(s.ram + 0xa000, g_snes->ram + 0xa000, 0x6000)) {
    s.valid = false;
    s.reason = "raster_layout_change";
    return;
  }
  memcpy(s.registers[line], g_ppu, PPU_SAVESTATE_REGS_SIZE);
  memcpy(s.palettes[line], g_ppu->cgram, 512);
}
static unsigned MapTile(unsigned logical, int x, int y) {
  unsigned off = logical * 2, w = Word(s.ram, 0x692 + off),
           h = Word(s.ram, 0x696 + off);
  if (x < 0 || y < 0 || x >= (int)w || y >= (int)h)
    return ~0u;
  unsigned map = Word(s.ram, 0x69e + off), defs = Word(s.ram, 0x6ae + off);
  unsigned a = map + (((y >> 8) * (w >> 8) + (x >> 8)) << 8) +
               (((y >> 4) & 15) << 4) + ((x >> 4) & 15);
  if (a >= 65536 || defs + s.ram[a] * 8 + 7 >= 65536)
    return ~0u;
  return Word(s.ram,
              defs + s.ram[a] * 8 + ((y >> 3) & 1) * 4 + ((x >> 3) & 1) * 2);
}
static bool Render(void) {
  Ppu *p = &s.picture;
  *p = s.base;
  Detach(p);
  int blank[2] = {-1, -1};
  for (unsigned logical = 0; logical < 2; logical++) {
    unsigned physical = logical ^ ((s.ram[0x6ee] >> 7) & 1),
             base = PPU_bgTileAdr(p, physical);
    for (unsigned c = 0; c < 1024; c++) {
      unsigned n = 0;
      for (; n < 16; n++)
        if (p->vram[(base + c * 16 + n) & 32767])
          break;
      if (n == 16) {
        blank[logical] = (int)c;
        break;
      }
    }
    if (blank[logical] < 0) {
      s.reason = "transparent_character";
      return false;
    }
  }
  memset(s.output, 0, sizeof(s.output));
  for (int row = 0; row < s.height; row++) {
    int ny = row - s.view.native_y, line = Clamp(ny, 0, 223) + 1;
    size_t count = 0;
    for (unsigned n = 0; n < s.visual.world.part_count; n++) {
      const IogVisualPart *q = &s.visual.world.parts[n];
      int py = row - q->y;
      if (py < 0 || py >= q->height)
        continue;
      for (unsigned x = 0; x < q->width; x++) {
        unsigned idx = q->indices[py * q->width + x];
        s.object_rows[count][x] =
            idx ? (uint16_t)(0x8000 | s.palettes[line][idx]) : 0;
      }
      s.objects[count] = (PpuExtraObject){q->x,         0,
                                          q->width,     1,
                                          q->width,     q->priority,
                                          q->math,      0,
                                          q->order + 1, s.object_rows[count]};
      count++;
    }
    for (int start = 0; start < s.width; start += Chunk) {
      int width = Clamp(s.width - start, 0, Chunk);
      unsigned dirty[64], nd = 0;
      memcpy(p, s.registers[line], PPU_SAVESTATE_REGS_SIZE);
      memcpy(p->cgram, s.palettes[line], 512);
      p->screenEnabled[0] &= ~4;
      p->screenEnabled[1] &= ~4;
      for (unsigned logical = 0; logical < 2; logical++) {
        unsigned phys = logical ^ ((s.ram[0x6ee] >> 7) & 1);
        int camx = (int16_t)Word(s.source.ram, 0x68a + logical * 2),
            camy = (int16_t)Word(s.source.ram, 0x68e + logical * 2);
        int wx = (int)p->hScroll[phys] + s.view.world_x -
                 (int16_t)Word(s.source.ram, 0x68a) + start,
            wy = (int)p->vScroll[phys] + ny;
        unsigned sh = p->hScroll[phys], sv = p->vScroll[phys];
        p->hScroll[phys] = (uint16_t)wx & 1023;
        p->vScroll[phys] = (uint16_t)wy & 1023;
        for (int x = wx & ~7; x < wx + width; x += 8) {
          unsigned tile = MapTile(logical, x, wy + 1);
          if (tile == ~0u)
            tile = (unsigned)blank[logical];
          /* Preserve the actually uploaded384 native field (virtualX-64..319).
           * This includes partial strip updates; beyond it use bounded authored
           * data. */
          if (ny >= 0 && ny < 224 && x + 8 > camx - 64 && x < camx + 320) {
            unsigned tx = (sh + (x - camx)) >> 3, ty = (sv + ny + 1) >> 3,
                     a = PPU_bgTilemapAdr(p, phys) + ((ty & 31) << 5) +
                         (tx & 31);
            if (PPU_bgTilemapWider(p, phys) && (tx & 32))
              a += 0x400;
            tile = s.base.vram[a & 32767];
          }
          unsigned tx = ((unsigned)x & 1023) >> 3,
                   ty = ((unsigned)(wy + 1) & 1023) >> 3,
                   a = PPU_bgTilemapAdr(p, phys) + ((ty & 31) << 5) + (tx & 31);
          if (PPU_bgTilemapWider(p, phys) && (tx & 32))
            a += 0x400;
          a &= 32767;
          if (nd >= 64) {
            s.reason = "patch_capacity";
            return false;
          }
          dirty[nd++] = a;
          p->vram[a] = (uint16_t)tile;
        }
        (void)camy;
      }
      for (size_t n = 0; n < count; n++)
        s.objects[n].x -= start;
      PpuSetExtraObjects(p, s.objects, count);
      IogWorldPixelsDrawLine(p, 0);
      IogWorldPixelsDrawLine(p, 1);
      for (unsigned n = 0; n < nd; n++)
        p->vram[dirty[n]] = s.base.vram[dirty[n]];
      for (size_t n = 0; n < count; n++)
        s.objects[n].x += start;
      for (int x = 0; x < width; x++) {
        int wx = s.view.world_x + start + x, wy = s.view.world_y + row;
        if (wx >= s.left && wx < s.right && wy >= s.top && wy < s.bottom &&
            !s.exterior[(wy / 16) * 48 + wx / 16])
          s.output[row * s.width + start + x] = s.row[x];
      }
    }
  }
  return true;
}
void IogReceivedWorldEndRaster(void) {
  if (!s.enabled)
    return;
  if (s.valid) {
    s.complete = Render();
    if (s.complete)
      s.reason = "received_classroom_ready";
  }
  if (s.audit) {
    fprintf(s.audit,
            "{\"frame\":%d,\"ready\":%s,\"reason\":\"%s\",\"source_x_bias\":64,"
            "\"authored_right\":%d}\n",
            s.frame, s.complete ? "true" : "false",
            s.reason ? s.reason : "disabled", s.right);
    fflush(s.audit);
  }
}
static uint32_t Rgb(unsigned color) {
  unsigned r = color & 31, g = (color >> 5) & 31, b = (color >> 10) & 31;
  return 0xff000000u | ((r << 3 | r >> 2) << 16) | ((g << 3 | g >> 2) << 8) |
         (b << 3 | b >> 2);
}
int IogReceivedWorldDraw(uint8_t *dst, size_t pitch, const uint8_t *field,
                         int w, int h, double alpha) {
  (void)alpha;
  if (!s.enabled || !dst || !field || w != s.width || h != s.height)
    return 0;
  for (int y = 0; y < h; y++)
    memset(dst + y * pitch, 0, w * 4);
  if (!s.complete) {
    int l = (w - 384) / 2, t = (h - 224) / 2;
    for (int y = 0; y < 224; y++)
      memcpy(dst + (y + t) * pitch + l * 4, field + y * 384 * 4, 384 * 4);
    return 1;
  }
  for (int y = 0; y < h; y++)
    memcpy(dst + y * pitch, s.output + y * w, w * 4);
  /* UI is independent of the world extent. Its authored384-column surface
   * and screen-space direct prefix retain their readable reference scale. */
  int uw = 384 * h / 224, ux = (w - uw) / 2;
  for (unsigned n = s.visual.screen_count; n > 0; n--) {
    IogVisualScreenPart *q = &s.visual.screen[n - 1];
    for (int y = 0; y < h; y++) {
      int py = y * 224 / h - q->y;
      if (py < 0 || py >= q->height)
        continue;
      for (int x = 0; x < uw; x++) {
        int px = x * 384 / uw - (q->x + 64);
        if (px < 0 || px >= q->width)
          continue;
        unsigned idx = q->indices[py * q->width + px];
        if (idx && x + ux >= 0 && x + ux < w)
          ((uint32_t *)(dst + y * pitch))[x + ux] =
              Rgb(s.palettes[Clamp(y * 224 / h, 0, 223) + 1][idx]);
      }
    }
  }
  for (int y = 0; y < h; y++)
    for (int x = 0; x < uw; x++) {
      uint32_t color = s.ui[(y * 224 / h) * 384 + x * 384 / uw];
      if ((color >> 24) && x + ux >= 0 && x + ux < w)
        ((uint32_t *)(dst + y * pitch))[x + ux] = color;
    }
  return 1;
}
