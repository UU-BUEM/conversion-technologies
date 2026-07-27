"""The internal, Calliope-version-agnostic technology representation.

Every technology in ``conversion_technologies.new`` builds one of these. It
carries only physical/economic facts about the technology; translating it
into a specific Calliope schema is the job of
``conversion_technologies.calliope_export``.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class TechnologySpec:
    """A single conversion technology option at a given deployment scale.

    Parameters
    ----------
    id : str
        Unique registry key, e.g. ``"heat_pump_electric_household"``.
    name : str
        Human-readable label used as the Calliope tech ``name``.
    category : str
        Technology family: ``"boiler"``, ``"heat_pump"`` or
        ``"combined_heat_and_power"``.
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
    """

    id: str
    name: str
    category: str
    scale: str
    carriers_in: dict[str, float]
    carriers_out: dict[str, float]
    flow_cap_max: float
    lifetime: int
    cost_flow_cap: float
    primary_carrier_in: str | None = None
    primary_carrier_out: str | None = None
    flow_cap_min: float | None = None
    cost_flow_om_annual: float | None = None
    cost_flow_out: float | None = None
    color: str | None = None
    notes: str | None = None
    extra: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.carriers_in:
            raise ValueError(
                f"Technology '{self.id}' must define at least one input carrier."
            )
        if not self.carriers_out:
            raise ValueError(
                f"Technology '{self.id}' must define at least one output carrier."
            )
        if self.flow_cap_max <= 0:
            raise ValueError(
                f"Technology '{self.id}' must have a positive flow_cap_max."
            )
