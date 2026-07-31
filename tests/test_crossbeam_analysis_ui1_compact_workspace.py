from __future__ import annotations

from pathlib import Path

from concrete_pmm_pro.ui.crossbeam_analysis_page import (
    _dataset_ready,
    _sls_check_table,
    _uls_check_table,
)


ANALYSIS_SOURCE = Path("concrete_pmm_pro/ui/analysis_page.py").read_text(encoding="utf-8")
PAGE_SOURCE = Path("concrete_pmm_pro/ui/crossbeam_analysis_page.py").read_text(encoding="utf-8")


def test_dataset_readiness_is_scoped_to_selected_dataset_mapping() -> None:
    assert _dataset_ready(
        {
            "Source ready": True,
            "Mapped check contexts": 5,
            "Mapping errors": 0,
        }
    ) is True
    assert _dataset_ready(
        {
            "Source ready": True,
            "Mapped check contexts": 0,
            "Mapping errors": 0,
        }
    ) is False
    assert _dataset_ready(
        {
            "Source ready": True,
            "Mapped check contexts": 5,
            "Mapping errors": 1,
        }
    ) is False


def test_compact_uls_table_has_only_four_engineering_checks() -> None:
    frame = _uls_check_table(selected_check="Flexure", source_ready=True)
    assert frame["Check"].tolist() == ["Flexure", "Shear", "Torsion", "Shear + Torsion"]
    assert set(frame["Status"]) == {"NOT CALCULATED"}
    assert len(frame.columns) == 5


def test_compact_sls_table_has_stress_and_joint_gate_only() -> None:
    precast = _sls_check_table(source_ready=True, construction_method="Precast Segmental")
    assert precast["Check"].tolist() == [
        "Concrete stress — top / bottom",
        "Physical segment-joint compression",
    ]
    assert precast.iloc[1]["Actual / limit"] == "≥ 0.70 MPa compression"

    cip = _sls_check_table(source_ready=True, construction_method="Cast-in-Place")
    assert cip.iloc[1]["Status"] == "NOT REQUIRED"


def test_crossbeam_analysis_ui_uses_disabled_actions_until_real_solvers_exist() -> None:
    assert 'st.button(\n            f"Calculate {selected_check}"' in PAGE_SOURCE
    assert 'st.button(\n            f"Calculate {stage}"' in PAGE_SOURCE
    assert PAGE_SOURCE.count("disabled=True") >= 2
    assert "The disabled action prevents a UI shell from being mistaken for a completed strength check." in PAGE_SOURCE


def test_crossbeam_router_does_not_fall_through_to_generic_beam_girder_solvers() -> None:
    crossbeam_branch = ANALYSIS_SOURCE.index("if is_portal_frame_crossbeam_workflow(settings):")
    generic_uls = ANALYSIS_SOURCE.index('elif active_subpage == "ULS Strength":', crossbeam_branch)
    assert crossbeam_branch < generic_uls
    assert "render_crossbeam_uls_workspace()" in ANALYSIS_SOURCE[crossbeam_branch:generic_uls]
    assert "render_crossbeam_sls_workspace()" in ANALYSIS_SOURCE[crossbeam_branch:generic_uls]


def test_crossbeam_header_uses_two_cards_to_avoid_duplicate_context() -> None:
    assert "Workflow, code, and units already appear in the active-context strip." in ANALYSIS_SOURCE
    assert 'if is_portal_frame_crossbeam_workflow(settings):\n        # Workflow, code, and units' in ANALYSIS_SOURCE


def test_main_crossbeam_pages_do_not_render_source_coverage_before_result_workspace() -> None:
    uls_start = PAGE_SOURCE.index("def render_crossbeam_uls_workspace")
    sls_start = PAGE_SOURCE.index("def render_crossbeam_sls_workspace")
    legacy_start = PAGE_SOURCE.index("def render_crossbeam_analysis_foundation")
    uls_body = PAGE_SOURCE[uls_start:sls_start]
    sls_body = PAGE_SOURCE[sls_start:legacy_start]
    assert "make_crossbeam_station_coverage_figure" not in uls_body
    assert "make_crossbeam_station_coverage_figure" not in sls_body
    assert "_render_source_audit" in uls_body
    assert "_render_source_audit" in sls_body
