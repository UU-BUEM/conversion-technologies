"""Phase 1 rerun: Loenen hourly demand with a realistic cooling setpoint.

``buem``'s default upper comfort bound (``DEFAULT_COMFORT_T_UB`` in
``buem/config/building_registry.py``) is 21 degC. ``buem`` cools whenever the
indoor temperature would exceed it, so with 21 degC the Loenen population's
cooling demand came out larger than its heating demand (median dwelling:
19.4 MWh/yr cooling vs. 27.5 MWh/yr heating, cooling peak above heating
peak) -- not plausible for Dutch dwellings.

This wrapper reruns ``buem``'s own ``scripts/run_region_hourly.py``
unchanged, with only that one default overridden *before* any ``buem``
module is imported (every ``from building_registry import
DEFAULT_COMFORT_T_UB`` then binds the new value). Nothing in the ``buem``
repository is edited. The patch sits at module top level on purpose:
``run_region_hourly`` uses a process pool, and on Windows each worker
re-imports this main module, so the override reaches every worker too.

Setpoint: 26 degC, the upper bound of the EN 16798-1 Category II
residential cooling-season range (22-26 degC operative temperature), which
the REHVA/Eurovent model regulation (2025) says cooling should be
dimensioned with. The heating setpoint (18 degC lower bound) is unchanged.

Usage (from the conversion-technologies repo root, in ``buem_env``)::

    python scenarios/NL/loenen_gas_free/scripts/run_demand_with_cooling_setpoint.py \\
        --buem-root D:/test/buem --cooling-setpoint 26 \\
        --output scenarios/NL/loenen_gas_free/data/loenen_single_dwelling_hourly_cool26.parquet \\
        --summary-output scenarios/NL/loenen_gas_free/data/loenen_single_dwelling_summary_cool26.parquet
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

SCENARIO_ROOT = Path(__file__).resolve().parent.parent

_pre = argparse.ArgumentParser(add_help=False)
_pre.add_argument("--buem-root", type=Path, default=Path("D:/test/buem"))
_pre.add_argument("--cooling-setpoint", type=float, default=26.0)
_known, _rest = _pre.parse_known_args()

# --- must run before ANY buem import (also in spawned pool workers) --------
sys.path.insert(0, str(_known.buem_root / "scripts"))
import buem.config.building_registry as _registry  # noqa: E402

_registry.DEFAULT_COMFORT_T_UB = _known.cooling_setpoint

import buem.config.cfg_attribute as _cfg_attribute  # noqa: E402
import run_region_hourly  # noqa: E402  (buem/scripts/run_region_hourly.py)


def main() -> None:
    applied = _cfg_attribute.ATTRIBUTE_SPECS["comfortT_ub"].default
    if applied != _known.cooling_setpoint:
        raise RuntimeError(
            f"cooling setpoint override did not take effect (buem uses {applied})"
        )
    print(f"buem comfortT_ub default = {applied} degC (buem's own default: 21.0)")
    region = _known.buem_root / "src/buem/data/buildings/netherlands/Loenen"
    ids = SCENARIO_ROOT / "data/loenen_single_dwelling_ids.txt"
    argv = [
        "--data-dir",
        str(region),
        "--country",
        "NL",
        "--building-ids-file",
        str(ids),
    ]
    run_region_hourly.main(argv + _rest)


if __name__ == "__main__":
    main()
