/* ROM-free fixture for the ACTUAL iog_ngplus implementation (New Game+):
 * continuing a finished file and answering the host prompt. Host services
 * are stubs; the prompt answers at once with the configured reply. */
#include <stdlib.h>
#include "../src/iog_ngplus.c"

static uint8_t test_ram[0x20000], test_sram[0x2000], test_rom[0x200000];
static Cart test_cart = {test_rom, sizeof test_rom, test_sram, sizeof test_sram};
static Snes test_snes = {test_ram, &test_cart, 0};
Snes *g_snes = &test_snes;
static unsigned assertions, prompts, resets;
static int answer = 1;
static SNESModActivationCallback plugin;
static SNESModFrameCallback frame;
#define CHECK(v) do {assertions++;if(!(v)){fprintf(stderr,"FAIL %s:%d: %s\n",__FILE__,__LINE__,#v);exit(1);}}while(0)

bool IogRandomizerActive(void) { return false; }
const char *IogI18nLanguage(void) { return "en"; }
void SnesRa_SetBlocked(const char *why) { (void)why; }
void snes_host_request_prompt(const char *q, const char *y, const char *n, void (*done)(int))
{ (void)q; (void)y; (void)n; prompts++; done(answer); }
void snes_host_request_reset(void) { resets++; }
int snes_mod_register_activation_plugin(const char *id, SNESModActivationCallback fn)
{ CHECK(!strcmp(id, "iog.ngplus")); plugin = fn; return 1; }
int snes_mod_register_frame_callback(SNESModFrameCallback fn) { frame = fn; return 1; }

/* A finished file being continued from the file select: scene $FA with the
 * saved map queued in $0642, the file's block already in RAM. */
static void finished_file(void)
{
    memset(test_ram, 0, sizeof test_ram);
    Wr(0x0644, 0x00FA); Wr(0x0642, 0x0034);
    test_ram[0x0B54] = 0x80;                      /* finished, first playthrough */
    test_ram[0x0AB0] = 0x18;                      /* Gem Man tally, BCD */
    for (int i = 0; i < 16; i++) test_ram[0x0AB4 + i] = (uint8_t)(i + 1);
    test_ram[0x0B55] = 4; test_ram[0x0B56] = 0x22; test_ram[0x0B57] = 1;   /* stacked herbs, jewels, crystals */
    memset(&test_ram[0x0A00], 0xFF, 0x60);
    Wr(0x0AB2, 0x0003); Wr(0x0AD4, 1);
}

int main(int argc, char **argv)
{
    CHECK(argc == 2 && !strcmp(argv[1], "ngplus"));
    register_iog_ngplus(); CHECK(plugin != NULL); plugin(); CHECK(frame != NULL);
    /* Yes: New Game+ from the school; the stacked extras go with the rest
     * of the inventory (they used to come back out of the empty inventory),
     * the tally stays. */
    finished_file(); answer = 1; frame();
    CHECK(prompts == 1);
    CHECK(test_ram[0x0B55] == 0 && test_ram[0x0B56] == 0 && test_ram[0x0B57] == 0);
    for (int i = 0; i < 16; i++) CHECK(test_ram[0x0AB4 + i] == 0);
    CHECK(test_ram[0x0AB0] == 0x18);
    CHECK(test_ram[0x0B54] == 0x01);
    CHECK(Rd(0x0642) == 0x0008 && Rd(0x064C) == 0x0050 && Rd(0x064E) == 0x00A0);
    CHECK(Rd(0x0AC4) == 0xFFFF && Rd(0x0AD4) == 0 && Rd(0x0AAC) == 3);
    for (int i = 0; i < 0x60; i++) CHECK(test_ram[0x0A00 + i] == 0);
    frame(); CHECK(prompts == 1);                 /* asked once per file select */
    /* No: the file continues exactly as saved, extras included. */
    Wr(0x0644, 0x0001); frame();
    finished_file(); answer = 0; frame();
    CHECK(prompts == 2);
    CHECK(test_ram[0x0B55] == 4 && test_ram[0x0B56] == 0x22 && test_ram[0x0B57] == 1);
    CHECK(test_ram[0x0B54] == 0x80 && Rd(0x0642) == 0x0034 && test_ram[0x0AB4] == 1);
    /* A file that is not finished: no question, nothing changes. */
    Wr(0x0644, 0x0001); frame();
    finished_file(); test_ram[0x0B54] = 0; frame();
    CHECK(prompts == 2 && test_ram[0x0B56] == 0x22);
    (void)resets;
    printf("PASS %u actual iog_ngplus callback integration assertions: ngplus; ROM-free host stubs\n", assertions);
    return 0;
}
