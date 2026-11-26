"""Hourly grid electricity price for the Loenen scenario: NL day-ahead 2018.

Writes ``grid_price_nl_2018.csv`` (scenario root) with, per model
timestep:

* ``day_ahead_eur_per_mwh``: the Netherlands bidding-zone day-ahead price,
  2018 (the scenario's weather year), from the Energy-Charts API of
  Fraunhofer ISE, which redistributes it under CC BY 4.0 from the
  Bundesnetzagentur's SMARD.de;
* ``cost_flow_out``: the price the scenario charges for grid electricity,
  EUR/kWh: the sourced flat price in ``energy_prices.csv`` (Eurostat NL
  household price excluding taxes, energy and network) plus the hour's
  deviation from the 2018 mean day-ahead price,
  ``flat + (day_ahead_t - mean(day_ahead)) / 1000``. The annual mean is
  therefore unchanged (results stay comparable with the flat-price runs);
  only the hourly shape is added, as a household on a dynamic contract
  would see it.

Day-ahead hours are labelled by their UTC start; the model's timesteps are
the weather data's UTC interval midpoints (HH:30), so hour HH:00 maps to
timestep HH:30.

Usage (from the scenario root)::

    python scripts/build_grid_price.py
    python scripts/build_grid_price.py --from-json nl_da_2018.json   # offline
"""

from __future__ import annotations

import argparse
import csv
import json
import urllib.request
from pathlib import Path

import pandas as pd

SCENARIO_ROOT = Path(__file__).resolve().parent.parent
OUTPUT = SCENARIO_ROOT / "grid_price_nl_2018.csv"
_API = (
    "https://api.energy-charts.info/price?bzn=NL"
    "&start=2018-01-01T00:00Z&end=2019-01-01T00:00Z"
)
_YEAR = 2018


def _flat_price() -> float:
    with (SCENARIO_ROOT / "energy_prices.csv").open(
        newline="", encoding="utf-8-sig"
    ) as fh:
        for row in csv.DictReader(fh):
            if row["supply_tech"] == "supply_grid_electricity":
                return float(row["cost_flow_out_eur_per_kwh"])
    raise KeyError("supply_grid_electricity not in energy_prices.csv")


def _load(from_json: Path | None) -> dict:
    if from_json is not None:
        return json.loads(from_json.read_text(encoding="utf-8"))
    with urllib.request.urlopen(_API, timeout=60) as response:  # noqa: S310 (fixed URL)
        return json.load(response)


def build(from_json: Path | None = None) -> pd.DataFrame:
    data = _load(from_json)
    if data.get("unit") != "EUR / MWh":
        raise ValueError(f"unexpected unit {data.get('unit')!r}")
    price = pd.Series(
        data["price"],
        index=pd.to_datetime(data["unix_seconds"], unit="s", utc=True),
        dtype=float,
    )
    price = price[price.index.year == _YEAR]
    expected = pd.date_range(f"{_YEAR}-01-01", periods=8760, freq="h", tz="UTC")
    if not price.index.equals(expected) or price.isna().any():
        raise ValueError(
            "day-ahead series is not a complete, gap-free 2018 hourly year"
        )

    flat = _flat_price()
    table = pd.DataFrame(
        {
            "day_ahead_eur_per_mwh": price.to_numpy(),
            "cost_flow_out": flat + (price.to_numpy() - price.mean()) / 1000.0,
        },
        index=pd.Index(
            (expected + pd.Timedelta(minutes=30))
            .tz_localize(None)
            .strftime("%Y-%m-%d %H:%M:%S"),
            name="timesteps",
        ),
    )
    table.to_csv(OUTPUT, float_format="%.6f")
    print(
        f"Wrote {OUTPUT.name}: day-ahead mean {price.mean():.2f} EUR/MWh "
        f"(min {price.min():.2f}, max {price.max():.2f}); grid price mean "
        f"{table.cost_flow_out.mean():.5f} EUR/kWh (flat {flat}), range "
        f"{table.cost_flow_out.min():.4f}-{table.cost_flow_out.max():.4f}. "
        f"License: {data.get('license_info')}"
    )
    return table


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--from-json", type=Path, default=None)
    build(parser.parse_args().from_json)


if __name__ == "__main__":
    main()
