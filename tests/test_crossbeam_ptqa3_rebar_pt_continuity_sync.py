import streamlit as st

from concrete_pmm_pro.crossbeam.rebar import (
    default_crossbeam_rebar_templates,
    default_crossbeam_rebar_zones,
)
from concrete_pmm_pro.crossbeam.section_library import (
    default_section_definitions,
    migrate_segment_rows_to_library,
)
from concrete_pmm_pro.crossbeam.tendon import (
    default_tendon_profile_points,
    default_tendon_system_rows,
)
from concrete_pmm_pro.crossbeam.tendon_persistence import (
    CB_PROFILE_ROWS_KEY,
    CB_TENDON_SYSTEM_ROWS_KEY,
)
from concrete_pmm_pro.crossbeam.workflow import default_crossbeam_segment_rows
from concrete_pmm_pro.ui.crossbeam_rebar_page import (
    _pt_continuity_review_from_state,
    _rebar_elevation_figure,
)


def _default_context():
    definitions = default_section_definitions()
    segments = migrate_segment_rows_to_library(
        default_crossbeam_segment_rows(20.0), definitions
    )
    system = default_tendon_system_rows()
    tendon_ids = [row["Tendon ID"] for row in system]
    profile = default_tendon_profile_points(
        20.0,
        tendon_ids=tendon_ids,
        width_mm=2500.0,
        height_mm=1500.0,
        t_left_mm=300.0,
        t_right_mm=300.0,
    )
    return definitions, segments, system, profile


def test_ptqa3_rebar_page_reads_verified_tendon_profile_continuity() -> None:
    definitions, segments, system, profile = _default_context()
    st.session_state.clear()
    st.session_state[CB_TENDON_SYSTEM_ROWS_KEY] = system
    st.session_state[CB_PROFILE_ROWS_KEY] = profile

    review = _pt_continuity_review_from_state(
        length_m=20.0,
        segment_rows=segments,
        section_definitions=definitions,
        tendon_enabled=True,
    )

    assert review["value"] == "GEOMETRY VERIFIED"
    assert review["status"] == "ready"
    assert review["joint_status"] == "PT GEOMETRY VERIFIED"
    assert review["joint_by_station"]
    assert {
        row["status"] for row in review["joint_by_station"].values()
    } == {"PT GEOMETRY VERIFIED"}


def test_ptqa3_rebar_elevation_annotation_uses_live_pt_review_label() -> None:
    definitions, segments, system, profile = _default_context()
    st.session_state.clear()
    st.session_state[CB_TENDON_SYSTEM_ROWS_KEY] = system
    st.session_state[CB_PROFILE_ROWS_KEY] = profile
    review = _pt_continuity_review_from_state(
        length_m=20.0,
        segment_rows=segments,
        section_definitions=definitions,
        tendon_enabled=True,
    )

    fig = _rebar_elevation_figure(
        segments,
        default_crossbeam_rebar_zones(segments),
        default_crossbeam_rebar_templates(),
        20.0,
        review,
    )
    annotations = [str(item.text) for item in fig.layout.annotations]

    assert any("PT geometry verified" in text for text in annotations)
    assert not any("PT not verified" in text for text in annotations)
