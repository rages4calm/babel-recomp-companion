"""Upstream prepared-boundary API coexists with lazy local profile imports."""
import pytest

from v2 import coverage_profile as coverage


def _row(**changes):
    row = dict(target_pc24=0x838100, entry_mx="M0X0", emulation=0,
               site_kind="goto_gap", observed_hits=1)
    row.update(changes)
    return row


class ForbiddenIterable:
    def __iter__(self):
        raise AssertionError("prepared boundaries must not consume declarations")


@pytest.mark.parametrize("prepared, expected", [
    ({0xC38100}, "candidate_requires_analysis_and_replay"),
    (set(), "landing_requires_function_boundary"),
    (frozenset({0xC38100}), "candidate_requires_analysis_and_replay"),
])
def test_upstream_prepared_keyword_reuses_supplied_set(prepared, expected):
    assert coverage.promotion_reason(_row(), ForbiddenIterable(), {"mapper": "hirom"},
        canonical_boundaries=prepared) == expected


def test_explicit_prepared_boundaries_do_not_trigger_second_lazy_cache():
    def forbidden_lookup():
        raise AssertionError("canonical_boundaries already supplies the lookup")
    assert coverage.promotion_reason(_row(), ForbiddenIterable(), {"mapper": "hirom"},
        canonical_boundaries={0xC38100}, boundary_lookup=forbidden_lookup) == \
        "candidate_requires_analysis_and_replay"


@pytest.mark.parametrize("change, expected", [
    ({"record_kind": "instruction"}, "instruction_cost_only"),
    ({"bail_hits": 1}, "bailed_requires_investigation"),
    ({"emulation": 1}, "emulation_mode_requires_analysis_support"),
    ({"observed_hits": 0}, "no_execution_evidence"),
])
def test_early_rejections_still_precede_any_boundary_lookup(change, expected):
    assert coverage.promotion_reason(_row(**change), ForbiddenIterable(),
        {"mapper": "hirom"}, canonical_boundaries=set()) == expected
