"""ROM-free regression tests for source-validated survey incoming windows."""
import contextlib
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location('survey_under_test', ROOT/'scripts/survey_iog_scenes.py')
SURVEY = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(SURVEY)


class IncomingCatalogTests(unittest.TestCase):
    def setUp(self):
        base = ROOT/'.local/survey-incoming-tests'; base.mkdir(parents=True, exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(prefix='synthetic-', dir=base)
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.source = self.root/'synthetic-warp-source.asm'
        # Authored synthetic records; no ROM, extracted source or game assets.
        self.source.write_text('warp_def_20 [\n'
            ' scene-warp < #01, #02, #01, #01, #33, #$0028, #$00C0, #00, #$1100 >\n'
            ']\nwarp_def_21 [\n'
            ' scene-warp < #03, #04, #01, #01, #2D, #$0020, #$00A0, #07, #$1300 >\n'
            ']\nwarp_def_22 [\n'
            ' scene-warp < #05, #06, #01, #01, #39, #$0048, #$01C0, #00, #$2210 >\n'
            ']\n')
        self.catalog = self.root/'catalog.json'
        self.data = {'schema':'iog-authentic-incoming-catalog-v1',
            'source':{'path':str(self.source), 'sha256':hashlib.sha256(self.source.read_bytes()).hexdigest()},
            'recipes':{'33':{'source_line':2,'source_scene':'20','incoming_hex':'2800c00000000011'},
                       '2D':{'source_line':5,'source_scene':'21','incoming_hex':'2000a00007000013'},
                       '39':{'source_line':8,'source_scene':'22','incoming_hex':'4800c00100001022'}}}
        self.write()

    def write(self):
        self.catalog.write_text(json.dumps(self.data))

    def load(self, scenes=(0x33,0x2D,0x39)):
        return SURVEY.incoming_catalog(self.catalog, scenes)

    def test_authentic_small_room_never_inherits_512_window(self):
        recipes, identity = self.load()
        room = recipes[0x33]
        self.assertEqual(room['authored_bounds'], [0,0,256,256])
        self.assertEqual(room['camera_window'], 0x1100)
        script = SURVEY.route(0x33, 600, room['incoming_hex'])
        self.assertIn('poke 064C 2800c00000000011\n', script)
        self.assertNotIn('8000a00000000022', script)
        self.assertEqual(script.count('poke '), 3)
        self.assertEqual(identity['source_sha256'], self.data['source']['sha256'])

    def test_distinct_width_and_nonzero_floor_origin_preserved(self):
        recipes, _ = self.load()
        self.assertEqual(recipes[0x2D]['authored_bounds'], [0,0,768,256])
        self.assertEqual(recipes[0x39]['authored_bounds'], [0,256,512,512])
        self.assertEqual(recipes[0x39]['destination'], [72,448])

    def test_missing_recipe_has_no_silent_default(self):
        self.assertEqual(SURVEY.incoming_catalog(None, [0x33]), ({},None))
        recipes, _ = self.load([0x33,0x55])
        self.assertNotIn(0x55, recipes)
        with self.assertRaises(ValueError):
            SURVEY.route(0x55)

    def test_forged_2200_override_rejected(self):
        self.data['recipes']['33']['incoming_hex'] = '8000a00000000022'; self.write()
        with self.assertRaisesRegex(ValueError, 'tuple disagrees'):
            self.load()

    def test_modified_source_rejected(self):
        self.source.write_text(self.source.read_text()+'; changed after catalog\n')
        with self.assertRaisesRegex(ValueError, 'source hash mismatch'):
            self.load()

    def test_wrong_source_scene_rejected(self):
        self.data['recipes']['33']['source_scene'] = '21'; self.write()
        with self.assertRaisesRegex(ValueError, 'source/destination mismatch'):
            self.load()

    def test_wrong_destination_record_rejected(self):
        self.data['recipes']['33']['source_line'] = 5
        self.data['recipes']['33']['source_scene'] = '21'; self.write()
        with self.assertRaisesRegex(ValueError, 'source/destination mismatch'):
            self.load()

    def test_nonrecord_and_out_of_range_provenance_rejected(self):
        for line in (1,0,999,True):
            with self.subTest(line=line):
                self.data['recipes']['33']['source_line'] = line; self.write()
                with self.assertRaises(ValueError):
                    self.load()

    def test_execution_without_catalog_refused_before_rom_or_game(self):
        fixture = self.root/'fixture'; fixture.mkdir(); (fixture/'mods').mkdir()
        (fixture/'config.ini').write_text('[Graphics]\n')
        seed = self.root/'seed.sav'; seed.write_bytes(b'synthetic seed only')
        output = self.root/'must-not-be-created'
        args = ['survey_iog_scenes.py', '--binary',str(self.root/'absent.exe'),
            '--seed',str(seed), '--rom',str(self.root/'absent.sfc'),
            '--fixture',str(fixture), '--output',str(output),'--scenes','33']
        with mock.patch.object(sys,'argv',args), mock.patch.object(SURVEY.subprocess,'Popen') as launch, contextlib.redirect_stderr(io.StringIO()) as errors:
            with self.assertRaises(SystemExit) as stopped:
                SURVEY.main()
        self.assertEqual(stopped.exception.code,2)
        self.assertIn('Missing authentic incoming recipes', errors.getvalue())
        self.assertFalse(output.exists()); launch.assert_not_called()


if __name__ == '__main__':
    unittest.main(verbosity=2)
