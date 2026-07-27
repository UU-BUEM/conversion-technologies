"""Importing this package registers every boiler technology."""

from __future__ import annotations

from conversion_technologies.new.boiler.specific import (  # noqa: F401
    biomass_boiler,
    electric_boiler,
    gas_boiler,
)
