"""PV profiles as Calliope data: ``source_use_max`` per node and hour.

The PV technology is ``source_unit: per_cap``, so ``source_use_max`` is the
AC output per kWp in each hour (:mod:`.roof`, :mod:`.pvwatts`), one column
per node. ``flow_cap_max`` per node (the roof's potential) is written with
it, so the technology is never placed without both: without
``source_use_max`` Calliope would treat the sun as unlimited.
"""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
from typing import Any

import pandas as pd

from conversion_technologies.calliope_export.writer import write_yaml_document
from conversion_technologies.core.validation import require_no_nan, require_range_array


def build_pv_data_tables(technology_id: str, profile_csv: str) -> dict[str, Any]:
    """The ``data_tables:`` block that reads ``profile_csv`` (rows
    timesteps, columns nodes) as the technology's ``source_use_max``."""
    return {
        "data_tables": {
            f"{technology_id}_source_use_max": {
                "table": profile_csv,
                "rows": "timesteps",
                "columns": "nodes",
                "add_dims": {"techs": technology_id, "inputs": "source_use_max"},
            }
        }
    }


def build_pv_nodes(
    technology_id: str, max_capacity_kwp: Mapping[str, float]
) -> dict[str, Any]:
    """``nodes:`` entries placing the technology at each node with its
    roof's potential as ``flow_cap_max`` (kWp, on electricity)."""
    return {
        "nodes": {
            node: {
                "techs": {
                    technology_id: {
                        "flow_cap_max": {
                            "data": round(float(kwp), 3),
                            "index": "electricity",
                            "dims": "carriers",
                        }
                    }
                }
            }
            for node, kwp in max_capacity_kwp.items()
            if kwp > 0
        }
    }


def write_pv_profiles(
    technology_id: str,
    capacity_factors: pd.DataFrame,
    max_capacity_kwp: Mapping[str, float],
    output_dir: str | Path,
    *,
    table_path: str | None = None,
) -> dict[str, Path]:
    """Write ``<id>_source_use_max.csv`` (rows timesteps, columns nodes),
    ``<id>_data_tables.yaml`` and ``<id>_nodes.yaml`` into ``output_dir``.

    ``capacity_factors`` columns are node names; nodes whose roof carries
    no PV (potential 0) are left out of both files. ``table_path`` is the
    CSV path as the model YAML should reference it (default: the file
    name).
    """
    nodes = [
        node for node in capacity_factors.columns if max_capacity_kwp.get(node, 0) > 0
    ]
    profile = capacity_factors[nodes]
    values = profile.to_numpy(dtype=float)
    labels = [str(t) for t in profile.index]
    for column in range(values.shape[1]):
        require_no_nan(
            values[:, column],
            name="PV source_use_max",
            tech_id=technology_id,
            labels=labels,
        )
        require_range_array(
            values[:, column],
            0,
            1,
            name="PV source_use_max",
            tech_id=technology_id,
            labels=labels,
        )

    out_dir = Path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    csv_path = out_dir / f"{technology_id}_source_use_max.csv"
    tables_path = out_dir / f"{technology_id}_data_tables.yaml"
    nodes_path = out_dir / f"{technology_id}_nodes.yaml"

    profile.rename_axis("timesteps").to_csv(csv_path)
    write_yaml_document(
        build_pv_data_tables(technology_id, table_path or csv_path.name), tables_path
    )
    write_yaml_document(
        build_pv_nodes(technology_id, {node: max_capacity_kwp[node] for node in nodes}),
        nodes_path,
    )
    return {
        "profile_csv": csv_path,
        "data_tables_yaml": tables_path,
        "nodes_yaml": nodes_path,
    }
