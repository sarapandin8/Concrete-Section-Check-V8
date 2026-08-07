from __future__ import annotations

from pathlib import Path

import pytest

from concrete_pmm_pro.analysis.crossbeam_uls import build_crossbeam_uls_flexure_preparation
from concrete_pmm_pro.analysis.crossbeam_uls_shear import build_crossbeam_uls_shear_preparation
from concrete_pmm_pro.crossbeam.cip_rebar_templates import (
    CIP_RB_TEMPLATE_ROWS_KEY,
    CIP_RB_ZONE_ROWS_KEY,
    CIP_TR_TEMPLATE_ROWS_KEY,
    default_cip_longitudinal_templates,
    default_cip_transverse_templates,
    default_cip_zone_assignments,
)
from concrete_pmm_pro.crossbeam.prestress_loss import CB_LOSS_ES_CONSTRUCTION_METHOD_KEY
from concrete_pmm_pro.crossbeam.section_library import CB_SECLIB_DEFINITIONS_KEY
from concrete_pmm_pro.crossbeam.uls_station_geometry import (
    CB_ULS_PT_END_ZONE_BASIS_KEY,
    CB_ULS_PT_END_ZONE_BASIS_LOCAL_DEPTH,
    CB_ULS_PT_END_ZONE_BASIS_MANUAL,
    CB_ULS_PT_END_ZONE_LEFT_M_KEY,
    CB_ULS_PT_END_ZONE_RIGHT_M_KEY,
    canonical_pt_end_zone_settings,
    interior_location_type,
    trace_owner_label,
)
from concrete_pmm_pro.io.project_io import (
    apply_project_to_session_state,
    project_from_json,
    project_from_session_state,
    project_to_json,
)
from tests.test_crossbeam_analysis2_uls_shear import _ready_state
from tests.test_crossbeam_analysis4_direct_uniaxial import _benchmark_state


def _cip_ready_state() -> dict[str, object]:
    state = _ready_state(include_guard_rows=False)
    state[CB_LOSS_ES_CONSTRUCTION_METHOD_KEY] = "Cast-in-Place"
    layout = state["crossbeam_ui1_segment_layout_rows"]
    longitudinal = default_cip_longitudinal_templates()
    transverse = default_cip_transverse_templates()
    state[CIP_RB_TEMPLATE_ROWS_KEY] = longitudinal
    state[CIP_TR_TEMPLATE_ROWS_KEY] = transverse
    state[CIP_RB_ZONE_ROWS_KEY] = default_cip_zone_assignments(
        layout,
        longitudinal,
        transverse,
    )
    return state


def test_full_member_policy_retains_end_rows_and_disables_pt_exclusion() -> None:
    state = _ready_state()
    settings = canonical_pt_end_zone_settings(
        state,
        member_length_m=float(state["crossbeam_ui1_length_m"]),
        segment_rows=list(state["crossbeam_ui1_segment_layout_rows"]),
        definitions=list(state[CB_SECLIB_DEFINITIONS_KEY]),
    )

    assert settings.ready, settings.errors
    assert settings.basis == "Full-member sectional ULS (no automatic PT end-zone exclusion)"
    assert settings.left_length_m == pytest.approx(0.0)
    assert settings.right_length_m == pytest.approx(0.0)
    assert settings.left_boundary_m == pytest.approx(0.0)
    assert settings.right_boundary_m == pytest.approx(20.0)

    preparation = build_crossbeam_uls_shear_preparation(state)
    assert preparation.ready, preparation.errors
    assert preparation.excluded_end_zone_rows == ()
    stations = {round(float(row.station_m), 6) for row in preparation.rows}
    assert 0.0 in stations
    assert 20.0 in stations


def test_legacy_pt_end_zone_fields_round_trip_without_changing_uls_fingerprint() -> None:
    state = _ready_state()
    baseline = build_crossbeam_uls_shear_preparation(state)

    state[CB_ULS_PT_END_ZONE_BASIS_KEY] = CB_ULS_PT_END_ZONE_BASIS_MANUAL
    state[CB_ULS_PT_END_ZONE_LEFT_M_KEY] = 1.2
    state[CB_ULS_PT_END_ZONE_RIGHT_M_KEY] = 1.4
    manual = build_crossbeam_uls_shear_preparation(state)

    assert manual.ready, manual.errors
    assert manual.fingerprint == baseline.fingerprint
    assert manual.pt_end_zone_settings["Left boundary s (m)"] == pytest.approx(0.0)
    assert manual.pt_end_zone_settings["Right boundary s (m)"] == pytest.approx(20.0)
    assert manual.excluded_end_zone_rows == ()

    restored: dict[str, object] = {}
    project = project_from_session_state(state)
    apply_project_to_session_state(project_from_json(project_to_json(project)), restored)
    assert restored[CB_ULS_PT_END_ZONE_BASIS_KEY] == CB_ULS_PT_END_ZONE_BASIS_MANUAL
    assert restored[CB_ULS_PT_END_ZONE_LEFT_M_KEY] == pytest.approx(1.2)
    assert restored[CB_ULS_PT_END_ZONE_RIGHT_M_KEY] == pytest.approx(1.4)


def test_flexure_generates_column_faces_only_and_omits_support_interiors() -> None:
    preparation = build_crossbeam_uls_flexure_preparation(_benchmark_state())

    assert preparation.ready, preparation.errors
    face_rows = [row for row in preparation.rows if row.location_type == "COLUMN FACE"]
    assert len(face_rows) == 6
    assert {row.check_point for row in face_rows} == {
        "C1-L Face",
        "C1-R Face",
        "C2-L Face",
        "C2-R Face",
        "C3-L Face",
        "C3-R Face",
    }
    assert not any("h/2" in row.check_point for row in preparation.rows)
    for footprint in preparation.support_footprints:
        left = float(footprint["s_left (m)"])
        right = float(footprint["s_right (m)"])
        assert not any(
            left < row.station_m < right
            and row.location_type not in {"PHYSICAL SEGMENT JOINT", "PHYSICAL JOINT SIDE"}
            for row in preparation.rows
        )


def test_shear_uses_faces_and_h2_while_cip_has_no_physical_joint_rows() -> None:
    precast = build_crossbeam_uls_shear_preparation(_ready_state())
    assert precast.ready, precast.errors
    assert any(row.location_type == "COLUMN FACE" for row in precast.rows)
    assert any(row.location_type == "ACI h/2 CRITICAL SECTION" for row in precast.rows)
    assert any(row.location_type == "PHYSICAL JOINT SIDE" for row in precast.rows)

    cip = build_crossbeam_uls_shear_preparation(_cip_ready_state())
    assert cip.ready, cip.errors
    assert any(row.location_type == "ZONE INTERIOR" for row in cip.rows)
    assert any(row.location_type == "COLUMN FACE" for row in cip.rows)
    assert any(row.location_type == "ACI h/2 CRITICAL SECTION" for row in cip.rows)
    assert not any("JOINT" in row.location_type for row in cip.rows)


def test_construction_mode_terminology_is_explicit() -> None:
    assert interior_location_type("Cast-in-Place") == "ZONE INTERIOR"
    assert trace_owner_label("Cast-in-Place") == "Zone-owned"
    assert interior_location_type("Precast Segmental") == "SEGMENT INTERIOR"
    assert trace_owner_label("Precast Segmental") == "Segment-owned"


def test_analysis_ui_uses_full_member_policy_and_mode_aware_chart_context() -> None:
    source = Path("concrete_pmm_pro/ui/analysis_page.py").read_text(encoding="utf-8")
    assert "ULS station routing / scope" in source
    assert "FULL MEMBER" in source
    assert "s = 0 to s = L stays eligible for governing" in source
    assert '"Zone-owned" if normalize_construction_method(construction_method)' in source
    assert 'else "Segment-owned"' in source
    assert "full-span PT end stations retained" in source
    assert "Cast-in-Place Zone boundaries" in source
    assert "PT end-zone exclusions" not in source
