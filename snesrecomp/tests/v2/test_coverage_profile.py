"""Per-profile boundary memoization must preserve promotion validation exactly."""
import json

import pytest

from v2 import coverage_profile as coverage
from v2.program_analysis import VariantKey
from v2.program_emit import discover_profile_roots


def _row(**changes):
    result = dict(site_pc24=0x038000, target_pc24=0x838100, entry_mx="M0X0",
                  emulation=0, site_kind="goto_gap", observed_hits=1)
    result.update(changes)
    return result


def _capture(path, rows, *, mapper="hirom", rom="a" * 64, build="b" * 64):
    path.write_text(json.dumps(dict(schema="snesrecomp tier2 coverage v2", capture_id=path.stem,
        identity=dict(rom_sha256=rom, module_id="main", mapper=mapper, program_digest="c" * 64,
                      build_digest=build), discoveries=rows)), encoding="utf-8")
    return path


def _outcome(call):
    try:
        return ("reason", call())
    except (ValueError, TypeError, OverflowError) as error:
        return (type(error).__name__, str(error))


@pytest.mark.parametrize("mapper", ["hirom", "lorom", "sa1", "sdd1", "superfx", "cx4", "dsp1", None])
def test_prepared_boundaries_keep_all_original_reasons_and_alias_rules(mapper):
    declared = {0x038100, 0x438100, 0x008200, 0x7E8100}
    identity = {"mapper": mapper}
    lookup = coverage._promotion_boundary_lookup(declared, mapper)
    for target in (0x038100, 0x438100, 0x838100, 0xC38100, 0x008200, 0x808200,
                   0x008300, 0x7E8100, 0x7F8100):
        for kind in ("call_gap", "goto_gap", "indirect_dispatch"):
            for change in ({}, {"record_kind": "instruction"}, {"bail_hits": 1}, {"emulation": None},
                           {"emulation": 1}, {"entry_mx": "unknown"}, {"observed_hits": 0}):
                row = _row(target_pc24=target, site_kind=kind, **change)
                assert coverage.promotion_reason(row, declared, identity, boundary_lookup=lookup) == \
                       coverage.promotion_reason(row, declared, identity)
    assert coverage.promotion_reason(_row(target_pc24=0x7E8100), declared, identity,
        boundary_lookup=lookup) == "ram_requires_decoded_snapshot_and_guard"


@pytest.mark.parametrize("bad", [float("nan"), float("inf"), -1, 0x1000000, "invalid-PC"])
def test_lazy_validation_keeps_malformed_declared_values_and_first_error(bad):
    declared = [bad]; identity = {"mapper": "hirom"}
    lookup = coverage._promotion_boundary_lookup(declared, "hirom")
    for row in (_row(bail_hits=1), _row(emulation=1), _row(observed_hits=0),
                _row(site_kind="call_gap"), _row(), _row(target_pc24="also-invalid")):
        baseline = _outcome(lambda: coverage.promotion_reason(row, declared, identity))
        prepared = _outcome(lambda: coverage.promotion_reason(row, declared, identity, boundary_lookup=lookup))
        assert prepared == baseline
    assert _outcome(lambda: coverage.promotion_reason(_row(site_kind="call_gap"), declared, identity,
        boundary_lookup=lookup))[0] == "ValueError"


def test_discovery_canonicalizes_declared_set_once_per_loaded_profile(tmp_path, monkeypatch):
    declared = set(range(0x038100, 0x038200))
    rows = [_row(site_pc24=0x038000 + i, target_pc24=0x838100 + i % 8) for i in range(64)]
    current = _capture(tmp_path / "current.json", rows)
    historical = [_capture(tmp_path / f"old-{i}.json", rows, build=str(i + 3) * 64) for i in range(2)]
    original = coverage.canonical_pc
    calls = []
    def counted(value, mapper):
        calls.append((value, mapper))
        return original(value, mapper)
    monkeypatch.setattr(coverage, "canonical_pc", counted)
    roots = discover_profile_roots([current], declared, historical_paths=historical)
    assert roots == tuple(VariantKey(0x838100 + i, 0, 0) for i in range(8))
    assert len(calls) == 3 * (len(declared) + len(rows))


def test_mutations_and_other_game_mapper_never_reuse_previous_boundaries(tmp_path):
    declared = [0x038100]
    hirom = _capture(tmp_path / "hirom.json", [_row()])
    sa1 = _capture(tmp_path / "sa1.json", [_row()], mapper="sa1", rom="d" * 64)
    assert discover_profile_roots([hirom], declared) == (VariantKey(0x838100, 0, 0),)
    assert discover_profile_roots([sa1], declared) == ()
    declared[:] = [0x838100]
    assert discover_profile_roots([sa1], declared) == (VariantKey(0x838100, 0, 0),)
    declared.clear()
    assert discover_profile_roots([hirom], declared) == ()


def test_one_shot_declared_iterables_keep_original_consumption_behavior(tmp_path):
    assert coverage._promotion_boundary_lookup(iter([0x038100]), "hirom") is None
    class CustomList(list):
        pass
    assert coverage._promotion_boundary_lookup(CustomList([0x038100]), "hirom") is None
    path = _capture(tmp_path / "single-pass.json", [
        _row(target_pc24=0x838100), _row(site_pc24=0x038001, target_pc24=0x838101)])
    assert discover_profile_roots([path], iter([0x038100, 0x038101])) == (VariantKey(0x838100, 0, 0),)
    assert discover_profile_roots([path], [0x038100, 0x038101]) == (
        VariantKey(0x838100, 0, 0), VariantKey(0x838101, 0, 0))


def test_root_discovery_keeps_early_rejection_and_identity_nonfinite_boundaries(tmp_path):
    bad_declared = ["invalid-PC"]
    path = _capture(tmp_path / "profile.json", [_row(bail_hits=1)])
    assert discover_profile_roots([path], bad_declared) == ()
    _capture(path, [_row(site_kind="call_gap")])
    with pytest.raises(ValueError):
        discover_profile_roots([path], bad_declared)
    with pytest.raises(ValueError, match="ROM does not match"):
        discover_profile_roots([path], [], expected_rom="d" * 64)
    _capture(path, [_row(guest_cycles=float("inf"))])
    with pytest.raises(OverflowError):
        discover_profile_roots([path], [])
    _capture(path, [_row(target_pc24=float("nan"))])
    with pytest.raises(ValueError):
        discover_profile_roots([path], [])
