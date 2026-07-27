"""Central registry of technology builders.

Adding a technology is: write a builder function in a ``specific/`` module,
call :func:`register_technology`, and import that module from the category's
``specific/__init__.py``. Nothing outside the new module needs to change.
"""

from __future__ import annotations

from collections.abc import Callable

from conversion_technologies.core.technology import TechnologySpec

TechnologyBuilder = Callable[[], TechnologySpec]

_REGISTRY: dict[str, TechnologyBuilder] = {}


def register_technology(tech_id: str, builder: TechnologyBuilder) -> None:
    """Register ``builder`` under ``tech_id``. Raises if the id is already taken."""
    if tech_id in _REGISTRY:
        raise ValueError(f"Technology '{tech_id}' is already registered.")
    _REGISTRY[tech_id] = builder


def get_technology(tech_id: str) -> TechnologySpec:
    """Build and return the technology registered under ``tech_id``."""
    try:
        builder = _REGISTRY[tech_id]
    except KeyError as exc:
        raise KeyError(
            f"Unknown technology id: {tech_id!r}. Available: {sorted(_REGISTRY)}"
        ) from exc
    return builder()


def all_technologies() -> dict[str, TechnologySpec]:
    """Build and return every registered technology, keyed by id."""
    return {tech_id: builder() for tech_id, builder in _REGISTRY.items()}


def list_technology_ids() -> list[str]:
    """Return the sorted list of registered technology ids."""
    return sorted(_REGISTRY)
