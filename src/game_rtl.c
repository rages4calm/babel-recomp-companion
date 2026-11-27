/*
 * Illusion Of Gaia Usa — per-game runtime glue.
 *
 * THIS FILE IS THE PORT. Everything else the scaffold produced is layout,
 * build wiring, and packaging; this is where the actual work happens.
 *
 * The framework does not, and cannot, drive an arbitrary SNES game on its
 * own. Two responsibilities always land on the game host:
 *
 *   1. Deciding what "one frame" means for THIS title, and returning from
 *      run_frame() at that boundary. A real ROM's reset vector never
 *      returns — it enters a main loop that waits on vblank — so somebody
 *      has to choose the yield point.
 *   2. Delivering NMI/IRQ at the hardware edge (see
 *      snesrecomp/docs/FRAME_MODEL_HOSTS.md).
 *
 * What follows is the shape every working port in this ecosystem converged
 * on, built from documented bridge entry points:
 *
 *      boot from the reset vector
 *      -> deliver NMI at the vblank edge, gated on NMITIMEN
 *      -> run the guest in slices until it parks or the frame's clock is out
 *      -> service a raster IRQ whenever the comparator asserts
 *      -> rasterize the field with HDMA per line
 *
 * It is a starting point, not a finished port: a title with unusual timing
 * will need the slice loop tightened (MetalWarriorsSNESRecomp's src/mw_rtl.c
 * and GundamWingEndlessDuelSNESRecomp's src/game_rtl.c are the two most
 * developed examples, and the second walks the beam explicitly while the CPU
 * is parked). What it will NOT do is sit at a black screen doing nothing,
 * which is what a driver that delivers no interrupt always does.
 *
 * Why NMI is not gated on WAI: an earlier version of this template delivered
 * an interrupt only when interp_bridge_lle_took_wai() was true. Real titles
 * overwhelmingly wait on a WRAM flag set by their own NMI handler, not on
 * WAI — Super Metroid spins `LDA $05B4 / BNE`, Zelda 3 on $0012, Super Mario
 * World on $0010 — so that branch never fired and the guest parked forever
 * on its first vblank wait. Quiescence on a read-only cycle IS the signal
 * that only an interrupt can make progress; that is the edge to act on.
 */

#include "game_rtl.h"
#include "iog_widescreen.h"
#include "iog_native_poll.h"
#include "iog_native_continuations.h"
#include "iog_world_renderer.h"
#include "iog_i18n.h"
#ifndef IOG_RECEIVED_REFERENCE
#include "iog_walkable_world.h"
#include "companion_achievements/audit.h"
#endif

#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#include "common_cpu_infra.h"
#include "common_rtl.h"          /* SimpleHdma_*, g_snesrecomp_last_hdmaen */
#include "cpu_state.h"
#include "snes/dma.h"
#include "snes/interp_bridge.h"
#include "snes/ppu.h"
#include "snes/saveload.h"
#include "snes/snes.h"

extern CpuState g_cpu;
extern Ppu *g_ppu;

/* One NTSC frame: 262 scanlines x 1364 master clocks. Bounds a productive
 * MMIO loop so it cannot run across several vblanks atomically. */
#define GAME_MASTER_CYCLES_PER_FRAME 357368ull

/* How many times a frame may re-enter the guest after it parks on a poll.
 * Each slice ends at a deterministic read-only cycle or at an IRQ; the bound
 * only stops a pathological loop from spinning the host. */
#define GAME_MAX_SLICES_PER_FRAME 64

/* 0 until the first frame has booted from the reset vector. */
static uint32_t g_resume_pc;
#ifndef IOG_RECEIVED_REFERENCE
static bool g_world_observers_ready;

/* Both tiers observe exactly the original instruction boundary. These
 * wrappers never change guest state; registration failure leaves the host
 * without a qualified publication pair rather than a partial observer. */
void GameWorldObserveCompose(const CpuState *cpu, uint32_t pc24)
{
    if (g_world_observers_ready)
        IogWorldCaptureAtCompose(cpu, pc24);
}

void GameWorldObserveAfterCompose(const CpuState *cpu, uint32_t pc24)
{
    if (g_world_observers_ready)
        IogWorldCaptureAfterCompose(cpu, pc24);
}

static void GameWorldInterpCompose(CpuState *cpu, uint32_t pc24)
{
    GameWorldObserveCompose(cpu, pc24);
}

static void GameWorldInterpAfterCompose(CpuState *cpu, uint32_t pc24)
{
    GameWorldObserveAfterCompose(cpu, pc24);
}

static void GameInitialize(void)
{
    IogNativePollInitialize();
    IogNativeContinuationsInitialize();
    IogWorldInitialize();
    IogAchievementAuditBind();
    IogI18nBindStock();
    IogWalkableWorldInitialize();
    g_world_observers_ready = false;
    bool observers_ok = true;
    static const uint32_t banks[] = {0x030000, 0x430000, 0x830000, 0xc30000};
    for (unsigned i = 0; i < sizeof(banks) / sizeof(banks[0]); i++) {
        if (!interp_bridge_add_pre_opcode_hook(banks[i] | 0xc714, GameWorldInterpCompose))
            observers_ok = false;
        if (!interp_bridge_add_pre_opcode_hook(banks[i] | 0xc789, GameWorldInterpAfterCompose))
            observers_ok = false;
    }
    g_world_observers_ready = observers_ok;
    if (!observers_ok) {
        IogWorldReset();
        fprintf(stderr, "[iog_world] composition observers unavailable; world publication disabled\n");
    }
    /* This frame host pulses inNmi below. A second beam-owned RDNMI edge
     * lets the original vblank wait return twice before NMI refreshes the
     * raw pad, so the game remaps an already-remapped controller word. */
    snes_set_rdnmi_beam_enabled(false);
}
#else
#include "iog_received_observer.h"
#include "iog_received_world.h"
#ifdef IOG_RECEIVED_MAIN_CONTENT
#include "iog_received_content.h"
#endif
static void GameInitialize(void)
{
    /* SnesInit calls this before reset/guest execution. No stock-address
     * hooks or generated dispatch are admitted for the received image. */
    interp_bridge_set_interpret_all(1);
    interp_bridge_clear_native_instructions();
    interp_bridge_clear_native_rdnmi_polls();
    snes_set_rdnmi_beam_enabled(false);
    IogReceivedObserverInitialize();
#ifdef IOG_RECEIVED_MAIN_CONTENT
    if (!IogReceivedContentInitialize())
        Die("GaiaLabs content correction refused its source identity");
#endif
}
#endif

static uint32_t read_vector(uint32_t addr)
{
    /* Read through the guest bus so a mapper or coprocessor window resolves
     * the same way the CPU sees it. */
    uint32_t lo = snes_read(g_snes, addr);
    uint32_t hi = snes_read(g_snes, addr + 1u);
    return (hi << 8) | lo;
}

static uint32_t reset_vector(void) { return read_vector(0x00FFFCu); }
static uint32_t nmi_vector(void)   { return read_vector(0x00FFEAu); }
static uint32_t irq_vector(void)   { return read_vector(0x00FFEEu); }

/* Run one interrupt handler to its RTI, entered as hardware enters it: the
 * frame is pushed at the PC the guest was interrupted AT, so the handler's
 * terminal RTI returns into that instruction stream. */
static void game_run_interrupt(uint32_t vector, uint64_t frame_end, bool nmi_edge)
{
    cpu_push_interrupt_frame_at(&g_cpu, g_resume_pc);
    interp_bridge_set_master_deadline(frame_end);
#ifndef IOG_RECEIVED_REFERENCE
    if (nmi_edge && vector == 0x00800Bu && IogNativeContinuationsNmiEnabled())
        (void)interp_bridge_run_native_nmi(&g_cpu, vector);
    else
#else
    (void)nmi_edge;
#endif
        (void)interp_bridge_run_interrupt(&g_cpu, vector);
    /* Clearing matters: a deadline left armed stays true for every AOT block
     * prologue afterwards, which turns every compiled body into an immediate
     * yield-unwind. */
    interp_bridge_set_master_deadline(0);
    {
        uint32_t resume = interp_bridge_lle_resume_pc();
        if (resume)
            g_resume_pc = resume;
    }
}

/* HDMA takes each channel's table address when the frame starts (line 0),
 * after the vertical-blank NMI and before most of the frame's logic, which on
 * the console runs while the picture is drawn. This host runs all the logic
 * first and draws afterwards, so the frame read whatever the logic bound last:
 * a double-buffered table rebuilt and rebound during the logic (the band
 * scroll of Edward's Castle $0A and the Gold Ship $2B/$2C) was shown one
 * camera step ahead of the wall layer the NMI scrolled, and the floor slid
 * under the walls in the Original picture. The channel set-up seen right
 * after the NMI is what line 0 uses; the table contents are still read live. */
typedef struct { bool valid; uint8_t bAdr, aBank, indBank, mode; bool indirect; uint16_t aAdr; } HdmaLatch;
static HdmaLatch g_hdma_latch[8];
/* IOG_HDMA_LIVE=1: the old reading after the logic, for comparison runs. */
static bool getenv_hdma_live(void)
{
    static int live = -1;
    if (live < 0) { const char *v = getenv("IOG_HDMA_LIVE"); live = v && *v == '1'; }
    return live != 0;
}
static void GameLatchHdmaChannels(void)
{
    const Dma *dma = g_snes ? g_snes->dma : NULL;
    for (int ch = 0; ch < 8; ch++) {
        if (!dma) { g_hdma_latch[ch].valid = false; continue; }
        const DmaChannel *c = &dma->channel[ch];
        g_hdma_latch[ch] = (HdmaLatch){true, c->bAdr, c->aBank, c->indBank, c->mode, c->indirect, c->aAdr};
    }
}

void GameRunOneFrame(void)
{
#ifndef IOG_RECEIVED_REFERENCE
    IogWorldSimulationTick();
    IogWalkableWorldTick();
#else
    IogReceivedObserverFrame();
#endif
    const uint64_t frame_end = g_cpu.master_cycles + GAME_MASTER_CYCLES_PER_FRAME;
    const int booting = (g_resume_pc == 0);
    int slice;


    if (booting) {
        g_resume_pc = reset_vector();
        /* Real SNES reset state: native mode, 8-bit A/X, interrupts
         * disabled. The runtime initialises to (M1X0), but the AOT
         * body emitted for I_RESET only exists as M1X1, so the dispatch
         * would miss and fall to the interpreter — which then never
         * bounces back into generated code from the reset path. */
        g_cpu.emulation = 1;
        g_cpu.m_flag = 1;
        g_cpu.x_flag = 1;
        g_cpu._flag_I = 1;
        /* Enter the guest through the AOT dispatch table so the compiled
         * I_RESET body runs. The interpreter only bounces to AOT on
         * JSR/JSL, and reset leaves the bank via JML, so entering via
         * the interp never reaches generated code. */
        /* Stay on the interpreter path for boot. The AOT loop at
         * $82:8051 (BPL waiting on $4210 NMI) has no per-instruction
         * deadline check, so dispatching via cpu_dispatch_pc wedges the
         * process. The interpreter checks the deadline per instruction
         * and bounces to AOT bodies on JSR/JSL — exactly what we want. */
    }

    /* Vblank edge. NMITIMEN gates it: delivering before the guest has enabled
     * NMI would land an interrupt frame in the middle of its SEI boot
     * sequence. Nothing is delivered on the very first frame either — reset
     * has not run yet, so there is no instruction stream to interrupt. */
    if (!booting) {
        /* Set inNmi and LEAVE it set. Hardware keeps the $4210 bit 7
         * pending until the guest reads $4210, and snes_readReg() clears
         * it. A port that waits on $4210 directly (rather than on a WRAM
         * flag set by the NMI handler, like SMW/Zelda 3) never sees the
         * edge if we clear it here before the guest has a chance to read.
         * The flag latches at every vblank regardless of NMITIMEN. */
        g_snes->inNmi = true;
        /* The interrupt itself is gated on NMITIMEN bit 7. IoG disables NMI
         * around its full-screen column redraw (code_02ABE6); the NMI
         * handler rewrites VMAIN and the DMA source bank, so forcing it
         * mid-loop turned the rest of the tilemap into garbage. */
        if (g_snes->nmiEnabled) {
#ifndef IOG_RECEIVED_REFERENCE
            IogWorldBeforeNmi();
#else
            IogReceivedObserverBeforeNmi();
#endif
            game_run_interrupt(nmi_vector(), frame_end, true);
#ifndef IOG_RECEIVED_REFERENCE
            IogWorldAfterNmi();
#else
            IogReceivedObserverAfterNmi();
#endif
        }
    }
    GameLatchHdmaChannels();

    /* Run the guest until it parks on a read-only poll (its vblank wait) or
     * the frame's clock runs out. A single call is not enough: the guest
     * typically parks several times per frame — on HVBJOY, on a DMA-complete
     * flag, on its own state machine — and each park needs either an
     * interrupt or simply more time. */
    for (slice = 0; slice < GAME_MAX_SLICES_PER_FRAME; slice++) {
        if (g_cpu.master_cycles >= frame_end)
            break;
        interp_bridge_set_master_deadline(frame_end);
        interp_bridge_run_until_quiescent(&g_cpu, g_resume_pc);
        interp_bridge_set_master_deadline(0);
        {
            uint32_t resume = interp_bridge_lle_resume_pc();
            if (resume)
                g_resume_pc = resume;
        }

        /* A raster IRQ asserted while the guest ran: service it before
         * continuing, exactly as the CPU samples it between instructions. */
        if (g_snes->inIrq && !g_cpu._flag_I) {
            game_run_interrupt(irq_vector(), frame_end, false);
            continue;
        }
        /* Parked with no interrupt pending and clock left over: the guest is
         * waiting for the next vblank. Nothing more happens this frame. */
        if (interp_bridge_lle_took_wai())
            break;
    }
}

void GameDrawPpuFrame(void)
{
    SimpleHdma hdma_chans[8];
    Dma *dma = g_snes->dma;
    int trigger;
    int line, ch;
    unsigned hdma_lines = 0, irq_count = 0;

#ifndef IOG_RECEIVED_REFERENCE
    IogWidescreenBeforeDraw();
    IogWorldBeginRaster();
#else
    IogReceivedWorldBeginRaster();
#endif

    /* Re-arm HDMA from the last $420C (HDMAEN) the guest wrote — typically
     * during the NMI just run. The framework records it for exactly this. */
    dma_startDma(dma, g_snesrecomp_last_hdmaen, true);
    for (ch = 0; ch < 8; ch++)
    {
        /* The set-up latched at the top of this frame (GameLatchHdmaChannels);
         * enable comes from HDMAEN as before. */
        DmaChannel at_start = dma->channel[ch];
        const HdmaLatch *l = &g_hdma_latch[ch];
        if (l->valid && !getenv_hdma_live()) {
            at_start.bAdr = l->bAdr; at_start.aBank = l->aBank; at_start.indBank = l->indBank;
            at_start.mode = l->mode; at_start.indirect = l->indirect; at_start.aAdr = l->aAdr;
        }
        SimpleHdma_Init(&hdma_chans[ch], &at_start);
    }

    /* Mid-frame raster split, if the guest programmed the V comparator. */
    trigger = g_snes->vIrqEnabled ? (int)g_snes->vTimer : -1;

    /* From line 0, not line 1: starting at 1 leaves the top scanline holding
     * the previous frame's state, which shows up as a stripe of stale
     * tilemap above a HUD. */
    for (line = 0; line <= 224; line++) {
        /* HDMA runs in the H-blank BEFORE each visible line, and the raster
         * IRQ then selects the register set that line is drawn with — so
         * both must precede ppu_runLine for this line, not follow it. */
        for (ch = 0; ch < 8; ch++)
            SimpleHdma_DoLine(&hdma_chans[ch]);
        hdma_lines++;
        if (line == trigger) {
            g_snes->inIrq = true;
            cpu_push_interrupt_frame_at(&g_cpu, g_resume_pc);
            (void)interp_bridge_run_interrupt(&g_cpu, irq_vector());
            irq_count++;
            g_snes->inIrq = false;
            {
                uint32_t resume = interp_bridge_lle_resume_pc();
                if (resume)
                    g_resume_pc = resume;
            }
            trigger = g_snes->vIrqEnabled ? (int)g_snes->vTimer : -1;
        }
#ifndef IOG_RECEIVED_REFERENCE
        IogWidescreenBeforeLine(line);
        IogWorldCaptureLine(line);
#else
        IogReceivedWorldCaptureLine(line);
#endif
        ppu_runLine(g_ppu, line);
    }
#ifndef IOG_RECEIVED_REFERENCE
    IogWorldEndRaster(g_resume_pc, hdma_lines, irq_count);
#else
    IogReceivedWorldEndRaster();
#endif
}

/* Savestates. snes_saveload stores the emulated machine, but the guest's
 * program position lives here: g_resume_pc (where the guest parked at the
 * end of the frame) and the recompiler's CpuState registers. Without them a
 * load resumes the CURRENT instruction stream over the loaded RAM (from the
 * boot code, a load fell back to the title; in play, the game froze). */
enum { kStateMagic = 0x31474F49u /* "IOG1" */ };

typedef struct GameState {
    uint32_t magic, resume_pc;
    uint16_t A, X, Y, S, D;
    uint8_t DB, PB, P, emulation;
} GameState;

/* Host state that has to rewind with the guest, after GameState: input
 * filter latches (iog_mods.c hold to advance). Optional on load, so states
 * made before it existed still load. 8 bytes, little-endian:
 *   +0 u32 magic "IOG2"
 *   +4 u16 hold_advance_latched  bits $0103 (A|B|Y): the paging latch
 *                                bits $1030 (A|B|Y << 4): held across a
 *                                  timeline jump, hidden until released
 *                                bit $8000: a jump not yet applied
 *   +6 u16 hold_advance_held     bit 15 an advance button down, low byte $36
 *                                  when it went down / last generated press
 * Beta 19 wrote +6 as 0 and both betas wrote only the $0103 bits of +4; they
 * read +4 masked to $0103, so the jump bits are invisible to them and their
 * tails load here with no jump pending. Size and magic are unchanged. */
enum { kStateTailMagic = 0x32474F49u /* "IOG2" */ };
typedef struct GameStateTail { uint32_t magic; uint16_t hold_advance_latched, hold_advance_held; } GameStateTail;
#ifndef IOG_RECEIVED_REFERENCE
uint16_t IogHoldAdvanceStateSave(void);
uint16_t IogHoldAdvanceHeldSave(void);
void IogHoldAdvanceStateLoad(uint16_t latched, uint16_t held);
void IogHoldAdvanceTimelineJump(void);
#else   /* the reference build has no input filters and keeps its old format */
static void IogHoldAdvanceTimelineJump(void) {}
#endif

static void GameStateSave(SaveLoadInfo *sli)
{
    GameState st;
    memset(&st, 0, sizeof(st));
    /* Rewind snapshots every frame through here: read-only on the CPU. */
    CpuState tmp = g_cpu;
    cpu_mirrors_to_p(&tmp);
    st.magic = kStateMagic;
    st.resume_pc = g_resume_pc;
    st.A = g_cpu.A, st.X = g_cpu.X, st.Y = g_cpu.Y, st.S = g_cpu.S, st.D = g_cpu.D;
    st.DB = g_cpu.DB, st.PB = g_cpu.PB, st.P = tmp.P, st.emulation = g_cpu.emulation;
    sli->func(sli, &st, sizeof(st));
#ifndef IOG_RECEIVED_REFERENCE
    GameStateTail tail = {kStateTailMagic, IogHoldAdvanceStateSave(), IogHoldAdvanceHeldSave()};
    sli->func(sli, &tail, sizeof(tail));
#endif
}

static void GameStateLoad(SaveLoadInfo *sli, uint32_t version)
{
    (void)version;
    GameState st;
    memset(&st, 0, sizeof(st));
    sli->func(sli, &st, sizeof(st));
    if (st.magic != kStateMagic)
        return;
    g_resume_pc = st.resume_pc;
    /* The bridge's own resume PC is host state too. Left from before the
     * load, the first NMI after it (game_run_interrupt) put the OLD parking
     * place back into g_resume_pc: a load made while the game was changing
     * rooms resumed inside that room loader over the loaded RAM (Will's
     * house $06 into South Cape: BRK at $00:0001, no composition for the
     * rest of the run, the wide view fell back to 4:3). Rollback loads
     * restore the bridge exactly from their own residue. */
    if (!RtlIsRollbackLoad())
        interp_bridge_set_lle_resume_pc(st.resume_pc);
    /* The HDMA set-up latched before the load belongs to the old timeline;
     * the next frame latches its own after the NMI. */
    for (int ch = 0; ch < 8; ch++) g_hdma_latch[ch].valid = false;
    g_cpu.A = st.A, g_cpu.X = st.X, g_cpu.Y = st.Y, g_cpu.S = st.S, g_cpu.D = st.D;
    g_cpu.DB = st.DB, g_cpu.PB = st.PB, g_cpu.P = st.P, g_cpu.emulation = st.emulation;
    cpu_p_to_mirrors(&g_cpu);
#ifndef IOG_RECEIVED_REFERENCE
    const size_t remaining = RtlStateBytesRemaining(sli);
    if (remaining != SIZE_MAX && remaining >= sizeof(GameStateTail)) {
        GameStateTail tail;
        memset(&tail, 0, sizeof(tail));
        sli->func(sli, &tail, sizeof(tail));
        if (tail.magic == kStateTailMagic)
            IogHoldAdvanceStateLoad(tail.hold_advance_latched, tail.hold_advance_held);
    }
#endif
#ifndef IOG_RECEIVED_REFERENCE
    IogWorldReset();
    IogAchievementAuditInvalidate();
#else
    IogReceivedObserverReset();
#endif
}

/* The battery save belongs to the game, not to a save state.
 *
 * A save state carries the cartridge RAM of the moment it was made, so
 * loading one used to put that older copy back: a diary written in the game
 * after the state was made vanished from the title screen, and the copy on
 * disk was replaced by the old one at the next exit. The cartridge RAM in
 * memory is now kept across every ordinary state load and rewind; only the
 * game writes it. One exception, which can only add: while the battery is
 * blank it takes the state's copy, so a save that survives only inside a
 * state can still be brought back. Rollback loads (speculative capture,
 * run-ahead) restore their own snapshot exactly, as before. */
static uint8_t s_battery_keep[0x8000];
static int s_battery_keep_size = -1;

static bool GameSnapshotPreflight(const void *data, size_t size)
{
    (void)data; (void)size;
    s_battery_keep_size = -1;
    if (g_sram && g_sram_size > 0 && (size_t)g_sram_size <= sizeof(s_battery_keep)) {
        memcpy(s_battery_keep, g_sram, (size_t)g_sram_size);
        s_battery_keep_size = g_sram_size;
    }
    return true;
}

static void GameStateLoaded(uint32_t version)
{
    (void)version;
    /* A rollback (run-ahead, netplay) restored the filter latch with the
     * state; a real load or rewind jumped, and held buttons must be let go. */
    if (!RtlIsRollbackLoad())
        IogHoldAdvanceTimelineJump();
    const int size = s_battery_keep_size;
    s_battery_keep_size = -1;
    if (RtlIsRollbackLoad() || size <= 0 || size != g_sram_size || !g_sram)
        return;
    const char *state_copy = getenv("IOG_STATE_BATTERY");   /* "1": the old behaviour, for comparison runs */
    if (state_copy && *state_copy == '1')
        return;
    int blank = 1;
    for (int i = 0; i < size && blank; i++)
        blank = s_battery_keep[i] == 0x00 || s_battery_keep[i] == 0xFF;
    if (blank)
        return;
    if (memcmp(g_sram, s_battery_keep, (size_t)size)) {
        memcpy(g_sram, s_battery_keep, (size_t)size);
        fprintf(stderr, "[battery] kept the in-game save across a state load\n");
    }
}

/* Reset (Ctrl+R, the settings menu, a script) resets the machine under a
 * running game. The guest's parked program position is host state, so it has
 * to go too: left in place, the next frame resumed the old main loop against
 * the reset CPU and memory map, ran into zeroed memory and either found its
 * way to the title by accident or stayed on a black screen. Cleared, the next
 * frame boots from the reset vector as a power-on does. */
static void GameHardwareReset(void)
{
    g_resume_pc = 0;
    IogHoldAdvanceTimelineJump();
#ifndef IOG_RECEIVED_REFERENCE
    IogWorldReset();
    IogAchievementAuditInvalidate();
#else
    IogReceivedObserverReset();
#endif
}

const RtlGameInfo kGameInfo = {
    .title = "illusionofgaiausa",
    .initialize = &GameInitialize,
    .run_frame = &GameRunOneFrame,
    .draw_ppu_frame = &GameDrawPpuFrame,
    .save_name_prefix = "save",
    .state_save_extra = &GameStateSave,
    .state_load_extra = &GameStateLoad,
    .on_state_loaded = &GameStateLoaded,
    .snapshot_preflight = &GameSnapshotPreflight,
    .hardware_reset = &GameHardwareReset,
};

void GameSessionReset(void)
{
    /* Rematch / soft-return: clear anything that must not survive a new
     * session. recomp-ai-rules/NETPLAY.md §3 — sticky state that "has always
     * been fine" is the usual desync culprit, because single-player never
     * re-enters the boot path twice in one process. */
    g_resume_pc = 0;
#ifndef IOG_RECEIVED_REFERENCE
    IogWorldReset();
    IogAchievementAuditInvalidate();
#else
    IogReceivedObserverReset();
#endif
}
