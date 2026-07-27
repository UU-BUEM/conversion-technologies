"""Shared CHP energy-hub dispatch factors (alpha, beta).

Every CHP technology here is specified directly via the energy-hub
dispatch-factor notation (Geidl & Andersson, 2007, "Optimal Power Flow of
Multiple Energy Carriers"): fuel input splits into electrical and thermal
output via two fixed per-unit-fuel efficiencies::

    P_elec = alpha * P_fuel
    P_heat = beta * P_fuel

so ``alpha`` is the electrical efficiency and ``beta`` the thermal
efficiency -- both fractions of fuel input, not of each other.
"""

from __future__ import annotations


def validate_dispatch_factors(alpha: float, beta: float) -> None:
    """Check that dispatch factors alpha (electrical) and beta (thermal) are valid."""
    if not 0.0 < alpha <= 1.0:
        raise ValueError("alpha (electrical efficiency) must be in (0, 1].")
    if not 0.0 < beta <= 1.0:
        raise ValueError("beta (thermal efficiency) must be in (0, 1].")
    if alpha + beta > 1.0:
        raise ValueError("alpha + beta (total fuel efficiency) cannot exceed 1.0.")


def power_to_heat_ratio(alpha: float, beta: float) -> float:
    """Derived power:heat ratio (``alpha / beta``) -- for notes/documentation only."""
    return alpha / beta
