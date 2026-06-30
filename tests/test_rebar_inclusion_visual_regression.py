from __future__ import annotations

from pathlib import Path

from concrete_pmm_pro.core.models import Rebar
from concrete_pmm_pro.core.reinforcement_system import (
    ORDINARY_REBAR_FLAG_KEY,
    PRESTRESSING_STEEL_FLAG_KEY,
    effective_rebars_for_analysis,
    ordinary_rebar_enabled,
    prestressing_steel_enabled,
    reinforcement_system_status,
)

REBAR_PAGE_SOURCE = Path("concrete_pmm_pro/ui/rebar_page.py").read_text(encoding="utf-8")


_SAMPLE_REBARS = [
    Rebar(x_mm=-100.0, y_mm=-200.0, diameter_mm=20.0, material_name="SD40", label="B1"),
    Rebar(x_mm=100.0, y_mm=-200.0, diameter_mm=20.0, material_name="SD40", label="B2"),
]


def _workflow_state(
    member_type: str,
    *,
    category: str,
    preset: str,
    family: str | None = None,
    include_rebar: bool | None = None,
    include_prestress: bool | None = None,
) -> dict[str, object]:
    state: dict[str, object] = {
        "analysis_mode_settings": {"member_type": member_type},
        "section_category": category,
        "section_preset_key": preset,
    }
    if family is not None:
        state["girder_section_family"] = family
    if include_rebar is not None:
        state[ORDINARY_REBAR_FLAG_KEY] = include_rebar
    if include_prestress is not None:
        state[PRESTRESSING_STEEL_FLAG_KEY] = include_prestress
    return state


def test_inclusion4_column_pier_defaults_publish_active_rebars() -> None:
    state = _workflow_state(
        "column_pier_pmm",
        category="Basic Solid",
        preset="rectangle",
    )

    assert ordinary_rebar_enabled(state, default=False) is True
    assert prestressing_steel_enabled(state, default=True) is False
    assert reinforcement_system_status(state) == {"ordinary_rebar": True, "prestressing_steel": False}
    assert effective_rebars_for_analysis(_SAMPLE_REBARS, state) == _SAMPLE_REBARS


def test_inclusion4_bridge_precast_girder_defaults_store_rebars_but_publish_none() -> None:
    state = _workflow_state(
        "beam_girder",
        category="Precast Composite Girder",
        preset="parametric_i_girder",
        family="precast_composite_girder",
    )

    assert ordinary_rebar_enabled(state, default=True) is False
    assert prestressing_steel_enabled(state, default=False) is True
    assert reinforcement_system_status(state) == {"ordinary_rebar": False, "prestressing_steel": True}
    assert effective_rebars_for_analysis(_SAMPLE_REBARS, state) == []


def test_inclusion4_building_shared_prestressed_girder_defaults_store_rebars_but_publish_none() -> None:
    state = _workflow_state(
        "building_beam_girder",
        category="Precast Composite Girder",
        preset="parametric_i_girder",
        family="precast_composite_girder",
    )

    assert ordinary_rebar_enabled(state, default=True) is False
    assert prestressing_steel_enabled(state, default=False) is True
    assert reinforcement_system_status(state) == {"ordinary_rebar": False, "prestressing_steel": True}
    assert effective_rebars_for_analysis(_SAMPLE_REBARS, state) == []


def test_inclusion4_building_basic_rc_beam_defaults_publish_active_rebars() -> None:
    state = _workflow_state(
        "building_beam_girder",
        category="Basic Solid",
        preset="rectangle",
    )

    assert ordinary_rebar_enabled(state, default=False) is True
    assert prestressing_steel_enabled(state, default=True) is False
    assert reinforcement_system_status(state) == {"ordinary_rebar": True, "prestressing_steel": False}
    assert effective_rebars_for_analysis(_SAMPLE_REBARS, state) == _SAMPLE_REBARS


def test_inclusion4_explicit_checkbox_state_remains_source_of_truth_for_visual_state() -> None:
    excluded_bridge_state = _workflow_state(
        "beam_girder",
        category="Precast Composite Girder",
        preset="parametric_i_girder",
        family="precast_composite_girder",
        include_rebar=True,
        include_prestress=False,
    )
    disabled_rc_state = _workflow_state(
        "column_pier_pmm",
        category="Basic Solid",
        preset="rectangle",
        include_rebar=False,
        include_prestress=True,
    )

    assert effective_rebars_for_analysis(_SAMPLE_REBARS, excluded_bridge_state) == _SAMPLE_REBARS
    assert reinforcement_system_status(excluded_bridge_state) == {"ordinary_rebar": True, "prestressing_steel": False}
    assert effective_rebars_for_analysis(_SAMPLE_REBARS, disabled_rc_state) == []
    assert reinforcement_system_status(disabled_rc_state) == {"ordinary_rebar": False, "prestressing_steel": True}


def test_inclusion4_rebar_page_disabled_visual_state_preserves_stored_rows_and_publishes_zero_active_rows() -> None:
    disabled_branch_start = REBAR_PAGE_SOURCE.index("if not ordinary_rebar_system_enabled:")
    disabled_branch_end = REBAR_PAGE_SOURCE.index('    if "rebar_table" not in st.session_state:', disabled_branch_start)
    disabled_branch = REBAR_PAGE_SOURCE[disabled_branch_start:disabled_branch_end]

    assert "Stored Rebar table data is preserved for later use" in disabled_branch
    assert 'st.session_state["rebars_stored_excluded"] = result.rebars' in disabled_branch
    assert 'st.session_state["rebars"] = []' in disabled_branch
    assert 'st.session_state["rebars_valid_for_analysis"] = False' in disabled_branch
    assert 'RebarMetric("Stored Bars"' in disabled_branch
    assert 'RebarMetric("Stored As"' in disabled_branch
    assert 'RebarMetric("Analysis Participation", "Excluded"' in disabled_branch
    assert 'RebarMetric("Active Analysis Bars", "0"' in disabled_branch
    assert 'RebarMetric("Active Analysis As", "0.0 mm^2")' in disabled_branch
    assert "Stored Rebar Preview — Excluded from Analysis" in disabled_branch
    assert "Preview only — these stored bars are excluded from analysis" in disabled_branch
    assert "Dimension guides are intentionally hidden on the Rebar page" in disabled_branch
    assert "create_section_preview(" in disabled_branch
    assert "geometry" in disabled_branch
    assert "result.rebars" in disabled_branch
    assert 'st.session_state.get("section_dimensions", [])' not in disabled_branch
