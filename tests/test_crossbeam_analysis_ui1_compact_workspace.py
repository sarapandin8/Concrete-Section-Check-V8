from __future__ import annotations

from pathlib import Path

from concrete_pmm_pro.ui.crossbeam_analysis_page import (
    _dataset_ready,
    _governing_actual_limit_text,
    _signed_stress_text,
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
    precast = _sls_check_table(stage="At Transfer", source_ready=True, construction_method="Precast Segmental")
    assert precast["Check"].tolist() == [
        "Concrete stress — top / bottom",
        "Physical segment-joint compression — Top / Bottom",
    ]
    assert precast.iloc[1]["Actual / limit"] == "fjoint ≤ −0.700 MPa"

    cip = _sls_check_table(stage="At Transfer", source_ready=True, construction_method="Cast-in-Place")
    assert cip.iloc[1]["Status"] == "NOT REQUIRED"


def test_crossbeam_analysis_ui_enables_flexure_only_and_keeps_both_sls_stages() -> None:
    assert 'st.button(\n            f"Calculate {selected_check}"' in PAGE_SOURCE
    assert 'st.button(\n            f"Calculate {stage}"' in PAGE_SOURCE
    assert 'selected_check != "Flexure"' in PAGE_SOURCE
    assert "disabled=not source_ready" in PAGE_SOURCE
    assert "calculate_crossbeam_transfer_stress" in PAGE_SOURCE
    assert "calculate_crossbeam_service_stress" in PAGE_SOURCE
    assert "Service stress basis" in PAGE_SOURCE
    assert "calculate_crossbeam_uls_flexure" in PAGE_SOURCE
    assert "P–M3 interaction" in PAGE_SOURCE


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


def test_signed_stress_text_shows_explicit_tension_plus_sign() -> None:
    assert _signed_stress_text(6.789) == "+6.789"
    assert _signed_stress_text(-6.789) == "−6.789"
    assert _signed_stress_text(0.0) == "0.000"


def test_compact_sls_actual_limit_text_keeps_signed_stress_visible() -> None:
    stress_text = _governing_actual_limit_text(
        {"Stress (MPa)": 8.958, "Limit (MPa)": 4.159, "Utilization": 2.154}
    )
    assert stress_text == "+8.958 / +4.159 MPa · D/C 2.154"

    table = _sls_check_table(
        stage="At Service",
        source_ready=True,
        construction_method="Precast Segmental",
        result={
            "stress_status": "FAIL",
            "joint_status": "FAIL",
            "joint_min_compression_mpa": 0.70,
            "governing": {
                "Stress (MPa)": 8.958,
                "Limit (MPa)": 4.159,
                "Utilization": 2.154,
            },
            "governing_joint": {
                "Stress (MPa)": 6.789,
                "Case / Combination": "ULS-01",
                "Station s (m)": 10.0,
                "Boundary ID": "S3 / S4",
                "Fiber": "Bottom",
            },
        },
        result_state="FAIL",
    )
    assert table.iloc[0]["Actual / limit"] == "+8.958 / +4.159 MPa · D/C 2.154"
    assert table.iloc[1]["Actual / limit"] == "+6.789 / ≤ −0.700 MPa"
