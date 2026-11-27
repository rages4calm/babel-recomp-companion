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
#include "snes/cart.h"
#include <stdlib.h>
#include <string.h>
#include <assert.h>
static Snes snes;
Snes *g_snes=&snes;
static const char *setting,*nmi_setting,*frame_setting;
static unsigned active,calls,clears;
static unsigned nmi_available=1;
static int frame_effects=2; /* 2 = never set by production code */
static bool reject;
char *getenv(const char *name) {return !strcmp(name,"IOG_NATIVE_CONTINUATIONS")?(char*)setting:!strcmp(name,"IOG_NATIVE_NMI_CONTINUATIONS")?(char*)nmi_setting:!strcmp(name,"IOG_NATIVE_FRAME_CONTINUATIONS")?(char*)frame_setting:NULL;}
void interp_bridge_clear_native_instructions(void) {active=0;clears++;}
bool IogRegisterNativeContinuations(void) {calls++;active=1;return !reject;}
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
#else
 /* Interpreter-only / no generated continuations: nothing turns them on. */
 for(unsigned i=0;i<5;i++){setting=values[i];nmi_setting=frame_setting="1";INIT();assert(!active&&!calls&&!NMI()&&frame_effects==2);}
 setting="0";INIT();assert(!active&&!calls&&!NMI()&&frame_effects==2);
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
            for flags in ([], ["-DIOG_HAS_NATIVE_CONTINUATIONS=1"],
                          ["-DIOG_HAS_NATIVE_CONTINUATIONS=1", "-DSNESRECOMP_INTERPRETER_ONLY=1"]):
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
