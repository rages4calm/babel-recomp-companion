"""Actual bridge execution and atomicity beyond the former uint16 registry.

Synthetic descriptors share fixed NOP/PHB callbacks; no ROM or giant generated
wrapper compilation. Public descriptor/stat/snapshot layouts are not changed.
"""
from pathlib import Path
import hashlib,json,os,re,shutil,subprocess
import pytest
from test_native_continuation import _source as protocol_source
from test_native_instruction_index import ALLOCATOR
from test_region_poll_fallback import REPO


MAIN=r'''
#include "snes/interp_native_wram.h"
_Static_assert(sizeof(*s_native_page_slots)==sizeof(uint32_t),"wide private descriptor IDs");
_Static_assert(sizeof(s_native_page_start[0])==sizeof(uint32_t),"wide legacy starts");
_Static_assert(sizeof(*s_native_page_ids)==sizeof(uint16_t),"bounded page IDs stay16bit");
_Static_assert(sizeof(s_native_page_count[0])==sizeof(uint16_t),"fourMX perpage staysbounded");
enum { CAPACITY=131072 };
static unsigned cap_pairs;
static uint8_t *cap_expected;
static int cap_nop(Interp816 *in){
 (void)in->read(in->mem,((uint32)in->k<<16)|in->pc++);return in->cyclesUsed=2;
}
static int cap_phb(Interp816 *in){
 (void)in->read(in->mem,((uint32)in->k<<16)|in->pc++);
 in->write(in->mem,in->sp--,in->db);return in->cyclesUsed=3;
}
static InterpNativeInstruction cap_desc(uint32_t pc,int m,int x){
 InterpNativeInstruction d={0};d.pc24=pc;d.m=m;d.x=x;d.length=1;d.bytes[0]=0xea;d.step=cap_nop;return d;
}
static NativeInstructionEntry *cap_lookup(const InterpNativeInstruction *d){
 Interp816 in={0};in.k=d->pc24>>16;in.pc=(uint16)d->pc24;in.mf=d->m;in.xf=d->x;in.e=d->e;
 s_lle_sched_depth=1;NativeInstructionEntry *p=bridge_native_instruction_step(&in,d->pc24,1,0);s_lle_sched_depth=0;return p;
}
static void cap_cpu(int m,int x){
 init_cpu();memset(&g_test_snes,0,sizeof g_test_snes);memset(&g_test_cart,0,sizeof g_test_cart);
 static Dma dma;memset(&dma,0,sizeof dma);g_test_snes.dma=&dma;g_test_snes.hdmaBeamOff=true;
 g_test_snes.ram=RAM;g_test_snes.cart=&g_test_cart;g_test_cart.type=CART_HIROM;g_test_cart.rom=RAM;g_test_cart.romSize=MEMSZ;
 g_c.emulation=0;g_c.m_flag=m;g_c.x_flag=x;g_c._flag_I=1;g_c.A=0x1234;g_c.X=x?0x34:0x1234;g_c.Y=x?0x78:0x5678;g_c.S=0x1ff;g_c.DB=0x7e;cpu_mirrors_to_p(&g_c);
 g_memsel=1;snes_set_rdnmi_beam_enabled(false);snes_set_raster_irq_beam_enabled(false);
 g_push_count=g_interp_push_count=g_push_depth=g_pop_underflow=g_recomp_stack_top=0;g_abandon_called=0;
 interp_bridge_set_pre_opcode_hook(0,NULL);interp_bridge_set_lle_bounce_exclusions(NULL,0);interp_bridge_reset_dynamic_cache();
 bus_hash=1469598103934665603ULL;bus_reads=bus_writes=0;last_data_ipc=overlay_probes=0;
}
typedef struct CapOutcome {CpuState cpu;Snes snes;uint32_t resume;uint64_t ni,nc,ii,ic,wi,wc,bus,reads,writes;} CapOutcome;
static CapOutcome cap_execute(const InterpNativeInstruction *d,int native){
 cap_cpu(d->m,d->x);interp_bridge_set_interpret_all(!native);
 uint64_t ni=interp_bridge_native_continuation_insns_total(),nc=interp_bridge_native_continuation_cycles_total();
 uint64_t ii=interp816_insns_total(),ic=interp816_cycles_total(),wi=interp_bridge_native_wram_copy_insns_total(),wc=interp_bridge_native_wram_copy_cycles_total();
 interp_bridge_set_master_deadline(1);CHECK(interp_bridge_run_until_quiescent(&g_c,d->pc24)==1,"bounded real owner executes one boundary opcode");interp_bridge_set_master_deadline(0);
 CapOutcome out={0};out.cpu=g_c;out.snes=g_test_snes;out.resume=interp_bridge_lle_resume_pc();
 out.ni=interp_bridge_native_continuation_insns_total()-ni;out.nc=interp_bridge_native_continuation_cycles_total()-nc;
 out.ii=interp816_insns_total()-ii;out.ic=interp816_cycles_total()-ic;out.wi=interp_bridge_native_wram_copy_insns_total()-wi;out.wc=interp_bridge_native_wram_copy_cycles_total()-wc;
 out.bus=bus_hash;out.reads=bus_reads;out.writes=bus_writes;
 CHECK(!g_recomp_stack_top&&!g_pop_underflow&&!g_abandon_called,"boundary keeps real owner stack clean");return out;
}
static int cap_pair(const InterpNativeInstruction *d,int wram){
 unsigned before=fixture_fail;CapOutcome ref=cap_execute(d,0);memcpy(cap_expected,RAM,MEMSZ);CapOutcome got=cap_execute(d,1);++cap_pairs;
 CHECK(!memcmp(&ref.cpu,&got.cpu,sizeof ref.cpu)&&!memcmp(&ref.snes,&got.snes,sizeof ref.snes),"boundary fullCPU/syntheticSnes clocks/PBR/width/stack parity");
 CHECK(!memcmp(cap_expected,RAM,MEMSZ)&&ref.bus==got.bus&&ref.reads==got.reads&&ref.writes==got.writes,"boundary wholememory/bus/stack parity");
 CHECK(ref.resume==got.resume&&got.resume==((d->pc24&0xff0000)|((d->pc24+1)&65535)),"architectural PC16 wrap preserves physicalPB");
 CHECK(!ref.ni&&!ref.nc&&got.ni==1&&got.nc==(uint64_t)(wram?3:2),"last/boundary descriptor actually executes native exactlyonce");
 CHECK(ref.ii==got.ii+got.ni&&ref.ic==got.ic+got.nc,"accepted work moves exactly from decoder to native counters");
 CHECK(got.wi==(uint64_t)wram&&got.wc==(uint64_t)(wram?3:0),"WRAM counters stay strict NI subset");return fixture_fail==before;
}
static int cap_permissions(const InterpNativeInstruction *cop,const InterpNativeInstruction *mid,const InterpNativeInstruction *last){
 NativeInstructionEntry *c=cap_lookup(cop),*m=cap_lookup(mid),*z=cap_lookup(last);
 return c&&m&&z&&c->frame_effect&&c->owner_scopes==1&&m->owner_scopes==3&&m->nmi_owner_pc24==0x8500&&z->owner_scopes==1&&interp_bridge_native_frame_grants()==1&&interp_bridge_native_nmi_grants()==2&&interp_bridge_native_wram_copy_grants()==1;
}
#define REQUIRE(expr,msg) do{int passed=(expr);CHECK(passed,msg);if(!passed)goto done;}while(0)
int main(void){
 InterpNativeInstruction *rom=NULL;RAM=malloc(MEMSZ);cap_expected=malloc(MEMSZ);if(!RAM||!cap_expected)return 2;memset(RAM,0,MEMSZ);memset(RAM+0x828000,0xea,0x8000);
 cap_cpu(0,0);interp_bridge_set_interpret_all(0);interp_bridge_clear_native_instructions();interp_bridge_clear_native_rdnmi_polls();interp_bridge_clear_idle_polls();
 REQUIRE(kNativeInstructionSlots==CAPACITY,"reviewed bounded registry capacity");
 const char *setting=getenv("SNESRECOMP_NATIVE_INSTRUCTION_INDEX");int mode=!(setting&&!strcmp(setting,"0"));
 InterpNativeInstruction probe=cap_desc(0x828100,0,0);
 for(unsigned f=1;f<=3;f++){alloc_calls=0;fail_at=f;CHECK(!interp_bridge_add_native_instructions(&probe,1),"empty allocation stage refuses atomically");CHECK(!s_native_instruction_count&&!s_native_instructions&&!s_native_page_ids&&!s_native_page_slots&&!live_bytes&&!live_allocations,"empty failure leaves no registry/index allocation");CHECK(s_native_instruction_index==-1,"empty failure cannot latch mode");}fail_at=0;
 rom=calloc(CAPACITY-1,sizeof *rom);REQUIRE(rom!=NULL,"bounded descriptor array allocation");
 rom[0]=cap_desc(0x818000,0,0);rom[0].length=2;rom[0].bytes[0]=2;rom[0].step=pure_decline;RAM[0x818000]=2;
 for(unsigned i=1;i<CAPACITY-1;i++){unsigned j=i-1;rom[i]=cap_desc(0x828000u+j/4,(j>>1)&1,j&1);}
 InterpNativeInstruction cop=rom[0],mid=rom[65534],last=rom[CAPACITY-2];
 InterpNativeWramCopyInstruction copy={0};copy.pc24=0x800402;copy.stub_pc=0x402;copy.scopes=3;copy.nmi_owner_pc24=0x8500;copy.step=cap_phb;
 const uint8_t shape[]={0x8b,0x54,0x7f,0x7e,0xab,0x60};memcpy(RAM+0x402,shape,sizeof shape);memcpy(RAM+0x800402,shape,sizeof shape);
 InterpNativeInstruction small[]={cop,mid,last};REQUIRE(interp_bridge_add_native_wram_copy_instructions(&copy,1)&&interp_bridge_add_native_instructions(small,3),"mixed original registry established");
 CHECK(interp_bridge_native_instruction_index_enabled()==mode,"requested lookup selected");interp_bridge_set_native_wram_copy_enabled(true);interp_bridge_set_native_frame_effects_enabled(true);
 CHECK(interp_bridge_allow_native_frame_instructions(&cop,1)&&interp_bridge_restrict_native_instructions(&cop,1,1),"original frame permission+scope established");
 CHECK(interp_bridge_allow_native_nmi_instructions(0x8500,&mid,1)&&interp_bridge_restrict_native_instructions(&mid,1,3)&&interp_bridge_restrict_native_instructions(&last,1,1),"original finiteNMI and scheduler scopes established");
 InterpNativeInstruction wd={0};wd.pc24=copy.pc24;wd.length=1;wd.bytes[0]=0x8b;
 REQUIRE(cap_pair(&wd,1)&&cap_pair(&mid,0)&&cap_pair(&last,0),"small registry used counters seeded by real execution");
 NativeInstructionEntry *old=s_native_instructions;uint16_t *ids=s_native_page_ids;uint32_t *slots=s_native_page_slots;size_t bytes=live_bytes;uint64_t total=interp_bridge_native_continuation_insns_total();
 REQUIRE(cap_permissions(&cop,&mid,&last),"all original permissions present before merge");
 for(unsigned f=1;f<=3;f++){
  alloc_calls=0;fail_at=f;CHECK(!interp_bridge_add_native_instructions(rom,CAPACITY-1),"large merge allocation stage failure");
  CHECK(s_native_instructions==old&&s_native_page_ids==ids&&s_native_page_slots==slots&&s_native_instruction_count==4,"large failure retains every old table pointer");
  CHECK(live_bytes==bytes&&live_allocations==3&&interp_bridge_native_continuation_insns_total()==total&&s_native_instruction_index==mode,"failure retains allocations/globalcounts/mode");
  CHECK(cap_permissions(&cop,&mid,&last)&&cap_lookup(&mid)->insns==1&&cap_lookup(&last)->insns==1,"failure preserves old perkey counts/permissions");
 }fail_at=0;
 REQUIRE(interp_bridge_add_native_instructions(rom,CAPACITY-1)&&s_native_instruction_count==CAPACITY,"successful deduplicated mixed merge reaches131072");
 REQUIRE(cap_permissions(&cop,&mid,&last),"successful merge retains frame/NMI/scopes/WRAM grants");
 REQUIRE(cap_lookup(&mid)&&cap_lookup(&last),"old used keys remain resolvable after reindex");
 CHECK(cap_lookup(&mid)->insns==1&&cap_lookup(&last)->insns==1,"successful merge preserves old perkey counts");
 const unsigned wanted[]={65535,65536,65537,131072};
 for(unsigned n=0;n<4;n++){
  unsigned id=wanted[n],index=id-1;const InterpNativeInstruction *d=&rom[index-1];NativeInstructionEntry *entry=cap_lookup(d);
  REQUIRE(entry==s_native_instructions+index,"exact boundary physical/mode key resolves without truncation");
  unsigned page_id=s_native_page_ids[d->pc24>>8],slot=((d->pc24&255)<<2)|(d->m<<1)|d->x;
  REQUIRE(page_id&&s_native_page_slots[(page_id-1)*1024u+slot]==id,"direct slot stores full nonzero32bit descriptor ID");
  REQUIRE(cap_pair(d,0),"actual interpreter/native execution matches at each boundary ID");
 }
 CHECK(s_native_page_start[0x82c0]==65538&&s_native_page_count[0x82c0]==1024,"legacy start exceeds65535 while perpageMXcount stays1024");
 CHECK(cap_permissions(&cop,&mid,&last),"boundary execution cannot mutate grants");
 REQUIRE(interp_bridge_add_native_instructions(rom,CAPACITY-1)&&s_native_instruction_count==CAPACITY,"full duplicate batch is idempotent beyond old limit");
 CHECK(cap_permissions(&cop,&mid,&last)&&cap_lookup(&mid)->insns==2&&cap_lookup(&last)->insns==2,"idempotent rebuild retains actual counters and grants");
 old=s_native_instructions;ids=s_native_page_ids;slots=s_native_page_slots;bytes=live_bytes;total=interp_bridge_native_continuation_insns_total();
 InterpNativeInstruction extra=cap_desc(0x838000,0,0);RAM[extra.pc24]=0xea;CHECK(!interp_bridge_add_native_instructions(&extra,1),"unique131073rd descriptor refuses atomically");
 alloc_calls=0;CHECK(!interp_bridge_add_native_instructions(&extra,131073)&&!alloc_calls,"overcapacity count refuses before input traversal/allocation");
 InterpNativeInstruction conflict=mid;conflict.step=pure_decline;CHECK(!interp_bridge_add_native_instructions(&conflict,1),"conflicting duplicate cannot mutate full registry");
 InterpNativeInstruction bad[]={extra,extra};bad[1].e=1;CHECK(!interp_bridge_add_native_instructions(bad,2),"late invalid E1 leaves no accepted prefix");
 CHECK(s_native_instructions==old&&s_native_page_ids==ids&&s_native_page_slots==slots&&live_bytes==bytes&&s_native_instruction_count==CAPACITY,"every refusal retains full current tables");
 CHECK(cap_permissions(&cop,&mid,&last)&&cap_lookup(&last)->insns==2&&interp_bridge_native_continuation_insns_total()==total,"every refusal preserves grants/perkey/global counts");
 unsigned pg=s_native_page_ids[last.pc24>>8],offset=(pg-1u)*1024u+((last.pc24&255)<<2)|(last.m<<1)|last.x;
 uint32_t good=s_native_page_slots[offset];s_native_page_slots[offset]=CAPACITY+1;CHECK(mode?!cap_lookup(&last):cap_lookup(&last)!=NULL,"out-of-range wideID failsclosed without changinglegacy");
 s_native_page_slots[offset]=1;CHECK(mode?!cap_lookup(&last):cap_lookup(&last)!=NULL,"wrongwideID cannot bypass physical/mode identity");s_native_page_slots[offset]=good;
 CHECK(!cap_lookup(&(InterpNativeInstruction){.pc24=last.pc24,.m=last.m,.x=last.x,.e=1}),"E1 remains refused");
 s_interp_bridge_depth=1;CHECK(!interp_bridge_add_native_instructions(&extra,1),"active owner still cannot register");interp_bridge_clear_native_instructions();CHECK(s_native_instructions==old&&s_native_page_slots==slots,"active clear cannot erase current tables");s_interp_bridge_depth=0;
done:
 fail_at=0;s_interp_bridge_depth=0;s_lle_sched_depth=0;interp_bridge_clear_native_instructions();CHECK(!live_bytes&&!live_allocations&&!s_native_instructions&&!s_native_page_ids&&!s_native_page_slots,"final clear frees all registry allocations");
 CHECK(!interp_bridge_native_frame_grants()&&!interp_bridge_native_nmi_grants()&&!interp_bridge_native_wram_copy_grants(),"clear removes all permission tables");
 printf("capacity=%d lookup=%d pairs=%u checks=%d failures=%d peak_registry_bytes=%zu\n",CAPACITY,interp_bridge_native_instruction_index_enabled(),cap_pairs,g_check,fixture_fail,peak_bytes);
 free(rom);free(cap_expected);free(RAM);return fixture_fail?1:0;
}
'''


def source(mutant=None):
    text=protocol_source();text=text[:text.index('static void metadata_checks(')]
    allocator=ALLOCATOR
    if mutant:
        bridge=(REPO/'runner/src/snes/interp_bridge.c').read_text()
        old,new=(('next_slots[page * 1024u + slot] = (uint32_t)(i + 1);',
                  'next_slots[page * 1024u + slot] = (uint16_t)(i + 1);')if mutant=='slot-truncation'else
                 ('s_native_page_start[page] = (uint32_t)i;',
                  's_native_page_start[page] = (uint16_t)i;'))
        assert bridge.count(old)==1
        allocator=allocator.replace('#include "snes/interp_bridge.c"',bridge.replace(old,new))
    return text+allocator+MAIN


@pytest.mark.parametrize('lookup,mutant',[('0',None),('1',None),('1','slot-truncation'),('0','range-truncation')])
def test_native_registry_capacity_actual_execution_and_atomicity(tmp_path,lookup,mutant):
    cc=os.environ.get('CC')or shutil.which('clang')or shutil.which('cc')
    if not cc:pytest.skip('C11 compiler required')
    src=tmp_path/'capacity.c';src.write_text(source(mutant),encoding='utf-8')
    core=tmp_path/'snes_core.c';core.write_text('#define snes_catchupApu unused_audio_catchup\n#include "snes/snes.c"\n')
    exe=tmp_path/('capacity.exe'if os.name=='nt'else'capacity')
    files=['interp816.c','tier2_capture.c','cx4.c','dma.c','sdd1.c']
    command=[cc,'-std=c11','-O1','-DSNESRECOMP_TIER2_TEST=1','-DSNESRECOMP_REVERSE_DEBUG=0',
        '-I',str(REPO/'runner/src'),'-I',str(REPO/'runner/src/snes'),'-I',str(REPO/'tests/dma'),
        str(src),str(core),*[str(REPO/'runner/src/snes'/f)for f in files],str(REPO/'runner/src/sha256.c'),'-lm','-o',str(exe)]
    built=subprocess.run(command,capture_output=True,text=True,timeout=90)
    (tmp_path/'compile.json').write_text(json.dumps(dict(command=command,exit_code=built.returncode,stdout=built.stdout,stderr=built.stderr),indent=2))
    assert built.returncode==0,built.stdout+built.stderr
    env={k:v for k,v in os.environ.items()if not k.startswith(('IOG_','SNESRECOMP_'))};env['SNESRECOMP_NATIVE_INSTRUCTION_INDEX']=lookup
    result=subprocess.run([str(exe)],env=env,cwd=tmp_path,capture_output=True,text=True,timeout=90)
    (tmp_path/'execution.json').write_text(json.dumps(dict(lookup=lookup,mutant=mutant,source_sha256=hashlib.sha256(src.read_bytes()).hexdigest(),exit_code=result.returncode,stdout=result.stdout,stderr=result.stderr),indent=2))
    if mutant:assert result.returncode==1 and 'FAIL:'in result.stdout+result.stderr,result.stdout+result.stderr
    else:assert result.returncode==0 and'failures=0'in result.stdout,result.stdout+result.stderr
