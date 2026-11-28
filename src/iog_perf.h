/* Opt-in per-frame timers for the presentation work (IOG_PERF=<file.csv>).
 * Off (the default build) the macros are constants; in a profiling build
 * they are one branch on a flag set from the environment. Nothing is
 * sampled and no guest or picture state is read or changed.
 * One row per rasterised frame: the game-side split of the host's
 * "raster-capture" stage (SNESRECOMP_FRAME_TIMING) plus the game's own
 * logic-frame count (composes), so a lagging guest frame is visible. */
#ifndef IOG_PERF_H
#define IOG_PERF_H

#include <stdint.h>

enum {
    kIogPerfLines,      /* ppu_runLine over the field */
    kIogPerfIrq,        /* the raster IRQ handler (guest code) */
    kIogPerfCapture,    /* per-line register/epoch capture */
    kIogPerfEnd,        /* end of raster: the wide picture (all of it) */
    kIogPerfVisual,     /*   visual objects (sprite decode) */
    kIogPerfRows,       /*   world rows (planes + objects) */
    kIogPerfHud,        /*   status display composite */
    kIogPerfMode7,      /*   Mode 7 plane */
    kIogPerfAudit,      /* after-frame hook: achievement audit */
    kIogPerfToast,      /*   achievement UI */
    kIogPerfMap,        /*   area map host */
    kIogPerfCompanion,  /*   companion */
    kIogPerfCount
};

/* Compiled in only with -DIOG_PERF_TIMERS=1 (a profiling build); otherwise
 * every macro is a constant and nothing needs to be linked. */
#if defined(IOG_PERF_TIMERS) && IOG_PERF_TIMERS
extern int g_iog_perf;
double IogPerfNow(void);
void IogPerfAdd(int slot, double start);
void IogPerfCompose(void);
void IogPerfFrame(unsigned frame);
#define IOG_PERF_ON g_iog_perf
#define IOG_PERF_START() (g_iog_perf ? IogPerfNow() : 0.0)
#define IOG_PERF_END(slot, t0) do { if (g_iog_perf) IogPerfAdd((slot), (t0)); } while (0)
#else
#define IOG_PERF_ON 0
#define IOG_PERF_START() 0.0
#define IOG_PERF_END(slot, t0) ((void)(slot), (void)(t0))
#define IogPerfCompose() ((void)0)
#define IogPerfFrame(frame) ((void)(frame))
#endif

#endif
