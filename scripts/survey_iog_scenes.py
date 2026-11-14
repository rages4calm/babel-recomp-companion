#!/usr/bin/env python3
"""Bounded private Original-USA scene entry survey; never grants visual approval."""
import argparse
from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import threading
import time

ROOT = Path(__file__).resolve().parents[1]
PRIVATE = (ROOT / '.local').resolve()
ROM_SHA = '32adc048fd89228a4310c03df243e83de7d436cdb2460b4cc83ade20d359b2bd'


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def scenes(value):
    tokens = value.split(',')
    if not 1 <= len(tokens) <= 32 or any(not re.fullmatch(r'[0-9a-fA-F]{2}', t) for t in tokens):
        raise argparse.ArgumentTypeError('Use 1..32 explicit two-digit hexadecimal IDs separated by commas')
    ids = [int(t, 16) for t in tokens]
    if len(set(ids)) != len(ids) or any(i >= 0xF0 for i in ids):
        raise argparse.ArgumentTypeError('IDs must be unique and below F0')
    return ids


def private_path(path):
    path = path.resolve()
    if not path.is_relative_to(PRIVATE):
        raise ValueError('Fixture, seed and output must remain under project .local/')
    return path


def route(scene, frames=600, incoming=None):
    if incoming is None or not re.fullmatch(r'[0-9a-fA-F]{16}', incoming):
        raise ValueError('An explicit source-validated incoming recipe is required')
    return (f'loadstate 0\nwait 20\n'
            'poke 0AF4 208e81\n'
            f'poke 064C {incoming.lower()}\n'
            f'poke 0642 {scene:02x}00\n'
            'until 0642 == 00 300\n'
            f'until 0644 == {scene:02x} 300\n'
            f'wait {max(240, frames - 120)}\ndump settled\n')


def incoming_catalog(path, requested):
    if path is None:
        return {}, None
    path = private_path(path)
    catalog = json.loads(path.read_text())
    if catalog.get('schema') != 'iog-authentic-incoming-catalog-v1':
        raise ValueError('Unsupported incoming catalog schema')
    source = private_path(Path(catalog['source']['path']))
    if sha(source) != catalog['source']['sha256']:
        raise ValueError('Incoming catalog source hash mismatch')
    lines = source.read_text().splitlines()
    recipes = {}
    for scene in requested:
        key = f'{scene:02X}'
        record = catalog['recipes'].get(key)
        if record is None:
            continue
        number = record['source_line']
        if type(number) is not int or not 1 <= number <= len(lines):
            raise ValueError('Invalid incoming source line: ' + key)
        match = re.fullmatch(r'\s*scene-warp\s*<\s*(.*?)\s*>\s*(?:;.*)?', lines[number-1])
        fields = match[1].split(',') if match else []
        if len(fields) != 9 or any(not re.fullmatch(r'\s*#\$?[0-9A-Fa-f]{2,4}\s*', t) for t in fields):
            raise ValueError('Incoming provenance is not a literal scene-warp: ' + key)
        values = [int(t.strip().lstrip('#$'), 16) for t in fields]
        if any(value > 255 for value in values[:5]):
            raise ValueError('Non-byte warp trigger/destination fields: ' + key)
        headers = re.findall(r'^warp_def_([0-9A-Fa-f]{2})\s*\[', '\n'.join(lines[:number]), re.M)
        if not headers or headers[-1].upper() != record['source_scene'].upper() or values[4] != scene:
            raise ValueError('Incoming source/destination mismatch: ' + key)
        x, y, facing, window = values[5:]
        if x > 65535 or y > 65535 or facing > 255 or not 0 < window <= 65535:
            raise ValueError('Invalid literal incoming fields: ' + key)
        bounds = [(window & 15)*256, ((window >> 4)&15)*256,
                  ((window >> 8)&15)*256, ((window >> 12)&15)*256]
        if bounds[2]-bounds[0] < 256 or bounds[3]-bounds[1] < 256:
            raise ValueError('Invalid incoming camera window: ' + key)
        incoming = (x.to_bytes(2, 'little') + y.to_bytes(2, 'little') + bytes([facing, 0]) + window.to_bytes(2, 'little')).hex()
        if incoming.lower() != record['incoming_hex'].lower():
            raise ValueError('Catalog tuple disagrees with Original warp source: ' + key)
        recipes[scene] = {'incoming_hex': incoming, 'source_line': number,
                          'source_scene': record['source_scene'].upper(),
                          'destination': [x, y], 'facing': facing,
                          'camera_window': window, 'authored_bounds': bounds,
                          'original_record_hex': (bytes(values[:5]) + x.to_bytes(2, 'little') + y.to_bytes(2, 'little') + bytes([facing]) + window.to_bytes(2, 'little')).hex()}
    return recipes, {'catalog': str(path), 'catalog_sha256': sha(path),
                     'source': str(source), 'source_sha256': sha(source)}


def ram_metadata(path):
    path = Path(path)
    if not path.exists() or path.stat().st_size != 131072:
        return None
    ram = path.read_bytes()
    word = lambda at: int.from_bytes(ram[at:at+2], 'little')
    actor = word(0x09F4)
    position = [word(actor+0x14), word(actor+0x16)] if 0x1000 <= actor < 0x1FC0 and (actor-0x1000) % 0x30 == 0 else None
    extent = [word(0x0692), word(0x0696)]
    return {'scene': word(0x0644), 'pending_scene': word(0x0642),
            'player_actor': actor, 'position': position, 'primary_map_extent': extent,
            'position_inside_primary_allocation': (0 <= position[0] < extent[0] and 0 <= position[1] < extent[1]) if position else None,
            'hp': word(0x0ACE), 'max_hp': word(0x0ACA), 'alive': word(0x0ACE) > 0,
            'control_flags': word(0x09EC), 'wram_sha256': sha(path)}


def capture_metadata(output, frame):
    source_path = Path(output) / 'world.ppm.source.json'
    source = json.loads(source_path.read_text()) if source_path.exists() else None
    ram = ram_metadata(Path(output) / 'world.ppm.active.wram.bin')
    bound = bool(source and source.get('frame') == frame and ram and source.get('scene') == ram['scene'])
    return source, ram if bound else None, bound


def fixture_inventory(fixture):
    result = {}
    for path in [fixture / 'config.ini', *sorted((fixture / 'mods').rglob('*'))]:
        stat = path.lstat()
        if path.is_symlink() or getattr(stat, 'st_file_attributes', 0) & 0x400:
            raise ValueError('Fixture links/reparse points are refused: ' + str(path))
        if path.is_file():
            result[str(path.relative_to(fixture))] = {'sha256': sha(path), 'bytes': stat.st_size}
    if not (fixture / 'mods').is_dir() or len(result) > 5000 or sum(x['bytes'] for x in result.values()) > 32 * 1024 * 1024:
        raise ValueError('Missing mods or oversized fixture metadata')
    return result


def run_case(args, scene):
    output = args.output / f'{scene:02X}'
    output.mkdir()
    (output / 'saves').mkdir(); (output / 'snapshots').mkdir()
    shutil.copy2(args.seed, output / 'saves/save0.sav')
    shutil.copytree(args.fixture / 'mods', output / 'mods')
    config = (args.fixture / 'config.ini').read_text()
    overrides = {'OutputMethod': 'SDL-Software', 'Fullscreen': '0',
                 'WindowSize': '1920x1080', 'DisableFrameDelay': '1', 'EnableAudio': '0'}
    for key, value in overrides.items():
        config, count = re.subn(r'(?m)^' + re.escape(key) + r'\s*=.*$', key + ' = ' + value, config)
        if count != 1:
            raise ValueError('Expected one fixture setting: ' + key)
    (output / 'config.ini').write_text(config)
    (output / 'route.txt').write_text(route(scene, args.frames, args.recipes[scene]['incoming_hex']))
    env = {k: v for k, v in os.environ.items() if not k.startswith(('IOG_', 'SNESRECOMP_'))}
    env.update(SDL_VIDEODRIVER='dummy', SDL_AUDIODRIVER='dummy',
        SNESRECOMP_RUN_FRAMES=str(args.frames), SNESRECOMP_LOG_FILE='0',
        SNESRECOMP_DUMP_DIR=str(output / 'snapshots'), IOG_WORLD_RENDERER='1',
        IOG_WORLD_VIEW_EXTENT='1.5', IOG_WORLD_SURVEY_SCENE=f'{scene:02X}',
        IOG_RENDERER_AUDIT=str(output / 'renderer.jsonl'), IOG_WORLD_SOURCE_PACKET='1',
        IOG_WORLD_OUTPUT=str(output / 'world.ppm'), IOG_WORLD_OUTPUT_FRAME=str(args.frames - 10))
    for name in ('CONTINUATIONS', 'RDNMI_POLL', 'NMI_CONTINUATIONS', 'FRAME_CONTINUATIONS', 'WRAM_COPY_CONTINUATIONS'):
        env['IOG_NATIVE_' + name] = '1'
    cmd = [str(args.binary), '--no-launcher', '--rom', str(args.rom), '--config',
           str(output / 'config.ini'), '--script', str(output / 'route.txt')]
    launch = {'command': cmd, 'producer_sha256': args.producer_sha256,
              'incoming_recipe': args.recipes[scene],
              'environment_overrides': {k: v for k, v in env.items()
              if k.startswith(('IOG_', 'SNESRECOMP_', 'SDL_'))}, 'script_sha256': sha(output / 'route.txt')}
    (output / 'LAUNCH.json').write_text(json.dumps(launch, indent=2) + '\n')
    if sha(__file__) != args.producer_sha256:
        raise ValueError('Survey producer changed after PLAN freeze; refusing launch')
    if (sha(args.incoming_identity['catalog']) != args.incoming_identity['catalog_sha256'] or
            sha(args.incoming_identity['source']) != args.incoming_identity['source_sha256']):
        raise ValueError('Incoming catalog/source changed after PLAN freeze; refusing launch')
    began = time.monotonic(); error = None; code = None
    log_limit = 4 * 1024 * 1024; log = bytearray(); total_log_bytes = [0]
    process = subprocess.Popen(cmd, cwd=output, env=env, stdout=subprocess.PIPE,
                               stderr=subprocess.STDOUT)
    def drain():
        while chunk := process.stdout.read(65536):
            total_log_bytes[0] += len(chunk)
            log.extend(chunk[:max(0, log_limit - len(log))])
    reader = threading.Thread(target=drain, daemon=True); reader.start()
    try:
        code = process.wait(timeout=60)
    except subprocess.TimeoutExpired:
        error = 'process_timeout_60s'; process.kill(); code = process.wait()
    reader.join(timeout=5)
    if reader.is_alive():
        error = error or 'log_pipe_did_not_close'
    log_truncated = total_log_bytes[0] > log_limit
    (output / 'run.log').write_bytes(log)
    text = log.decode('utf-8', errors='replace')
    snapshot = ram_metadata(output / 'snapshots/settled.wram.bin')
    source, capture_ram, capture_bound = capture_metadata(output, args.frames - 10)
    rows = []
    audit = output / 'renderer.jsonl'
    if audit.exists():
        rows = [json.loads(line) for line in audit.read_text().splitlines()]
    final = next((row for row in reversed(rows) if 'reason' in row), None)
    regs_path = output / 'snapshots/settled.regs.json'
    ppu = json.loads(regs_path.read_text()) if regs_path.exists() else None
    script_errors = [line for line in text.splitlines() if re.search(r'script.*(timed out|timeout|unknown|cannot open|bad)', line, re.I)]
    checks = {'process_exit_zero': code == 0, 'no_process_timeout': error is None,
              'log_not_truncated': not log_truncated, 'script_settled_dump': 'dump settled ok' in text,
              'no_script_error': not script_errors, 'requested_scene_entered': snapshot is not None and snapshot['scene'] == scene,
              'snapshot_complete': snapshot is not None, 'picture_exported': (output / 'world.ppm').is_file()}
    result = {'scene': scene, 'hex': f'{scene:02X}', 'entry_checks_passed': all(checks.values()),
              'checks': checks, 'exit_code': code, 'error': error, 'script_errors': script_errors,
              'elapsed_seconds': round(time.monotonic()-began, 3), 'snapshot': snapshot,
              'ppu_mode': ppu['bgmode'] & 7 if ppu else None,
              'ppu_inidisp': ppu.get('inidisp') if ppu else None,
              'capture_source_schema': source.get('schema') if source else None,
              'capture_frame': source.get('frame') if source else None,
              'capture_bound_snapshot': capture_ram if capture_bound else None,
              'visual_classification_metadata': 'capture_bound' if capture_bound else 'unavailable_or_unpaired_do_not_use_probe_as_capture',
              'capture_scene_matches_request': capture_ram['scene'] == scene if capture_bound else None,
              'probe_and_capture_extents_match': snapshot['primary_map_extent'] == capture_ram['primary_map_extent'] if snapshot and capture_bound else None,
              'final_renderer_state': final, 'visually_approved': False,
              'scope': 'Assisted entry at fixed incoming coordinates; fallback/readiness is not visual approval or campaign progress'}
    (output / 'RECEIPT.json').write_text(json.dumps(result, indent=2) + '\n')
    return result


def safe_case(args, scene):
    try:
        return run_case(args, scene)
    except Exception as error:
        result = {'scene': scene, 'hex': f'{scene:02X}', 'entry_checks_passed': False,
                  'visually_approved': False, 'error': type(error).__name__ + ': ' + str(error)}
        output = args.output / f'{scene:02X}'
        output.mkdir(exist_ok=True)
        (output / 'RECEIPT.json').write_text(json.dumps(result, indent=2) + '\n')
        return result


def main():
    p = argparse.ArgumentParser(description=__doc__)
    for name in ('binary', 'seed', 'rom', 'fixture', 'output'):
        p.add_argument('--' + name, type=Path, required=True)
    p.add_argument('--scenes', type=scenes, required=True)
    p.add_argument('--frames', type=int, default=600)
    p.add_argument('--jobs', type=int, default=1)
    p.add_argument('--plan', action='store_true', help='Write plan only; no game or ROM read')
    p.add_argument('--incoming-catalog', type=Path, help='Private source-validated Original inbound warp recipes; required for execution')
    args = p.parse_args()
    try:
        if not 400 <= args.frames <= 1000 or not 1 <= args.jobs <= 2:
            raise ValueError('Frames must be 400..1000 and jobs 1..2')
        for name in ('seed', 'fixture', 'output'):
            setattr(args, name, private_path(getattr(args, name)))
        args.binary = private_path(args.binary); args.rom = args.rom.resolve()
        if args.output.exists():
            raise ValueError('Use a new output directory; existing evidence is not overwritten')
        if args.output.is_relative_to(args.fixture):
            raise ValueError('Survey output may not be nested inside the input fixture')
        fixture_files = fixture_inventory(args.fixture)
        seed_hash = sha(args.seed)
        args.recipes, incoming_identity = incoming_catalog(args.incoming_catalog, args.scenes)
        args.incoming_identity = incoming_identity
        missing = [f'{scene:02X}' for scene in args.scenes if scene not in args.recipes]
        if not args.plan:
            if missing:
                raise ValueError('Missing authentic incoming recipes: ' + ','.join(missing))
            if not args.binary.is_file() or args.rom.stat().st_size != 2097152 or sha(args.rom) != ROM_SHA:
                raise ValueError('Existing binary and exact bare Original-USA ROM required')
            rom = args.rom.read_bytes()
            for scene, recipe in args.recipes.items():
                needle = bytes.fromhex(recipe['original_record_hex'])
                offsets = []; start = 0
                while (at := rom.find(needle, start)) >= 0:
                    offsets.append(at); start = at + 1
                if not offsets:
                    raise ValueError(f'Incoming source record absent from verified Original ROM: {scene:02X}')
                recipe['original_rom_matching_record_offsets'] = offsets
        args.output.mkdir(parents=True)
        plan = {'schema': 'iog-bounded-scene-survey-v1', 'plan_only': args.plan,
                'producer_sha256': sha(__file__),
                'binary': str(args.binary), 'binary_sha256': sha(args.binary) if args.binary.exists() else None,
                'rom': str(args.rom), 'expected_rom_sha256': ROM_SHA, 'rom_validation_deferred': args.plan,
                'seed': str(args.seed), 'seed_sha256': seed_hash, 'fixture': str(args.fixture),
                'fixture_files': fixture_files, 'frames': args.frames, 'jobs': args.jobs,
                'incoming_provenance': incoming_identity, 'missing_incoming_recipes': missing,
                'cases': [{'scene': scene, 'hex': f'{scene:02X}',
                           'incoming_recipe': args.recipes.get(scene),
                           'script': route(scene, args.frames, args.recipes[scene]['incoming_hex']) if scene in args.recipes else None} for scene in args.scenes],
                'assistance': 'Private seed, verified original inbound pose/facing/camera window and pending scene request; retained stock return context. Story prerequisites are not established; no all-flags/enemy/outcome writes',
                'visually_approved': False}
        (args.output / 'PLAN.json').write_text(json.dumps(plan, indent=2) + '\n')
        args.producer_sha256 = plan['producer_sha256']
        if args.plan:
            print('PLAN ONLY:', ','.join(f'{scene:02X}' for scene in args.scenes)); return
        with ThreadPoolExecutor(max_workers=args.jobs) as pool:
            results = list(pool.map(lambda scene: safe_case(args, scene), args.scenes))
        inputs_unchanged = (sha(args.seed) == seed_hash and fixture_inventory(args.fixture) == fixture_files and
                            sha(args.binary) == plan['binary_sha256'] and sha(args.rom) == ROM_SHA and
                            sha(incoming_identity['catalog']) == incoming_identity['catalog_sha256'] and
                            sha(incoming_identity['source']) == incoming_identity['source_sha256'])
        producer_unchanged = sha(__file__) == plan['producer_sha256']
        (args.output / 'SURVEY.json').write_text(json.dumps({'plan_sha256': sha(args.output / 'PLAN.json'),
            'cases': results, 'entry_checks_passed': sum(r['entry_checks_passed'] for r in results),
            'visually_approved': False, 'inputs_unchanged': inputs_unchanged,
            'producer_unchanged': producer_unchanged,
            'diagnostic_only': not inputs_unchanged or not producer_unchanged}, indent=2) + '\n')
        print('SURVEY:', len(results), 'cases;', sum(r['entry_checks_passed'] for r in results), 'entry checks passed; zero visual approvals')
    except (ValueError, OSError) as error:
        p.error(str(error))


if __name__ == '__main__':
    main()
