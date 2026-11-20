#!/usr/bin/env python3
"""ROM-free native map preferences: roundtrip, corruption and storage guards."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import zlib

ROOT=Path(__file__).resolve().parents[1]
HARNESS=r'''
#include "iog_map_preferences.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
static unsigned checks;
#define C(x)do{checks++;if(!(x)){fprintf(stderr,"line %u: %s\n",__LINE__,#x);exit(1);}}while(0)
int main(int argc,char **argv){
 C(argc==2);IogMapPreferences p={false,{5,4,3,2,1}},q={true,{0,1,2,3,4}};
 if(!strcmp(argv[1],"normal")){
  C(!IogMapPreferencesLoad(&q));C(q.radar&&q.bindings[0]==0);
  C(!IogMapPreferencesLoad(NULL));C(!IogMapPreferencesSave(NULL));
  C(IogMapPreferencesSave(&p));C(IogMapPreferencesLoad(&q));
  C(!q.radar&&!memcmp(p.bindings,q.bindings,5));
  p.radar=true;p.bindings[0]=1;p.bindings[4]=5;
  C(IogMapPreferencesSave(&p));C(IogMapPreferencesLoad(&q));
  C(q.radar&&!memcmp(p.bindings,q.bindings,5));
  p.bindings[0]=4;C(!IogMapPreferencesSave(&p));p.bindings[0]=6;
  C(!IogMapPreferencesSave(&p));C(IogMapPreferencesLoad(&p));
 }else if(!strcmp(argv[1],"reject")){
  C(!IogMapPreferencesLoad(&q));C(q.radar&&q.bindings[0]==0);
 }else if(!strcmp(argv[1],"guard")){
  C(!IogMapPreferencesLoad(&q));C(!IogMapPreferencesSave(&p));
 }else C(0);
 printf("%u preferences assertions passed\n",checks);return 0;
}
'''
def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--compiler',default='cc');p.add_argument('--out',type=Path,required=True);a=p.parse_args()
 out=a.out.resolve();assert out.is_relative_to((ROOT/'.local').resolve());out.mkdir(parents=True,exist_ok=False)
 maps=out/'saves/maps';maps.mkdir(parents=True);sentinel=out/'saves/owner-sentinel';sentinel.write_bytes(b'Owner data untouched')
 c=out/'preferences.c';c.write_text(HARNESS);exe=out/'preferences.exe'
 sources=[ROOT/'src/iog_map_preferences.c',ROOT/'src/iog_map_preferences.h']
 cmd=[a.compiler,'-std=c11','-O1','-Wall','-Wextra','-Werror','-I'+str(ROOT/'src'),str(c),str(sources[0]),'-o',str(exe)]
 r=subprocess.run(cmd,capture_output=True,text=True);(out/'build.log').write_text(r.stdout+r.stderr);r.check_returncode()
 runs=[]
 def run(phase):
  r=subprocess.run([str(exe),phase],cwd=out,capture_output=True,text=True,timeout=10);r.check_returncode();runs.append(r.stdout.strip())
 run('normal');file=maps/'controls.iogprefs';good=file.read_bytes();assert len(good)==24
 for n in range(24):
  bad=bytearray(good);bad[n]^=0x80;file.write_bytes(bad);run('reject')
 for bad in (b'',good[:1],good[:-1],good+b'x'):
  file.write_bytes(bad);run('reject')
 for index,value in ((7,ord('2')),(8,2),(9,6),(9,good[10])):
  bad=bytearray(good);bad[index]=value;bad[20:]=zlib.crc32(bad[:20]).to_bytes(4,'little');file.write_bytes(bad);run('reject')
 file.write_bytes(good)
 # Replace only our disposable directory entry. A guarded writer must refuse
 # the alias and leave the otherwise valid target record unchanged.
 real=out/'saves/maps-real';maps.rename(real);target=out/'junction-target';target.mkdir();(target/'controls.iogprefs').write_bytes(good)
 if os.name=='nt':
  quote=lambda x:"'"+str(x).replace("'","''")+"'"
  command='$null=New-Item -ItemType Junction -Path '+quote(maps)+' -Target '+quote(target)
  subprocess.run(['powershell','-NoProfile','-Command',command],capture_output=True,text=True,check=True)
 else:maps.symlink_to(target,target_is_directory=True)
 run('guard');assert(target/'controls.iogprefs').read_bytes()==good
 if os.name=='nt':assert maps.is_junction();os.rmdir(maps)
 else:maps.unlink()
 real.rename(maps)
 assert file.read_bytes()==good and sentinel.read_bytes()==b'Owner data untouched'
 assert not list(maps.glob('*.tmp-*'))
 receipt=dict(passed=True,runs=runs,corrupt_cases=32,junction_or_symlink_refused=True,owner_data_preserved=True,no_atomic_temp_files=True,sources={str(x.relative_to(ROOT)):hashlib.sha256(x.read_bytes()).hexdigest()for x in sources+[Path(__file__)]},scope='Native24-byte host preferences only; no ROM, save state, guest execution or live controller claim.')
 (out/'receipt.json').write_text(json.dumps(receipt,indent=2)+'\n');print(json.dumps({k:v for k,v in receipt.items()if k not in ('sources','runs')},indent=2))
if __name__=='__main__':main()
