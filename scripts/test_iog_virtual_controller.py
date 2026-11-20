#!/usr/bin/env python3
"""ROM-free SDL3 virtual trigger ranges and actual SDK GamepadMap routing.

Uses an existing Ninja build only for SDL link libraries, and never runs a game
or opens a real controller. Explicit --sdl-include points at the matching SDL3
headers. Only the virtual device created here is opened and detached.
"""
import argparse
import hashlib
import json
from pathlib import Path
import shlex
import subprocess

ROOT = Path(__file__).resolve().parents[1]
HARNESS = r'''
#define SDL_MAIN_HANDLED
#include "desktop/mmx_config.c"
#include <stdio.h>
#include <stdlib.h>
static unsigned checks;
void Die(const char *error){fprintf(stderr,"%s\n",error);exit(2);}
#define C(x) do{checks++;if(!(x)){fprintf(stderr,"line %u: %s; SDL: %s\n",__LINE__,#x,SDL_GetError());exit(1);}}while(0)
static uint32 trigger_modifiers(SDL_Gamepad *pad){
 uint32 modifiers=0;
 if(SDL_GetGamepadAxis(pad,SDL_GAMEPAD_AXIS_LEFT_TRIGGER)>=12000)modifiers|=1u<<kGamepadBtn_L2;
 if(SDL_GetGamepadAxis(pad,SDL_GAMEPAD_AXIS_RIGHT_TRIGGER)>=12000)modifiers|=1u<<kGamepadBtn_R2;
 return modifiers;
}
static int mapped(SDL_Gamepad *pad){
 return FindCmdForGamepadButton(kGamepadBtn_Start,trigger_modifiers(pad));
}
int main(void){
 SDL_SetMainReady();C(SDL_Init(SDL_INIT_GAMEPAD));
 SDL_VirtualJoystickDesc desc;SDL_INIT_INTERFACE(&desc);
 desc.type=SDL_JOYSTICK_TYPE_GAMEPAD;desc.naxes=SDL_GAMEPAD_AXIS_COUNT;
 desc.nbuttons=15;desc.name="Gaia ROM-free trigger range test";
 SDL_JoystickID id=SDL_AttachVirtualJoystick(&desc);C(id!=0);
 SDL_Joystick *joy=SDL_OpenJoystick(id);C(joy!=NULL);
 SDL_Gamepad *pad=SDL_OpenGamepad(id);C(pad!=NULL);SDL_UpdateJoysticks();
 RegisterDefaultKeys();
 int initial_left=SDL_GetGamepadAxis(pad,SDL_GAMEPAD_AXIS_LEFT_TRIGGER);
 int initial_right=SDL_GetGamepadAxis(pad,SDL_GAMEPAD_AXIS_RIGHT_TRIGGER);
 /* SDL3 itself correctly initializes virtual trigger axes to signed minimum.
  * The integration bug occurs only if a caller writes raw zero as release. */
 C(SDL_GetJoystickAxis(joy,SDL_GAMEPAD_AXIS_LEFT_TRIGGER)==SDL_JOYSTICK_AXIS_MIN);
 C(initial_left==0&&initial_right==0&&mapped(pad)==kKeys_Controls+5);
 C(SDL_SetJoystickVirtualAxis(joy,SDL_GAMEPAD_AXIS_LEFT_TRIGGER,0));
 C(SDL_SetJoystickVirtualAxis(joy,SDL_GAMEPAD_AXIS_RIGHT_TRIGGER,0));SDL_UpdateJoysticks();
 int zero_left=SDL_GetGamepadAxis(pad,SDL_GAMEPAD_AXIS_LEFT_TRIGGER);
 int zero_right=SDL_GetGamepadAxis(pad,SDL_GAMEPAD_AXIS_RIGHT_TRIGGER);
 C(zero_left==16383&&zero_right==16383);
 int zero_command=mapped(pad);C(zero_command==kKeys_SaveStateMenu);
 C(FindCmdForGamepadButton(kGamepadBtn_L2,trigger_modifiers(pad))==0);
 C(FindCmdForGamepadButton(kGamepadBtn_R2,trigger_modifiers(pad))==0);
 C(FindCmdForSdlKey(SDLK_TAB,0)==kKeys_Turbo);
 C(FindCmdForGamepadButton(kGamepadBtn_R2,0)==0);
 C(SDL_SetJoystickVirtualAxis(joy,SDL_GAMEPAD_AXIS_LEFT_TRIGGER,SDL_JOYSTICK_AXIS_MIN));
 C(SDL_SetJoystickVirtualAxis(joy,SDL_GAMEPAD_AXIS_RIGHT_TRIGGER,SDL_JOYSTICK_AXIS_MIN));
 SDL_UpdateJoysticks();
 int released_left=SDL_GetGamepadAxis(pad,SDL_GAMEPAD_AXIS_LEFT_TRIGGER);
 int released_right=SDL_GetGamepadAxis(pad,SDL_GAMEPAD_AXIS_RIGHT_TRIGGER);
 C(released_left==0&&released_right==0);
 int released_command=mapped(pad);C(released_command==kKeys_Controls+5);
 C(SDL_SetJoystickVirtualAxis(joy,SDL_GAMEPAD_AXIS_LEFT_TRIGGER,SDL_JOYSTICK_AXIS_MAX));
 SDL_UpdateJoysticks();C(SDL_GetGamepadAxis(pad,SDL_GAMEPAD_AXIS_LEFT_TRIGGER)==32767);
 C(mapped(pad)==kKeys_SaveStateMenu);
 /* Releasing to raw zero reproduces the same modifier bug after attachment. */
 C(SDL_SetJoystickVirtualAxis(joy,SDL_GAMEPAD_AXIS_LEFT_TRIGGER,0));SDL_UpdateJoysticks();
 C(SDL_GetGamepadAxis(pad,SDL_GAMEPAD_AXIS_LEFT_TRIGGER)==16383&&mapped(pad)==kKeys_SaveStateMenu);
 C(SDL_SetJoystickVirtualAxis(joy,SDL_GAMEPAD_AXIS_LEFT_TRIGGER,SDL_JOYSTICK_AXIS_MIN));
 SDL_UpdateJoysticks();C(mapped(pad)==kKeys_Controls+5);
 char custom_turbo[]="L2+R2";
 C(HandleIniConfig(5,"Turbo",custom_turbo));
 C(FindCmdForGamepadButton(kGamepadBtn_R2,1u<<kGamepadBtn_L2)==kKeys_Turbo);
 printf("{\"passed\":true,\"assertions\":%u,\"sdl_version\":%d,\"attach_default_gamepad_triggers\":[%d,%d],\"zero_gamepad_triggers\":[%d,%d],\"released_gamepad_triggers\":[%d,%d],\"zero_start_routes_save_browser\":true,\"released_start_routes_guest_start\":true,\"default_pad_turbo_unbound\":true,\"tab_and_custom_pad_turbo_preserved\":true}\n",
 checks,SDL_GetVersion(),initial_left,initial_right,zero_left,zero_right,released_left,released_right);
 SDL_CloseGamepad(pad);SDL_CloseJoystick(joy);C(SDL_DetachVirtualJoystick(id));SDL_Quit();return 0;
}
'''

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--compiler', default='cc')
    parser.add_argument('--build', type=Path, required=True)
    parser.add_argument('--sdl-include', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    out = args.out.resolve()
    assert out.is_relative_to((ROOT / '.local').resolve())
    out.mkdir(parents=True, exist_ok=False)
    ninja = (args.build / 'build.ninja').read_text()
    libraries = next(line.split('=', 1)[1] for line in ninja.splitlines()
                     if line.startswith('  LINK_LIBRARIES = '))
    source = out / 'virtual-controller.c'
    source.write_text(HARNESS)
    exe = out / 'virtual-controller.exe'
    inputs = [ROOT / 'snesrecomp/runner/src/desktop/mmx_config.c',
              ROOT / 'snesrecomp/runner/src/desktop/config.h',
              ROOT / 'snesrecomp/runner/src/desktop/sdl_compat.h',
              ROOT / 'snesrecomp/runner/src/util.c']
    cmd = [args.compiler, '-std=gnu11', '-O1', '-DSNESRECOMP_SDL3=1',
        '-DSNESRECOMP_NO_DEFAULT_PAD_TURBO=1',
        '-I' + str(args.sdl_include.resolve()), '-I' + str(ROOT / 'snesrecomp/runner/src'),
        '-I' + str(ROOT / 'snesrecomp/runner/src/desktop'), str(source),
        str(ROOT / 'snesrecomp/runner/src/util.c'), *shlex.split(libraries), '-o', str(exe)]
    result = subprocess.run(cmd, capture_output=True, text=True)
    (out / 'build.log').write_text(result.stdout + result.stderr)
    result.check_returncode()
    result = subprocess.run([str(exe)], cwd=out, capture_output=True, text=True, timeout=30)
    (out / 'run.log').write_text(result.stdout + result.stderr)
    result.check_returncode()
    receipt = json.loads(result.stdout)
    receipt.update(command=cmd, stderr=result.stderr,
        sources={str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest()
                 for p in inputs + [Path(__file__)]},
        scope='Real SDL3 virtual joystick/gamepad ranges plus actual SDK default GamepadMap lookup. No ROM, game execution, rendering, real controller button input or campaign claim.')
    (out / 'receipt.json').write_text(json.dumps(receipt, indent=2) + '\n')
    print(json.dumps(receipt, indent=2))

if __name__ == '__main__':
    main()
