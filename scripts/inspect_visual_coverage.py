#!/usr/bin/env python3
"""Inventory scene presentation policy without executing or reading a ROM.

Source admission is not visual approval. Optional private source-index and
closed manual-test receipts refine labels/evidence, never renderer eligibility.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
SAMPLES = {0x08: 'Classroom', 0x01: 'South Cape', 0x0E: 'Aqueduct',
           0x85: 'Great Wall', 0x4F: 'Sky Garden', 0x55: 'Viper',
           0xEA: 'Solid Arm', 0xCC: 'Pyramid'}
PRIORITY = {0x0D: 'Aqueduct exit', 0x4C: 'Sky Garden hub / Viper exit',
            0x83: 'Great Wall adjoining room'}


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def function(text, name):
    match = re.search(r'\b' + re.escape(name) + r'\s*\([^;{}]*\)\s*\{', text)
    if not match:
        raise ValueError('Missing source function: ' + name)
    start = match.end() - 1
    depth = 0
    for pos in range(start, len(text)):
        if text[pos] == '{':
            depth += 1
        elif text[pos] == '}':
            depth -= 1
            if not depth:
                return text[start:pos + 1]
    raise ValueError('Unclosed source function: ' + name)


def cases(body):
    return {int(token, 16) for token in re.findall(r'\bcase\s+0x([0-9A-Fa-f]+)\s*:', body)}


def effect_scenes(body):
    # The current explicit predicate is an OR of scene comparisons. Refuse a
    # changed policy rather than silently interpreting arbitrary C as a list.
    cleaned = re.sub(r'/\*.*?\*/|//[^\n]*', '', body, flags=re.S).strip('{} \n\r')
    match = re.fullmatch(r'return\s+(.+);\s*', cleaned, re.S)
    if not match or not re.fullmatch(r'\s*scene\s*==\s*0x[0-9A-Fa-f]+(?:\s*\|\|\s*scene\s*==\s*0x[0-9A-Fa-f]+)*\s*', match[1]):
        raise ValueError('EffectPlaneScene policy changed; update this inspector')
    return {int(x, 16) for x in re.findall(r'0x([0-9A-Fa-f]+)', match[1])}


def manual_evidence(path):
    if path is None:
        return None
    path = path.resolve()
    if not path.is_relative_to((ROOT / '.local').resolve()):
        raise ValueError('Visual evidence must be a private project receipt')
    complete = json.loads(path.read_text())
    if complete.get('passed') is not True:
        raise ValueError('Visual receipt did not pass')
    for name, expected in complete['receipts'].items():
        target = (path.parent / name).resolve()
        if not target.is_relative_to(path.parent) or sha(target) != expected:
            raise ValueError('Visual receipt dependency mismatch: ' + name)
    build = json.loads((path.parent / 'build-v2.json').read_text())
    gpu = json.loads((path.parent / 'GPU-v2.json').read_text())
    if build['binary_sha256'] != complete['binary_sha256']:
        raise ValueError('Visual build identity mismatch')
    if gpu.get('passed') is not True or {row['slot'] for row in gpu['checks'] if row['passed']} != set(range(1, 9)):
        raise ValueError('Eight GPU samples are not all present')
    relevant = ['src/iog_world_renderer.c', 'src/iog_visual_objects.c',
                'src/iog_scene_view.c', 'src/iog_world_view.c',
                'src/iog_world_pixels.c', 'src/iog_widescreen.c']
    current = all(sha(ROOT / name) == build['source_catalog'].get(name) for name in relevant)
    return {'receipt': str(path.relative_to(ROOT)), 'receipt_sha256': sha(path),
            'binary_sha256': complete['binary_sha256'],
            'renderer_dependencies_match_current_source': current,
            'scope': 'Eight bounded assisted samples, not complete scene/phase approval'}


def inventory(scene_index=None, visual_receipt=None):
    paths = {name: ROOT / ('src/' + name) for name in
             ['iog_world_renderer.c', 'iog_visual_objects.c', 'iog_widescreen.c']}
    texts = {name: path.read_text() for name, path in paths.items()}
    world = texts['iog_world_renderer.c']
    admitted = cases(function(texts['iog_visual_objects.c'], 'IogVisualObjectsSupportsScene'))
    bounded = cases(function(world, 'BoundedRoomScene'))
    effects = effect_scenes(function(world, 'EffectPlaneScene'))
    capture = function(world, 'IogWorldCaptureLine')
    mode1_capture_gate = bool(re.search(r'bgmode\s*&\s*7\)\s*!=\s*1', capture))
    mode7_plane = all(name in world for name in ('Mode7PlaneLayout', 'RenderMode7Plane'))
    mode7_plane = mode7_plane and 'RenderMode7Plane()' in function(world, 'RenderWorld')
    generic_camera = 'ReadEffectCamera' in world
    generic_window = 'AuthoredWindow' in world
    calibrated_perspective = mode7_plane and all(name in world for name in
        ('IogMode7PerspectiveMatches', 'IogMode7PerspectiveSample', 'ready_mode7_perspective'))
    raster_band = mode7_plane and 'ready_mode7_raster_band' in world
    deferred_raster_camera = 'ready_legacy_raster_effect' in world
    if not effects <= admitted or not bounded <= admitted:
        raise ValueError('Scene policies disagree with supported-scene admission')
    unused = set()
    index_identity = None
    if scene_index:
        index = scene_index.resolve()
        data = index.read_text()
        unused = {int(x, 16) for x in re.findall(r'^\s*&scene_default_actors\s*;\s*([0-9A-Fa-f]{2})\s*$', data, re.M)}
        if not unused:
            raise ValueError('No explicit default-scene aliases in supplied index')
        index_identity = {'path': str(index), 'sha256': sha(index),
                          'interpretation': 'Shared default-record aliases; source classification, not runtime unreachability proof'}
    evidence = manual_evidence(visual_receipt)
    scenes = []
    for scene in range(256):
        sampled = scene in SAMPLES and evidence is not None
        current = sampled and evidence['renderer_dependencies_match_current_source']
        scenes.append({'scene': scene, 'hex': f'{scene:02X}',
            'label': SAMPLES.get(scene, PRIORITY.get(scene)),
            'source_index_class': 'default_record_alias' if scene in unused else 'not_classified_unused',
            'independent_world_format_admitted': scene in admitted,
            'authored_window_policy': scene in bounded,
            'generic_authored_window_candidate': generic_window and scene in admitted,
            'explicit_secondary_camera_model': scene in effects,
            'mode1_policy': 'conditionally_admitted' if scene in admitted else 'original_field_fallback',
            'mode7_scene_assignment': 'not_inferred_from_scene_id',
            'visual_evidence': ('bounded_current_renderer_sample' if current else
                                'historical_bounded_sample' if sampled else 'unreviewed'),
            'full_scene_visual_approval': False,
            'priority': 'adjacent_to_manual_save' if scene in PRIORITY else
                        'preserve_manual_save_fix' if scene in SAMPLES else 'full_game_sweep'})
    return {'schema': 'gaia-visual-coverage-inventory-v1',
        'scope': 'Static source policy and separately bound visual evidence; no game execution or ROM read',
        'sources': {str(path.relative_to(ROOT)): sha(path) for path in paths.values()},
        'scene_index': index_identity, 'manual_visual_evidence': evidence,
        'secondary_camera': {'legacy_scene_fallback_models': len(effects),
                             'generic_live_producer_reader_present': generic_camera,
                             'unbound_raster_producer_deferred': deferred_raster_camera,
                             'raster_limitation': 'Per-line HDMA camera derivatives are not established by a global actor ratio; deferred raster paths need visual review',
                             'scope': 'Structural producer support is not room-by-room runtime/visual qualification'},
        'authored_window': {'generic_live_window_reader_present': generic_window,
                            'scope': 'Conditional source-window framing; neither full scene admission nor secondary outdoor-plane extent approval'},
        'mode7': {'independent_world_uniform_plane_structural_support': bool(mode7_plane),
                  'calibrated_perspective_structural_support': bool(calibrated_perspective),
                  'perspective_validation': 'Extension requires calibrated parameters matching the captured original rows; no all-scene perspective claim',
                  'safe_captured_raster_band_structural_support': bool(raster_band),
                  'raster_band_limitation': 'Captured row transforms retain a bounded original-height band; unsupported vertical rows remain padding',
                  'independent_world_admitted': 'conditional_plane_perspective_or_captured_band' if calibrated_perspective or raster_band else 'conditional_uniform_plane' if mode7_plane else False if mode1_capture_gate else None,
                  'reason': ('Mode 7 layout-gated uniform plane, calibrated perspective and captured-raster-band paths are inventoried separately'
                             if calibrated_perspective or raster_band else 'Uniform Mode 7 plane sampler with layout/raster gates; nonuniform effects require separate qualification'
                             if mode7_plane else 'World raster capture requires Mode 1; generic widescreen has a separate Mode 7 margin path'
                             if mode1_capture_gate else 'World raster policy changed; independent Mode 7 admission needs review'),
                  'generic_margin_branch_present': bool(re.search(r'bgmode\s*&\s*7\)\s*==\s*7', texts['iog_widescreen.c'])),
                  'full_game_mode7_visual_approval': False},
        'summary': {'scene_ids': 256, 'default_record_aliases': len(unused),
                    'independent_world_format_admissions': len(admitted),
                    'explicit_secondary_camera_models': len(effects),
                    'bounded_current_renderer_samples': sum(s['visual_evidence'] == 'bounded_current_renderer_sample' for s in scenes),
                    'full_scene_visual_approvals': 0},
        'scenes': scenes}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--scene-index', type=Path, help='Optional external extracted scene-index source; never copied')
    parser.add_argument('--visual-receipt', type=Path, help='Optional private COMPLETE-v2.json from the manual-save correction')
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    output = args.output.resolve()
    if not output.is_relative_to((ROOT / '.local').resolve()):
        parser.error('Detailed inventory output must remain in ignored project .local/')
    if output.exists():
        parser.error('Use a new inventory filename; existing evidence is not overwritten')
    try:
        result = inventory(args.scene_index, args.visual_receipt)
    except (ValueError, KeyError, OSError) as error:
        parser.error(str(error))
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps(result['summary'], indent=2))


if __name__ == '__main__':
    main()
