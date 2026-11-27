"""Production continuation setup stays private, explicit and stock-bound."""
import hashlib
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = r'''
#include "iog_native_continuations.h"
#include "snes/interp_bridge.h"
#include "snes/interp_native_wram.h"
#include "snes/cart.h"
#include <stdlib.h>
#include <string.h>
#include <assert.h>
static Snes snes;
Snes *g_snes=&snes;
static const char *setting,*nmi_setting,*frame_setting,*wram_setting;
static unsigned active,calls,clears;
static unsigned nmi_available=1;
static int frame_effects=2; /* 2 = never set by production code */
static bool reject;
/* WRAM-copy path: registration count, its result, and the bridge's launch
 * enable. As in interp_bridge.c, clearing registrations clears the enable. */
static unsigned wram_calls,wram_sets,wram_registered;
static bool wram_reject,wram_enabled;
char *getenv(const char *name) {return !strcmp(name,"IOG_NATIVE_CONTINUATIONS")?(char*)setting:!strcmp(name,"IOG_NATIVE_NMI_CONTINUATIONS")?(char*)nmi_setting:!strcmp(name,"IOG_NATIVE_FRAME_CONTINUATIONS")?(char*)frame_setting:!strcmp(name,"IOG_NATIVE_WRAM_COPY_CONTINUATIONS")?(char*)wram_setting:NULL;}
void interp_bridge_clear_native_instructions(void) {active=0;clears++;wram_registered=0;wram_enabled=false;}
bool IogRegisterNativeContinuations(void) {calls++;active=1;return !reject;}
bool IogRegisterNativeWramCopyContinuations(void) {wram_calls++;wram_registered=1;return !wram_reject;}
void interp_bridge_set_native_wram_copy_enabled(bool enabled) {wram_sets++;wram_enabled=enabled;}
size_t interp_bridge_native_instruction_stats(InterpNativeInstructionStats *out,size_t capacity) {(void)out;(void)capacity;return 0;}
uint64_t interp_bridge_native_continuation_insns_total(void) {return 0;}
uint64_t interp_bridge_native_continuation_cycles_total(void) {return 0;}
uint64_t interp_bridge_native_wram_copy_insns_total(void) {return 0;}
uint64_t interp_bridge_native_wram_copy_cycles_total(void) {return 0;}
void interp_bridge_set_native_frame_effects_enabled(bool enabled) {frame_effects=enabled;}
bool interp_bridge_native_instruction_index_enabled(void) {return true;}
size_t interp_bridge_native_nmi_grants(void) {return active?nmi_available:0;}
#define INIT() IogNativeContinuationsInitialize()
#define NMI() IogNativeContinuationsNmiEnabled()
int main(void) {
 Cart cart={0};snes.cart=&cart;cart.type=CART_HIROM;
 cart.romSize=cart.romImageSize=2097152;cart.rom=calloc(1,2097152);assert(cart.rom);
 /* Since 3ebc857 every native path is on in a build that has it; only an
  * exact "0" turns one off (unset, empty and other spellings leave it on). */
 const char *values[]={NULL,"","1","true","01"};
#if defined(IOG_HAS_NATIVE_CONTINUATIONS) && !defined(SNESRECOMP_INTERPRETER_ONLY)
 unsigned expected=0;
 setting="0";nmi_setting="1";frame_setting="1";INIT();assert(!active&&!calls&&!NMI()&&frame_effects==2);
 nmi_setting=frame_setting=NULL;
 for(unsigned i=0;i<5;i++){setting=values[i];INIT();expected++;assert(active==1&&calls==expected&&NMI()&&frame_effects==1);}
 setting="1";
 frame_setting="0";INIT();expected++;assert(active&&calls==expected&&NMI()&&frame_effects==0);frame_setting=NULL;
 reject=true;frame_effects=2;INIT();expected++;assert(!active&&calls==expected&&!NMI()&&frame_effects==2);reject=false;
 for(unsigned bad=0;bad<6;bad++){
  cart.type=CART_HIROM;cart.romSize=cart.romImageSize=2097152;snes.cart=&cart;g_snes=&snes;
  if(bad==0)cart.type=CART_LOROM;if(bad==1)cart.romImageSize--;if(bad==2)cart.romSize--;
  if(bad==3)cart.rom[0]=1;if(bad==4)snes.cart=NULL;if(bad==5)g_snes=NULL;
  INIT();assert(!active&&calls==expected&&!NMI()&&frame_effects==2);cart.rom[0]=0;
 }
 cart.type=CART_HIROM;cart.romSize=cart.romImageSize=2097152;snes.cart=&cart;g_snes=&snes;
 for(unsigned i=0;i<5;i++){nmi_setting=values[i];INIT();assert(active&&NMI());}
 nmi_setting="0";INIT();assert(active&&!NMI());nmi_setting=NULL;
 nmi_available=0;INIT();assert(active&&!NMI());
 nmi_available=1;reject=true;INIT();assert(!active&&!NMI());
 reject=false;setting="0";INIT();assert(!active&&!NMI());
#ifdef IOG_HAS_NATIVE_WRAM_CONTINUATIONS
 {
  /* WRAM copies register after the ordinary continuations and are on by
   * default: unset, empty and any spelling but exactly "0" enable them. */
  const char *wram_on[]={NULL,"","1","true","01","00"," 0","0 ","false","off"};
  setting=nmi_setting=frame_setting=NULL;
  unsigned base=calls,wc=wram_calls,ws=wram_sets;
  for(unsigned i=0;i<10;i++){
   wram_setting=wram_on[i];frame_effects=2;INIT();base++;wc++;ws++;
   assert(active&&calls==base&&wram_calls==wc&&wram_registered&&wram_sets==ws&&wram_enabled);
   assert(NMI()&&frame_effects==1);
  }
  /* Exactly "0" turns only the WRAM path off; registration still happened
   * and the other native paths stay on. */
  wram_setting="0";frame_effects=2;INIT();base++;wc++;ws++;
  assert(active&&calls==base&&wram_calls==wc&&wram_registered&&wram_sets==ws&&!wram_enabled);
  assert(NMI()&&frame_effects==1);
  /* Reinitialization: off -> on -> off follows the setting each time. */
  wram_setting=NULL;INIT();base++;wc++;ws++;assert(wram_calls==wc&&wram_sets==ws&&wram_enabled);
  wram_setting="0";INIT();base++;wc++;ws++;assert(wram_calls==wc&&wram_sets==ws&&!wram_enabled);
  wram_setting=NULL;INIT();base++;wc++;ws++;assert(wram_calls==wc&&wram_sets==ws&&wram_enabled);
  /* WRAM registration failure clears every registration (including the
   * ordinary ones) and leaves nothing native on: no WRAM enable, no frame
   * effects, no NMI. */
  unsigned cl=clears;wram_reject=true;frame_effects=2;INIT();base++;wc++;
  assert(!active&&!wram_registered&&calls==base&&wram_calls==wc&&wram_sets==ws&&!wram_enabled);
  assert(!NMI()&&frame_effects==2&&clears==cl+2);
  /* The failure is not sticky: the next initialization enables again. */
  wram_reject=false;INIT();base++;wc++;ws++;
  assert(active&&wram_registered&&wram_calls==wc&&wram_sets==ws&&wram_enabled&&NMI());
  /* A failed ordinary registration never reaches the WRAM registration, and
   * the reinitialization clears the earlier WRAM enable. */
  reject=true;INIT();base++;
  assert(!active&&calls==base&&wram_calls==wc&&wram_sets==ws&&!wram_enabled&&!wram_registered);
  reject=false;INIT();base++;wc++;ws++;assert(wram_enabled);
  /* IOG_NATIVE_CONTINUATIONS=0 and a wrong cart skip WRAM too, and clear an
   * enable left by the previous initialization. */
  setting="0";INIT();assert(calls==base&&wram_calls==wc&&wram_sets==ws&&!wram_enabled&&!wram_registered);
  setting=NULL;INIT();base++;wc++;ws++;assert(wram_enabled);
  cart.rom[0]=1;INIT();cart.rom[0]=0;
  assert(calls==base&&wram_calls==wc&&wram_sets==ws&&!wram_enabled&&!wram_registered);
  /* Exactly "0" on the WRAM switch does not disable registration as a whole. */
  wram_setting="0";INIT();base++;wc++;ws++;assert(active&&wram_registered&&!wram_enabled);
  wram_setting=NULL;
 }
#else
 /* A native build without the WRAM module never touches the WRAM path. */
 assert(!wram_calls&&!wram_sets&&!wram_enabled);
#endif
#else
 /* Interpreter-only / no generated continuations: nothing turns them on. */
 for(unsigned i=0;i<5;i++){setting=values[i];nmi_setting=frame_setting="1";INIT();assert(!active&&!calls&&!NMI()&&frame_effects==2);}
 setting="0";INIT();assert(!active&&!calls&&!NMI()&&frame_effects==2);
 /* ...including the WRAM-copy path, whatever IOG_NATIVE_WRAM_COPY_CONTINUATIONS says. */
 const char *wram_any[]={NULL,"","1","true","0"};
 for(unsigned i=0;i<5;i++){setting=NULL;wram_setting=wram_any[i];INIT();assert(!wram_calls&&!wram_sets&&!wram_enabled&&!wram_registered);}
#endif
 assert(clears>=6);free(cart.rom);return 0;
}
'''


class ContinuationSetupTests(unittest.TestCase):
    def test_real_setup_explicit_identity_and_default_fallback(self):
        cc = shutil.which("clang") or shutil.which("cc")
        if not cc:
            self.skipTest("C11 compiler required")
        with tempfile.TemporaryDirectory(prefix="gaia-continuation-") as folder:
            out = Path(folder)
            (out / "snesrecomp_rom_identity.h").write_text(
                '#define SNESRECOMP_ROM_EXPECTED_SHA256 "' + hashlib.sha256(bytes(2097152)).hexdigest() + '"\n')
            (out / "fixture.c").write_text(FIXTURE)
            wram = "-DIOG_HAS_NATIVE_WRAM_CONTINUATIONS=1"
            for flags in ([], ["-DIOG_HAS_NATIVE_CONTINUATIONS=1"],
                          ["-DIOG_HAS_NATIVE_CONTINUATIONS=1", "-DSNESRECOMP_INTERPRETER_ONLY=1"],
                          ["-DIOG_HAS_NATIVE_CONTINUATIONS=1", wram],
                          ["-DIOG_HAS_NATIVE_CONTINUATIONS=1", wram, "-DSNESRECOMP_INTERPRETER_ONLY=1"],
                          [wram]):
                with self.subTest(flags=flags):
                    exe = out / "fixture.exe"
                    cmd = [cc, "-std=c11", "-O1", *flags, "-I", str(out), "-I", str(ROOT / "src"),
                           "-I", str(ROOT / "snesrecomp/runner/src"), str(out / "fixture.c"),
                           str(ROOT / "src/iog_native_continuations.c"),
                           str(ROOT / "snesrecomp/runner/src/sha256.c"), "-o", str(exe)]
                    built = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
                    self.assertEqual(built.returncode, 0, built.stderr)
                    ran = subprocess.run([str(exe)], capture_output=True, text=True, timeout=15)
                    self.assertEqual(ran.returncode, 0, ran.stderr)


if __name__ == "__main__":
    unittest.main()
