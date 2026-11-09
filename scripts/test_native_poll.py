"""ROM-free production callback and title admission tests; no game fixture."""
import hashlib
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = r'''
#include "iog_native_poll.h"
#include "snes/interp_bridge.h"
#include "snes/cart.h"
#include <assert.h>
#include <stdlib.h>
#include <string.h>
static Snes snes;
Snes *g_snes = &snes;
static const char *setting;
static unsigned registrations, clears, fail_registration;
static uint32_t entries[4];
char *getenv(const char *name) {
  return strcmp(name,"IOG_NATIVE_RDNMI_POLL")==0 ? (char *)setting : NULL;
}
void interp_bridge_clear_native_rdnmi_polls(void) { registrations=0; ++clears; }
bool interp_bridge_add_native_rdnmi_poll(uint32_t pc, InterpNativePollStep step) {
  assert(step==IogNativePollStep);
  if(fail_registration && registrations+1==fail_registration)return false;
  assert(registrations<4);entries[registrations++]=pc;return true;
}
static uint32_t reads[8];static unsigned nr;static uint8_t answer;
static uint8_t bus(void *mem,uint32_t addr) {
  assert(mem==reads && nr<8);reads[nr++]=addr;
  return addr==0x804210 ? answer : 0xEA;
}
static void effects(void) {
  const uint8_t banks[]={2,0x42,0x82,0xC2}, values[]={0,0x80,0x42};
  for(unsigned b=0;b<4;b++)for(unsigned v=0;v<3;v++) {
    Interp816 in={0};in.mem=reads;in.read=bus;in.k=banks[b];in.pc=0x804D;
    in.a=0xAAFF;in.x=0x1234;in.y=0x5678;in.sp=0x01F4;in.dp=0x102;
    in.db=0x7F;in.mf=true;in.c=in.d=in.v=in.i=true;
    Interp816 expected=in;answer=values[v];nr=0;
    assert(IogNativePollStep(&in)==5);
    expected.a=0xAA00|answer;expected.pc=0x8051;expected.cyclesUsed=5;
    expected.n=(answer&0x80)!=0;expected.z=answer==0;
    assert(!memcmp(&in,&expected,sizeof in));assert(nr==5);
    for(unsigned i=0;i<4;i++)assert(reads[i]==((uint32_t)banks[b]<<16|0x804D+i));
    assert(reads[4]==0x804210);nr=0;
    assert(IogNativePollStep(&in)==(expected.n?2:3));
    expected.pc=expected.n?0x8053:0x804D;expected.cyclesUsed=expected.n?2:3;
    assert(!memcmp(&in,&expected,sizeof in));assert(nr==2);
    assert(reads[0]==((uint32_t)banks[b]<<16|0x8051));
    assert(reads[1]==((uint32_t)banks[b]<<16|0x8052));
  }
  for(unsigned bad=0;bad<5;bad++) {
    Interp816 in={0};in.mem=reads;in.read=bus;in.k=0x82;in.pc=0x804D;in.mf=true;
    if(bad==0)in.read=NULL;if(bad==1)in.e=true;if(bad==2)in.mf=false;
    if(bad==3)in.k=0x83;if(bad==4)in.pc=0x8053;
    Interp816 before=in;nr=0;assert(!IogNativePollStep(&in));
    assert(!nr && !memcmp(&in,&before,sizeof in));
  }
  assert(!IogNativePollStep(NULL));
}
int main(void) {
  effects();Cart cart={0};snes.cart=&cart;
  cart.type=CART_HIROM;cart.romSize=cart.romImageSize=2097152;
  cart.rom=calloc(1,cart.romSize);assert(cart.rom);
  const char *settings[]={NULL,"","0","true","01"};
  for(unsigned i=0;i<5;i++){setting=settings[i];IogNativePollInitialize();assert(!registrations);}
  setting="1";IogNativePollInitialize();
#ifdef SNESRECOMP_INTERPRETER_ONLY
  assert(!registrations);
#else
  assert(registrations==4);
  assert(entries[0]==0x02804D && entries[1]==0x42804D && entries[2]==0x82804D && entries[3]==0xC2804D);
  for(unsigned bad=0;bad<5;bad++) {
    cart.type=CART_HIROM;cart.romImageSize=cart.romSize=2097152;snes.cart=&cart;g_snes=&snes;
    if(bad==0)cart.type=CART_LOROM;if(bad==1)cart.romImageSize--;
    if(bad==2)cart.romSize--;if(bad==3)cart.rom[0]=1;if(bad==4)g_snes=NULL;
    IogNativePollInitialize();assert(!registrations);cart.rom[0]=0;
  }
  g_snes=&snes;cart.type=CART_HIROM;cart.romImageSize=cart.romSize=2097152;
  for(unsigned i=1;i<=4;i++){fail_registration=i;IogNativePollInitialize();assert(!registrations);}
#endif
  assert(clears>=6);free(cart.rom);return 0;
}
'''


class NativePollTests(unittest.TestCase):
    def test_production_effects_and_explicit_stock_admission(self):
        cc = shutil.which("clang") or shutil.which("cc")
        if not cc:
            self.skipTest("C11 compiler required")
        with tempfile.TemporaryDirectory(prefix="gaia-native-poll-") as folder:
            work = Path(folder)
            # Synthetic all-zero image, with its own generated identity header.
            digest = hashlib.sha256(bytes(2097152)).hexdigest()
            (work / "snesrecomp_rom_identity.h").write_text(
                '#define SNESRECOMP_ROM_EXPECTED_SHA256 "' + digest + '"\n', encoding="utf-8")
            source = work / "fixture.c"
            source.write_text(FIXTURE, encoding="utf-8")
            for interpreter_only in (False, True):
                with self.subTest(interpreter_only=interpreter_only):
                    exe = work / ("default.exe" if interpreter_only else "native.exe")
                    command = [cc, "-std=c11", "-O1", "-I", str(work), "-I", str(ROOT / "src"),
                               "-I", str(ROOT / "snesrecomp/runner/src"),
                               str(source), str(ROOT / "src/iog_native_poll.c"),
                               str(ROOT / "snesrecomp/runner/src/sha256.c"), "-o", str(exe)]
                    if interpreter_only:
                        command.insert(1, "-DSNESRECOMP_INTERPRETER_ONLY=1")
                    compiled = subprocess.run(command, capture_output=True, text=True, timeout=60)
                    self.assertEqual(compiled.returncode, 0, compiled.stderr)
                    result = subprocess.run([str(exe)], capture_output=True, text=True, timeout=15)
                    self.assertEqual(result.returncode, 0, result.stdout + result.stderr)


if __name__ == "__main__":
    unittest.main()
