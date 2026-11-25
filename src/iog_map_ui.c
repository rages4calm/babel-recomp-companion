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
  ui->scale = 1;
}
static int UiScale(const IogMapUi *ui) { return ui->scale == 2 ? 2 : 1; }
void IogMapUiSetScale(IogMapUi *ui, unsigned scale) {
  if (ui && ui->magic == Magic)
    ui->scale = scale == 2 ? 2 : 1;
}
static void CopyPrompt(IogMapUiPrompt *to, const IogMapUiPrompt *from) {
  memset(to, 0, sizeof(*to));
  if (!from)
    return;
  snprintf(to->glyph, sizeof(to->glyph), "%.7s", from->glyph);
  snprintf(to->text, sizeof(to->text), "%.15s", from->text);
  to->color = from->color;
}
void IogMapUiSetPrompts(IogMapUi *ui, const IogMapUiPrompt *prompts,
                        unsigned count, const IogMapUiPrompt *back) {
  if (!ui || ui->magic != Magic)
    return;
  if (!prompts || count > IOG_MAP_UI_PROMPTS)
    count = prompts ? IOG_MAP_UI_PROMPTS : 0;
  for (unsigned n = 0; n < IOG_MAP_UI_PROMPTS; n++)
    CopyPrompt(&ui->prompts[n], n < count ? &prompts[n] : NULL);
  ui->prompt_count = count;
  CopyPrompt(&ui->back_prompt, count ? back : NULL);
}
int IogMapUiGlyphWidth(const char *glyph, uint32_t color, int scale) {
  if (!glyph || !glyph[0] || scale < 1)
    return 0;
  return color ? 18 * scale : ((int)strlen(glyph) * 8 + 6) * scale;
}
void IogMapUiGlyphDraw(uint32_t *pixels, int stride, int height, int x, int y,
                       const char *glyph, uint32_t color, int scale) {
  if (!pixels || !glyph || !glyph[0] || scale < 1)
    return;
  if (color) {
    snes_ovl_fill_disc(pixels, stride, height, x + 9 * scale, y + 9 * scale,
                       9 * scale, color);
    snes_ovl_fill_disc(pixels, stride, height, x + 9 * scale, y + 9 * scale,
                       9 * scale - scale, 0xff171b25u);
    snes_ovl_draw_char(pixels, stride, height, x + 5 * scale, y + 5 * scale,
                       glyph[0], color, scale);
    return;
  }
  int w = IogMapUiGlyphWidth(glyph, 0, scale);
  snes_ovl_fill_rect(pixels, stride, height, x, y + 2 * scale, w, 14 * scale,
                     0xff171b25u);
  for (int n = 0; n < scale; n++)
    snes_ovl_stroke_rect(pixels, stride, height, x + n, y + 2 * scale + n,
                         w - 2 * n, 14 * scale - 2 * n, Ivory);
  snes_ovl_draw_text(pixels, stride, height, x + 3 * scale, y + 5 * scale,
                     glyph, Ivory, scale);
}
void IogMapUiControllerHints(IogMapUi *ui,const char *hint,const char *back) {
  if(!ui||ui->magic!=Magic)return;
  snprintf(ui->controller_hint,sizeof(ui->controller_hint),"%s",hint?hint:"");
  snprintf(ui->controller_back,sizeof(ui->controller_back),"%s",back?back:"");
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
  int scale = (int)scales[Clamp(ui->zoom_index, 0, 7)] * UiScale(ui);
  ms *= (unsigned)UiScale(ui);   /* the same screen speed at either size */
  int delta = (int)((uint64_t)ms * 96 * 256 / (1000u * (unsigned)scale));
  ui->center_x_q8 =
      Clamp(ui->center_x_q8 + Clamp(in->pan_x, -1, 1) * delta, 0, 256 * 256);
  ui->center_y_q8 =
      Clamp(ui->center_y_q8 + Clamp(in->pan_y, -1, 1) * delta, 0, 256 * 256);
}
typedef struct FullLayout {
  int x, y, w, h, mx, my, mw, mh, back, minus, plus, center;
} FullLayout;
/* The panel takes the whole canvas but a small margin; s multiplies every
 * chrome dimension. Title row 26, button row 24 (an 18-high glyph fits). */
static FullLayout Layout(unsigned w, unsigned h, int s) {
  FullLayout r;
  r.x = ((int)w >= 344 * s ? 6 : 4) * s;
  r.y = r.x;
  r.w = (int)w - 2 * r.x;
  r.h = (int)h - 2 * r.y;
  r.mx = r.x + 6 * s;
  r.my = r.y + 26 * s;
  r.mw = r.w - 12 * s;
  r.mh = r.h - 50 * s;
  r.back = r.x + r.w - 82 * s;
  r.minus = r.back - 58 * s;
  r.plus = r.back - 30 * s;
  r.center = r.w >= 300 * s ? r.minus - 66 * s : -1;
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
  const int s = UiScale(ui);
  FullLayout r = Layout(w, h, s);
  bool pressed = !ui->pointer_down;
  ui->pointer_down = true;
  if (pressed) {
    IogMapUiInput in = {0};
    if (Hit(x, y, r.back, r.y + 4 * s, 72 * s, 18 * s))
      in.close = true;
    else if (Hit(x, y, r.minus, r.y + 5 * s, 20 * s, 16 * s))
      in.zoom_out = true;
    else if (Hit(x, y, r.plus, r.y + 5 * s, 20 * s, 16 * s))
      in.zoom_in = true;
    else if (r.center >= 0 && Hit(x, y, r.center, r.y + 5 * s, 56 * s, 16 * s))
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
  unsigned scale = scales[Clamp(ui->zoom_index, 0, 7)] * (unsigned)UiScale(ui);
  int64_t cx = (int64_t)ui->center_x_q8 - dx * 256 / scale,
          cy = (int64_t)ui->center_y_q8 - dy * 256 / scale;
  ui->center_x_q8 = cx < 0 ? 0 : cx > 65536 ? 65536 : (int32_t)cx;
  ui->center_y_q8 = cy < 0 ? 0 : cy > 65536 ? 65536 : (int32_t)cy;
  ui->pointer_x = x;
  ui->pointer_y = y;
  return true;
}
static void TextScaled(uint32_t *pixels, int stride, int height, int x, int y,
                       const char *text, uint32_t color, int available, int s) {
  char clipped[128];
  size_t n = strlen(text), cap = available > 0 ? (unsigned)available / (8u * (unsigned)s) : 0;
  if (n > cap)
    n = cap;
  if (n >= sizeof(clipped))
    n = sizeof(clipped) - 1;
  memcpy(clipped, text, n);
  clipped[n] = 0;
  snes_ovl_draw_text(pixels, stride, height, x, y, clipped, color, s);
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
bool IogMapUiDrawControls(uint8_t *dst,size_t bytes,size_t pitch,unsigned w,
    unsigned h,const uint8_t bindings[5],unsigned selected,bool radar,bool persistent)
{
    if(!dst||((uintptr_t)dst&3)||!bindings||selected>5||w<256||w>2048||h<256||h>2048||
        pitch<(size_t)w*4||(pitch&3)||pitch>SIZE_MAX/h||bytes<pitch*h||
        Overlap(dst,pitch*h,bindings,5))return false;
    unsigned used=0;
    for(unsigned n=0;n<5;n++){
        if(bindings[n]>=6||(used&(1u<<bindings[n])))return false;
        used|=1u<<bindings[n];
    }
    static const char *const names[]={"A","B","X","Y","L","R"};
    static const char *const labels[]={"Radar","Zoom in","Zoom out","Center","Radar button","Back button"};
    uint32_t *pixels=(uint32_t*)dst;int stride=(int)(pitch/4),height=(int)h;
    snes_ovl_fill_rect(pixels,stride,height,0,0,(int)w,(int)h,Stone);
    snes_ovl_stroke_rect(pixels,stride,height,12,12,(int)w-24,(int)h-24,Gold);
    Text(pixels,stride,height,24,23,"Map controls",Ivory,(int)w-48);
    Text(pixels,stride,height,24,40,"SNES buttons / Controller physical mapping",Gold,(int)w-48);
    int top=64,step=((int)h-142)/6;if(step<11)step=11;if(step>27)step=27;
    for(unsigned n=0;n<6;n++){
        int y=top+(int)n*step;
        if(n==selected)snes_ovl_fill_rect(pixels,stride,height,22,y-3,(int)w-44,15,0xff344251u);
        Text(pixels,stride,height,30,y,labels[n],n==selected?Gold:Ivory,(int)w-110);
        Text(pixels,stride,height,(int)w-70,y,n?names[bindings[n-1]]:(radar?"ON":"OFF"),Gold,46);
    }
    Text(pixels,stride,height,24,(int)h-59,"Pad Choose  Left/Right Change  B Back",Ivory,(int)w-48);
    Text(pixels,stride,height,24,(int)h-43,"Assigned buttons swap; Back stays available.",Ivory,(int)w-48);
    Text(pixels,stride,height,24,(int)h-27,persistent?"Saved on this PC":"Session only: settings could not be saved",Gold,(int)w-48);
    return true;
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
  const int s = ui->full ? UiScale(ui) : 1;
  if (ui->full) {
    FullLayout r = Layout(w, h, s);
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
      /* Start with what has been explored filling the viewport around the
       * map's centre (the player), so a little-explored area is not a patch
       * in an empty panel. Never below the atlas detail (large maps pan;
       * zoom-out remains for an overview) nor above twice it. */
      unsigned detail = source->scenery_cell_pixels;
      if (detail < 8)
        detail = 8;
      int x0 = INT_MAX, y0 = INT_MAX, x1 = -1, y1 = -1;
      for (int y = 0; y < (int)d->height; y++)
        for (int x = 0; x < (int)d->width; x++)
          if (IogMapDiscoveryIsRevealed(d, x, y)) {
            if (x < x0) x0 = x;
            if (x > x1) x1 = x;
            if (y < y0) y0 = y;
            if (y > y1) y1 = y;
          }
      unsigned fit;
      if (x1 >= 0) {
        int cx = ui->center_x_q8 / 256, cy = ui->center_y_q8 / 256;
        int halfw = (cx - x0 > x1 - cx ? cx - x0 : x1 - cx) + 2;
        int halfh = (cy - y0 > y1 - cy ? cy - y0 : y1 - cy) + 2;
        unsigned fitx = (unsigned)mw / (2u * (unsigned)halfw),
                 fity = (unsigned)mh / (2u * (unsigned)halfh);
        fit = (fitx < fity ? fitx : fity) / (unsigned)s;
      } else {
        unsigned fitx = (unsigned)mw / d->width, fity = (unsigned)mh / d->height;
        fit = (fitx < fity ? fitx : fity) / (unsigned)s;
      }
      if (fit < detail)
        fit = detail;
      if (fit > 2 * detail)
        fit = 2 * detail;
      ui->zoom_index = 0;
      for (unsigned n = 0; n < 8; n++)
        if (scales[n] <= fit)
          ui->zoom_index = (int)n;
    }
    ui->zoom_index = Clamp(ui->zoom_index, 0, 7);
    scale = scales[ui->zoom_index] * (unsigned)s;
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
  settings.player_radius_pixels = ui->full ? 2 * s : 1;
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
  for (int n = 0; n < s; n++)
    snes_ovl_stroke_rect(p, stride, (int)h, px + n, py + n, pw - 2 * n,
                         ph - 2 * n, Gold);
  for (int n = 0; n < s; n++)
    snes_ovl_stroke_rect(p, stride, (int)h, px + 2 * s + n, py + 2 * s + n,
                         pw - 4 * s - 2 * n, ph - 4 * s - 2 * n, 0xff344251u);
  if (ui->full) {
    const int H = (int)h;
    TextScaled(p, stride, H, px + 9 * s, py + 9 * s, "Area map", Ivory,
               pw - 18 * s, s);
    FullLayout layout = Layout(w, h, s);
    if (meta->floor_number && pw >= 360 * s) {
      char floor[32];
      snprintf(floor, sizeof(floor), "Floor %u", meta->floor_number);
      TextScaled(p, stride, H, px + 105 * s, py + 9 * s, floor, Gold,
                 layout.center - (px + 105 * s) - 10 * s, s);
    }
    const bool glyphs = meta->gamepad && ui->prompt_count;
    int bx = layout.back;
    if (glyphs && ui->back_prompt.glyph[0]) {
      IogMapUiGlyphDraw(p, stride, H, bx, py + 4 * s, ui->back_prompt.glyph,
                        ui->back_prompt.color, s);
      bx += IogMapUiGlyphWidth(ui->back_prompt.glyph, ui->back_prompt.color, s) + 4 * s;
      TextScaled(p, stride, H, bx, py + 9 * s, "Back", Gold, pw - bx + px - 7 * s, s);
    } else {
      const char *back = meta->gamepad ?
          (ui->controller_back[0]?ui->controller_back:"B Back") : "Esc Back";
      TextScaled(p, stride, H, bx, py + 9 * s, back, Gold, pw - bx + px - 7 * s, s);
    }
    for (int n = 0; n < s; n++) {
      snes_ovl_stroke_rect(p, stride, H, layout.minus + n, py + 5 * s + n,
                           20 * s - 2 * n, 16 * s - 2 * n, Gold);
      snes_ovl_stroke_rect(p, stride, H, layout.plus + n, py + 5 * s + n,
                           20 * s - 2 * n, 16 * s - 2 * n, Gold);
    }
    TextScaled(p, stride, H, layout.minus + 6 * s, py + 9 * s, "-", Ivory, 8 * s, s);
    TextScaled(p, stride, H, layout.plus + 6 * s, py + 9 * s, "+", Ivory, 8 * s, s);
    if (layout.center >= 0) {
      for (int n = 0; n < s; n++)
        snes_ovl_stroke_rect(p, stride, H, layout.center + n, py + 5 * s + n,
                             56 * s - 2 * n, 16 * s - 2 * n, 0xff344251u);
      TextScaled(p, stride, H, layout.center + 4 * s, py + 9 * s, "Center",
                 Ivory, 48 * s, s);
    }
    /* Bottom row: the marker legend on the right, button prompts beside it.
     * A prompt that would reach the legend is left out, never clipped. */
    const int row = py + ph - 21 * s, text_y = row + 5 * s;
    int right = px + pw - 9 * s;
    const IogMapViewColor colors[] = {meta->chest_legend, meta->exit_legend};
    const char *const labels[] = {"Chest", "Exit"};
    for (unsigned i = 0; i < sizeof(colors) / sizeof(colors[0]); i++) {
      IogMapViewColor color = colors[i];
      int width = (10 + 8 * (int)strlen(labels[i])) * s;
      if (!color.a || right - width < px + 9 * s)
        continue;
      uint32_t dot = 0xff000000u | (uint32_t)color.r << 16 |
                     (uint32_t)color.g << 8 | color.b;
      right -= width;
      snes_ovl_fill_rect(p, stride, H, right, text_y + s, 5 * s, 5 * s, dot);
      TextScaled(p, stride, H, right + 10 * s, text_y, labels[i], Ivory,
                 width - 10 * s, s);
      right -= 12 * s;
    }
    int x = px + 9 * s;
    if (glyphs) {
      for (unsigned i = 0; i < ui->prompt_count; i++) {
        const IogMapUiPrompt *q = &ui->prompts[i];
        /* An empty action joins this glyph to the next (LB RB Zoom). */
        int width = IogMapUiGlyphWidth(q->glyph, q->color, s) +
                    (q->text[0] ? (4 + 8 * (int)strlen(q->text)) * s : 0);
        int group = width;
        for (unsigned j = i; !ui->prompts[j].text[0] && j + 1 < ui->prompt_count;) {
          const IogMapUiPrompt *next = &ui->prompts[++j];
          group += 2 * s + IogMapUiGlyphWidth(next->glyph, next->color, s) +
                   (next->text[0] ? (4 + 8 * (int)strlen(next->text)) * s : 0);
        }
        if (x + group > right)
          break;
        IogMapUiGlyphDraw(p, stride, H, x, row, q->glyph, q->color, s);
        x += IogMapUiGlyphWidth(q->glyph, q->color, s);
        if (q->text[0]) {
          TextScaled(p, stride, H, x + 4 * s, text_y, q->text, Ivory,
                     8 * (int)strlen(q->text) * s, s);
          x += (4 + 8 * (int)strlen(q->text) + 12) * s;
        } else {
          x += 2 * s;
        }
      }
    } else {
      const char *hint = meta->gamepad ? "SNES: L/R Zoom Y Center X Radar"
                                       : "Arrows Move  +/- Zoom  Home Center  Tab Controls";
      if (pw < 360 * s)
        hint = meta->gamepad ? "SNES: L/R Zoom Y Center X Radar"
                             : "Arrows Move +/- Zoom Home Center";
      if(meta->gamepad&&ui->controller_hint[0])hint=ui->controller_hint;
      TextScaled(p, stride, H, x, text_y, hint, Ivory, right - x, s);
    }
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
