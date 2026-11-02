"""Prepare and run private, source-pinned assisted scene-transition fixtures.

A plan names at most 24 incoming records in the owner's verified original ROM.
Each record has name, scene, kind (scene_warp or cop26), and physical offset.
No destination bytes or game data are embedded in this public helper. Each case
starts from the same private checkpoint, dismisses the source-observed scene
banner through controller input, then requests the original incoming tuple.
These visits are assisted engine coverage, not natural campaign progression.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re

from check_assisted_routes import run
from check_native_routes import ROOT, sha


def integer(value):
    return int(value, 0) if isinstance(value, str) else int(value)


def incoming(image: bytes, record: dict) -> dict:
    name = record.get('name', '')
    if not re.fullmatch(r'[a-z0-9][a-z0-9-]{0,63}', name):
        raise ValueError('case names must be simple unique lower-case slugs')
    scene = integer(record['scene'])
    offset = integer(record['offset'])
    kind = record['kind']
    if not 1 <= scene <= 0xF9 or kind not in ('scene_warp', 'cop26'):
        raise ValueError('only ordinary nonzero scene IDs and known source records are accepted')
    size = 12 if kind == 'scene_warp' else 10
    if offset < 0 or offset + size > len(image):
        raise ValueError('source record lies outside the verified original ROM')
    raw = image[offset:offset + size]
    if kind == 'cop26' and raw[:2] != b'\x02\x26':
        raise ValueError('COP26 source must begin at the actual COP opcode and argument')
    if kind == 'scene_warp' and raw[0] >= 0x80:
        raise ValueError('source is a warp delimiter or unsupported rectangle')
    payload = raw[4:] if kind == 'scene_warp' else raw[2:]
    if payload[0] != scene:
        raise ValueError('the source record destination does not match the requested scene')
    # Stock $82AA5A..AAF1 establishes return context for scene_warp rows.
    # Ordinary rows always set AF4/AF6; bit7 rows additionally set AF0/AF2
    # and clear bit7 in the effective incoming flags. COP26's special branch
    # has a different actor-script context and remains deliberately unsupported.
    context = None
    if kind == 'scene_warp':
        if offset >> 16 != 1:
            raise ValueError('stock scene_warp records must reside in bank81')
        context = ((offset + 4) & 0xFFFF).to_bytes(2, 'little').hex() + '81'
    elif payload[5] & 0x80:
        raise ValueError('special COP26 actor context requires a separate verified fixture')
    return dict(record, name=name, scene=scene, kind=kind, offset=offset,
                source_sha256=hashlib.sha256(raw).hexdigest(),
                pending_hex=f'{scene:02x}00',
                return_context_hex=context, set_exit_context=bool(payload[5] & 0x80),
                parameters_hex=(payload[1:5] + bytes((payload[5] & 0x7F, 0)) + payload[6:8]).hex())


def route(record: dict, dismiss_button: str = 'a') -> str:
    if dismiss_button not in ('a', 'left'):
        raise ValueError('only reviewed controller dismissal stimuli are accepted')
    dismiss_frames = 12 if dismiss_button == 'a' else 2
    context = ''
    if record['return_context_hex']:
        context += f"poke 0AF4 {record['return_context_hex']} # Stock warp writer return-context pointer, row+4 in bank81.\n"
        if record['set_exit_context']:
            context += f"poke 0AF0 {record['return_context_hex']} # Original bit7 incoming row also establishes special exit context.\n"
    return f'''# Assisted source-pinned transition; source {record['kind']} offset {record['offset']:06X}.
loadstate 0
wait 20
# $83DA8A..DAA4 waits for processed controller input while a scene title is shown.
press a 2
wait 30
until16 00B4 == 0000 90
dump ready
{context}poke 064C {record['parameters_hex']} # Original incoming spawn/flags/extra tuple; no player/story/ability writes.
poke 0642 {record['pending_hex']} # Original incoming destination; loader must set current scene itself.
until 0644 == {record['scene']:02X} 300
until 0642 == 00 300
wait 240
press {dismiss_button} {dismiss_frames}
wait 30
until16 00B4 == 0000 90
dump arrived
savestate 1
# Bounded controller stimulus. No movement-rate or coordinate modification.
press left 12
wait 12
press right 12
wait 12
press b 8
wait 24
press start 2
wait 20
dump menu
press start 2
wait 20
dump final
'''


def inspect_case(output: Path, record: dict, receipt: dict) -> dict:
    entries = {s['tag']: s for s in receipt['snapshots']}
    checks = dict(runner_passed=receipt['passed'])
    observed = {}
    for tag in ('ready', 'arrived', 'final'):
        p = output / 'snapshots' / f'{tag}.wram.bin'
        data = p.read_bytes() if p.is_file() else b''
        entry = entries.get(tag, {})
        if len(data) != 0x20000:
            checks[tag + '_complete'] = False
            continue
        state = dict(scene=data[0x644], pending=data[0x642],
                     banner=int.from_bytes(data[0xB4:0xB6], 'little'),
                     player=int.from_bytes(data[0x9AA:0x9AC], 'little'),
                     hp=int.from_bytes(data[0xACE:0xAD0], 'little'),
                     max_hp=int.from_bytes(data[0xACA:0xACC], 'little'),
                     control_flags=int.from_bytes(data[0x9AE:0x9B0], 'little'),
                     event_flags=int.from_bytes(data[0x9EC:0x9EE], 'little'),
                     nonblack=entry.get('nonblack_pixels', 0),
                     framebuffer_sha256=entry.get('framebuffer_sha256'),
                     x=int.from_bytes(data[0x1014:0x1016], 'little'),
                     y=int.from_bytes(data[0x1016:0x1018], 'little'))
        observed[tag] = state
        if tag == 'ready':
            checks['seed_banner_dismissed'] = state['banner'] == 0
        if tag != 'ready':
            checks[tag + '_destination'] = state['scene'] == record['scene']
            checks[tag + '_request_consumed'] = state['pending'] == 0
            checks[tag + '_banner_dismissed'] = state['banner'] == 0
            checks[tag + '_player'] = state['player'] == 0x1000
            checks[tag + '_hp_positive'] = state['hp'] > 0
            checks[tag + '_visible'] = state['nonblack'] > 0
    if 'ready' in observed and 'arrived' in observed:
        checks['destination_differs_from_seed'] = observed['ready']['scene'] != record['scene']
        checks['render_changed'] = observed['ready']['framebuffer_sha256'] != observed['arrived']['framebuffer_sha256']
    checkpoint = output / 'saves/save1.sav'
    checks['area_checkpoint_present'] = checkpoint.is_file() and checkpoint.stat().st_size > 0
    result = dict(schema='iog-assisted-transition-v1', passed=all(checks.values()),
                  checks=checks, source=record, observations=observed,
                  checkpoint=str(checkpoint), checkpoint_sha256=sha(checkpoint) if checkpoint.is_file() else None,
                  scope='Source-pinned assisted scene visit and bounded inputs; no story/ability/combat/campaign qualification.')
    if 'arrived' in observed and 'final' in observed:
        result['movement_delta'] = [observed['final'][axis] - observed['arrived'][axis] for axis in ('x', 'y')]
        result['movement_observed'] = any(result['movement_delta'])
    result['inventory_scene_observed'] = any(s.get('scene') == 0xFF for s in entries.values())
    (output / 'transition-receipt.json').write_text(json.dumps(result, indent=2) + '\n')
    return result


def self_test():
    # Synthetic records check schema/width preservation without a ROM or engine.
    image = bytes(0x10000) + bytes((1, 2, 3, 4, 8, 0x50, 0, 0xA0, 0, 3, 0, 0x12))
    got = incoming(image, dict(name='test', scene=8, offset=0x10000, kind='scene_warp'))
    assert got['parameters_hex'] == '5000a00003000012'
    assert got['pending_hex'] == '0800'
    assert 'poke 0644' not in route(got) and 'press a 2' in route(got)
    assert got['return_context_hex'] == '040081'
    failures = [dict(name='bad/name', scene=8, offset=0x10000, kind='scene_warp'),
                dict(name='bad', scene=9, offset=0x10000, kind='scene_warp'),
                dict(name='bad', scene=8, offset=0x10001, kind='scene_warp'),
                dict(name='bad', scene=8, offset=0, kind='cop26')]
    for bad in failures:
        try:
            incoming(image, bad)
        except ValueError:
            pass
        else:
            raise AssertionError('invalid source record accepted')
    special = bytearray(image); special[0x10009] |= 0x80
    got = incoming(special, dict(name='special', scene=8, offset=0x10000, kind='scene_warp'))
    assert got['set_exit_context'] and got['parameters_hex'] == '5000a00003000012'
    assert 'poke 0AF0 040081' in route(got)
    print('10 ROM-free transition preparation checks passed')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--self-test', action='store_true')
    for name in ('plan', 'rom', 'binary', 'seed-state', 'output'):
        parser.add_argument('--' + name, type=Path)
    parser.add_argument('--interpret-all', action='store_true')
    parser.add_argument('--wide', action='store_true')
    parser.add_argument('--infinite-hp', action='store_true')
    parser.add_argument('--prepare-only', action='store_true')
    parser.add_argument('--dismiss-button', choices=('a', 'left'), default='a',
                        help='A preserves the first collection; left avoids item-use dialogue after title-free entries')
    args = parser.parse_args()
    if args.self_test:
        self_test(); return 0
    if any(getattr(args, name) is None for name in ('plan', 'rom', 'binary', 'seed_state', 'output')):
        parser.error('--plan, --rom, --binary, --seed-state and --output are required')
    output = args.output.resolve()
    if not output.is_relative_to((ROOT / '.local').resolve()):
        parser.error('all fixture artifacts must remain in the private .local directory')
    image = args.rom.read_bytes()
    expected = re.search(r'^expected_sha256\s*=\s*(\w+)', (ROOT / 'rom_identity.txt').read_text(), re.M)[1]
    if len(image) != 2097152 or hashlib.sha256(image).hexdigest() != expected:
        parser.error('verified bare USA ROM required')
    plan = json.loads(args.plan.read_text())
    if not isinstance(plan.get('cases'), list) or not 1 <= len(plan['cases']) <= 24:
        parser.error('a named, source-reviewed cohort of 1..24 cases is required')
    records = [incoming(image, record) for record in plan['cases']]
    if len({record['name'] for record in records}) != len(records):
        parser.error('case names must be unique')
    output.mkdir(parents=True, exist_ok=False)
    results = []
    for record in records:
        script = output / (record['name'] + '.txt')
        script.write_text(route(record, args.dismiss_button), encoding='utf-8')
        item = dict(source=record, script=str(script), script_sha256=sha(script), frames=600)
        if not args.prepare_only:
            destination = output / record['name']
            receipt = run(args.binary.resolve(), args.rom.resolve(), script, destination, 600,
                          args.seed_state.resolve(), 1, args.interpret_all, record['scene'], 180,
                          capture=True, wide=args.wide, infinite_hp=args.infinite_hp)
            item['result'] = inspect_case(destination, record, receipt)
            print(json.dumps(dict(name=record['name'], passed=item['result']['passed'],
                                  failed_checks=[k for k, v in item['result']['checks'].items() if not v],
                                  final=item['result']['observations'].get('final'))), flush=True)
        results.append(item)
    summary = dict(schema='iog-assisted-transition-collection-v1',
                   prepared_only=args.prepare_only,
                   passed=None if args.prepare_only else all(item['result']['passed'] for item in results),
                   binary_sha256=sha(args.binary), rom_sha256=expected, seed_sha256=sha(args.seed_state),
                   plan_sha256=sha(args.plan), interpret_all=args.interpret_all, wide=args.wide,
                   infinite_hp=args.infinite_hp, cases=results)
    summary['dismiss_button'] = args.dismiss_button
    (output / 'collection.json').write_text(json.dumps(summary, indent=2) + '\n')
    return 0 if args.prepare_only or summary['passed'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
