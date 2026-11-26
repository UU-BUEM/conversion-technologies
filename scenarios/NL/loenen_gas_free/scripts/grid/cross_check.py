"""Compare two grid packages' stations (e.g. pylovo against Liander).

Matches each station of ``test`` to the nearest station of ``reference``
and reports distances, counts and ratings. A synthetic grid will not put
transformers in exactly the right places; the figures show how far off it
is, and they are reported, never used to correct anything.
"""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

from grid.common import nearest_station, to_rd


def compare(
    reference: pd.DataFrame, test: pd.DataFrame
) -> tuple[pd.DataFrame, dict[str, Any]]:
    rx, ry = to_rd(reference["longitude"], reference["latitude"])
    tx, ty = to_rd(test["longitude"], test["latitude"])
    idx, dist = nearest_station(np.column_stack([tx, ty]), np.column_stack([rx, ry]))
    pairs = pd.DataFrame(
        {
            "trafo_id": test["trafo_id"].to_numpy(),
            "rated_kva": test["rated_kva"].to_numpy(),
            "nearest_reference": reference["trafo_id"].to_numpy()[idx],
            "reference_rated_kva": reference["rated_kva"].to_numpy()[idx],
            "distance_m": np.round(dist, 1),
        }
    )
    ref_rated = reference[reference["data"] == "rated"]
    summary = {
        "n_reference": int(len(reference)),
        "n_reference_rated": int(len(ref_rated)),
        "n_test": int(len(test)),
        "distance_m": {
            "median": float(np.median(dist)),
            "p90": float(np.percentile(dist, 90)),
        },
        "share_within_50_m": float(np.mean(dist <= 50)),
        "share_within_100_m": float(np.mean(dist <= 100)),
        "total_rated_kva": {
            "reference": float(pd.to_numeric(ref_rated["rated_kva"]).sum()),
            "test": float(pd.to_numeric(test["rated_kva"], errors="coerce").sum()),
        },
    }
    return pairs, summary
