"""The experimental timing contract must never reuse conservative output."""
import importlib
from pathlib import Path
import subprocess
import sys
import pytest

from v2.program_analysis import ProgramManifest
from v2.program_emit import _bank_cache_key

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "tools"))


def test_live_wram_address_changes_analysis_and_bank_cache_keys():
    tool = importlib.import_module("v2_emit")
    options = dict(rom=b"synthetic", generator_digest="a" * 64,
                   config_digest="b" * 64, additional_roots=(), force_lle=(),
                   cfg_roots=False, analysis_backend="native", enable_hle=True,
                   max_insns=1024, max_nodes=12000, shard_threshold_bytes=4096,
                   shard_pc_span=0x800, instruction_blocks=True, region_paced=True)
    default = tool._analysis_input_digest(**options)
    assert default == tool._analysis_input_digest(**options, region_live_wram_addresses=False)
    assert default != tool._analysis_input_digest(**options, region_live_wram_addresses=True)
    bank = dict(bank=0x83, manifest=ProgramManifest(roots=(), nodes={}),
                rom_digest="c" * 64, generator_digest="a" * 64,
                config_digest="b" * 64, helpers={}, inline_args={},
                enable_hle=True, host_alias_entries={}, shard_threshold_bytes=4096,
                shard_pc_span=0x800, instruction_blocks=True, region_paced=True)
    default = _bank_cache_key(**bank)
    assert default == _bank_cache_key(**bank, region_live_wram_addresses=False)
    assert default != _bank_cache_key(**bank, region_live_wram_addresses=True)


def test_cli_refuses_live_wram_addresss_without_pacing(tmp_path):
    result = subprocess.run([sys.executable, str(REPO / "tools/v2_emit.py"),
        "--rom", str(tmp_path / "absent.sfc"), "--cfg-dir", str(tmp_path / "absent"),
        "--out-dir", str(tmp_path / "output"), "--instruction-blocks", "--region-live-wram-addresses"],
        capture_output=True, text=True)
    assert result.returncode == 2
    assert "--region-live-wram-addresses requires --region-paced" in result.stderr
    assert not (tmp_path / "output").exists()


@pytest.mark.parametrize("enabled", [False, True])
def test_modern_sdk_cli_forwards_live_wram_address_mode(tmp_path, monkeypatch, enabled):
    sys.path.insert(0, str(REPO))
    cli = importlib.import_module("snesrecomp_cli")
    sdk = importlib.import_module("tools.sdk_generate")
    argv = ["generate", "--rom", str(tmp_path / "synthetic.sfc"),
            "--cfg-dir", str(tmp_path), "--out-dir", str(tmp_path / "out"),
            "--instruction-blocks", "--region-paced"]
    if enabled:
        argv.append("--region-live-wram-addresses")
    args = cli.parser().parse_args(argv)
    captured = {}
    monkeypatch.setattr(sdk, "generate", lambda **kwargs: captured.update(kwargs) or {})
    assert sdk.generate_command(args, sdk.ProgressReporter()) == 0
    assert captured["region_live_wram_addresses"] is enabled
    assert captured["instruction_blocks"] and captured["region_paced"]
