"""Rooftop PV technologies, built from ``generation_technologies/technologies.csv``.

A Calliope ``supply`` technology on ``electricity``:

- ``source_unit: per_cap``: the scenario supplies ``source_use_max`` as AC
  output per kW of installed DC capacity for each hour (the profile from
  :mod:`..profiles`). The system losses, inverter efficiency and DC/AC
  ratio are already inside that profile, so ``flow_out_eff`` is 1 and
  nothing applies them a second time.
- ``flow_cap`` is the DC nameplate capacity (kWp). ``flow_cap_max`` here is
  a catalogue ceiling; the scenario bounds it per node by the roof
  (:func:`..roof.max_capacity_kwp`).
- Costs per kWp from OpenTech-DB (``costs.csv``; conversion in
  ``docs/sources/parameter_sources.csv``).

The PVWatts and roof-layout columns of ``technologies.csv`` configure the
profile engine and the roof layout, not Calliope, so they stay out of the
exported body.
"""

from __future__ import annotations

from functools import partial
from typing import Any

from conversion_technologies.core.carriers import ELECTRICITY
from conversion_technologies.core.csv_loader import (
    load_technology_rows,
    passthrough_params,
)
from conversion_technologies.core.registry import register_technology
from conversion_technologies.core.technology import TechnologySpec
from conversion_technologies.core.validation import (
    require_range,
    require_scale_capacity,
)

PACKAGE = "conversion_technologies.generation_technologies"

#: technologies.csv columns that configure the profile engine and the roof
#: layout rather than Calliope.
PROFILE_COLUMNS = (
    "carrier_out",
    "losses",
    "dc_ac_ratio",
    "inverter_efficiency",
    "module_type",
    "mounting",
    "min_face_area_m2",
    "flat_roof_max_tilt",
    "flat_roof_tilt",
    "flat_roof_azimuth",
    "max_azimuth_from_south_deg",
    "kwp_per_m2",
    "roof_usable_fraction",
)


def pv_rows() -> list[dict[str, Any]]:
    """The ``pv`` rows of this subpackage's parameter tables."""
    return [row for row in load_technology_rows(PACKAGE) if row["category"] == "pv"]


def tech_id(row: dict[str, Any]) -> str:
    return f"pv_{row['variant']}_{row['scale']}"


def pv_row(technology_id: str) -> dict[str, Any]:
    """The parameter row behind a registered PV technology id."""
    for row in pv_rows():
        if tech_id(row) == technology_id:
            return row
    raise ValueError(f"'{technology_id}' is not a registered PV technology id.")


def _build(row: dict[str, Any]) -> TechnologySpec:
    technology_id = tech_id(row)
    if row["carrier_out"] != ELECTRICITY:
        raise ValueError(
            f"Technology '{technology_id}': carrier_out must be {ELECTRICITY!r}, "
            f"got {row['carrier_out']!r}."
        )
    require_scale_capacity(row["flow_cap_max"], row["scale"], tech_id=technology_id)
    for column in ("losses", "roof_usable_fraction"):
        require_range(
            row[column], 0, 1, name=column, tech_id=technology_id, inclusive_hi=False
        )
    require_range(
        row["kwp_per_m2"],
        0,
        0.3,
        name="kwp_per_m2",
        tech_id=technology_id,
        inclusive_lo=False,
    )
    return TechnologySpec(
        id=technology_id,
        name=f"{row['name']} ({row['scale']})",
        category="pv",
        variant=row["variant"],
        scale=row["scale"],
        carriers_in={},
        carriers_out={ELECTRICITY: 1.0},
        primary_carrier_out=ELECTRICITY,
        flow_cap_max=row["flow_cap_max"],
        lifetime=int(row["lifetime"]),
        cost_flow_cap=row["cost_flow_cap"],
        color=row["color"],
        base_tech="supply",
        source_unit="per_cap",
        params=passthrough_params(row, formula_columns=PROFILE_COLUMNS),
        notes=(
            "Rooftop PV; flow_cap = DC kWp. source_use_max (scenario data) is "
            "the PVWatts v8 AC output per kWp, losses already applied, so "
            "flow_out_eff = 1."
        ),
    )


for _row in pv_rows():
    register_technology(tech_id(_row), partial(_build, _row))
