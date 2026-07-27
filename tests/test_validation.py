from __future__ import annotations

import pytest

from conversion_technologies.core.technology import TechnologySpec
from conversion_technologies.core.validation import (
    require_positive_costs,
    require_range,
    require_scale_capacity,
)


def _valid_kwargs(**overrides: object) -> dict:
    kwargs = {
        "id": "test_tech",
        "name": "Test Technology",
        "category": "boiler",
        "variant": "electric",
        "scale": "household",
        "carriers_in": {"electricity": 1.0},
        "carriers_out": {"heat": 0.95},
        "flow_cap_max": 10.0,
        "lifetime": 20,
        "cost_flow_cap": 100.0,
        "params": {},
    }
    kwargs.update(overrides)
    return kwargs


# -- require_range ----------------------------------------------------------


def test_require_range_accepts_an_in_range_value() -> None:
    assert require_range(5.0, 0, 10, name="x", tech_id="t") == 5.0


def test_require_range_rejects_below_lower_bound() -> None:
    with pytest.raises(ValueError, match="x=-1"):
        require_range(-1.0, 0, 10, name="x", tech_id="t")


def test_require_range_rejects_above_upper_bound() -> None:
    with pytest.raises(ValueError, match="x=11"):
        require_range(11.0, 0, 10, name="x", tech_id="t")


def test_require_range_exclusive_bounds_reject_the_boundary_value() -> None:
    with pytest.raises(ValueError):
        require_range(0.0, 0, 10, name="x", tech_id="t", inclusive_lo=False)
    with pytest.raises(ValueError):
        require_range(10.0, 0, 10, name="x", tech_id="t", inclusive_hi=False)


def test_require_range_inclusive_bounds_accept_the_boundary_value() -> None:
    assert require_range(0.0, 0, 10, name="x", tech_id="t") == 0.0
    assert require_range(10.0, 0, 10, name="x", tech_id="t") == 10.0


# -- require_positive_costs --------------------------------------------------


def test_require_positive_costs_accepts_positive_values() -> None:
    require_positive_costs({"cost_flow_cap": 1.0, "cost_flow_in": 0.02}, tech_id="t")


def test_require_positive_costs_rejects_a_zero_or_negative_cost() -> None:
    with pytest.raises(ValueError, match="cost_flow_in"):
        require_positive_costs({"cost_flow_in": 0.0}, tech_id="t")
    with pytest.raises(ValueError, match="cost_flow_out"):
        require_positive_costs({"cost_flow_out": -5.0}, tech_id="t")


def test_require_positive_costs_ignores_non_cost_keys() -> None:
    require_positive_costs({"flow_ramping": -1.0}, tech_id="t")  # not a cost_* key


def test_require_positive_costs_exempts_cost_interest_rate() -> None:
    # cost_interest_rate is a fraction, not a currency amount; it has its
    # own bound applied separately, so a value of 0 here must not raise.
    require_positive_costs({"cost_interest_rate": 0.0}, tech_id="t")


# -- require_scale_capacity ---------------------------------------------------


def test_require_scale_capacity_accepts_a_value_under_the_ceiling() -> None:
    require_scale_capacity(50.0, "household", tech_id="t")


def test_require_scale_capacity_rejects_a_value_over_the_ceiling() -> None:
    with pytest.raises(ValueError, match="household"):
        require_scale_capacity(100_000.0, "household", tech_id="t")


def test_require_scale_capacity_uses_a_custom_ceiling_dict_when_given() -> None:
    with pytest.raises(ValueError):
        require_scale_capacity(
            5.0, "household", tech_id="t", ceilings={"household": 1.0}
        )
    require_scale_capacity(5.0, "household", tech_id="t", ceilings={"household": 10.0})


def test_require_scale_capacity_ignores_a_scale_with_no_ceiling_entry() -> None:
    require_scale_capacity(1_000_000.0, "household", tech_id="t", ceilings={})


# -- TechnologySpec common bounds (__post_init__) ----------------------------


def test_technology_spec_accepts_valid_common_values() -> None:
    TechnologySpec(**_valid_kwargs())


def test_technology_spec_rejects_lifetime_out_of_range() -> None:
    with pytest.raises(ValueError, match="lifetime"):
        TechnologySpec(**_valid_kwargs(lifetime=0))
    with pytest.raises(ValueError, match="lifetime"):
        TechnologySpec(**_valid_kwargs(lifetime=50))


def test_technology_spec_rejects_non_positive_cost_flow_cap() -> None:
    with pytest.raises(ValueError, match="cost_flow_cap"):
        TechnologySpec(**_valid_kwargs(cost_flow_cap=0.0))


def test_technology_spec_rejects_cost_interest_rate_out_of_range() -> None:
    with pytest.raises(ValueError, match="cost_interest_rate"):
        TechnologySpec(**_valid_kwargs(params={"cost_interest_rate": 0.5}))


def test_technology_spec_accepts_a_missing_cost_interest_rate() -> None:
    # cost_interest_rate is optional (lives in params); absent is fine.
    TechnologySpec(**_valid_kwargs(params={}))


def test_technology_spec_rejects_a_non_positive_params_cost() -> None:
    with pytest.raises(ValueError, match="cost_flow_in"):
        TechnologySpec(**_valid_kwargs(params={"cost_flow_in": -0.01}))
