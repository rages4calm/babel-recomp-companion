"""Production pure code preview; mapper is a counted, stable-ROM dependency.

This verifies refusal ordering and absence of architectural bus effects. It
does not substitute for mapper or real-game qualification.
"""
import os
from pathlib import Path
import shutil
import subprocess

import pytest

from test_region_pacing import _c_function


def test_plain_code_preview_is_pure_and_observes_patch_restore(tmp_path):
    root = Path(__file__).resolve().parents[2]
    cc = os.environ.get("CC") or shutil.which("clang") or shutil.which("cc")
    if not cc:
        pytest.skip("C compiler required")
    helper = _c_function((root / "runner/src/cpu_state.c").read_text(), "cpu_preview_code16")
    source = r'''
#include "cpu_state.h"
#include "snes/snes.h"
#include "snes/cart.h"
#include <assert.h>
#include <string.h>
Snes *g_snes;
static unsigned mapped;
static uint8 bytes[65536];
uint8 *cart_getRomPtr(Cart *cart, uint8 bank, uint16 addr) {
  (void)cart; (void)bank; mapped++; return &bytes[addr];
}
HELPER
int main(void) {
  CpuState cpu={0}, before; Cart cart={0}, cart_before; Snes snes={0}, snes_before;
  cart.type=CART_HIROM;cart.rom=bytes;cart.romSize=sizeof bytes;snes.cart=&cart;g_snes=&snes;
  cpu.open_bus=0xA5;cpu.master_cycles=1234;cpu.cycles=789;
  before=cpu;cart_before=cart;snes_before=snes;
  const uint8 banks[]={3,0x43,0x83,0xC3}; uint16 value;
  for(unsigned i=0;i<4;i++)for(unsigned phase=0;phase<3;phase++) {
    bytes[0x8101]=phase==1?0x00:0x8A;bytes[0x8102]=phase==1?0x1E:0x06;
    mapped=0;value=0xDEAD;
    assert(cpu_preview_code16(&cpu,banks[i],0x8101,&value));
    assert(value==(phase==1?0x1E00:0x068A));assert(mapped==2);
    assert(!memcmp(&cpu,&before,sizeof cpu));assert(!memcmp(&cart,&cart_before,sizeof cart));
    assert(!memcmp(&snes,&snes_before,sizeof snes));
  }
  for(unsigned mode=0;mode<10;mode++) {
    cart=cart_before;snes=snes_before;g_snes=&snes;
    uint8 bank=3;uint16 addr=0x8101;const CpuState *cp=&cpu;uint16 *out=&value;
    switch(mode) {
      case 0:cp=0;break;case 1:out=0;break;case 2:g_snes=0;break;
      case 3:cart.rom=0;break;case 4:cart.romSize=0;break;
      case 5:cart.type=CART_SA1;break;case 6:addr=0x7FFF;break;
      case 7:addr=0xFFFF;break;case 8:bank=0x7E;break;
      case 9:bank=0xA0;cart.overlayBank[0]=(void*)bytes;break;
    }
    mapped=0;value=0xDEAD;Cart cb=cart;Snes sb=snes;
    assert(!cpu_preview_code16(cp,bank,addr,out));assert(value==0xDEAD);assert(!mapped);
    assert(!memcmp(&cpu,&before,sizeof cpu));assert(!memcmp(&cart,&cb,sizeof cart));
    assert(!memcmp(&snes,&sb,sizeof snes));
  }
  return 0;
}
'''.replace("HELPER", helper)
    path = tmp_path / "preview.c"
    path.write_text(source)
    exe = tmp_path / ("preview.exe" if os.name == "nt" else "preview")
    result = subprocess.run([cc, "-std=c11", "-O1", "-I", str(root / "runner/src"),
                             str(path), "-o", str(exe)], capture_output=True, text=True, timeout=60)
    assert result.returncode == 0, result.stderr
    executed = subprocess.run([str(exe)], capture_output=True, text=True, timeout=20)
    assert executed.returncode == 0, executed.stdout + executed.stderr
