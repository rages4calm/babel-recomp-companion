#ifndef IOG_WORLD_RENDERER_H
#define IOG_WORLD_RENDERER_H
#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>
struct CpuState;
void IogWorldInitialize(void);
bool IogWorldEnabled(void);
bool IogWorldStockVerified(void);
void IogWorldReset(void);
/* The player-facing "Enhanced world map" setting: filtered Mode 7 plane, open
 * sea past the map edge and a hazed horizon. Off is the point-sampled picture. */
void IogWorldSetMapEnhanced(bool enhanced);
void IogWorldSimulationTick(void);
void IogWorldGeometry(int drawable_w, int drawable_h, int *width, int *height);
void IogWorldCaptureAtCompose(const struct CpuState *cpu, uint32_t pc);
void IogWorldCaptureAfterCompose(const struct CpuState *cpu, uint32_t pc);
void IogWorldBeforeNmi(void);
void IogWorldAfterNmi(void);
void IogWorldBeginRaster(void);
void IogWorldCaptureLine(int line);
void IogWorldEndRaster(uint32_t resume_pc, unsigned hdma_lines, unsigned irq_count);
/* GPU ground for the Enhanced walking map; see iog_world_renderer.c and the
 * publisher in main.c. Samples per axis the presenter will use for frames
 * built from now on; 0 keeps the software plane. */
void IogWorldSetMapGpu(int samples);
/* One ground row as the runner's prepared-camera (affine) row. */
typedef struct IogWorldHdRow {
    uint8_t kind, haze, light, control, cgwsel, cgadsub;
    uint16_t fixed;
    int edge, samples; /* edge: palette index shown past the map, or -1 */
    double affine[8];
    const uint16_t *vram, *cgram;
    const uint32_t *soft; /* the software picture's row */
} IogWorldHdRow;
bool IogWorldHdQuery(int row, int width, int height, IogWorldHdRow *out);
uint32_t IogWorldHdHaze(int x, unsigned light);
int IogWorldDraw(uint8_t *dst, size_t pitch, const uint8_t *field,
                 int width, int height, double alpha);
#endif
