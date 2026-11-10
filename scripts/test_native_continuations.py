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
static const char *setting,*nmi_setting;
static unsigned active,calls,clears;
static unsigned nmi_available=1;
static bool reject;
char *getenv(const char *name) {return !strcmp(name,"IOG_NATIVE_CONTINUATIONS")?(char*)setting:!strcmp(name,"IOG_NATIVE_NMI_CONTINUATIONS")?(char*)nmi_setting:NULL;}
void interp_bridge_clear_native_instructions(void) {active=0;clears++;}
bool IogRegisterNativeContinuations(void) {calls++;active=1;return !reject;}
size_t interp_bridge_native_instruction_stats(InterpNativeInstructionStats *out,size_t capacity) {(void)out;(void)capacity;return 0;}
uint64_t interp_bridge_native_continuation_insns_total(void) {return 0;}
uint64_t interp_bridge_native_continuation_cycles_total(void) {return 0;}
bool interp_bridge_native_instruction_index_enabled(void) {return true;}
size_t interp_bridge_native_nmi_grants(void) {return active?nmi_available:0;}
int main(void) {
 Cart cart={0};snes.cart=&cart;cart.type=CART_HIROM;
 cart.romSize=cart.romImageSize=2097152;cart.rom=calloc(1,2097152);assert(cart.rom);
 const char *values[]={NULL,"","0","true","01"};
 for(unsigned i=0;i<5;i++){setting=values[i];nmi_setting="1";IogNativeContinuationsInitialize();assert(!active&&!calls&&!IogNativeContinuationsNmiEnabled());}
 nmi_setting=NULL;
 setting="1";IogNativeContinuationsInitialize();
#if defined(IOG_HAS_NATIVE_CONTINUATIONS) && !defined(SNESRECOMP_INTERPRETER_ONLY)
 assert(active==1&&calls==1&&!IogNativeContinuationsNmiEnabled());reject=true;IogNativeContinuationsInitialize();assert(!active&&calls==2&&!IogNativeContinuationsNmiEnabled());reject=false;
 for(unsigned bad=0;bad<6;bad++){
  cart.type=CART_HIROM;cart.romSize=cart.romImageSize=2097152;snes.cart=&cart;g_snes=&snes;
  if(bad==0)cart.type=CART_LOROM;if(bad==1)cart.romImageSize--;if(bad==2)cart.romSize--;
  if(bad==3)cart.rom[0]=1;if(bad==4)snes.cart=NULL;if(bad==5)g_snes=NULL;
  IogNativeContinuationsInitialize();assert(!active&&calls==2&&!IogNativeContinuationsNmiEnabled());cart.rom[0]=0;
 }
 cart.type=CART_HIROM;cart.romSize=cart.romImageSize=2097152;snes.cart=&cart;g_snes=&snes;
 for(unsigned i=0;i<5;i++){nmi_setting=values[i];IogNativeContinuationsInitialize();assert(active&&!IogNativeContinuationsNmiEnabled());}
 nmi_setting="1";IogNativeContinuationsInitialize();assert(active&&IogNativeContinuationsNmiEnabled());
 nmi_available=0;IogNativeContinuationsInitialize();assert(active&&!IogNativeContinuationsNmiEnabled());
 nmi_available=1;reject=true;IogNativeContinuationsInitialize();assert(!active&&!IogNativeContinuationsNmiEnabled());
 reject=false;setting="0";IogNativeContinuationsInitialize();assert(!active&&!IogNativeContinuationsNmiEnabled());
#else
 assert(!active&&!calls&&!IogNativeContinuationsNmiEnabled());
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
