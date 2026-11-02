"""SDK limit forwarding without heavyweight analysis or any game ROM."""
import argparse
import hashlib
import pathlib
import sys

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from tools import sdk_generate
from tools.smoke_sdk_generate import write_fixture_rom


def test_generate_defaults_and_explicit_cli_limits():
    parser = argparse.ArgumentParser()
    sdk_generate.add_generate_parser(parser.add_subparsers(dest="command"))
    required = ["generate", "--rom", "fixture", "--cfg-dir", "cfg", "--out-dir", "gen"]
    defaults = parser.parse_args(required)
    assert (defaults.max_insns, defaults.max_nodes) == (4096, 100000)
    assert not defaults.instruction_blocks
    assert not defaults.region_paced
    explicit = parser.parse_args(required + ["--max-insns", "1024", "--max-nodes", "12000", "--instruction-blocks"])
    assert (explicit.max_insns, explicit.max_nodes) == (1024, 12000)
    assert explicit.instruction_blocks


def test_public_historical_profiles_reach_generation(monkeypatch):
    from types import SimpleNamespace
    parser = argparse.ArgumentParser()
    sdk_generate.add_generate_parser(parser.add_subparsers(dest="command"))
    args = parser.parse_args(["generate", "--rom", "fixture", "--cfg-dir", "cfg", "--out-dir", "gen",
                              "--historical-profile-manifest", "old-one.json",
                              "--historical-profile-manifest", "old-two.json"])
    calls = []
    monkeypatch.setattr(sdk_generate, "generate", lambda **options: calls.append(options))
    assert sdk_generate.generate_command(args, SimpleNamespace()) == sdk_generate.EXIT_OK
    assert calls[0]["historical_profile_manifests"] == [pathlib.Path("old-one.json").resolve(), pathlib.Path("old-two.json").resolve()]


def test_limits_reach_emitter_and_result(tmp_path, monkeypatch):
    cfg = tmp_path / "recomp"
    cfg.mkdir()
    (cfg / "bank00.cfg").write_text("bank = 0\n")
    rom = tmp_path / "fixture.sfc"
    write_fixture_rom(rom)
    calls = []
    monkeypatch.setattr(sdk_generate, "run_tool", lambda tool, args: calls.append(args) or 0)
    result = sdk_generate._generate(rom=rom, cfg_dir=cfg, out_dir=tmp_path / "gen",
                                   max_insns=1024, max_nodes=12000, instruction_blocks=True, region_paced=True)
    assert calls[0][calls[0].index("--max-insns") + 1] == "1024"
    assert calls[0][calls[0].index("--max-nodes") + 1] == "12000"
    assert result["analysis_limits"] == {"max_insns": 1024, "max_nodes": 12000}
    assert "--instruction-blocks" in calls[0]
    assert result["instruction_blocks"]
    assert "--region-paced" in calls[0] and result["region_paced"]


@pytest.mark.parametrize("limits", [(0, 12), (32, -1), (True, 32)])
def test_invalid_limits_fail_before_rom_access(tmp_path, limits):
    with pytest.raises(ValueError, match="positive integers"):
        sdk_generate._generate(rom=tmp_path / "absent", cfg_dir=tmp_path,
                               out_dir=tmp_path / "gen", max_insns=limits[0], max_nodes=limits[1])


def test_recipe_identity_includes_analysis_limits(tmp_path, monkeypatch):
    from tools.generation_recipe import load_recipe
    cfg = tmp_path / "recomp"
    cfg.mkdir()
    (cfg / "bank00.cfg").write_text("bank = 0\n")
    (cfg / "generate.toml").write_text("schema = 1\n")
    rom = tmp_path / "fixture.sfc"
    write_fixture_rom(rom)
    digests = []
    def fake_generate(**options):
        digests.append(options["generation_recipe_digest"])
        (options["out_dir"] / "synthetic.c").write_text("/* synthetic */\n")
        return {"ok": True}
    monkeypatch.setattr(sdk_generate, "_generate", fake_generate)
    for insns in (1024, 2048, 1024):
        sdk_generate.generate(rom=rom, cfg_dir=cfg, out_dir=tmp_path / "gen",
                              max_insns=insns, max_nodes=12000)
    assert digests[0] == digests[2] != digests[1]
    expected = hashlib.sha256((load_recipe(cfg).digest() + "\0analysis_limits=1024:12000\0instruction_blocks=0\0region_paced=0").encode("ascii")).hexdigest()
    assert digests[0] == expected
    sdk_generate.generate(rom=rom, cfg_dir=cfg, out_dir=tmp_path / "gen",
                          max_insns=1024, max_nodes=12000, instruction_blocks=True)
    assert digests[-1] != digests[0]
    sdk_generate.generate(rom=rom, cfg_dir=cfg, out_dir=tmp_path / "gen",
                          max_insns=1024, max_nodes=12000, instruction_blocks=True, region_paced=True)
    assert digests[-1] != digests[-2]


def test_region_paced_requires_instruction_blocks_before_rom_access(tmp_path):
    with pytest.raises(ValueError, match="requires instruction-blocks"):
        sdk_generate._generate(rom=tmp_path / "absent", cfg_dir=tmp_path,
                               out_dir=tmp_path / "gen", region_paced=True)
