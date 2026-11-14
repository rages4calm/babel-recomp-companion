"""ROM-free perspective recurrence tests; optional private captured-row calibration."""
from pathlib import Path
import argparse,hashlib,json,random,re,struct,subprocess
R=Path(__file__).resolve().parents[1]
HARNESS=r'''
#include <stdio.h>
#include <stdlib.h>
#include <stddef.h>
#include "snes/ppu.h"
#include "iog_mode7_perspective.h"
int main(int argc,char**argv){
 if(argc!=2)return 2;FILE*f=fopen(argv[1],"r");if(!f)return 3;
 unsigned d,i;int c,s;unsigned n=0;
 printf("OFFSET %u\n",(unsigned)offsetof(Ppu,m7matrix));
 while(fscanf(f,"%u %u %d %d",&d,&i,&c,&s)==4){
  IogMode7PerspectiveParameters p={(uint16_t)d,(uint16_t)i,(int16_t)c,(int16_t)s};
  int16_t captured[224][4];
  for(int row=-56;row<=279;row++){
   int16_t m[4];int st=IogMode7PerspectiveSample(&p,row,m);
   printf("%u %d %d %d %d %d %d\n",n,row,st,m[0],m[1],m[2],m[3]);
   if(row>=0&&row<224)for(unsigned a=0;a<4;a++)captured[row][a]=m[a];
  }
  if(!IogMode7PerspectiveMatches(&p,captured))return 4;
  captured[113][2]^=1;if(IogMode7PerspectiveMatches(&p,captured))return 5;
  n++;
 }
 fclose(f);return 0;
}
'''
def signed(x):
 x&=65535
 return x-65536 if x>=32768 else x

def reference(p):
 d,inc,co,si=p;dp=bytearray(8)
 def put(a,v):struct.pack_into('<H',dp,a,v&65535)
 def word(a):return struct.unpack_from('<H',dp,a)[0]
 put(0,d);put(2,inc);put(4,abs(co));put(6,abs(si));fraction=0
 while dp[1]:
  for a in (0,2,4,6):put(a,word(a)//2)
 rows=[]
 for k in range(280):
  div=word(0);c=word(4)//div if div else 65535;s=word(6)//div if div else 65535
  a=signed(-c if co<0 else c);b=signed(-s if si<0 else s)
  rows.append([a,b,signed(-b),a])
  low=fraction+(dp[0]<<8)+word(2);fraction=low%256;dp[0]=(low//256)%256
  if low>=65536:
   dp[1]=(dp[1]+1)%256
   for off in (0,2,4,6):put(off,word(off)//2)
 return rows

def main():
 p=argparse.ArgumentParser();p.add_argument('--compiler',default='cc');p.add_argument('--out',type=Path,required=True);p.add_argument('--snapshot-prefix',type=Path);p.add_argument('--packet',type=Path);p.add_argument('--rom',type=Path);a=p.parse_args()
 out=a.out.resolve();assert out.is_relative_to(R/'.local');out.mkdir(parents=True,exist_ok=True)
 cases=[];calibration=None
 if any((a.snapshot_prefix,a.packet,a.rom)):
  assert all((a.snapshot_prefix,a.packet,a.rom))
  ram=Path(str(a.snapshot_prefix)+'.wram.bin').read_bytes();info=json.loads(Path(str(a.snapshot_prefix)+'.info.json').read_text());packet=json.loads(Path(str(a.packet)+'.mode7.json').read_text());rom=a.rom.read_bytes();u=lambda at:struct.unpack_from('<H',ram,at)[0]
  identity=re.search(r'^expected_sha256\s*=\s*(\w+)',(R/'rom_identity.txt').read_text(),re.M)[1]
  assert len(rom)==2097152 and hashlib.sha256(rom).hexdigest()==identity
  assert info['frame']==packet['frame'] and u(0x644)==0xfe
  angle=(u(0xbc)&511)*2;co=struct.unpack_from('<h',rom,0x1c695+angle)[0];si=struct.unpack_from('<h',rom,0x1c595+angle)[0]
  cases.append((u(0xb8),u(0xb6),co,si));calibration={'frame':packet['frame'],'scene':254,'source':'Original-USA FE perspective thinker; captured frame identity shared with snapshot','parameters':list(cases[0]),'snapshot_sha256':hashlib.sha256(ram).hexdigest(),'packet_sha256':hashlib.sha256(Path(str(a.packet)+'.mode7.json').read_bytes()).hexdigest(),'rom_sha256':hashlib.sha256(rom).hexdigest()}
 for d in (0,1,128,177,256,1024,65535):
  for inc in (0,1,255,256,1019,65535):
   for c,s in ((32767,0),(23170,23170),(-23170,23170),(-23170,-23170),(23170,-23170),(-32768,-32768)):
    cases.append((d,inc,c,s))
 rng=random.Random(314159)
 cases.extend((rng.randrange(65536),rng.randrange(65536),rng.randrange(-32768,32768),rng.randrange(-32768,32768))for _ in range(64))
 inp=out/'parameters.txt';inp.write_text(''.join('%d %d %d %d\n'%x for x in cases));source=out/'recurrence.c';source.write_text(HARNESS);exe=out/'recurrence.exe'
 cmd=[a.compiler,'-std=c11','-O2','-Wall','-Wextra','-Werror','-I'+str(R/'src'),'-I'+str(R/'snesrecomp/runner/src'),str(source),'-o',str(exe)]
 b=subprocess.run(cmd,capture_output=True,text=True);(out/'build.log').write_text(b.stdout+b.stderr);b.check_returncode()
 res=subprocess.run([str(exe),str(inp)],capture_output=True,text=True,timeout=60);(out/'run.log').write_text(res.stdout+res.stderr);res.check_returncode()
 lines=res.stdout.splitlines();offset=int(lines[0].split()[1]);observed={};checks=0
 for line in lines[1:]:
  n,row,status,*matrix=map(int,line.split());par=cases[n]
  if row<0:
   div,inc,co,si=par;nc,ns=abs(co),abs(si)
   while div>=256:div//=2;inc//=2;nc//=2;ns//=2
   depth=div*256+inc*row
   if depth<256:assert status==2 and matrix==[0]*4
   else:
    rd,frac=divmod(depth,256);c=nc//rd;s=ns//rd;aa=signed(-c if co<0 else c);bb=signed(-s if si<0 else s)
    assert status==1 and matrix==[aa,bb,signed(-bb),aa],(n,row,matrix,depth)
    # Prove this initialized-camera prefix reconnects without any lossy
    # carry normalization. This is not an inverse of discarded raster bits.
    for step in range(-row):
     packed=rd*256+frac+inc;assert packed<65536
     rd,frac=divmod(packed,256)
    assert rd==div and frac==0
  else:
   if n not in observed:observed[n]=reference(par)
   assert status==1 and matrix==observed[n][max(row,0)],(n,row,matrix,observed[n][max(row,0)])
  checks+=1
 if calibration:
  actual=[list(struct.unpack_from('<4h',bytes.fromhex(x['regs']),offset))for x in packet['lines'][:224]]
  expected=observed[0][:224];mismatches=[i for i,(x,y)in enumerate(zip(actual,expected))if x!=y]
  calibration['all224_matrices_match']=not mismatches;calibration['mismatching_rows']=mismatches;calibration['native_matrix_words_compared']=896
  calibration['capture_phase']='table word0 at raster0; visible1 uses word1; raster224 holds word223'
  calibration['terminal_row_retains_last_word']=list(struct.unpack_from('<4h',bytes.fromhex(packet['lines'][224]['regs']),offset))==expected[223]
  (out/'calibration.json').write_text(json.dumps(calibration,indent=2)+'\n')
  assert not mismatches,('producer calibration FAILED',mismatches[:20],actual[:3],expected[:3])
  assert calibration['terminal_row_retains_last_word']
 mutant=out/'mutant';mutant.mkdir(exist_ok=True)
 text=(R/'src/iog_mode7_perspective.h').read_text();needle='            /* Fraction is intentionally NOT shifted by the original code. */'
 assert text.count(needle)==1
 (mutant/'iog_mode7_perspective.h').write_text(text.replace(needle,'            fraction>>=1; /* Deliberate hardware-recurrence fault. */'))
 mutant_cmd=cmd.copy();mutant_cmd.insert(1,'-I'+str(mutant));mutant_cmd[-1]=str(out/'recurrence-mutant.exe')
 mb=subprocess.run(mutant_cmd,capture_output=True,text=True);(out/'mutant-build.log').write_text(mb.stdout+mb.stderr);mb.check_returncode()
 mr=subprocess.run([mutant_cmd[-1],str(inp)],capture_output=True,text=True,timeout=60);(out/'mutant-run.log').write_text(mr.stdout+mr.stderr);mr.check_returncode()
 fault_rows=0
 for line in mr.stdout.splitlines()[1:]:
  n,row,status,*matrix=map(int,line.split())
  if row>=0 and status==1:fault_rows+=matrix!=observed[n][row]
 assert fault_rows>0
 receipt={'passed':True,'cases':len(cases),'row_checks':checks,'single_changed_native_matrix_rejected_in_each_case':True,'fraction_shift_fault_rows_detected':fault_rows,'upper_positive_depth_status':'Matrix from normalized initialized-camera prefix; exact no-carry reconnection checked for every tested upper row','upper_integer_divisor_zero_status':'Sky when packed depth<256; explicit host horizon policy; native divide-zero preserved','calibration':calibration,'command':cmd,'sources':{str(x.relative_to(R)):hashlib.sha256(x.read_bytes()).hexdigest()for x in [R/'src/iog_mode7_perspective.h',Path(__file__)]},'scope':'Forward integer recurrence, initialized-camera upper extension and admission predicate; no full game/GPU/campaign qualification.'}
 (out/'receipt.json').write_text(json.dumps(receipt,indent=2)+'\n');print('PASS',checks,'row checks;',len(cases),'parameter cases; actual224-row calibration',bool(calibration))
if __name__=='__main__':main()
