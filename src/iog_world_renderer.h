#ifndef IOG_WORLD_RENDERER_H
#define IOG_WORLD_RENDERER_H
#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>
struct CpuState;
void IogWorldInitialize(void);
bool IogWorldEnabled(void);
void IogWorldReset(void);
void IogWorldSimulationTick(void);
void IogWorldGeometry(int drawable_w, int drawable_h, int *width, int *height);
void IogWorldCaptureAtCompose(const struct CpuState *cpu, uint32_t pc);
void IogWorldCaptureAfterCompose(const struct CpuState *cpu, uint32_t pc);
void IogWorldBeforeNmi(void);
void IogWorldAfterNmi(void);
void IogWorldBeginRaster(void);
void IogWorldCaptureLine(int line);
void IogWorldEndRaster(uint32_t resume_pc, unsigned hdma_lines, unsigned irq_count);
int IogWorldDraw(uint8_t *dst, size_t pitch, const uint8_t *field,
                 int width, int height, double alpha);
#endif
