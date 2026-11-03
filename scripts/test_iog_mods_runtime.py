#!/usr/bin/env python3
"""ROM-free actual iog_mods callback integration with explicit host stubs.

The production mod implementation and reward tracker are compiled unchanged.
The source-fingerprint decision is injected because no game ROM is used; its
real guard was covered separately by test_iog_cheat_rates.c. This does not run
the CPU, prove natural room-clear timing, or validate framework run-ahead.
"""
from pathlib import Path
import argparse
import hashlib
import json
import re
import subprocess

ROOT=Path(__file__).resolve().parents[1]
STUBS={
"common_cpu_infra.h":'''#pragma once
#include "snes/snes.h"
extern Snes *g_snes;
''',
"common_rtl.h":'''#pragma once
#include <stdint.h>
uint64_t RtlStateGeneration(void);
''',
"snes/cart.h":'''#pragma once
#include <stdint.h>
typedef struct Cart {uint8_t *rom;unsigned romSize;} Cart;
''',
"snes/snes.h":'''#pragma once
#include <stdint.h>
#include "cart.h"
typedef struct Snes {uint8_t *ram;Cart *cart;uint32_t input1_currentState;} Snes;
''',
"present_filter.h":'''#pragma once
enum {kPresentFilter_Config,kPresentFilter_Sharp,kPresentFilter_Smooth};
void PresentFilter_Set(int);
''',
"snes_ra.h":'''#pragma once
void SnesRa_SetBlocked(const char *);
''',
"mod_runtime.h":'''#pragma once
#include <stdint.h>
#include <stddef.h>
typedef void (*SNESModActivationCallback)(void);
typedef void (*SNESModFrameCallback)(void);
typedef uint32_t (*SNESModInputFilter)(uint32_t);
#define SNES_MOD_CONSTRUCTOR(name) void name(void)
int snes_mod_register_reset_callback(SNESModActivationCallback);
int snes_mod_register_activation_plugin(const char *,SNESModActivationCallback);
int snes_mod_register_presentation_plugin(const char *,SNESModActivationCallback);
int snes_mod_register_frame_callback(SNESModFrameCallback);
int snes_mod_register_input_filter(SNESModInputFilter);
int snes_mod_runtime_feature_enabled_c(const char *,const char *);
int snes_mod_runtime_feature_option_value_c(const char *,const char *,const char *,char *,size_t);
int snes_mod_runtime_persist_feature_c(const char *,const char *,int,const char *,const char *);
'''}

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--compiler',default='clang')
    p.add_argument('--out',type=Path,default=ROOT/'.local/batch-001/native-002/cheat-rates/runtime-integration')
    args=p.parse_args();out=args.out.resolve()
    if not out.is_relative_to((ROOT/'.local').resolve()):p.error('fixture output must remain under .local/')
    include=out/'include';out.mkdir(parents=True,exist_ok=True)
    for name,text in STUBS.items():
        path=include/name;path.parent.mkdir(parents=True,exist_ok=True);path.write_text(text)
    exe=out/'test_iog_mods_runtime.exe'
    command=[args.compiler,'-std=c11','-O2','-Wall','-Wextra','-Werror',
        '-I',str(include),'-I',str(ROOT/'src'),str(ROOT/'scripts/test_iog_mods_runtime.c'),
        str(ROOT/'src/iog_cheat_rates.c'),'-o',str(exe)]
    subprocess.run(command,check=True)
    cases=[]
    for name in ['rewards','taint-hp','taint-dp','taint-stats','taint-room','taint-toggle','taint-api','live-cheats','run']:
        result=subprocess.run([str(exe),name],capture_output=True,text=True,check=True)
        print(result.stdout.strip())
        assertions=int(re.search(r'PASS (\d+)',result.stdout).group(1))
        cases.append({'case':name,'assertions':assertions,'passed':True})
    report={'schema':'iog actual mod callback integration fixture v1','passed':True,
        'rom_free':True,'actual_mod_source_compiled':True,'source_fingerprint_gate_injected':True,
        'framework_execution_emulated':False,'natural_reward_qualified':False,
        'assertions':sum(c['assertions']for c in cases),'cases':cases,
        'source_sha256':{str(path.relative_to(ROOT)):hashlib.sha256(path.read_bytes()).hexdigest()
            for path in [ROOT/'src/iog_mods.c',ROOT/'src/iog_cheat_rates.c',ROOT/'src/iog_cheat_rates.h',
                         ROOT/'scripts/test_iog_mods_runtime.c',Path(__file__).resolve()]}}
    (out/'receipt.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps({'passed':True,'assertions':report['assertions'],'cases':len(cases),'receipt':str(out/'receipt.json')}))

if __name__=='__main__':main()
