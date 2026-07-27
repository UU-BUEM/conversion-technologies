"""The internal, Calliope-version-agnostic technology representation.

Every technology in ``conversion_technologies.new`` builds one of these. It
carries only physical/economic facts about the technology; translating it
into a specific Calliope schema is the job of
``conversion_technologies.calliope_export``.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from conversion_technologies.core.validation import (
    require_positive_costs,
    require_range,
)


@dataclass(frozen=True)
class TechnologySpec:
    """A single conversion technology option at a given deployment scale.

    Only the handful of fields every technology always has are named
    explicitly; everything else (``flow_cap_min``, ``cost_om_annual``,
    ``cost_flow_in``, ``cost_flow_out``, ``cost_interest_rate``,
    ``flow_ramping``, and any parameter added later) lives in ``params``,
    keyed by its exact ``technologies.csv``/``costs.csv`` column name. The
    ``modern`` exporter passes ``params`` straight through under those same
    names, so adding a new column -- or renaming one to track a future
    Calliope release -- needs no change here or in that exporter. See
    ``docs/calliope_schema_mapping.md``.

    Common engineering bounds (lifetime, cost_flow_cap, cost_interest_rate,
    every populated cost being positive) are enforced in
    ``__post_init__`` below, via ``core.validation``. Technology-specific
    bounds (boiler efficiency, heat pump COP, per-scale capacity ceilings,
    CHP dispatch factors) are enforced by each category's
    ``specific/__init__.py`` before it constructs this dataclass.

    Parameters
    ----------
    id : str
        Unique registry key, e.g. ``"heat_pump_electric_household"``.
    name : str
        Human-readable label used as the Calliope tech ``name``.
    category : str
        Technology family: ``"boiler"``, ``"heat_pump"`` or
        ``"combined_heat_and_power"``.
    variant : str
        The specific technology within its category, e.g. ``"electric"``,
        ``"geothermal"``, ``"gas"``, ``"biomass"``. Combined with
        ``category`` and ``scale`` this is what the CLI's ``--variant``/
        ``--scale`` filters match against.
    scale : str
        Deployment scale: ``"household"``, ``"building"`` or ``"community"``.
    carriers_in : dict[str, float]
        Input carrier -> flow ratio relative to the technology's shared
        internal capacity (e.g. ``{"electricity": 1.0, "ambient_heat": 2.5}``).
    carriers_out : dict[str, float]
        Output carrier -> flow ratio, same convention as ``carriers_in``.
    flow_cap_max : float
        Maximum installable capacity, in kW.
    lifetime : int
        Technical lifetime, in years.
    cost_flow_cap : float
        Investment cost per unit of installed capacity, currency/kW.
    params : dict[str, float]
        Every other Calliope-modern-schema-named numeric parameter this
        technology has a value for (only non-blank CSV columns end up
        here) -- e.g. ``{"cost_flow_in": 0.04, "cost_interest_rate": 0.10}``.
    """

    id: str
    name: str
    category: str
    variant: str
    scale: str
    carriers_in: dict[str, float]
    carriers_out: dict[str, float]
    flow_cap_max: float
    lifetime: int
    cost_flow_cap: float
    primary_carrier_in: str | None = None
    primary_carrier_out: str | None = None
    color: str | None = None
    notes: str | None = None
    params: dict[str, float] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.carriers_in:
            raise ValueError(
                f"Technology '{self.id}' must define at least one input carrier."
            )
        if not self.carriers_out:
            raise ValueError(
                f"Technology '{self.id}' must define at least one output carrier."
            )
        require_range(
            self.flow_cap_max,
            0,
            float("inf"),
            name="flow_cap_max",
            tech_id=self.id,
            inclusive_lo=False,
            inclusive_hi=False,
        )
        require_range(
            self.cost_flow_cap,
            0,
            float("inf"),
            name="cost_flow_cap",
            tech_id=self.id,
            inclusive_lo=False,
            inclusive_hi=False,
        )
        require_range(
            self.lifetime,
            0,
            50,
            name="lifetime",
            tech_id=self.id,
            inclusive_lo=False,
            inclusive_hi=False,
        )
        if "cost_interest_rate" in self.params:
            require_range(
                self.params["cost_interest_rate"],
                0,
                0.4,
                name="cost_interest_rate",
                tech_id=self.id,
                inclusive_lo=False,
                inclusive_hi=False,
            )
        require_positive_costs(self.params, tech_id=self.id)
