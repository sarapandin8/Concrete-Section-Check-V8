"""Section-level reinforcement/prestress enable flags.

The flags introduced in REBAR.SYSTEM1 are intentionally metadata gates.  They
must not delete user-entered rebar/prestress tables; they only determine whether
ordinary rebar and prestressing steel are active for UI display and analysis
input assembly.
"""

from __future__ import annotations

from typing import Any

from concrete_pmm_pro.core.analysis import AnalysisSettings
from concrete_pmm_pro.core.models import PrestressElement, Rebar

ORDINARY_REBAR_FLAG_KEY = "section_has_ordinary_rebar"
PRESTRESSING_STEEL_FLAG_KEY = "section_has_prestressing_steel"
REINFORCEMENT_FLAGS_PRESET_KEY = "reinforcement_flags_preset_key"

# Section-level prestress rows are a generic/legacy input model.  Precast
# girder workflows use the dedicated strand-layout/debonding metadata instead,
# so PS1/PS2-style section rows must be ignored by analysis for these presets.
GIRDER_SECTION_LEVEL_PRESTRESS_IGNORED_PRESET_KEYS = frozenset(
    {
        "parametric_i_girder",
        "u_girder",
        "box_section_fillet",
        "precast_box_beam_exterior",
        "parametric_plank_girder_interior",
        "parametric_plank_girder_exterior",
        "parametric_plank_girder_voided_interior",
        "parametric_plank_girder_voided_exterior",
        "psc_i_girder",
        "single_cell_box_girder",
    }
)


_MISSING = object()


def _get_value(source: Any, key: str, default: Any = None) -> Any:
    """Return a section/workflow flag from session-like sources.

    UI pages normally read reinforcement-system flags directly from
    ``st.session_state``.  Saved projects can restore older/newer files with
    the flags mirrored in ``project_metadata`` before every top-level key has
    been materialized by the active page.  Falling back to metadata keeps
    Section Builder, Rebar, Prestress, Analysis, and Project views aligned
    without deleting the stored input tables.
    """

    if hasattr(source, "get"):
        value = source.get(key, _MISSING)
        if value is not _MISSING:
            return value
        metadata = source.get("project_metadata", _MISSING)
        if isinstance(metadata, dict):
            metadata_value = metadata.get(key, _MISSING)
            if metadata_value is not _MISSING:
                return metadata_value
        return default

    if hasattr(source, key):
        return getattr(source, key)
    metadata = getattr(source, "project_metadata", _MISSING)
    if isinstance(metadata, dict):
        metadata_value = metadata.get(key, _MISSING)
        if metadata_value is not _MISSING:
            return metadata_value
    return default


def _to_bool(value: Any, default: bool) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    text = str(value).strip().casefold()
    if text in {"1", "true", "yes", "y", "on", "enabled"}:
        return True
    if text in {"0", "false", "no", "n", "off", "disabled"}:
        return False
    return bool(value)


def default_section_reinforcement_flags(
    *,
    member_type: str | None,
    section_category: str | None,
    section_preset_key: str | None,
    girder_section_family: str | None = None,
) -> tuple[bool, bool]:
    """Return default ordinary-rebar and prestress flags for a selected section.

    Defaults are intentionally conservative for the two active product
    workflows.  Column/Pier/Wall/Pylon PMM starts as ordinary RC.  Bridge
    Beam/Girder sections start with ordinary rebar enabled so longitudinal
    mild bars / torsion Al remain active unless the engineer explicitly turns
    them off; prestressing is seeded on for prestressed/precast girder presets.
    """

    member = (member_type or "").casefold()
    category = (section_category or "").casefold()
    preset = (section_preset_key or "").casefold()
    family = (girder_section_family or "").casefold()

    if member == "beam_girder":
        # Beam/Girder workflows often need mild longitudinal bars for flexure
        # participation, confinement/detailing review, and torsion Al checks.
        # Keep the data active by default; the Section Builder switch remains
        # available when the engineer intentionally wants an unreinforced
        # concrete-only review.
        ordinary_rebar = True
        prestress = family == "precast_composite_girder" or category == "precast composite girder"
        # Legacy PSC I-girder is non-composite in the preset library but is still
        # a prestressed girder by intent.
        if preset == "psc_i_girder":
            prestress = True
        return ordinary_rebar, prestress

    if member == "building_beam_girder":
        # WORKFLOW.TYPE3: shared precast girder geometry can be used in the ACI
        # Building Beam/Girder workflow without enabling bridge-specific tools.
        # For Precast I-Girder, seed prestressing on because that is the usual
        # engineering intent; ordinary RC beam shapes still default to rebar only.
        if preset == "parametric_i_girder":
            return False, True
        return True, False

    if member == "portal_frame_crossbeam":
        # CROSSBEAM.WF1: PC crossbeams require mild reinforcement detailing and
        # prestressing tendon definitions as active source data from the start.
        return True, True

    return True, False




def _member_type_from_source(source: Any) -> str:
    settings = _get_value(source, "analysis_mode_settings", None)
    if settings is not None:
        if hasattr(settings, "member_type"):
            return str(getattr(settings, "member_type") or "").strip().casefold()
        if hasattr(settings, "get"):
            return str(settings.get("member_type") or "").strip().casefold()
    return str(_get_value(source, "member_type", "") or "").strip().casefold()


def section_level_prestress_ignored_for_girder(source: Any) -> bool:
    """Return True when legacy section-level prestress rows are ignored.

    Precast/simple-supported girder workflows use the dedicated strand layout and
    force-state inputs.  The old section-level tendon table may remain in saved
    projects for compatibility, but it must not be assembled into PMM/SLS
    AnalysisInput for girder presets because that can silently double-count or
    reintroduce stale PS1/PS2 reference rows.
    """

    member_type = _member_type_from_source(source)
    family = str(_get_value(source, "girder_section_family", "") or "").strip().casefold()
    category = str(_get_value(source, "section_category", "") or "").strip().casefold()
    preset = str(_get_value(source, "section_preset_key", "") or "").strip().casefold()
    bridge_dedicated_girder = (
        member_type == "beam_girder"
        and (
            family == "precast_composite_girder"
            or category == "precast composite girder"
            or preset in GIRDER_SECTION_LEVEL_PRESTRESS_IGNORED_PRESET_KEYS
        )
    )
    building_shared_prestressed_girder = member_type == "building_beam_girder" and preset == "parametric_i_girder"
    return bridge_dedicated_girder or building_shared_prestressed_girder


def _workflow_default_flags_from_source(source: Any, *, default_rebar: bool, default_prestress: bool) -> tuple[bool, bool]:
    """Return workflow-aware default steel-system flags for session-like sources.

    The visible Section Builder switches are the source of truth once they exist.
    Before a page has materialized those top-level keys, downstream pages such
    as Rebar may still need a safe default from the active member type and
    section preset.  This prevents Bridge Beam/Girder and shared Building
    Beam/Girder prestressed presets from presenting stored mild bars as active
    analysis reinforcement merely because the explicit checkbox state has not
    been loaded in the current rerun yet.
    """

    member_type = _member_type_from_source(source)
    section_category = str(_get_value(source, "section_category", "") or "").strip()
    section_preset_key = str(_get_value(source, "section_preset_key", "") or "").strip()
    girder_section_family = str(_get_value(source, "girder_section_family", "") or "").strip()
    if not (member_type or section_category or section_preset_key or girder_section_family):
        return default_rebar, default_prestress
    try:
        return default_section_reinforcement_flags(
            member_type=member_type,
            section_category=section_category,
            section_preset_key=section_preset_key,
            girder_section_family=girder_section_family,
        )
    except Exception:
        return default_rebar, default_prestress


def ordinary_rebar_enabled(source: Any, *, default: bool = True) -> bool:
    workflow_rebar_default, _ = _workflow_default_flags_from_source(
        source, default_rebar=default, default_prestress=True
    )
    return _to_bool(_get_value(source, ORDINARY_REBAR_FLAG_KEY, None), workflow_rebar_default)


def prestressing_steel_enabled(source: Any, *, default: bool = True) -> bool:
    _, workflow_prestress_default = _workflow_default_flags_from_source(
        source, default_rebar=True, default_prestress=default
    )
    return _to_bool(_get_value(source, PRESTRESSING_STEEL_FLAG_KEY, None), workflow_prestress_default)


def effective_rebars_for_analysis(
    rebars: list[Rebar],
    source: Any,
    settings: AnalysisSettings | None = None,
) -> list[Rebar]:
    if settings is not None and not settings.include_rebars:
        return []
    if not ordinary_rebar_enabled(source, default=True):
        return []
    return list(rebars)


def effective_prestress_for_analysis(
    prestress_elements: list[PrestressElement],
    source: Any,
    settings: AnalysisSettings | None = None,
) -> list[PrestressElement]:
    if settings is not None and not settings.include_prestress:
        return []
    if not prestressing_steel_enabled(source, default=True):
        return []
    if section_level_prestress_ignored_for_girder(source):
        return []
    return list(prestress_elements)


def reinforcement_system_status(source: Any) -> dict[str, bool]:
    return {
        "ordinary_rebar": ordinary_rebar_enabled(source, default=True),
        "prestressing_steel": prestressing_steel_enabled(source, default=True),
    }
