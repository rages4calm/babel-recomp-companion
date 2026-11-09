"""ROM-free owning-bridge proof for opt-in live ABS WRAM data reads.

The code preview is a pure stable-ROM fake; production Cart preview has its
own runtime tests. Interpreter/bridge and paced bus helpers are production.
This does not qualify a game's Sort routine, mapper, full devices or NMI latency.
"""
from pathlib import Path
import hashlib,json,os,shutil,subprocess
import pytest
from snes65816 import get_rom_mapping,set_rom_mapping
from v2.emit_function import emit_function
from test_region_pacing import _c_function
from test_region_live_operand_refusal import _EXTRA

REPO=Path(__file__).resolve().parents[2]
BANKS=(3,0x43,0x83,0xC3)
ABS_OPS={'LDA':0xAD,'LDX':0xAE,'LDY':0xAC,'ADC':0x6D,'SBC':0xED,'AND':0x2D,
         'ORA':0x0D,'EOR':0x4D,'CMP':0xCD,'CPX':0xEC,'CPY':0xCC,'BIT':0x2C}


def _scan_program():
    # Synthetic stack-as-data loop, not copied from a game. Save P/D/S,
    # consume empty/nonempty/sentinel buckets, restore S before a real JSR.
    code=bytearray.fromhex('08 0B C2 30 A9 00 00 5B 3B 85 00 A9 FF 01 1B')
    head=len(code)
    code+=bytes.fromhex('7A F0 00 30 00 84 44 80 00')
    done=len(code)
    code+=bytes.fromhex('A5 00 1B 20 00 82 2B 28 60')
    code[head+2]=(head-(head+3))&255
    code[head+4]=(done-(head+5))&255
    code[head+8]=(head-(head+9))&255
    return bytes(code),0x8300+head


def _generated(m,x,opcode=0xED):
    rom=bytearray(0x40000)
    absolute=bytes((0xEA,opcode,0x8A,0x06,0x85,0x44,0x60))
    scan,head=_scan_program()
    rom[0x38100:0x38100+len(absolute)]=absolute
    rom[0x38200:0x38202]=bytes.fromhex('E8 60')
    rom[0x38300:0x38300+len(scan)]=scan
    old=get_rom_mapping()
    try:
        set_rom_mapping('hirom');bodies=[];declarations=[];cases=[]
        for bank in BANKS:
            for frozen in(False,True):
                name=f"{'Frozen'if frozen else'Live'}{bank:02X}"
                bodies.append(emit_function(bytes(rom),bank,0x8100,m,x,end=0x8100+len(absolute),func_name=name,
                  instruction_blocks=True,region_paced=True,region_live_wram_addresses=not frozen,
                  live_operand_sites=None if frozen else{bank<<16|0x8101}))
                declarations.append(f'RecompReturn {name}_M{m}X{x}(CpuState *);')
            name=f'Scan{bank:02X}'
            bodies.append(emit_function(bytes(rom),bank,0x8300,m,x,end=0x8300+len(scan),func_name=name,
              instruction_blocks=True,region_paced=True,entry_hooks={bank<<16|head:'ScanObserver'}))
            declarations.append(f'RecompReturn {name}_M{m}X{x}(CpuState *);')
            leaf=f'bank_{bank:02X}_8200'
            for lm,lx in((0,0),(0,1),(1,0),(1,1)):
                bodies.append(emit_function(bytes(rom),bank,0x8200,lm,lx,end=0x8202,func_name=leaf,
                  instruction_blocks=True,region_paced=True,entry_hooks={bank<<16|0x8200:'LeafObserver'}))
                declarations.append(f'RecompReturn {leaf}_M{lm}X{lx}(CpuState *);')
            cases.append(f'''case 0x{bank:02X}:
 if(low==0x8100){{++root_entries;return frozen_mode?Frozen{bank:02X}_M{m}X{x}(cpu):Live{bank:02X}_M{m}X{x}(cpu);}}
 if(low==0x8300){{++scan_entries;return Scan{bank:02X}_M{m}X{x}(cpu);}}
 if(low==0x8200){{return {leaf}_M0X0(cpu);}}break;''')
        return '\n'.join(bodies),'\n'.join(declarations),'\n'.join(cases),scan,head
    finally:set_rom_mapping(old)


_MAIN=r'''
static const uint8_t banks[]={3,0x43,0x83,0xC3};
typedef struct Snap {
 uint16_t a,x,y,s,d;uint8_t db,pb,p,m,xf,e,bus;uint64_t cycles,master;
} Snap;
static Snap state(const CpuState *cpu) {
 CpuState copy=*cpu;cpu_mirrors_to_p(&copy);Snap s;memset(&s,0,sizeof s);
 s.a=copy.A;s.x=copy.X;s.y=copy.Y;s.s=copy.S;s.d=copy.D;s.db=copy.DB;s.pb=copy.PB;s.p=copy.P;
 s.m=copy.m_flag;s.xf=copy.x_flag;s.e=copy.emulation;s.bus=copy.open_bus;s.cycles=copy.cycles;s.master=copy.master_cycles;return s;
}
static Snap preview_before,interpreter_before,tail_before,scan_snaps[8];
static unsigned preview_calls,interpreter_hooks,live_tails,scan_hooks;
static unsigned reads_at_tail,data_at_tail,preview_pure_fail;
static int preview_mode;
static void LeafObserver(const CpuState *cpu,uint32 pc){(void)pc;++leaf_entries;leaf_s=cpu->S;}
bool cpu_preview_code16(const CpuState *cpu,uint8 bank,uint16 addr,uint16 *out) {
 CpuState prior=*cpu;unsigned reads=operand_reads+data_reads;
 preview_before=state(cpu);preview_calls++;
 bool accepted=preview_mode==0 && bank!=0x7e && bank!=0x7f && addr>=0x8000 && addr!=0xffff;
 if(accepted)*out=RAM[((uint32)bank<<16)|addr]|(uint16)(RAM[((uint32)bank<<16)|(uint16)(addr+1)]<<8);
 if(memcmp(&prior,cpu,sizeof prior)||reads!=operand_reads+data_reads)preview_pure_fail++;
 return accepted;
}
static void observe_interpreter(CpuState *cpu,uint32 pc) {
 CHECK(pc==((current_bank<<16)|0x8101),"ABS interpreter hook alias");
 interpreter_before=state(cpu);interpreter_hooks++;
}
void ScanObserver(const CpuState *cpu,uint32 pc) {
 CHECK(pc==((current_bank<<16)|SCAN_HEAD),"scan hook alias");
 if(scan_hooks<8)scan_snaps[scan_hooks]=state(cpu);scan_hooks++;
}
static void scan_interpreter_observer(CpuState *cpu,uint32 pc){ScanObserver(cpu,pc);}
static RecompReturn observe_tail(CpuState *cpu,uint32 target,uint32 site,uint16 entry_s,uint8 hrv) {
 if(target==((current_bank<<16)|0x8101)) {
  live_tails++;tail_before=state(cpu);reads_at_tail=operand_reads;data_at_tail=data_reads;
 }
 return interp_tier_dispatch_tail(cpu,target,site,entry_s,hrv);
}
/* GENERATED_BODIES */
typedef struct Result {
 Snap before,after,tail,yield,scan[8];unsigned previews,hooks,tails,reads,data,low,high,tail_reads,tail_data;
 unsigned roots,scans,leaves,scan_hooks,pure_fail,order;int rc,depth,underflow,bad;uint32_t resume;uint16_t leaf_s;
} Result;
static uint8_t *expected_memory;
static void reset(unsigned bank,int native) {
 memset(RAM,0,MEMSZ);init_cpu();interp_bridge_reset_dynamic_cache();interp_bridge_set_master_deadline(0);
 interp_bridge_set_pre_opcode_hook(0,NULL);interp_bridge_set_interpret_all(!native);
 current_bank=bank;operand_reads=data_reads=operand_low_reads=operand_high_reads=0;
 operand_order=0;
 preview_calls=interpreter_hooks=live_tails=scan_hooks=reads_at_tail=data_at_tail=preview_pure_fail=0;
 root_entries=scan_entries=leaf_entries=unexpected_dispatch=0;leaf_s=0;
 memset(&preview_before,0,sizeof preview_before);memset(&interpreter_before,0,sizeof interpreter_before);
 memset(&tail_before,0,sizeof tail_before);memset(scan_snaps,0,sizeof scan_snaps);
 g_push_count=g_interp_push_count=g_push_depth=g_pop_underflow=g_recomp_stack_top=0;g_abandon_called=0;
 g_c.emulation=0;g_c.m_flag=MFLAG;g_c.x_flag=XFLAG;g_c._flag_I=1;g_c.master_cycles=1000;
}
static Result result(int rc) {
 Result r={0};r.rc=rc;r.before=preview_calls?preview_before:interpreter_before;r.after=state(&g_c);r.tail=tail_before;
 r.previews=preview_calls;r.hooks=interpreter_hooks;r.tails=live_tails;r.reads=operand_reads;r.data=data_reads;
 r.low=operand_low_reads;r.high=operand_high_reads;r.tail_reads=reads_at_tail;r.tail_data=data_at_tail;
 r.roots=root_entries;r.scans=scan_entries;r.leaves=leaf_entries;r.scan_hooks=scan_hooks;r.pure_fail=preview_pure_fail;
 memcpy(r.scan,scan_snaps,sizeof r.scan);r.depth=g_recomp_stack_top;r.underflow=g_pop_underflow;
 r.bad=unexpected_dispatch+g_abandon_called;r.leaf_s=leaf_s;r.order=operand_order;return r;
}
static Result execute_abs(unsigned bank,unsigned db,unsigned address,unsigned fast,unsigned carry,unsigned decimal,
                           int native,int frozen,int extra_clock,int failed_preview) {
 reset(bank,native);preview_mode=failed_preview;double_clock_reads=extra_clock;frozen_mode=frozen;
 current_db=db;current_address=address;g_memsel=fast;g_c.DB=db;g_c.A=0x0220;
 g_c.X=XFLAG?0x20:0x0140;g_c.Y=XFLAG?0x20:0x0150;g_c._flag_C=carry;g_c._flag_D=decimal;cpu_mirrors_to_p(&g_c);
 const uint8_t body[]={0xea,OPCODE,0x8a,0x06,0x85,0x44,0x60};const uint8_t owner[]={0x20,0x00,0x81,0x60};
 for(unsigned k=0;k<4;k++){unsigned base=(unsigned)banks[k]<<16;load(base|0x8000,owner,sizeof owner);load(base|0x8100,body,sizeof body);}
 RAM[(bank<<16)|0x8102]=address&255;RAM[(bank<<16)|0x8103]=address>>8;
 RAM[bus_index(db,0x068a)]=0x12;RAM[bus_index(db,0x068b)]=WFLAG?0:0x01;
 RAM[bus_index(db,0x1e00)]=0x34;RAM[bus_index(db,0x1e01)]=WFLAG?0:0x02;
 if(address!=0x068a&&address!=0x1e00){RAM[bus_index(db,address)]=0x34;RAM[bus_index(db,(uint16)(address+1))]=0x02;}
 interp_bridge_set_pre_opcode_hook((bank<<16)|0x8101,observe_interpreter);
 cpu_push_jsr_return_frame(&g_c);g_c.open_bus=0x5a;
 return result(interp_bridge_run(&g_c,(bank<<16)|0x8000));
}
static const uint8_t scan_code[]={ SCAN_BYTES };
static Result execute_scan(unsigned bank,unsigned fast,int native,uint64_t deadline,int interrupt) {
 reset(bank,native);preview_mode=0;double_clock_reads=0;frozen_mode=0;g_memsel=fast;
 current_db=0;current_address=0xffff;g_c.DB=0x80;g_c.D=0x0100;g_c.S=0x1fff;g_c.A=0x0220;g_c.X=0x40;g_c.Y=0x50;
 g_c._flag_C=1;g_c._flag_D=1;cpu_mirrors_to_p(&g_c);
 const uint8_t owner[]={0x20,0x00,0x83,0x60},loop[]={0x20,0x00,0x83,0x80,0xfe},leaf[]={0xe8,0x60};
 for(unsigned k=0;k<4;k++){unsigned base=(unsigned)banks[k]<<16;load(base|0x8000,deadline?loop:owner,deadline?sizeof loop:sizeof owner);load(base|0x8300,scan_code,sizeof scan_code);load(base|0x8200,leaf,sizeof leaf);}
 const uint8_t buckets[]={0,0,0,0,0x34,0x12,0,0,0xff,0xff};load(0x200,buckets,sizeof buckets);
 interp_bridge_set_pre_opcode_hook((bank<<16)|SCAN_HEAD,scan_interpreter_observer);
 cpu_push_jsr_return_frame(&g_c);g_c.open_bus=0x5a;int rc;
 Snap yielded={0};uint32_t resume=0;
 if(deadline){
  interp_bridge_set_master_deadline(deadline);rc=interp_bridge_run_until_quiescent(&g_c,(bank<<16)|0x8000);
  yielded=state(&g_c);resume=interp_bridge_lle_resume_pc();
  CHECK(resume==((bank<<16)|SCAN_HEAD)&&g_c.S==0x0201,"deadline while S points at bucket array: pc%06x S%04x",resume,g_c.S);
  interp_bridge_set_master_deadline(0);
  if(interrupt){
   const uint8_t handler[]={0x48,0xa9,0x66,0x00,0x85,0x60,0x68,0x40};load(0x008600,handler,sizeof handler);
   cpu_push_interrupt_frame_at(&g_c,resume);CHECK(interp_bridge_run_interrupt(&g_c,0x008600)==1,"scan real interrupt-frame RTI");
  }
  rc=interp_bridge_run_until_quiescent(&g_c,resume);
 }else rc=interp_bridge_run(&g_c,(bank<<16)|0x8000);
 Result r=result(rc);r.yield=yielded;r.resume=resume;return r;
}
int main(void){
 RAM=malloc(MEMSZ);expected_memory=malloc(MEMSZ);if(!RAM||!expected_memory)return 2;
 g_test_cart.type=CART_HIROM;g_test_snes.cart=&g_test_cart;
 unsigned scenarios=0,rejections=0,negative=0,scans=0,interrupts=0;
 const unsigned dbs[]={0,0x3f,0x80,0xbf,0x7e,0x7f};
 for(unsigned b=0;b<4;b++)for(unsigned fast=0;fast<2;fast++)for(unsigned db=0;db<6;db++)
  for(unsigned carry=0;carry<2;carry++)for(unsigned decimal=0;decimal<2;decimal++){
   for(unsigned phase=0;phase<3;phase++){
    unsigned address=phase==1?0x1e00:0x068a;
    Result ref=execute_abs(banks[b],dbs[db],address,fast,carry,decimal,0,0,0,0);memcpy(expected_memory,RAM,MEMSZ);
    Result got=execute_abs(banks[b],dbs[db],address,fast,carry,decimal,1,0,0,0);scenarios++;
    CHECK(ref.rc==1&&got.rc==1,"ABS real owner return");
    CHECK(!memcmp(&ref.before,&got.before,sizeof(Snap)),"pure preview before any charge/effect");
    CHECK(!memcmp(&ref.after,&got.after,sizeof(Snap))&&!memcmp(expected_memory,RAM,MEMSZ),"ABS final registers/fullmemory/cycles/master/openbus");
    CHECK(got.previews==1&&!got.pure_fail&&!got.tails&&!got.hooks&&ref.hooks==1,"accepted live operation remains native");
    CHECK(got.reads==2&&got.low==1&&got.high==1&&got.order==0x12&&got.data==(WFLAG?1:2),"two ordered code operand reads and actual width data fetch");
    CHECK(got.roots==1&&!ref.roots&&got.after.s==0x1ff&&!got.depth&&!got.underflow&&!got.bad,"ABS owning guest/host stack");
   }
   Result ref=execute_abs(banks[b],dbs[db],0x1e00,fast,carry,decimal,0,0,0,0);
   Result stale=execute_abs(banks[b],dbs[db],0x1e00,fast,carry,decimal,1,1,0,0);
   CHECK(memcmp(&ref.after,&stale.after,sizeof(Snap))!=0,"oracle detects stale ABS address");negative++;
   Result doubled=execute_abs(banks[b],dbs[db],0x1e00,fast,carry,decimal,1,0,1,0);
   CHECK(ref.after.master!=doubled.after.master&&ref.after.cycles==doubled.after.cycles,"oracle detects double operand fetch clocks");negative++;
  }
 const struct{unsigned db,address;int preview;} bad[]={{0,0x2140,0},{0x83,0x9000,0},{0x43,0x068a,0},{0,0x068a,1},{0,0x068a,2},{0,0x1fff,0},{0x7e,0xffff,0}};
 for(unsigned b=0;b<4;b++)for(unsigned fast=0;fast<2;fast++)for(unsigned k=0;k<sizeof bad/sizeof bad[0];k++){
  if(WFLAG&&k>=5)continue;
  Result ref=execute_abs(banks[b],bad[k].db,bad[k].address,fast,1,0,0,0,0,bad[k].preview);memcpy(expected_memory,RAM,MEMSZ);
  Result got=execute_abs(banks[b],bad[k].db,bad[k].address,fast,1,0,1,0,0,bad[k].preview);rejections++;
  CHECK(got.tails==1&&!got.tail_reads&&!got.tail_data,"bad target/code preview refuses before operand/data reads");
  CHECK(!memcmp(&ref.before,&got.tail,sizeof(Snap)),"refusal before opcode/data clocks/openbus/effects");
  CHECK(!memcmp(&ref.after,&got.after,sizeof(Snap))&&!memcmp(expected_memory,RAM,MEMSZ),"refused real interpreter result");
  CHECK(got.hooks==1&&got.roots==1&&!got.depth&&!got.underflow&&!got.bad,"refusal resumes exactly once in owner");
 }
 if(OPCODE==0xed)for(unsigned b=0;b<4;b++)for(unsigned fast=0;fast<2;fast++){
  Result ref=execute_scan(banks[b],fast,0,0,0);memcpy(expected_memory,RAM,MEMSZ);
  Result got=execute_scan(banks[b],fast,1,0,0);scans++;
  CHECK(ref.scan_hooks==5&&got.scan_hooks==5&&!memcmp(ref.scan,got.scan,sizeof ref.scan),"PLY/BEQ scan boundaries/flags/clocks");
  CHECK(!memcmp(&ref.after,&got.after,sizeof(Snap))&&!memcmp(expected_memory,RAM,MEMSZ),"relocated scan full parity");
  CHECK(got.scans==1&&got.leaves==1&&!ref.scans&&!ref.leaves&&got.after.s==0x1fff&&got.after.d==0x100,"restore S/D/P before ordinary native JSR: scans%u leaf%u ref%u/%u S%04x D%04x",got.scans,got.leaves,ref.scans,ref.leaves,got.after.s,got.after.d);
  CHECK(got.leaf_s==0x1ff6&&!got.depth&&!got.underflow&&!got.bad,"ordinary post-restore JSR owns correct frame");
  uint64_t deadline=ref.scan[1].master;
  Result yr=execute_scan(banks[b],fast,0,deadline,1);memcpy(expected_memory,RAM,MEMSZ);
  Result yn=execute_scan(banks[b],fast,1,deadline,1);interrupts++;
  CHECK(!memcmp(&yr.yield,&yn.yield,sizeof(Snap)),"relocated S deadline state");
  CHECK(!memcmp(&yr.after,&yn.after,sizeof(Snap))&&!memcmp(expected_memory,RAM,MEMSZ),"relocated NMI-frame/RTI continuation parity");
  CHECK(yn.after.s==0x1ffd&&yn.after.d==0x100&&yn.leaves==1&&!yn.depth&&!yn.underflow&&!yn.bad,"relocated owner resumed with original caller frame: S%04x D%04x leaf%u depth%d under%d bad%d",yn.after.s,yn.after.d,yn.leaves,yn.depth,yn.underflow,yn.bad);
 }
 interp_bridge_set_master_deadline(0);interp_bridge_set_pre_opcode_hook(0,NULL);interp_bridge_set_interpret_all(0);
 printf("live WRAM: %u scenarios, %u refusals, %u negative controls, %u scans, %u interrupt boundaries, %d checks, %d failures\n",scenarios,rejections,negative,scans,interrupts,g_check,fixture_fail);
 free(expected_memory);free(RAM);return fixture_fail?1:0;
}
'''


def _fixture(m,x,opcode=0xED):
    bodies,declarations,dispatch,scan,head=_generated(m,x,opcode)
    fixture=(REPO/'tests/interp816/bridge_test.c').read_text(encoding='utf-8')
    fixture=fixture[:fixture.index('int main(void) {')].replace('g_fail','fixture_fail')
    fixture=fixture.replace('(void)cpu; return RAM[(((uint32)bank << 16) | addr) & 0xFFFFFF];',r'''
      if(bank==current_bank && (addr==0x8102||addr==0x8103)) {
        operand_reads++;if(addr==0x8102)operand_low_reads++;else operand_high_reads++;
        operand_order=(operand_order<<4)|(addr==0x8102?1:2);
        if(double_clock_reads)cpu->master_cycles+=cpu_region_speed(((uint32)bank<<16)|addr);
      }
      if(bank==current_db && (addr==current_address || (!WFLAG&&addr==(uint16)(current_address+1))))data_reads++;
      return cpu->open_bus=RAM[bus_index(bank,addr)];''')
    fixture=fixture.replace('(void)cpu; RAM[(((uint32)bank << 16) | addr) & 0xFFFFFF] = v;',
      'RAM[bus_index(bank,addr)]=v;cpu->open_bus=v;')
    fixture=fixture.replace(_c_function(fixture,'cpu_dispatch_has_entry'),
      'int cpu_dispatch_has_entry(CpuState *cpu,uint32 pc){(void)cpu;unsigned low=pc&0xffff;return low==0x8100||low==0x8200||low==0x8300;}\n')
    fixture=fixture.replace(_c_function(fixture,'cpu_dispatch_pc'),
      'RecompReturn cpu_dispatch_pc(CpuState *cpu,uint32 pc,uint16 restore){(void)restore;return dispatch_generated(cpu,pc);}\n')
    fixture=fixture.replace(_c_function(fixture,'cpu_dispatch_pc_paired'),
      'RecompReturn cpu_dispatch_pc_paired(CpuState *cpu,uint32 pc,uint8 frame){cpu->host_return_valid=frame;return dispatch_generated(cpu,pc);}\n')
    extra=_EXTRA.replace('/* GENERATED_DECLARATIONS */',declarations)
    extra=extra[:extra.index('static RecompReturn dispatch_generated')]+(
      'static RecompReturn dispatch_generated(CpuState *cpu,uint32 pc24){unsigned low=pc24&0xffff;switch(pc24>>16){'+dispatch+'}++unexpected_dispatch;return 0;}\n')
    runtime=(REPO/'runner/src/cpu_state.c').read_text(encoding='utf-8')
    paced='\n'.join(_c_function(runtime,name)for name in('is_hw_reg','cpu_add_aot_master_cycles','cpu_read8_paced','cpu_read16_paced','cpu_write8_paced','cpu_write16_paced'))
    narrow=x if opcode in(0xAE,0xAC,0xEC,0xCC)else m
    preamble=(f'#define MFLAG {m}\n#define XFLAG {x}\n#define WFLAG {narrow}\n#define OPCODE {opcode}\n#define SCAN_HEAD 0x{head:04x}\n'
      '#include "cpu_state.h"\nstatic unsigned current_bank,current_db,current_address,operand_reads,data_reads,operand_low_reads,operand_high_reads,operand_order;\n'
      'static unsigned scan_entries;static uint16_t leaf_s;static int double_clock_reads;\n'
      'static RecompReturn dispatch_generated(CpuState *,uint32);\n'
      'static unsigned bus_index(uint8 bank,uint16 addr){if(bank==0x7e)return addr;if(bank==0x7f)return 0x10000u+addr;if((bank&0x7f)<0x40&&addr<0x2000)return addr;return ((unsigned)bank<<16)|addr;}\n')
    main=_MAIN.replace('/* GENERATED_BODIES */',bodies.replace('interp_tier_dispatch_tail(','observe_tail('))
    main=main.replace('SCAN_BYTES',','.join(map(str,scan)))
    return preamble+fixture+extra+paced+main


@pytest.mark.parametrize('m,x',[(0,0),(0,1),(1,0),(1,1)])
def test_live_sbc_abs_wram_and_relocated_stack_real_owner(tmp_path,m,x):
    _run_fixture(tmp_path,m,x)


@pytest.mark.parametrize('name',[name for name in ABS_OPS if name!='SBC'])
@pytest.mark.parametrize('m,x',[(0,0),(0,1),(1,0),(1,1)])
def test_other_live_abs_operations_real_owner(tmp_path,m,x,name):
    _run_fixture(tmp_path,m,x,ABS_OPS[name])


def _run_fixture(tmp_path,m,x,opcode=0xED):
    cc=os.environ.get('CC')or shutil.which('clang')or shutil.which('cc')or shutil.which('gcc')
    if not cc:pytest.skip('C11 compiler required')
    source=tmp_path/'live_wram.c';source.write_text(_fixture(m,x,opcode),encoding='utf-8')
    exe=tmp_path/('live_wram.exe'if os.name=='nt'else'live_wram')
    command=[cc,'-std=c11','-O1','-DSNESRECOMP_TIER2_TEST=1','-I',str(REPO/'runner/src'),'-I',str(REPO/'runner/src/snes'),str(source),
      *[str(REPO/p)for p in('runner/src/snes/interp816.c','runner/src/sha256.c','runner/src/snes/tier2_capture.c','runner/src/snes/interp_bridge.c','runner/src/snes/cx4.c')],'-lm','-o',str(exe)]
    compiled=subprocess.run(command,capture_output=True,text=True,timeout=60)
    (tmp_path/'compile.json').write_text(json.dumps({'command':command,'exit_code':compiled.returncode,'stdout':compiled.stdout,'stderr':compiled.stderr},indent=2),encoding='utf-8')
    assert compiled.returncode==0,compiled.stdout+compiled.stderr
    run=subprocess.run([str(exe)],capture_output=True,text=True,timeout=60)
    (tmp_path/'execution.json').write_text(json.dumps({'source_sha256':hashlib.sha256(source.read_bytes()).hexdigest(),
      'binary_sha256':hashlib.sha256(exe.read_bytes()).hexdigest(),'exit_code':run.returncode,'stdout':run.stdout,'stderr':run.stderr},indent=2),encoding='utf-8')
    assert run.returncode==0,run.stdout+run.stderr
    assert '0 failures'in run.stdout


def test_default_abs_live_annotation_still_rejected():
    old=get_rom_mapping()
    try:
        set_rom_mapping('hirom');rom=bytearray(0x40000);rom[0x38100:0x38104]=bytes.fromhex('ED 8A 06 60')
        with pytest.raises(ValueError,match='live_operand'):
            emit_function(bytes(rom),0x83,0x8100,0,0,instruction_blocks=True,region_paced=True,live_operand_sites={0x838100})
    finally:set_rom_mapping(old)
