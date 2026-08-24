"""Geometry helpers for closed transverse torsion hoop centerlines.

The Precast I-Girder torsion workflow uses the actual centerline perimeter ``ph``
of the closed transverse torsion reinforcement.  The section shape is constant
along the member, so ``ph`` should be derived from one section geometry rather
than manually re-entered in every longitudinal reinforcement zone.
"""

from __future__ import annotations

from dataclasses import dataclass
import math

from concrete_pmm_pro.core.models import SectionGeometry
from concrete_pmm_pro.geometry.summary import to_shapely_polygon


@dataclass(frozen=True)
class ClosedHoopCenterlineResult:
    ready: bool
    ph_mm: float | None
    centerline_offset_mm: float | None
    clear_cover_mm: float | None
    bar_diameter_mm: float | None
    coordinates: tuple[tuple[float, float], ...]
    note: str


def derive_closed_hoop_centerline(
    section_geometry: SectionGeometry,
    *,
    clear_cover_mm: float,
    bar_diameter_mm: float,
    centerline_offset_override_mm: float | None = None,
) -> ClosedHoopCenterlineResult:
    """Return the inward-offset closed-hoop centerline and its perimeter ``ph``.

    Default centerline offset is ``clear cover + db/2``.  A positive audited
    centerline-offset override may be supplied for a shop-detail-specific cage.
    The returned path is the exterior of the single inward-offset polygon; a
    split/empty offset is treated as not ready rather than silently choosing a
    region.
    """

    cover = float(clear_cover_mm)
    db = float(bar_diameter_mm)
    if not math.isfinite(cover) or cover < 0.0:
        return ClosedHoopCenterlineResult(False, None, None, None, None, (), "Clear cover must be a finite nonnegative value.")
    if not math.isfinite(db) or db <= 0.0:
        return ClosedHoopCenterlineResult(False, None, None, cover, None, (), "Closed-hoop bar diameter must be positive.")

    override = centerline_offset_override_mm
    if override is not None:
        override = float(override)
        if not math.isfinite(override) or override <= 0.0:
            return ClosedHoopCenterlineResult(False, None, None, cover, db, (), "Audited centerline-offset override must be positive when enabled.")
        offset = override
        basis = f"audited centerline offset = {offset:.1f} mm"
    else:
        offset = cover + 0.5 * db
        basis = f"clear cover {cover:.1f} mm + db/2 = {0.5*db:.1f} mm"

    try:
        polygon = to_shapely_polygon(section_geometry)
    except Exception as exc:
        return ClosedHoopCenterlineResult(False, None, offset, cover, db, (), f"Section geometry could not be converted for hoop derivation ({type(exc).__name__}).")
    if polygon.is_empty or not polygon.is_valid or polygon.area <= 0.0:
        return ClosedHoopCenterlineResult(False, None, offset, cover, db, (), "Section geometry is not a valid positive-area polygon.")

    try:
        inset = polygon.buffer(-offset, join_style=2)
    except Exception as exc:
        return ClosedHoopCenterlineResult(False, None, offset, cover, db, (), f"Closed-hoop centerline offset failed ({type(exc).__name__}).")
    if inset.is_empty or float(inset.area) <= 0.0:
        return ClosedHoopCenterlineResult(False, None, offset, cover, db, (), "Closed-hoop centerline offset is too large for the active section geometry.")
    if getattr(inset, "geoms", None):
        return ClosedHoopCenterlineResult(False, None, offset, cover, db, (), "Closed-hoop centerline offset splits into multiple regions; use an audited geometry basis rather than an automatic ph.")
    if not hasattr(inset, "exterior"):
        return ClosedHoopCenterlineResult(False, None, offset, cover, db, (), "Closed-hoop centerline did not produce a single closed polygon.")

    ph = float(inset.exterior.length)
    coords = tuple((float(x), float(y)) for x, y in list(inset.exterior.coords)[:-1])
    if not math.isfinite(ph) or ph <= 0.0 or len(coords) < 3:
        return ClosedHoopCenterlineResult(False, None, offset, cover, db, (), "Automatic closed-hoop centerline perimeter is not finite.")
    return ClosedHoopCenterlineResult(
        True,
        ph,
        offset,
        cover,
        db,
        coords,
        f"Auto ph from the active section closed-hoop centerline using {basis}.",
    )
