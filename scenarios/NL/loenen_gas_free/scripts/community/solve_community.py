"""Solve a community model from ``build_community.py`` and summarise it.

Writes ``<model dir>/results.json``: total and per-technology cost, sizes
(PV kWp, battery kW/kWh), annual energy, and the station exchange (import,
export, peak, hours at the limit).

Usage (scenario_env with Library/bin on PATH, scenario root)::

    python scripts/community/solve_community.py data/community/MSR5000927/community
"""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

import calliope
import pandas as pd

# Not investment decisions: market techs, demands and lossless links have
# placeholder capacities (1e6 kW supplies, 1000 kW links).
_NOT_SIZED = ("supply_", "demand_", "link_")


def _by_tech(da) -> dict[str, float]:
    """Built capacity per node|tech(|carrier), investment decisions only."""
    s = da.to_series().dropna()
    s = s[s.abs() > 1e-6]
    out = {}
    for key, value in s.items():
        parts = [str(k) for k in (key if isinstance(key, tuple) else (key,))]
        if any(p.startswith(_NOT_SIZED) for p in parts):
            continue
        out["|".join(parts)] = float(value)
    return out


def _totals(sized: dict[str, float], suffix: str = "") -> dict[str, float]:
    """Sum of ``sized`` per technology (and carrier), across nodes."""
    totals: dict[str, float] = {}
    for key, value in sized.items():
        tech = "|".join(key.split("|")[1:]) + suffix
        totals[tech] = round(totals.get(tech, 0.0) + value, 3)
    return totals


def summarise(m, model_dir: Path) -> dict:
    res = m.results
    cost = res["cost"].sum("nodes", skipna=True).to_series().dropna()
    flow_out = res["flow_out"].sum("timesteps")
    flow_in = res["flow_in"].sum("timesteps")

    def total(da, tech, carrier="electricity") -> float:
        if tech not in da.techs.values:
            return 0.0
        v = da.sel(techs=tech, carriers=carrier).sum(skipna=True)
        return float(v)

    out: dict = {
        "total_cost_eur": float(res["cost"].sum(skipna=True)),
        "cost_by_tech_eur": {
            str(k[-1] if isinstance(k, tuple) else k): float(v)
            for k, v in cost.groupby(level="techs").sum().items()
            if abs(v) > 1e-6
        },
        "flow_cap_total_kw": _totals(_by_tech(res["flow_cap"])),
        "storage_cap_total_kwh": (
            _totals(_by_tech(res["storage_cap"])) if "storage_cap" in res else {}
        ),
        "flow_cap_kw": _by_tech(res["flow_cap"]),
        "storage_cap_kwh": _by_tech(res["storage_cap"]) if "storage_cap" in res else {},
        "annual_kwh": {
            "grid_import": total(flow_out, "supply_grid_electricity"),
            "grid_export": total(flow_in, "demand_grid_export"),
            "pv_generation": total(flow_out, "pv_rooftop_household"),
            "appliance_demand": total(flow_in, "demand_elec"),
        },
    }
    imp = res["flow_out"].sel(techs="supply_grid_electricity", carriers="electricity")
    imp = imp.sum("nodes", skipna=True).to_series()
    exp = res["flow_in"].sel(techs="demand_grid_export", carriers="electricity")
    exp = exp.sum("nodes", skipna=True).to_series()
    # Hourly exchange with the grid, so per-member (independent) solves can
    # be summed hour by hour into a coincident station load.
    pd.DataFrame({"import_kW": imp, "export_kW": exp}).fillna(0.0).to_csv(
        model_dir / "exchange_hourly.csv"
    )
    out["station_exchange"] = {
        "import_peak_kw": float(imp.max()),
        "export_peak_kw": float(exp.max()),
        "hours_importing": int((imp > 1e-3).sum()),
        "hours_exporting": int((exp > 1e-3).sum()),
    }
    lim = model_dir / "nodes" / "station_import_limit.csv"
    if lim.exists():
        limit = pd.read_csv(lim, index_col=0)["community"]
        limit.index = pd.to_datetime(limit.index)
        limit = limit.reindex(pd.to_datetime(imp.index))
        out["station_exchange"]["hours_import_at_limit"] = int(
            ((limit - imp.to_numpy()) < 1e-3).sum()
        )
    return out


def solve_model(model_dir: Path) -> dict:
    """Build, solve and summarise ``model_dir/model.yaml``; writes
    ``results.json`` (and ``exchange_hourly.csv``) there."""
    t0 = time.time()
    m = calliope.read_yaml(str(model_dir / "model.yaml"))
    m.build()
    m.solve()
    # Calliope 0.7.0 keeps it on m.runtime, not on the results' attrs.
    status = str(getattr(m.runtime, "termination_condition", "unknown"))
    result = {
        "model_dir": str(model_dir),
        "termination": status,
        "solved_in_s": round(time.time() - t0, 1),
    }
    if status == "optimal":
        result.update(summarise(m, model_dir))
    (model_dir / "results.json").write_text(json.dumps(result, indent=2))
    return result


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("model_dir", type=Path)
    args = parser.parse_args(argv)
    print(json.dumps(solve_model(args.model_dir), indent=2))


if __name__ == "__main__":
    main()
