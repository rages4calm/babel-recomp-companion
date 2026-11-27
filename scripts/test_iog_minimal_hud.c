/* ROM-free fixture for the GaiaLabs Minimal HUD (src/iog_minimal_hud.c).
 * Includes the ACTUAL implementation (the path comes from
 * IOG_MINIMAL_HUD_SOURCE, so an older revision can be compiled for a before
 * run); only the host it touches is stubbed.
 *
 * The runner is modelled as far as the HUD code can see it: g_ppu->vram, the
 * BG3 map base (BG3SC), BG mode, vramWriteCount, and the VRAM write paths.
 * A guest store goes through the same steps as the runner's ports: the byte
 * port ($2118/$2119, ppu.c ppu_write, which DMA and HDMA use) bumps the
 * counter and calls the VRAM write log hook once per byte; the word store
 * (common_rtl.c WriteVramWord, a 16-bit STA $2118) bumps it once and calls
 * the hook for both bytes. A host-only change bumps the counter alone.
 *
 * The cartridge holds the stock loader signature and a made-up HUD stream
 * (positions and words are synthetic, not the game's), so the fixed-tile
 * test runs as it does with the real ROM.
 *
 * Every case runs one frame: BeginDraw, the raster (where the picture is
 * sampled and guest writes may land), EndDraw. It checks what the raster
 * saw and that VRAM afterwards equals what the stock game would hold: the
 * HUD words before the frame plus every guest write, whatever its value. */
#include IOG_MINIMAL_HUD_SOURCE

static uint8_t test_ram[0x20000], test_rom[0x40000];
static Cart test_cart = {test_rom, sizeof test_rom};
static Snes test_snes = {test_ram, &test_cart};
static Ppu test_ppu;
Snes *g_snes = &test_snes;
Ppu *g_ppu = &test_ppu;

static PpuVramWriteLogHook test_hook;
void ppu_set_vram_write_log_hook(PpuVramWriteLogHook hook) { test_hook = hook; }
int snes_mod_register_reset_callback(SNESModActivationCallback fn) { (void)fn; return 1; }
int snes_mod_register_activation_plugin(const char *id, SNESModActivationCallback fn) { (void)id; (void)fn; return 1; }

static unsigned assertions, failures;
static const char *current_case;
#define CHECK(v) do { assertions++; if (!(v)) { failures++; \
    fprintf(stderr, "FAIL %s %s:%d: %s\n", current_case, __FILE__, __LINE__, #v); } } while (0)

enum { kMapBase = 0x7800, kFixed = 41 };
static uint16_t fixed_pos[kFixed], fixed_word[kFixed];
static uint16_t stock[0x8000];      /* VRAM the stock game would hold */
static uint16_t picture[kHudWords]; /* the HUD rows as the raster drew them */

static void BuildRom(bool loader)
{
    memset(test_rom, 0, sizeof test_rom);
    static const uint8_t kSig[] = {
        0xAD, 0xED, 0x09, 0x89, 0x40, 0xF0, 0x01, 0x6B, 0x08, 0xC2, 0x20,
        0x8B, 0x4B, 0xAB, 0xA0, 0x00, 0x00, 0xBB, 0xB9, 0x0A, 0xDF,
    };
    if (loader) memcpy(test_rom + kLoaderRom, kSig, sizeof kSig);
    /* 41 fixed tiles spread over rows 0-4 with skips between runs. */
    uint8_t *p = test_rom + kStreamRom;
    unsigned pos = 0, n = 0;
    while (n < kFixed) {
        unsigned run = 1 + n % 4;
        for (unsigned k = 0; k < run && n < kFixed; k++, n++) {
            uint16_t w = (uint16_t)(0x2100 + n * 3);
            fixed_pos[n] = (uint16_t)pos; fixed_word[n] = w;
            *p++ = (uint8_t)w; *p++ = (uint8_t)(w >> 8); pos++;
        }
        unsigned skip = 2;
        *p++ = 0; *p++ = 0; *p++ = (uint8_t)skip; *p++ = 0; pos += skip;
    }
    *p++ = 0; *p++ = 0; *p++ = 0; *p++ = 0;
}

static void Setup(bool on, bool lock, bool loader)
{
    memset(&test_ppu, 0, sizeof test_ppu);
    memset(test_ram, 0, sizeof test_ram);
    test_hook = NULL;
    BuildRom(loader);
    g_fixed_count = -1;
    g_on = on;
    g_blanked = false;
    test_ppu.bgmode = 1;
    test_ppu.bgXsc[2] = kMapBase >> 8;
    test_ram[kPlayerFlags] = lock ? kCombatLock : 0;
    /* Background junk everywhere, then the HUD rows: changing stat words
     * (nonzero, never blank) with the fixed tiles placed over them. */
    for (unsigned i = 0; i < 0x8000; i++) test_ppu.vram[i] = (uint16_t)(0x1000 | (i * 7 & 0x3ff));
    uint16_t *map = &test_ppu.vram[kMapBase];
    for (unsigned i = 0; i < kHudWords; i++) map[i] = (uint16_t)(0x3400 | (i & 0x3ff));
    if (loader) {
        for (unsigned n = 0; n < kFixed; n++) map[fixed_pos[n]] = fixed_word[n];
    } else {
        map[32 + 11] = 0x20EF; map[32 + 20] = 0x60EF; map[32 + 15] = 0x201E;
    }
    test_ppu.vramWriteCount = 100;
    memcpy(stock, test_ppu.vram, sizeof stock);
}

/* The runner's write paths (see the header comment). */
static void BytePort(uint16_t word, uint8_t lo, uint8_t hi)
{
    word &= 0x7fff;
    test_ppu.vram[word] = (uint16_t)((test_ppu.vram[word] & 0xff00) | lo);
    test_ppu.vramWriteCount++;
    if (test_hook) test_hook((uint32_t)word << 1, lo);
    test_ppu.vram[word] = (uint16_t)((test_ppu.vram[word] & 0x00ff) | hi << 8);
    test_ppu.vramWriteCount++;
    if (test_hook) test_hook(((uint32_t)word << 1) + 1, hi);
    stock[word] = (uint16_t)(lo | hi << 8);
}
static void WordStore(uint16_t word, uint16_t value)
{
    word &= 0x7fff;
    test_ppu.vram[word] = value;
    test_ppu.vramWriteCount++;
    if (test_hook) { test_hook((uint32_t)word << 1, (uint8_t)value); test_hook(((uint32_t)word << 1) + 1, (uint8_t)(value >> 8)); }
    stock[word] = value;
}
static void GuestWrite(uint16_t word, uint16_t value, bool word_store)
{
    if (word_store) WordStore(word, value);
    else BytePort(word, (uint8_t)value, (uint8_t)(value >> 8));
}

typedef void (*RasterFn)(void);
static void Frame(RasterFn raster)
{
    IogMinimalHudBeginDraw();
    /* The raster draws the HUD rows from the top of the screen first. */
    memcpy(picture, &test_ppu.vram[kMapBase], sizeof picture);
    if (raster) raster();
    IogMinimalHudEndDraw();
}

static bool VramIsStock(void) { return !memcmp(test_ppu.vram, stock, sizeof stock); }
static bool PictureBlank(void)
{
    for (unsigned i = 0; i < kHudWords; i++) if (picture[i] != kBlankWord) return false;
    return true;
}
static bool PictureIsStock(void) { return !memcmp(picture, &stock[kMapBase], sizeof picture); }

/* --- rasters --- */
static void RasterNothing(void) {}
static void RasterHostBump(void) { test_ppu.vramWriteCount++; }
static void RasterNonzero(void)
{
    GuestWrite(kMapBase + 2 * 32 + 5, 0x2C41, false);
    GuestWrite(kMapBase + 3 * 32 + 9, 0x2C42, true);
    GuestWrite(kMapBase + fixed_pos[7], 0x2C43, false);
}
static void RasterBlank(void)
{
    /* A clear of the HUD rows (ClearBg3TilemapBuffer_Full writes $0000)
     * plus one row cleared by word stores. */
    for (unsigned i = 0; i < 4 * 32; i++) GuestWrite((uint16_t)(kMapBase + i), kBlankWord, false);
    for (unsigned i = 4 * 32; i < kHudWords; i++) GuestWrite((uint16_t)(kMapBase + i), kBlankWord, true);
}
static void RasterMixed(void)
{
    GuestWrite(kMapBase + 33, kBlankWord, false);
    GuestWrite(kMapBase + 34, 0x2C50, false);
    GuestWrite(kMapBase + fixed_pos[0], kBlankWord, true);
    GuestWrite(0x1234, 0x0000, false);
}
static void RasterElsewhere(void)
{
    GuestWrite(0x1234, 0x0000, false);
    GuestWrite(kMapBase + kHudWords, 0x0000, true);     /* row 5, below the HUD */
    GuestWrite(kMapBase - 1, 0x0000, false);            /* just before the map */
    GuestWrite(0x4000, 0xBEEF, true);
}

static void CheckHidden(void) { CHECK(PictureBlank()); }

static int RunCase(const char *name)
{
    current_case = name;
    if (!strcmp(name, "no-writes")) {
        Setup(true, true, true);
        uint32_t c0 = test_ppu.vramWriteCount;
        Frame(RasterNothing);
        CheckHidden(); CHECK(VramIsStock());
        CHECK(test_ppu.vramWriteCount != c0);   /* frame caches see the change */
    } else if (!strcmp(name, "host-bump")) {
        Setup(true, true, true); Frame(RasterHostBump);
        CheckHidden(); CHECK(VramIsStock());
    } else if (!strcmp(name, "nonzero-writes")) {
        Setup(true, true, true); Frame(RasterNonzero);
        CheckHidden(); CHECK(VramIsStock());
    } else if (!strcmp(name, "blank-writes")) {
        Setup(true, true, true); Frame(RasterBlank);
        CheckHidden(); CHECK(VramIsStock());
        for (unsigned i = 0; i < kHudWords; i++) CHECK(test_ppu.vram[kMapBase + i] == kBlankWord);
    } else if (!strcmp(name, "mixed-writes")) {
        Setup(true, true, true); Frame(RasterMixed);
        CheckHidden(); CHECK(VramIsStock());
        CHECK(test_ppu.vram[kMapBase + 33] == kBlankWord);
        CHECK(test_ppu.vram[kMapBase + fixed_pos[0]] == kBlankWord);
    } else if (!strcmp(name, "elsewhere")) {
        Setup(true, true, true); Frame(RasterElsewhere);
        CheckHidden(); CHECK(VramIsStock());
    } else if (!strcmp(name, "option-off")) {
        Setup(false, true, true); Frame(RasterBlank); CHECK(VramIsStock());
        Setup(false, true, true); uint32_t c0 = test_ppu.vramWriteCount;
        Frame(RasterNothing);
        CHECK(PictureIsStock()); CHECK(VramIsStock()); CHECK(test_ppu.vramWriteCount == c0);
    } else if (!strcmp(name, "lock-clear")) {
        Setup(true, false, true); uint32_t c0 = test_ppu.vramWriteCount;
        Frame(RasterNothing);
        CHECK(PictureIsStock()); CHECK(VramIsStock()); CHECK(test_ppu.vramWriteCount == c0);
        Setup(true, false, true); Frame(RasterBlank); CHECK(VramIsStock());
    } else if (!strcmp(name, "fixed-overwritten")) {
        /* A box drawn over one fixed tile: the frame is drawn untouched. */
        Setup(true, true, true);
        test_ppu.vram[kMapBase + fixed_pos[20]] = 0x2001; stock[kMapBase + fixed_pos[20]] = 0x2001;
        uint32_t c0 = test_ppu.vramWriteCount;
        Frame(RasterNothing);
        CHECK(PictureIsStock()); CHECK(VramIsStock()); CHECK(test_ppu.vramWriteCount == c0);
        Setup(true, true, true);
        test_ppu.vram[kMapBase + fixed_pos[0]] = kBlankWord; stock[kMapBase + fixed_pos[0]] = kBlankWord;
        Frame(RasterBlank); CHECK(VramIsStock());
    } else if (!strcmp(name, "not-mode1")) {
        Setup(true, true, true); test_ppu.bgmode = 7;
        Frame(RasterNothing); CHECK(PictureIsStock()); CHECK(VramIsStock());
    } else if (!strcmp(name, "ornament-fallback")) {
        Setup(true, true, false); Frame(RasterNothing);
        CheckHidden(); CHECK(VramIsStock());
        Setup(true, true, false); Frame(RasterBlank);
        CheckHidden(); CHECK(VramIsStock());
    } else if (!strcmp(name, "next-frames")) {
        /* Writes between frames are the game's own (no tracking leaks into
         * them), and a later frame blanks and restores again. */
        Setup(true, true, true); Frame(RasterBlank); CHECK(VramIsStock());
        for (unsigned n = 0; n < kFixed; n++) GuestWrite(kMapBase + fixed_pos[n], fixed_word[n], false);
        GuestWrite(kMapBase + kHudWords - 1, 0x3555, true);     /* a stat word, not a fixed tile */
        Frame(RasterNothing); CheckHidden(); CHECK(VramIsStock());
        Frame(RasterNonzero); CheckHidden(); CHECK(VramIsStock());
        /* That raster drew over fixed tile 7: the next frame shows it as is. */
        Frame(RasterNothing); CHECK(PictureIsStock()); CHECK(VramIsStock());
        GuestWrite(kMapBase + fixed_pos[7], fixed_word[7], false);
        Frame(RasterNothing); CheckHidden(); CHECK(VramIsStock());
        CHECK(test_hook == NULL);
    } else if (!strcmp(name, "begin-twice")) {
        /* A second BeginDraw without EndDraw must not save the blank rows
         * as the HUD (that would lose the HUD art from VRAM for good). */
        Setup(true, true, true);
        IogMinimalHudBeginDraw(); IogMinimalHudBeginDraw();
        memcpy(picture, &test_ppu.vram[kMapBase], sizeof picture);
        IogMinimalHudEndDraw();
        CheckHidden(); CHECK(VramIsStock()); CHECK(test_hook == NULL);
    } else {
        fprintf(stderr, "unknown case %s\n", name);
        return 2;
    }
    printf("%s %s %u assertions\n", failures ? "FAIL" : "PASS", name, assertions);
    return failures ? 1 : 0;
}

int main(int argc, char **argv)
{
    if (argc != 2) { fprintf(stderr, "usage: %s case\n", argv[0]); return 2; }
    return RunCase(argv[1]);
}
