"""Run bounded assisted Gaia fixtures in new private directories.

Use an immutable copied executable and private fixture-owned checkpoints only.
Explicit script pokes/loads are recorded; no owner saves/settings are imported.
This runs the engine but cannot turn assisted coverage into natural progression.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import time

from check_native_routes import ROOT,sha,snapshots


def run(binary:Path,rom:Path,script:Path,output:Path,frames:int,seed:Path|None=None,
        rate:int=1,interpret_all:bool=False,expect_scene:int|None=None,timeout:int=180,
        capture:bool=False,wide:bool=False,infinite_hp:bool=False,
        watch_wram:tuple[int,int]|None=None)->dict:
    private=(ROOT/'.local').resolve();output=output.resolve()
    if not output.is_relative_to(private) or not 60<=frames<=10000 or not 1<=rate<=8 or not 1<=timeout<=300:
        raise ValueError('private output, 60..10000 frames, 1x..8x rate and 1..300 second timeout required')
    if seed and not seed.resolve().is_relative_to(private):
        raise ValueError('Only private fixture-owned checkpoints may be imported')
    if watch_wram and not (0<=watch_wram[0]<=watch_wram[1]<=0xFFFF):
        raise ValueError('The native WRAM watch accepts a 16-bit address range')
    image=rom.read_bytes();expected=re.search(r'^expected_sha256\s*=\s*(\w+)',(ROOT/'rom_identity.txt').read_text(),re.M)[1]
    if len(image)!=2097152 or hashlib.sha256(image).hexdigest()!=expected:
        raise ValueError('the verified bare USA ROM is required')
    text=script.read_text(encoding='utf-8');changes=[]
    loads=re.findall(r'(?m)^\s*loadstate\s+(\d+)',text)
    if (loads and(not seed or any(slot!='0'for slot in loads)))or(seed and not loads):
        raise ValueError('checkpoint fixtures must explicitly load slot0 from the supplied private seed')
    for number,line in enumerate(text.splitlines(),1):
        words=line.split('#',1)[0].split()
        if words and words[0]in('poke','pokefor','forcepoke'):
            changes.append({'line':number,'command':words[0],'address':words[1],'bytes':words[2],
                            'frames':words[3]if len(words)>3 else 1,
                            'reason':line.partition('#')[2].strip()})
    if not re.search(r'(?m)^dump\s+',text):raise ValueError('fixture requires visible state dumps')
    hashes={'binary':sha(binary),'rom':sha(rom),'route':sha(script)}
    if seed:hashes['seed_state']=sha(seed)
    output.mkdir(parents=True,exist_ok=False);(output/'snapshots').mkdir()
    shutil.copy2(binary,output/'babel-recomp.exe')
    for name in('assets','i18n'):
        if (binary.parent/name).is_dir():shutil.copytree(binary.parent/name,output/name)
    for dll in binary.parent.glob('*.dll'):shutil.copy2(dll,output/dll.name)
    shutil.copytree(ROOT/'mods/preloaded',output/'mods/preloaded')
    state='format_version = 1\n\n[[package]]\nid = "iog.cheats"\nversion = "1.0.0"\n\n'
    state+='[[feature]]\npackage_id = "iog.cheats"\nid = "room_rewards"\n'
    state+=f'enabled = {str(rate>1).lower()}\n\n[feature.values]\nmultiplier = "{rate}"\n'
    if infinite_hp:
        state+='\n[[feature]]\npackage_id = "iog.cheats"\nid = "infinite_hp"\nenabled = true\n'
    (output/'mods/preloaded/state.toml').write_text(state)
    if seed:
        (output/'saves').mkdir();shutil.copy2(seed,output/'saves/save0.sav')
    (output/'route.txt').write_text(text,encoding='utf-8')
    config=output/'test.ini';config.write_text('[Graphics]\nOutputMethod = SDL-Software\nNewRenderer = 1\n'+f'Widescreen = {int(wide)}\n'+'DisplayAspect = 4:3\nMode7Enabled = 0\n[General]\nDisableFrameDelay = 1\nRetroAchievements = 0\n[Sound]\nEnableAudio = 0\n[GamepadMap]\nEnableGamepad1 = false\nEnableGamepad2 = false\n')
    env={k:v for k,v in os.environ.items()if not k.startswith(('SNESRECOMP_','IOG_','IOGR_'))}
    env.update(SDL_VIDEODRIVER='dummy',SDL_AUDIODRIVER='dummy',SNESRECOMP_RUN_FRAMES=str(frames),
               SNESRECOMP_STATE_TRACE=str(output/'trace.csv'),SNESRECOMP_DUMP_DIR=str(output/'snapshots'),
               SNESRECOMP_SCREENSHOT=str(output/'final.ppm'),SNESRECOMP_SCREENSHOT_FRAME=str(frames-1))
    if interpret_all:env['SNESRECOMP_INTERPRET_ALL']='1'
    command=[str(output/'babel-recomp.exe'),'--no-launcher','--config',str(config),'--script',str(output/'route.txt'),'--rom',str(rom)]
    if capture:
        env.update(SNESRECOMP_TIER2_MANIFEST=str(output/'tier2-manifest.json'),
                   SNESRECOMP_TIER2_JOURNAL=str(output/'tier2-journal.jsonl'))
        command.insert(1,'--coverage-capture=on')
    if watch_wram:
        env['SNESRECOMP_WLOG_ADDR']=f'{watch_wram[0]:X}:{watch_wram[1]:X}:{output / "wram-writes.log"}'
        env['SNESRECOMP_WLOG_ADDR_CAP']='100000'
        env['SNESRECOMP_WLOG_STATE']='1'
    began=time.monotonic()
    try:
        result=subprocess.run(command,cwd=output,env=env,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,timeout=timeout)
        code=result.returncode;log=result.stdout.decode('utf-8',errors='replace')
    except subprocess.TimeoutExpired as error:
        code=None;log=(error.stdout or b'').decode('utf-8',errors='replace')+'\nFIXTURE TIMEOUT\n'
    (output/'run.log').write_text(log)
    trace=output/'trace.csv';rows=trace.read_text().splitlines()if trace.exists()else[]
    states=snapshots(output)
    for entry in states:
        ram=(output/'snapshots'/(entry['tag']+'.wram.bin')).read_bytes()
        entry.update(strength=int.from_bytes(ram[0x0ADE:0x0AE0],'little'),defense=int.from_bytes(ram[0x0ADC:0x0ADE],'little'),
            room_flags=ram[0x0A60:0x0A80].hex(),player_x=int.from_bytes(ram[0x1014:0x1016],'little'),
            player_y=int.from_bytes(ram[0x1016:0x1018],'little'))
    requested=set(re.findall(r'(?m)^dump\s+(\w+)',text));observed=set(re.findall(r'(?m)^script f=\d+ dump (\w+) ok',log))
    final=states[-1]if states else{}
    checks={'exit_zero':code==0,'frame_count':len(rows)==frames,'script_valid':not any(s in log for s in('script: unknown','script: cannot open','script: bad','timed out','FIXTURE TIMEOUT')),
            'all_requested_dumps':bool(requested)and requested<=observed,'complete_wram':bool(states)and all(s['wram_bytes']==131072 for s in states),
            'visible_last_snapshot':final.get('nonblack_pixels',0)>0,'player_actor_present':final.get('player_actor',0)!=0,
            'owner_inputs_unchanged':hashes['binary']==sha(binary)and hashes['rom']==sha(rom)and hashes['route']==sha(script)and(not seed or hashes['seed_state']==sha(seed))}
    if expect_scene is not None:checks['expected_scene']=final.get('scene')==expect_scene
    coverage=None
    if capture:
        manifest=output/'tier2-manifest.json';journal=output/'tier2-journal.jsonl'
        checks['coverage_files_written']=manifest.is_file()and journal.is_file()
        if manifest.is_file():
            raw=json.loads(manifest.read_text())
            checks['coverage_identity_matches']=raw.get('identity',{}).get('rom_sha256')==expected
            checks['coverage_complete']=raw.get('schema')=='snesrecomp tier2 coverage v2'and raw.get('checkpoint_complete')is True
            counters=('overflowed_tuples','journal_write_failures','dropped_cost_samples','ram_routines_overflow')
            checks['coverage_not_truncated']=all(raw.get(key)==0 for key in counters)
            coverage={key:raw.get(key)for key in('schema','capture_id','identity','checkpoint_complete','sequence','distinct_sites',*counters)}
            coverage.update(manifest_sha256=sha(manifest),cost_rows=len(raw.get('costs',[])),transfer_rows=len(raw.get('discoveries',[])))
    share=json.loads((output/'last_run_report.json').read_text()).get('execution_share')if(output/'last_run_report.json').exists()else None
    report={'schema':'iog-native-route-v1','passed':all(checks.values()),'checks':checks,'frames_requested':frames,'frames_traced':len(rows),
        'input_sha256':hashes,'exit_code':code,'elapsed_seconds':round(time.monotonic()-began,3),'widescreen':wide,
        'route_assisted':bool(changes or seed or re.search(r'(?m)^loadstate\s+',text)),
        'interpret_all':interpret_all,'room_reward_multiplier':rate,'script_writes':changes,'seed_state':str(seed)if seed else None,
        'snapshots':states,'execution_share':share,'fixture_mod_state_sha256':sha(output/'mods/preloaded/state.toml'),
        'runner_source_sha256':sha(Path(__file__)),
        'capture_requested':capture,'coverage':coverage,'infinite_hp':infinite_hp,'watch_wram':watch_wram,
        'evidence_scope':'Isolated dummy video/audio engine fixture. Explicit checkpoint loads/WRAM writes are assisted; no natural combat, puzzle, speaker/controller or campaign claim.'}
    (output/'receipt.json').write_text(json.dumps(report,indent=2)+'\n');return report


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    for name in('binary','rom','script','output'):parser.add_argument('--'+name,type=Path,required=True)
    parser.add_argument('--frames',type=int,required=True);parser.add_argument('--seed-state',type=Path)
    parser.add_argument('--room-rate',type=int,default=1);parser.add_argument('--interpret-all',action='store_true')
    parser.add_argument('--expect-scene',type=lambda x:int(x,0));parser.add_argument('--timeout',type=int,default=180)
    parser.add_argument('--capture',action='store_true');parser.add_argument('--wide',action='store_true')
    parser.add_argument('--infinite-hp',action='store_true')
    parser.add_argument('--watch-wram',type=lambda value:tuple(int(v,16)for v in value.split(':')))
    args=parser.parse_args()
    if args.watch_wram and len(args.watch_wram)!=2:parser.error('--watch-wram needs LO:HI in hex')
    r=run(args.binary.resolve(),args.rom.resolve(),args.script.resolve(),args.output,args.frames,args.seed_state,args.room_rate,args.interpret_all,args.expect_scene,args.timeout,args.capture,args.wide,args.infinite_hp,args.watch_wram)
    print(json.dumps({'passed':r['passed'],'checks':r['checks'],'frames':r['frames_traced'],'assisted':r['route_assisted'],'scenes':sorted({s['scene']for s in r['snapshots']}),'last':r['snapshots'][-1]if r['snapshots']else None}))
    return 0 if r['passed']else 1

if __name__=='__main__':raise SystemExit(main())
