/* Host-only map chrome and interaction. Uses the framework's existing overlay
 * font/drawing helpers; preserves their attribution and license in the vendor.
 * Scenery and discovery are supplied by the qualified runtime, not this UI. */
#include "iog_map_ui.h"
#include "snes_overlay_draw.h"
#include <limits.h>
#include <stdio.h>
#include <string.h>
enum { Magic = 0x49554d47u };
static const unsigned scales[] = {2, 4, 6, 8, 12, 16, 24, 32};
static const uint32_t Stone = 0xff152131u, Gold = 0xffc6ad6bu,
                      Ivory = 0xffe8e1c8u;
static bool Overlap(const void *a, size_t an, const void *b, size_t bn) {
  uintptr_t x = (uintptr_t)a, y = (uintptr_t)b;
  return an && bn && (x <= y ? y - x < an : x - y < bn);
}
static int Clamp(int v, int lo, int hi) {
  return v < lo ? lo : v > hi ? hi : v;
}
void IogMapUiInit(IogMapUi *ui) {
  if (!ui)
    return;
  memset(ui, 0, sizeof(*ui));
  ui->magic = Magic;
  ui->radar = true;
  ui->center_pending = true;
  ui->zoom_index = -1;
}
void IogMapUiHandleInput(IogMapUi *ui, const IogMapUiInput *in) {
  if (!ui || !in || ui->magic != Magic)
    return;
  if (in->toggle_radar)
    ui->radar = !ui->radar;
  if (in->close) {
    ui->full = false;
    ui->pointer_down = ui->dragging = false;
    ui->visible = false;
    return;
  }
  if (in->toggle_full) {
    ui->full = !ui->full;
    ui->pointer_down = ui->dragging = false;
    ui->visible = false;
    if (ui->full)
      ui->center_pending = true;
  }
  if (!ui->full)
    return;
  if (in->recenter)
    ui->center_pending = true;
  if (in->zoom_in) {
    ui->zoom_index = Clamp(ui->zoom_index + 1, 0, 7);
  }
  if (in->zoom_out) {
    ui->zoom_index = Clamp(ui->zoom_index - 1, 0, 7);
  }
  /* Pan is cell-based and bounded; diagonal axes have identical rates.
   * Long suspended-frame deltas cannot throw the map away from the player. */
  unsigned ms = in->dt_ms > 100 ? 100 : in->dt_ms;
  int scale = (int)scales[Clamp(ui->zoom_index, 0, 7)];
  int delta = (int)((uint64_t)ms * 96 * 256 / (1000u * (unsigned)scale));
  ui->center_x_q8 =
      Clamp(ui->center_x_q8 + Clamp(in->pan_x, -1, 1) * delta, 0, 256 * 256);
  ui->center_y_q8 =
      Clamp(ui->center_y_q8 + Clamp(in->pan_y, -1, 1) * delta, 0, 256 * 256);
}
typedef struct FullLayout {
  int x, y, w, h, mx, my, mw, mh, back, minus, plus, center;
} FullLayout;
static FullLayout Layout(unsigned w, unsigned h) {
  FullLayout r;
  r.x = w >= 344 ? 20 : 10;
  r.y = 20;
  r.w = (int)w - 2 * r.x;
  r.h = (int)h - 40;
  r.mx = r.x + 8;
  r.my = r.y + 26;
  r.mw = r.w - 16;
  r.mh = r.h - 46;
  r.back = r.x + r.w - 74;
  r.minus = r.back - 58;
  r.plus = r.back - 30;
  r.center = r.w >= 300 ? r.minus - 66 : -1;
  return r;
}
static bool Hit(int x, int y, int rx, int ry, int w, int h) {
  return x >= rx && y >= ry && x < rx + w && y < ry + h;
}
bool IogMapUiPointer(IogMapUi *ui, int x, int y, bool down, unsigned w,
                     unsigned h) {
  if (!ui || ui->magic != Magic)
    return false;
  if (!down) {
    bool used = ui->pointer_down;
    ui->pointer_down = ui->dragging = false;
    return used;
  }
  if (!ui->full || !ui->visible || w != ui->draw_width ||
      h != ui->draw_height || w < 256 || w > 2048 || h < 160 || h > 2048)
    return false;
  FullLayout r = Layout(w, h);
  bool pressed = !ui->pointer_down;
  ui->pointer_down = true;
  if (pressed) {
    IogMapUiInput in = {0};
    if (Hit(x, y, r.back, r.y + 5, 64, 16))
      in.close = true;
    else if (Hit(x, y, r.minus, r.y + 5, 20, 16))
      in.zoom_out = true;
    else if (Hit(x, y, r.plus, r.y + 5, 20, 16))
      in.zoom_in = true;
    else if (r.center >= 0 && Hit(x, y, r.center, r.y + 5, 56, 16))
      in.recenter = true;
    if (in.close || in.zoom_in || in.zoom_out || in.recenter) {
      IogMapUiHandleInput(ui, &in);
      return true;
    }
    ui->dragging = Hit(x, y, r.mx, r.my, r.mw, r.mh);
    ui->pointer_x = x;
    ui->pointer_y = y;
    return ui->dragging;
  }
  if (!ui->dragging)
    return false;
  int64_t dx = (int64_t)x - ui->pointer_x, dy = (int64_t)y - ui->pointer_y;
  unsigned scale = scales[Clamp(ui->zoom_index, 0, 7)];
  int64_t cx = (int64_t)ui->center_x_q8 - dx * 256 / scale,
          cy = (int64_t)ui->center_y_q8 - dy * 256 / scale;
  ui->center_x_q8 = cx < 0 ? 0 : cx > 65536 ? 65536 : (int32_t)cx;
  ui->center_y_q8 = cy < 0 ? 0 : cy > 65536 ? 65536 : (int32_t)cy;
  ui->pointer_x = x;
  ui->pointer_y = y;
  return true;
}
static void Text(uint32_t *pixels, int stride, int height, int x, int y,
                 const char *text, uint32_t color, int available) {
  char clipped[128];
  size_t n = strlen(text), cap = available > 0 ? (unsigned)available / 8 : 0;
  if (n > cap)
    n = cap;
  if (n >= sizeof(clipped))
    n = sizeof(clipped) - 1;
  memcpy(clipped, text, n);
  clipped[n] = 0;
  snes_ovl_draw_text(pixels, stride, height, x, y, clipped, color, 1);
}
static bool SourceAliases(const IogMapViewSource *s, const void *out,
                          size_t n) {
  return Overlap(out, n, s, sizeof(*s)) ||
         Overlap(out, n, s->discovery, sizeof(*s->discovery)) ||
         Overlap(out, n, s->scenery_rgba, s->scenery_bytes) ||
         Overlap(out, n, s->walkable, s->walkable_bytes) ||
         (s->marker_count <= 256 &&
          Overlap(out, n, s->markers, s->marker_count * sizeof(*s->markers)));
}
bool IogMapUiDraw(IogMapUi *ui, uint8_t *dst, size_t bytes, size_t pitch,
                  unsigned w, unsigned h, const IogMapViewSource *source,
                  const IogMapUiMetadata *meta) {
  if (!ui || !meta || ui->magic != Magic || !dst || !source ||
      !source->discovery || w < 256 || h < 160 || w > 2048 || h > 2048 ||
      pitch % 4 || pitch < (size_t)w * 4 || pitch > (size_t)INT_MAX * 4 ||
      (h > 1 && pitch / 4 > ((size_t)INT_MAX - (w - 1)) / (h - 1)) ||
      (h > 1 && pitch > (SIZE_MAX - (size_t)w * 4) / (h - 1)))
    return false;
  size_t required = (size_t)(h - 1) * pitch + (size_t)w * 4;
  if (bytes < required || Overlap(dst, required, ui, sizeof(*ui)) ||
      Overlap(dst, required, meta, sizeof(*meta)) ||
      SourceAliases(source, dst, required))
    return false;
  ui->visible = false;
  if (!meta->valid || meta->hidden ||
      !IogMapDiscoveryEncodedSize(source->discovery)) {
    ui->full = false;
    ui->pointer_down = ui->dragging = false;
    ui->center_pending = true;
    return false;
  }
  if (!ui->full && !ui->radar)
    return false;
  const IogMapDiscovery *d = source->discovery;
  if (!ui->identity_valid ||
      memcmp(&ui->identity, &d->identity, sizeof(ui->identity))) {
    ui->pointer_down = ui->dragging = false;
    ui->identity = d->identity;
    ui->identity_valid = true;
    ui->center_pending = true;
    ui->zoom_index = -1;
  }
  int px, py, pw, ph, mx, my, mw, mh;
  if (ui->full) {
    FullLayout r = Layout(w, h);
    px = r.x;
    py = r.y;
    pw = r.w;
    ph = r.h;
    mx = r.mx;
    my = r.my;
    mw = r.mw;
    mh = r.mh;
  } else {
    pw = Clamp((int)w / 5, 104, 152);
    ph = pw * 3 / 4 + 18;
    px = (int)w - pw - 10;
    py = (int)h - ph - 10;
    mx = px + 5;
    my = py + 18;
    mw = pw - 10;
    mh = ph - 23;
  }
  if (mw <= 0 || mh <= 0)
    return false;
  int center_x = source->player_present ? source->player_x * 256 + 128
                                        : (int)d->width * 128;
  int center_y = source->player_present ? source->player_y * 256 + 128
                                        : (int)d->height * 128;
  if (ui->center_pending) {
    ui->center_x_q8 = center_x;
    ui->center_y_q8 = center_y;
    ui->center_pending = false;
  }
  unsigned scale;
  if (ui->full) {
    if (ui->zoom_index < 0) {
      unsigned fitx = (unsigned)mw / d->width, fity = (unsigned)mh / d->height,
               fit = fitx < fity ? fitx : fity;
      /* Start at the supplied atlas detail, not a tiny whole-dungeon icon.
       * Large maps pan naturally; zoom-out remains available for an overview.
       */
      unsigned detail = source->scenery_cell_pixels;
      if (detail < 8)
        detail = 8;
      if (fit < detail)
        fit = detail;
      ui->zoom_index = 0;
      for (unsigned n = 0; n < 8; n++)
        if (scales[n] <= fit)
          ui->zoom_index = (int)n;
    }
    ui->zoom_index = Clamp(ui->zoom_index, 0, 7);
    scale = scales[ui->zoom_index];
    ui->center_x_q8 = Clamp(ui->center_x_q8, 0, (int)d->width * 256);
    ui->center_y_q8 = Clamp(ui->center_y_q8, 0, (int)d->height * 256);
  } else {
    scale = 4;
    ui->center_x_q8 = center_x;
    ui->center_y_q8 = center_y;
  }
  int cx = ui->center_x_q8, cy = ui->center_y_q8;
  /* Denominator256 retains subcell pan and exact cell-center positioning. */
  IogMapViewSettings settings;
  memset(&settings, 0, sizeof(settings));
  settings.mode = ui->full ? kIogMapViewScenery : kIogMapViewRadar;
  settings.transform =
      (IogMapViewTransform){Clamp(cx - (mw * 128) / (int)scale, -65536, 65536),
                            Clamp(cy - (mh * 128) / (int)scale, -65536, 65536),
                            256, (uint16_t)scale, 1};
  settings.fog = (IogMapViewColor){10, 17, 26, 255};
  settings.floor = (IogMapViewColor){124, 145, 147, 255};
  settings.wall = (IogMapViewColor){38, 54, 67, 255};
  settings.player = (IogMapViewColor){232, 225, 200, 255};
  settings.player_radius_pixels = ui->full ? 2 : 1;
  uint8_t *map = dst + (size_t)my * pitch + (unsigned)mx * 4;
  size_t mapbytes = bytes - ((size_t)my * pitch + (unsigned)mx * 4);
  if (!IogMapViewRender(map, mapbytes, pitch, (unsigned)mw, (unsigned)mh,
                        source, &settings))
    return false;
  /* MapView is RGBA; the game frame is BGRA. Conversion is confined to the
   * successfully validated map viewport, never a second atlas or game copy. */
  for (int y = 0; y < mh; y++)
    for (int x = 0; x < mw; x++) {
      uint8_t *p = map + (size_t)y * pitch + x * 4;
      uint8_t r = p[0];
      p[0] = p[2];
      p[2] = r;
    }
  uint32_t *p = (uint32_t *)dst;
  int stride = (int)(pitch / 4);
  if (ui->full) {
    for (unsigned y = 0; y < h; y++)
      for (unsigned x = 0; x < w; x++)
        if (x < (unsigned)px || x >= (unsigned)(px + pw) || y < (unsigned)py ||
            y >= (unsigned)(py + ph)) {
          uint8_t *q = dst + (size_t)y * pitch + x * 4;
          q[0] /= 3;
          q[1] /= 3;
          q[2] /= 3;
          q[3] = 255;
        }
  }
  /* Fill only chrome around the viewport; artwork remains the focus. */
  snes_ovl_fill_rect(p, stride, (int)h, px, py, pw, my - py, Stone);
  snes_ovl_fill_rect(p, stride, (int)h, px, my + mh, pw, py + ph - my - mh,
                     Stone);
  snes_ovl_fill_rect(p, stride, (int)h, px, my, mx - px, mh, Stone);
  snes_ovl_fill_rect(p, stride, (int)h, mx + mw, my, px + pw - mx - mw, mh,
                     Stone);
  snes_ovl_stroke_rect(p, stride, (int)h, px, py, pw, ph, Gold);
  snes_ovl_stroke_rect(p, stride, (int)h, px + 2, py + 2, pw - 4, ph - 4,
                       0xff344251u);
  if (ui->full) {
    Text(p, stride, (int)h, px + 9, py + 9, "Area map", Ivory, pw - 18);
    FullLayout layout = Layout(w, h);
    if (meta->floor_number && pw >= 360) {
      char floor[32];
      snprintf(floor, sizeof(floor), "Floor %u", meta->floor_number);
      Text(p, stride, (int)h, px + 105, py + 9, floor, Gold,
           layout.center - (px + 105) - 10);
    }
    const char *back = meta->gamepad ? "B Back" : "Esc Back";
    int bx = layout.back;
    Text(p, stride, (int)h, bx, py + 9, back, Gold, 64);
    snes_ovl_stroke_rect(p, stride, (int)h, layout.minus, py + 5, 20, 16, Gold);
    snes_ovl_stroke_rect(p, stride, (int)h, layout.plus, py + 5, 20, 16, Gold);
    Text(p, stride, (int)h, layout.minus + 6, py + 9, "-", Ivory, 8);
    Text(p, stride, (int)h, layout.plus + 6, py + 9, "+", Ivory, 8);
    if (layout.center >= 0) {
      snes_ovl_stroke_rect(p, stride, (int)h, layout.center, py + 5, 56, 16,
                           0xff344251u);
      Text(p, stride, (int)h, layout.center + 4, py + 9, "Center", Ivory, 48);
    }
    const char *hint = meta->gamepad ? "Pad Move  L/R Zoom  Y Center"
                                     : "Arrows Move  +/- Zoom  Home Center";
    if (pw < 360)
      hint = meta->gamepad ? "Pad Move L/R Zoom Y Center"
                           : "Arrows Move +/- Zoom Home Center";
    Text(p, stride, (int)h, px + 9, py + ph - 13, hint, Ivory, pw - 18);
  } else {
    Text(p, stride, (int)h, px + 7, py + 6, "Area", Ivory, pw - 14);
  }
  if (ui->draw_width != w || ui->draw_height != h)
    ui->pointer_down = ui->dragging = false;
  ui->draw_width = w;
  ui->draw_height = h;
  ui->visible = true;
  return true;
}
