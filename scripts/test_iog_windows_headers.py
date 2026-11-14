#!/usr/bin/env python3
"""ROM-free two-C-TU reproduction of SDK FORCEINLINE leaking into WinNT."""
import argparse,hashlib,json,subprocess,re
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
BASE='#include "types.h"\n'
UNPROTECTED=BASE+'#include <windows.h>\n'
PROTECTED=BASE+'#pragma push_macro("FORCEINLINE")\n#undef FORCEINLINE\n#include <windows.h>\n#pragma pop_macro("FORCEINLINE")\n'
A='#include <string.h>\n#define STRINGIFY_INNER(x) #x\n#define STRINGIFY(x) STRINGIFY_INNER(x)\nint helper(void); int main(void){return helper()!=7 || strcmp(STRINGIFY(FORCEINLINE), "inline");}\n'
B='int helper(void){return 7;}\n'
def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--compiler',default='clang');p.add_argument('--out',type=Path,default=ROOT/'.local/batch-001/visual-fullgame-002/windows-header-tests');a=p.parse_args();out=a.out.resolve();assert out.is_relative_to((ROOT/'.local').resolve());out.mkdir(parents=True,exist_ok=True)
 version=subprocess.check_output([a.compiler,'--version'],text=True)
 macros=subprocess.run([a.compiler,'-dM','-E','-x','c','-include','_mingw.h','-'],input='',capture_output=True,text=True);macros.check_returncode()
 header_version={m[1]:m[2]for m in re.finditer(r'^#define (__MINGW(?:32|64)_VERSION_[A-Z_]+) (.*)$',macros.stdout,re.M)}
 results={}
 for name,includes in [('unprotected',UNPROTECTED),('protected',PROTECTED)]:
  d=out/name;d.mkdir(exist_ok=True);sources=[]
  for n,tail in [('a',A),('b',B)]:
   f=d/(n+'.c');f.write_text(includes+tail);sources.append(f)
  exe=d/'probe.exe';cmd=[a.compiler,'-std=gnu11','-O0','-I'+str(ROOT/'snesrecomp/runner/src'),*[str(x)for x in sources],'-o',str(exe)]
  r=subprocess.run(cmd,capture_output=True,text=True);log=r.stdout+r.stderr;(d/'build.log').write_text(log)
  if name=='unprotected':
   assert r.returncode and 'duplicate symbol' in log and all(t in log for t in ['NtCurrentTeb','GetCurrentFiber','GetFiberData']),log
  else:
   r.check_returncode();run=subprocess.run([str(exe)],capture_output=True,text=True);(d/'run.log').write_text(run.stdout+run.stderr);run.check_returncode()
  results[name]={'returncode':r.returncode,'command':cmd,'duplicate_symbols':[t for t in ['NtCurrentTeb','GetCurrentFiber','GetFiberData']if 'duplicate symbol: '+t in log]}
 # Ensure the tested workaround is the actual integration boundary, not merely
 # an unrelated synthetic success. The independent reference link is recorded
 # by its real build receipt after both Windows-using title modules are built.
 for name in ['src/iog_received_observer.c','src/iog_map_runtime.c']:
  text=(ROOT/name).read_text();assert re.search(r'#pragma push_macro\("FORCEINLINE"\)\s*#undef FORCEINLINE\s*#include <windows.h>\s*#pragma pop_macro\("FORCEINLINE"\)',text),name
 receipt={'passed':True,'compiler':version,'mingw_header_version':header_version,'cases':results,'source_pin':'80a41241e39bfffd384506fbe7ca65b386e03050','sdk_types_sha256':hashlib.sha256((ROOT/'snesrecomp/runner/src/types.h').read_bytes()).hexdigest(),'scope':'Two actual C translation units at-O0: unprotected WinNT duplicates fail, protected headers compile/link/run. No game data or runtime qualification.'}
 (out/'receipt.json').write_text(json.dumps(receipt,indent=2)+'\n');print(json.dumps({'passed':True,'unprotected_returncode':results['unprotected']['returncode'],'protected_returncode':results['protected']['returncode'],'mingw_header_version':header_version}))
if __name__=='__main__':main()
