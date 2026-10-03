"""Calculation-local reuse of concrete/rebar states for the I-girder PMM sweep.

Only one complete base sweep is retained. Prestress forces, phi and demand
checks are evaluated separately for every physical prestress state/station.
No state is persisted to the project or shared across Calculate operations.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from shapely import intersects_xy
from shapely.errors import GEOSException

from concrete_pmm_pro.analysis.strain_compatibility import is_point_inside_compression_block


@dataclass(frozen=True, slots=True)
class SectionBasePoint:
    concrete_area: float
    concrete_force: float
    Pn: float
    Mnx: float
    Mny: float
    eps_t: float | None
    eps_t_fy: float
    eps_t_es: float
    rebar_displaced_concrete_subtracted: float
    rebar_inside_compression_count: int


class PMMSectionCache:
    """One bounded, exact-key snapshot of a concrete/rebar neutral-axis sweep."""

    def __init__(self) -> None:
        self._key: tuple[Any, ...] | None = None
        self._points: tuple[SectionBasePoint, ...] = ()
        self.build_count = 0
        self.hit_count = 0

    def get(self, key: tuple[Any, ...]) -> tuple[SectionBasePoint, ...] | None:
        if key != self._key:
            return None
        self.hit_count += 1
        return self._points

    def store(self, key: tuple[Any, ...], points: list[SectionBasePoint]) -> None:
        # Publish only a completed sweep. A failed/interrupted solve cannot
        # leave a partial base available to the next physical prestress state.
        self._key, self._points = key, tuple(points)
        self.build_count += 1


def compression_membership(region: Any, xy: tuple[tuple[float, float], ...]) -> tuple[bool, ...]:
    """Same inside/on-boundary point predicate, in one GEOS batch per block.

    For valid polygonal regions, intersects_xy includes boundary points just
    like covers(Point). Keep the existing conservative scalar exception route.
    """
    if not xy:
        return ()
    try:
        if region is None or region.is_empty or not region.is_valid:
            return (False,) * len(xy)
        return tuple(bool(value) for value in intersects_xy(region, xy))
    except (GEOSException, TypeError, ValueError):
        return tuple(is_point_inside_compression_block(x, y, region) for x, y in xy)
