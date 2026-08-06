"""Real (weather-driven) hourly heat pump COP -- an opt-in path, separate
from the registry's fixed design-point COP.

Deliberately **not** wired into ``new/heat_pump/specific/__init__.py``'s
zero-argument registry builders -- see ``.claude/heat_pump/resolved.md``
"weather-integration-scope", which anticipated exactly this as "a new,
non-catalog entry point". The catalog's design-point COP is unchanged; this
module produces a second, opt-in artifact (two ``data_tables`` CSVs + the
YAML block referencing them) for one specific technology, from a real
2 m outdoor-air temperature series, for whoever wants an hourly-varying COP
instead of the design-point value.

Gets that temperature series from the sibling ``weather`` package's own
``get_point_weather(latitude, longitude, year)`` -- a real per-location
fetch of an already-processed archive, **not** ground/soil temperature
(``weather`` doesn't produce that). ``weather`` is a compulsory dependency
of this package (see ``pyproject.toml``/``infrastructure/env/
conversion_env.yml``), matching how ``UU-BUEM/buem`` treats the same
dependency -- there is deliberately no CSV/local-file fallback. See
``docs/calliope_schema_mapping.md`` "Weather-driven COP profiles".
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from weather import get_point_weather

from conversion_technologies.calliope_export.writer import write_yaml_document
from conversion_technologies.core.csv_loader import load_technology_rows
from conversion_technologies.core.registry import get_technology
from conversion_technologies.core.validation import require_no_nan, require_range_array
from conversion_technologies.new.heat_pump.generic.cop_calculation import carnot_cop


def compute_hourly_cop(
    temperature_c: pd.Series,
    *,
    sink_temp_c: float,
    quality_factor: float,
    tech_id: str,
) -> pd.Series:
    """Hourly COP from an hourly 2 m outdoor-air temperature series.

    Same ``carnot_cop`` formula and the same ``[1, 20]`` sanity bound the
    registry's design-point COP is checked against
    (``new/heat_pump/specific/__init__.py``), applied elementwise instead of
    once. Raises ``ValueError`` -- naming the count and first offending
    timestamp, not just "some value is bad" -- if any hour is NaN (source
    temperature met or exceeded the sink temperature that hour: a real
    possible condition, not a bug, but silently writing NaN into a Calliope
    data table is worse than failing loudly) or outside ``[1, 20]``.
    """
    cop = carnot_cop(
        t_source_c=temperature_c.to_numpy(dtype=np.float64),
        t_sink_c=sink_temp_c,
        carnot_efficiency=quality_factor,
    )
    assert isinstance(cop, np.ndarray)  # array in (an hourly series), array out
    labels = list(temperature_c.index)
    require_no_nan(cop, name="hourly COP", tech_id=tech_id, labels=labels)
    require_range_array(cop, 1, 20, name="hourly COP", tech_id=tech_id, labels=labels)
    return pd.Series(cop, index=temperature_c.index, name="cop")


def _design_row(technology_id: str) -> dict[str, Any]:
    """The raw ``technologies.csv`` row backing ``technology_id``.

    Recovers ``design_sink_temp_c``/``efficiency`` (the quality factor) --
    ``TechnologySpec`` doesn't carry these itself, only the scalar COP
    they were already reduced to at registry-build time. Re-reading the CSV
    (the same source `new/heat_pump/specific/__init__.py`'s registry
    builder reads) keeps it the single source of truth rather than asking
    the caller to retype values that already live there.
    """
    for row in load_technology_rows("conversion_technologies.new"):
        if (
            row["category"] == "heat_pump"
            and f"heat_pump_{row['variant']}_{row['scale']}" == technology_id
        ):
            return row
    raise ValueError(f"'{technology_id}' is not a registered heat_pump technology id.")


def build_cop_data_tables(
    technology_id: str,
    ambient_carrier: str,
    *,
    flow_out_eff_csv: str,
    flow_in_eff_csv: str,
) -> dict[str, Any]:
    """The ``data_tables:`` YAML block referencing the two COP CSVs.

    Two single-value-column CSVs (one per parameter) rather than one shared
    multi-column file -- Calliope's ``data_tables`` column-selection syntax
    for picking one of several value columns out of a shared file wasn't
    something this investigation could verify against a running Calliope
    install, so this uses the simplest documented shape (one CSV column per
    ``data_tables`` entry) instead of guessing at the more compact one.

    Deliberately omits ``nodes`` from ``add_dims`` -- this package has no
    concept of a Calliope node/location (it only ever emits ``techs:``
    bodies); the consuming model must add its own node mapping, called out
    in the returned block's ``_comment``.
    """
    return {
        "_comment": (
            "Add a 'nodes' entry to each add_dims block below matching "
            "wherever this technology is actually placed in your model -- "
            "this package has no concept of a Calliope node."
        ),
        "data_tables": {
            f"{technology_id}_flow_out_eff": {
                "table": flow_out_eff_csv,
                "rows": "timesteps",
                "add_dims": {
                    "techs": technology_id,
                    "carriers": "heat",
                    "inputs": "flow_out_eff",
                },
            },
            f"{technology_id}_flow_in_eff": {
                "table": flow_in_eff_csv,
                "rows": "timesteps",
                "add_dims": {
                    "techs": technology_id,
                    "carriers": ambient_carrier,
                    "inputs": "flow_in_eff",
                },
            },
        },
    }


def export_weather_cop(
    technology_id: str,
    output_dir: str | Path,
    *,
    latitude: float,
    longitude: float,
    year: int,
    provider: str = "era5-land",
    data_dir: str | Path | None = None,
) -> dict[str, Path]:
    """End to end: a registered heat pump id + a location -> written files.

    Fetches the 2 m outdoor-air temperature series for ``(latitude,
    longitude, year)`` via ``weather.get_point_weather`` (extracts the
    nearest already-processed grid cell for ``provider`` -- raises
    ``FileNotFoundError`` if nothing has been processed yet for that
    ``(provider, year)``; it does not download or process data itself),
    computes the hourly COP (:func:`compute_hourly_cop`) using the design
    sink temperature and quality factor already in ``technologies.csv`` for
    ``technology_id``, and writes three files into ``output_dir``:
    ``<id>_flow_out_eff.csv``, ``<id>_flow_in_eff.csv``,
    ``<id>_data_tables.yaml``. Returns their paths, keyed
    ``"flow_out_eff_csv"``/``"flow_in_eff_csv"``/``"data_tables_yaml"``.

    Raises ``ValueError`` if ``technology_id`` isn't registered or isn't
    heat-pump-shaped (exactly 2 input carriers: electricity + a free heat
    source) -- e.g. called against a boiler or CHP id.
    """
    tech = get_technology(technology_id)
    if len(tech.carriers_in) != 2:
        raise ValueError(
            f"'{technology_id}' has {len(tech.carriers_in)} input carrier(s); "
            "weather_cop only applies to a heat pump (exactly 2: electricity "
            "+ a free heat source)."
        )
    ambient_carrier = next(c for c in tech.carriers_in if c != tech.primary_carrier_in)
    row = _design_row(technology_id)

    weather_df = get_point_weather(
        latitude, longitude, year, provider=provider, data_dir=data_dir
    )
    temperature_c = weather_df["T"]

    cop = compute_hourly_cop(
        temperature_c,
        sink_temp_c=row["design_sink_temp_c"],
        quality_factor=row["efficiency"],
        tech_id=technology_id,
    )

    out_dir = Path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    flow_out_eff_path = out_dir / f"{technology_id}_flow_out_eff.csv"
    flow_in_eff_path = out_dir / f"{technology_id}_flow_in_eff.csv"
    data_tables_path = out_dir / f"{technology_id}_data_tables.yaml"

    cop.rename("flow_out_eff").rename_axis("timesteps").to_csv(flow_out_eff_path)
    (cop - 1.0).rename("flow_in_eff").rename_axis("timesteps").to_csv(flow_in_eff_path)

    data_tables = build_cop_data_tables(
        technology_id,
        ambient_carrier,
        flow_out_eff_csv=flow_out_eff_path.name,
        flow_in_eff_csv=flow_in_eff_path.name,
    )
    write_yaml_document(data_tables, data_tables_path)

    return {
        "flow_out_eff_csv": flow_out_eff_path,
        "flow_in_eff_csv": flow_in_eff_path,
        "data_tables_yaml": data_tables_path,
    }
