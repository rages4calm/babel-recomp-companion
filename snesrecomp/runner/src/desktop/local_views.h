#pragma once

#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>
#include <string.h>
#include "display_aspect.h"

/* Presentation surfaces, independent of the guest PPU's line buffer. A game
 * renders each seat from one completed simulation frame, then publishes both
 * together. Shared menus/cutscenes can pass NULL for right to duplicate left. */
enum {
  kSnesDesktopMaxViewWidth = 1024,
  kSnesDesktopMaxFrameWidth = 2 * kSnesDesktopMaxViewWidth,
  kSnesDesktopMaxFrameHeight = 512,
};

/* Validate a title-owned presentation surface separately from the raster. */
static inline bool SnesLocalViews_PresentationSize(int requested_width,
    int requested_height, int fallback_width, int fallback_height,
    int *width, int *height) {
  bool valid = requested_width > 0 &&
      requested_width <= kSnesDesktopMaxFrameWidth && requested_height > 0 &&
      requested_height <= kSnesDesktopMaxFrameHeight;
  *width = valid ? requested_width : fallback_width;
  *height = valid ? requested_height : fallback_height;
  return valid;
}

/* A custom compositor may refuse an output frame. Center/crop its actual
 * source field into a black output without inferring source pitch/height
 * from presentation geometry. The two surfaces must not overlap. */
static inline bool SnesLocalViews_CopyRaster(void *dst, size_t pitch,
    int width, int height, const void *src, size_t source_pitch,
    int source_width, int source_height) {
  if (!dst || !src || width <= 0 || width > kSnesDesktopMaxFrameWidth ||
      height <= 0 || height > kSnesDesktopMaxFrameHeight || source_width <= 0 ||
      source_width > kSnesDesktopMaxFrameWidth || source_height <= 0 ||
      source_height > kSnesDesktopMaxFrameHeight ||
      pitch < (size_t)width * 4 || source_pitch < (size_t)source_width * 4 ||
      pitch > SIZE_MAX / (size_t)height ||
      source_pitch > SIZE_MAX / (size_t)source_height)
    return false;
  uintptr_t d = (uintptr_t)dst, s = (uintptr_t)src;
  size_t dn = pitch * (size_t)height, sn = source_pitch * (size_t)source_height;
  if (d <= s ? s - d < dn : d - s < sn) return false;
  int copy_width = width < source_width ? width : source_width;
  int copy_height = height < source_height ? height : source_height;
  int dx = (width - copy_width) / 2, dy = (height - copy_height) / 2;
  int sx = (source_width - copy_width) / 2, sy = (source_height - copy_height) / 2;
  for (int y = 0; y < height; ++y)
    memset((uint8_t *)dst + (size_t)y * pitch, 0, (size_t)width * 4);
  for (int y = 0; y < copy_height; ++y)
    memcpy((uint8_t *)dst + (size_t)(dy + y) * pitch + (size_t)dx * 4,
           (const uint8_t *)src + (size_t)(sy + y) * source_pitch + (size_t)sx * 4,
           (size_t)copy_width * 4);
  return true;
}

/* Preserve each pane's native pixel proportions while widening its field.
 * target_aspect is per pane, including half the drawable for adaptive views. */
static inline SnesDisplayFrame SnesLocalViews_ComputePane(
    int native_width, int height, double native_aspect, double target_aspect) {
  if (native_width <= 0 || native_width > kSnesDesktopMaxViewWidth ||
      height <= 0 || height > 240 || !(native_aspect > 0))
    return (SnesDisplayFrame){0};
  int max_width = kSnesDesktopMaxViewWidth - ((kSnesDesktopMaxViewWidth - native_width) & 1);
  double maximum = native_aspect * max_width / native_width;
  if (!(target_aspect >= native_aspect)) target_aspect = native_aspect;
  if (target_aspect > maximum) target_aspect = maximum;
  int extra = (int)((native_width * target_aspect / native_aspect - native_width) / 2 + .5);
  return (SnesDisplayFrame){native_width + 2 * extra, extra, target_aspect};
}

static inline SnesDisplayViewport SnesLocalViews_Viewport(
    double pane_aspect, int drawable_width, int drawable_height) {
  return SnesDisplayAspect_FitViewport(
      2 * pane_aspect, drawable_width, drawable_height);
}

static inline bool SnesLocalViews_ComposeSideBySide(
    void *dst, size_t pitch, int pane_width, int height,
    const void *left, size_t left_pitch, const void *right, size_t right_pitch) {
  if (!dst || !left || pane_width <= 0 ||
      pane_width > kSnesDesktopMaxViewWidth || height <= 0 || height > 240)
    return false;
  size_t row_bytes = (size_t)pane_width * sizeof(uint32_t);
  if (!right) { right = left; right_pitch = left_pitch; }
  if (pitch < 2 * row_bytes || left_pitch < row_bytes || right_pitch < row_bytes)
    return false;
  for (int y = 0; y < height; ++y) {
    uint8_t *row = (uint8_t *)dst + (size_t)y * pitch;
    memcpy(row, (const uint8_t *)left + (size_t)y * left_pitch, row_bytes);
    memcpy(row + row_bytes, (const uint8_t *)right + (size_t)y * right_pitch, row_bytes);
  }
  return true;
}
