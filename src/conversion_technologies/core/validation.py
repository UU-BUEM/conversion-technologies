"""Shared engineering-bound validation, called from source, not from tests.

Validation belongs here (common bounds) and in each category's
``specific/__init__.py`` (technology-specific bounds) -- **not** in
``tests/``. Tests check that bad input is rejected; they must never be the
only place a bound is enforced. If you're tempted to write
``assert tech.lifetime < 50`` in a test, the check belongs in
:func:`TechnologySpec.__post_init__` instead, and the test should assert
that an out-of-range CSV value raises ``ValueError``.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

import numpy as np
from numpy.typing import NDArray

# Generous, order-of-magnitude sanity ceilings on installed capacity per
# deployment scale, in kW -- catch a CSV typo (an extra digit, a misplaced
# scale) without constraining legitimate research variation. Shared across
# categories by default; a category may pass its own dict to
# require_scale_capacity() if its real-world scale genuinely differs.
DEFAULT_CAPACITY_CEILINGS_KW: dict[str, float] = {
    "household": 100.0,
    "building": 2_000.0,
    "community": 50_000.0,
}


def require_range(
    value: float,
    lo: float,
    hi: float,
    *,
    name: str,
    tech_id: str,
    inclusive_lo: bool = True,
    inclusive_hi: bool = True,
) -> float:
    """Raise ``ValueError`` unless ``lo (<)= value (<)= hi``; otherwise return ``value``."""
    lo_ok = value >= lo if inclusive_lo else value > lo
    hi_ok = value <= hi if inclusive_hi else value < hi
    if not (lo_ok and hi_ok):
        lo_sym = "<=" if inclusive_lo else "<"
        hi_sym = "<=" if inclusive_hi else "<"
        raise ValueError(
            f"Technology '{tech_id}': {name}={value} is out of range "
            f"({lo} {lo_sym} {name} {hi_sym} {hi})."
        )
    return value


def require_positive_costs(params: dict[str, float], *, tech_id: str) -> None:
    """Every populated ``cost_*`` entry in ``params`` must be > 0.

    ``cost_interest_rate`` is excluded -- it has its own bound (a fraction,
    not a currency amount) applied separately in
    :func:`TechnologySpec.__post_init__`.
    """
    for key, value in params.items():
        if key.startswith("cost_") and key != "cost_interest_rate" and value <= 0:
            raise ValueError(f"Technology '{tech_id}': {key}={value} must be positive.")


def require_no_nan(
    values: NDArray[np.float64],
    *,
    name: str,
    tech_id: str,
    labels: Sequence[Any] | None = None,
) -> NDArray[np.float64]:
    """Raise ``ValueError`` if any element of ``values`` is NaN; else return it.

    ``labels`` (e.g. timestamps parallel to ``values``) makes the error name
    *which* element is bad instead of just how many.
    """
    nan_mask = np.isnan(values)
    if nan_mask.any():
        count = int(nan_mask.sum())
        first = int(np.argmax(nan_mask))
        where = f"{labels[first]!r}" if labels is not None else f"index {first}"
        raise ValueError(
            f"Technology '{tech_id}': {name} is NaN at {count} of {values.size} "
            f"timestep(s), first at {where}."
        )
    return values


def require_range_array(
    values: NDArray[np.float64],
    lo: float,
    hi: float,
    *,
    name: str,
    tech_id: str,
    labels: Sequence[Any] | None = None,
    inclusive_lo: bool = True,
    inclusive_hi: bool = True,
) -> NDArray[np.float64]:
    """Elementwise ``require_range``: raise ``ValueError`` naming how many
    timesteps are out of ``[lo, hi]`` and the first offending one.
    """
    lo_ok = values >= lo if inclusive_lo else values > lo
    hi_ok = values <= hi if inclusive_hi else values < hi
    bad_mask = ~(lo_ok & hi_ok)
    if bad_mask.any():
        count = int(bad_mask.sum())
        first = int(np.argmax(bad_mask))
        lo_sym = "<=" if inclusive_lo else "<"
        hi_sym = "<=" if inclusive_hi else "<"
        where = f"{labels[first]!r}" if labels is not None else f"index {first}"
        raise ValueError(
            f"Technology '{tech_id}': {name} is out of range "
            f"({lo} {lo_sym} {name} {hi_sym} {hi}) at {count} of {values.size} "
            f"timestep(s), first at {where} (value={values[first]})."
        )
    return values


def require_scale_capacity(
    flow_cap_max: float,
    scale: str,
    *,
    tech_id: str,
    ceilings: dict[str, float] = DEFAULT_CAPACITY_CEILINGS_KW,
) -> None:
    """Sanity-check ``flow_cap_max`` against a generous per-scale ceiling.

    Not a tight engineering limit -- a household heat pump is realistically
    3-20 kW, but the default household ceiling is 100 kW, deliberately
    generous so real research variation isn't blocked. It exists to catch
    gross data-entry errors (e.g. a stray digit), not to model reality.
    """
    ceiling = ceilings.get(scale)
    if ceiling is not None and flow_cap_max > ceiling:
        raise ValueError(
            f"Technology '{tech_id}': flow_cap_max={flow_cap_max} kW exceeds the "
            f"sanity ceiling for scale '{scale}' ({ceiling} kW). If this is "
            "genuinely intended, raise the ceiling where this technology is built."
        )
