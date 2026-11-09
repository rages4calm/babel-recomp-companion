"""Executed transactional/index tests over the actual bridge implementation."""
import hashlib
import json
import os
import shutil
import subprocess

import pytest
from test_native_continuation import _source as protocol_source
from test_region_poll_fallback import REPO

ALLOCATOR = r'''
/* Instrument allocations only inside the real bridge translation unit. */
typedef struct Allocation {void *p;size_t bytes;} Allocation;
static Allocation allocations[256];static unsigned alloc_calls,fail_at,live_allocations;
static size_t live_bytes,peak_bytes;
static const char *index_setting_override;
static char *index_getenv(const char *name){
  if(index_setting_override&&!strcmp(name,"SNESRECOMP_NATIVE_INSTRUCTION_INDEX"))return(char*)index_setting_override;
  return getenv(name);
}
static void *index_calloc(size_t n,size_t size){
  ++alloc_calls;if(fail_at&&alloc_calls==fail_at)return NULL;
  void *p=calloc(n,size);if(!p)return NULL;
  for(unsigned i=0;i<256;i++)if(!allocations[i].p){allocations[i].p=p;allocations[i].bytes=n*size;
    ++live_allocations;live_bytes+=n*size;if(live_bytes>peak_bytes)peak_bytes=live_bytes;return p;}
  free(p);return NULL;
}
static void index_free(void *p){
  if(!p)return;
  for(unsigned i=0;i<256;i++)if(allocations[i].p==p){live_bytes-=allocations[i].bytes;--live_allocations;allocations[i].p=NULL;break;}
  free(p);
}
#define calloc index_calloc
#define free index_free
#define getenv index_getenv
#include "snes/interp_bridge.c"
#undef calloc
#undef free
#undef getenv
'''

MAIN = r'''
static int real_native_nop(Interp816 *in){
  (void)in->read(in->mem,((uint32)in->k<<16)|in->pc++);return in->cyclesUsed=2;
}
static InterpNativeInstruction nop_descriptor(uint32 pc){
  InterpNativeInstruction d={0};d.pc24=pc;d.m=1;d.length=1;d.bytes[0]=0xea;d.step=real_native_nop;return d;
}
static NativeInstructionEntry *lookup(uint32 pc,int m,int x,int e){
  Interp816 in={0};in.k=pc>>16;in.pc=(uint16)pc;in.mf=m;in.xf=x;in.e=e;
  s_lle_sched_depth=1;
  NativeInstructionEntry *result=bridge_native_instruction_step(&in,pc,1,0);
  s_lle_sched_depth=0;return result;
}
int main(void){
  RAM=malloc(MEMSZ);if(!RAM)return 2;memset(RAM,0,MEMSZ);init_cpu();
  memset(&g_test_snes,0,sizeof g_test_snes);memset(&g_test_cart,0,sizeof g_test_cart);
  static Dma dma;memset(&dma,0,sizeof dma);g_test_snes.dma=&dma;g_test_snes.hdmaBeamOff=true;
  g_test_snes.ram=RAM;g_test_snes.cart=&g_test_cart;g_test_cart.type=CART_HIROM;g_test_cart.rom=RAM;g_test_cart.romSize=MEMSZ;
  snes_set_rdnmi_beam_enabled(false);snes_set_raster_irq_beam_enabled(true);
  g_c.emulation=0;g_c.m_flag=1;g_c.x_flag=0;g_c._flag_I=1;cpu_mirrors_to_p(&g_c);
  interp_bridge_set_interpret_all(0);interp_bridge_set_pre_opcode_hook(0,NULL);interp_bridge_clear_native_rdnmi_polls();
  const uint8 owner[]={0x22,0x00,0x81,0x82,0x80,0xfe},body[]={0xea,0x6b};
  load(0x838000,owner,sizeof owner);load(0x828100,body,sizeof body);RAM[0x8280ff]=0xea;
  InterpNativeInstruction d=nop_descriptor(0x828100),early=nop_descriptor(0x8280ff);
  /* Each failure point on an empty table must leave even the lazy launch
   * setting unmodified. There must be no leaked partial index allocation. */
  for(unsigned failure=1;failure<=3;failure++){
    alloc_calls=0;fail_at=failure;
    CHECK(!interp_bridge_add_native_instructions(&d,1),"empty registry allocation failure");
    CHECK(!s_native_instruction_count&&!s_native_instructions&&!s_native_page_ids&&!s_native_page_slots,"empty failure keeps all structures empty");
    CHECK(s_native_instruction_index==-1,"failed setup does not latch mode");
    CHECK(!live_allocations&&!live_bytes,"empty failure frees all partial allocations");
  }
  fail_at=0;alloc_calls=0;
  CHECK(interp_bridge_add_native_instructions(&d,1),"actual registry and both indexes constructed");
  const char *setting=getenv("SNESRECOMP_NATIVE_INSTRUCTION_INDEX");int mode=!(setting&&!strcmp(setting,"0"));
  CHECK(interp_bridge_native_instruction_index_enabled()==mode,"launch setting selected exactly");
  index_setting_override=mode?"0":"1";
  CHECK(interp_bridge_native_instruction_index_enabled()==mode,"later environment changes cannot switch launch mode");
  CHECK(live_allocations==3,"three owned registry/index allocations");
  interp_bridge_set_master_deadline(1000);
  CHECK(interp_bridge_run_until_quiescent(&g_c,0x838000)==1,"real owning bridge executes indexed native NOP");
  interp_bridge_set_master_deadline(0);
  CHECK(!g_recomp_stack_top&&!g_pop_underflow,"real owner stack balanced");
  CHECK(interp_bridge_native_continuation_insns_total()==1&&interp_bridge_native_continuation_cycles_total()==2,"real native attribution");
  InterpNativeInstructionStats saved={0};CHECK(interp_bridge_native_instruction_stats(&saved,1)==1&&saved.insns==1&&saved.cycles==2,"real per-PC stats populated");
  NativeInstructionEntry *old=s_native_instructions;uint16_t *ids=s_native_page_ids,*slots=s_native_page_slots;
  size_t bytes=live_bytes;
  for(unsigned failure=1;failure<=3;failure++){
    alloc_calls=0;fail_at=failure;
    CHECK(!interp_bridge_add_native_instructions(&early,1),"nonempty atomic allocation refusal");
    CHECK(s_native_instructions==old&&s_native_page_ids==ids&&s_native_page_slots==slots&&s_native_instruction_count==1,"all old structures retained atomically");
    CHECK(live_bytes==bytes&&live_allocations==3,"nonempty failure no allocation leak");
    CHECK(s_native_instruction_index==mode,"nonempty failure preserves launch mode");
    InterpNativeInstructionStats now={0};CHECK(interp_bridge_native_instruction_stats(&now,1)==1&&now.insns==saved.insns&&now.cycles==saved.cycles,"allocation failure preserves used statistics");
  }
  fail_at=0;
  CHECK(interp_bridge_add_native_instructions(&d,1),"idempotent duplicate preserves counts");
  CHECK(interp_bridge_native_instruction_stats(&saved,1)==1&&saved.insns==1&&saved.cycles==2,"idempotent duplicate not double credited");
  CHECK(interp_bridge_add_native_instructions(&early,1),"insertion rebuild shifts descriptor indexes");
  NativeInstructionEntry *entry=lookup(0x828100,1,0,0);
  CHECK(entry&&entry->descriptor.pc24==0x828100&&entry->insns==1&&entry->cycles==2,"shifted direct index preserves exact entry and stats");
  CHECK(lookup(0x8280ff,1,0,0)!=NULL,"separate page index resolves correctly");
  CHECK(!lookup(0x828101,1,0,0),"same page exactPC miss");
  CHECK(!lookup(0x828100,0,0,0)&&!lookup(0x828100,1,1,0),"exact mode misses");
  CHECK(!lookup(0x428100,1,0,0)&&!lookup(0x828100,1,0,1),"foreign alias and E1 rejected");
  unsigned id=s_native_page_ids[0x8281],slot=(0x00<<2)|(1<<1),position=(id-1)*1024+slot;
  uint16_t good=s_native_page_slots[position];
  s_native_page_slots[position]=8192;
  CHECK(mode?!lookup(0x828100,1,0,0):lookup(0x828100,1,0,0)!=NULL,"out of bounds direct entry fails closed without changing legacy");
  s_native_page_slots[position]=1;
  CHECK(mode?!lookup(0x828100,1,0,0):lookup(0x828100,1,0,0)!=NULL,"wrong direct entry key cannot bypass identity guard");
  s_native_page_slots[position]=good;
  InterpNativeInstruction conflict=d;conflict.bytes[0]=0x1a;
  old=s_native_instructions;ids=s_native_page_ids;slots=s_native_page_slots;bytes=live_bytes;
  CHECK(!interp_bridge_add_native_instructions(&conflict,1),"conflicting descriptor rejected");
  CHECK(old==s_native_instructions&&ids==s_native_page_ids&&slots==s_native_page_slots&&bytes==live_bytes,"conflict preserves all index state");
  s_interp_bridge_depth=1;
  CHECK(!interp_bridge_add_native_instructions(&d,1),"active owner cannot register");
  interp_bridge_clear_native_instructions();
  CHECK(old==s_native_instructions&&ids==s_native_page_ids&&slots==s_native_page_slots,"active owner cannot clear either index");
  s_interp_bridge_depth=0;
  interp_bridge_clear_native_instructions();
  CHECK(!s_native_instruction_count&&!s_native_instructions&&!s_native_page_ids&&!s_native_page_slots&&!live_allocations&&!live_bytes,"clear frees all three allocations");
  for(unsigned i=0;i<65536;i++)CHECK(!s_native_page_start[i]&&!s_native_page_count[i],"clear zeros legacy ranges");
  CHECK(interp_bridge_native_continuation_insns_total()==1&&interp_bridge_native_continuation_cycles_total()==2,"clear preserves process-global attribution");
  CHECK(interp_bridge_native_instruction_index_enabled()==mode,"clear preserves launch mode");
  /* Four M/X modes on each of8192 valid sparse pages fill32768 slots.
   * The direct page storage remains16MiB; entries have grown separately. */
  InterpNativeInstruction *full=calloc(32768,sizeof *full);CHECK(full!=NULL,"capacity descriptor allocation");
  if(full){
    for(unsigned i=0;i<32768;i++){
      unsigned page=i/4;
      full[i]=nop_descriptor(((page/128)<<16)|((0x80+page%128)<<8));
      full[i].m=(i>>1)&1;full[i].x=i&1;RAM[full[i].pc24]=0xea;
    }
    CHECK(interp_bridge_add_native_instructions(full,32768),"32768 mode descriptors on8192 sparse pages supported");
    CHECK(live_bytes==32768*sizeof(NativeInstructionEntry)+131072+16777216,"exact sparse allocation bound");
    for(unsigned i=0;i<32768;i+=127)CHECK(lookup(full[i].pc24,full[i].m,full[i].x,0)!=NULL,"sparse page descriptor lookup");
    NativeInstructionEntry *last=lookup(full[32767].pc24,1,1,0);
    CHECK(last==s_native_instructions+32767&&last->descriptor.pc24==0x3fff00,"last uint16 descriptor ID32768 resolves exactly");
    unsigned page_id=s_native_page_ids[full[32767].pc24>>8];
    CHECK(s_native_page_slots[(page_id-1u)*1024u+3u]==32768,"direct slot stores32768 without truncation");
    g_c.m_flag=1;g_c.x_flag=1;cpu_mirrors_to_p(&g_c);
    uint64_t before_insns=interp_bridge_native_continuation_insns_total();
    interp_bridge_set_master_deadline(g_c.master_cycles+1);
    CHECK(interp_bridge_run_until_quiescent(&g_c,full[32767].pc24)==1,"actual owner executes last sparse native descriptor");
    interp_bridge_set_master_deadline(0);
    CHECK(last->insns==1&&last->cycles==2&&interp_bridge_native_continuation_insns_total()==before_insns+1,"last sparse descriptor exact native counters");
    old=s_native_instructions;ids=s_native_page_ids;slots=s_native_page_slots;bytes=live_bytes;
    for(unsigned failure=1;failure<=3;failure++){
      alloc_calls=0;fail_at=failure;
      CHECK(!interp_bridge_add_native_instructions(full,32768),"full registry allocation refusal");
      CHECK(s_native_instructions==old&&s_native_page_ids==ids&&s_native_page_slots==slots&&s_native_instruction_count==32768,"full registry allocation failure preserves both lookups");
      CHECK(live_bytes==bytes&&live_allocations==3&&last->insns==1&&last->cycles==2,"full allocation failure preserves memory and per-site counters");
      CHECK(s_native_instruction_index==mode&&interp_bridge_native_continuation_insns_total()==before_insns+1,"full allocation refusal preserves launch setting and global counters");
    }
    fail_at=0;
    CHECK(interp_bridge_add_native_instructions(full,32768),"full idempotent batch");
    last=lookup(full[32767].pc24,1,1,0);
    CHECK(last==s_native_instructions+32767&&last->insns==1&&last->cycles==2,"full idempotent rebuild preserves last ID and statistics");
    InterpNativeInstruction overflow=nop_descriptor(0x408000);
    CHECK(!interp_bridge_add_native_instructions(&overflow,1),"unique capacity overflow refused");
    CHECK(interp_bridge_native_instruction_stats(NULL,0)==32768&&lookup(full[32767].pc24,1,1,0)==last&&last->insns==1&&last->cycles==2,"capacity refusal retains full indexes and used statistics");
    free(full);
  }
  interp_bridge_clear_native_instructions();
  CHECK(!live_allocations&&!live_bytes,"final clear no registry leaks");
  printf("index=%d checks=%d failures=%d peak_registry_bytes=%zu\n",mode,g_check,fixture_fail,peak_bytes);
  free(RAM);return fixture_fail?1:0;
}
'''


def _source():
    text=protocol_source();text=text[:text.index("int main(void){")]
    return text+ALLOCATOR+MAIN


@pytest.mark.parametrize("mode",["0","1"])
def test_actual_native_indexes_atomic_failure_and_lookup(tmp_path,mode):
    cc=os.environ.get("CC")or shutil.which("clang")or shutil.which("cc")or shutil.which("gcc")
    if not cc:pytest.skip("C11 compiler required")
    source=tmp_path/"index.c";source.write_text(_source(),encoding="utf-8")
    core=tmp_path/"snes_core.c";core.write_text('#define snes_catchupApu unused_audio_catchup\n#include "snes/snes.c"\n',encoding="utf-8")
    exe=tmp_path/("index.exe"if os.name=="nt"else"index")
    command=[cc,"-std=c11","-O1","-DSNESRECOMP_TIER2_TEST=1","-DSNESRECOMP_REVERSE_DEBUG=0",
      "-I",str(REPO/"runner/src"),"-I",str(REPO/"runner/src/snes"),"-I",str(REPO/"tests/dma"),str(source),str(core),
      *[str(REPO/f)for f in ("runner/src/snes/interp816.c","runner/src/sha256.c","runner/src/snes/tier2_capture.c",
          "runner/src/snes/cx4.c","runner/src/snes/dma.c","runner/src/snes/sdd1.c")],"-lm","-o",str(exe)]
    built=subprocess.run(command,capture_output=True,text=True,timeout=60)
    (tmp_path/"compile.json").write_text(json.dumps(dict(command=command,exit_code=built.returncode,stdout=built.stdout,stderr=built.stderr),indent=2),encoding="utf-8")
    assert built.returncode==0,built.stdout+built.stderr
    env=os.environ.copy();env["SNESRECOMP_NATIVE_INSTRUCTION_INDEX"]=mode
    result=subprocess.run([str(exe)],capture_output=True,text=True,timeout=30,cwd=tmp_path,env=env)
    (tmp_path/"execution.json").write_text(json.dumps(dict(mode=mode,exit_code=result.returncode,
      source_sha256=hashlib.sha256(source.read_bytes()).hexdigest(),binary_sha256=hashlib.sha256(exe.read_bytes()).hexdigest(),stdout=result.stdout,stderr=result.stderr),indent=2),encoding="utf-8")
    assert result.returncode==0,result.stdout+result.stderr
    assert "failures=0"in result.stdout
