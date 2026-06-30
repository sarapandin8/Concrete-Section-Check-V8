from __future__ import annotations

import pytest

from concrete_pmm_pro.geometry.generators import railway_u_girder
from concrete_pmm_pro.serviceability.railway_u_girder_stages import (
    railway_u_girder_lifting_stage_audit_dataframe,
)
from concrete_pmm_pro.ui.prestress_page import _default_girder_strand_layout_table


def _railway_geometry():
    return railway_u_girder(
        width_mm=5500,
        depth_mm=1600,
        top_wall_width_mm=600,
        bottom_side_width_mm=650,
        haunch_x_mm=300,
        haunch_y_mm=300,
        h1_step_height_mm=670,
        h2_bottom_opening_mm=305,
        h3_floor_side_thickness_mm=395,
        h4_floor_center_thickness_mm=450,
    )


def _stage_settings():
    return {
        "web_fc_MPa": 45.0,
        "web_fci_MPa": 36.0,
        "slab_fc_MPa": 35.0,
        "concrete_unit_weight_kN_m3": 24.0,
        "wet_slab_distribution_each_web": 0.5,
        "formwork_construction_load_kN_m2": 2.5,
        "lifting_point_ratio": 0.05,
        "lifting_impact_factor": 1.10,
    }


def _deboned_layout_table():
    geom = _railway_geometry()
    table = _default_girder_strand_layout_table(geom)
    # Match the user-facing Railway U-Girder pattern: row 1 controls at 2.0 m,
    # row 2 at 1.5 m, row 3 at 1.0 m. The audit helper filters to one web for
    # lifting-stage preview.
    for group, length, nos in (
        ("L Row 1", 2.0, "1,3,7,9"),
        ("L Row 2", 1.5, "1,3,7,9"),
        ("L Row 3", 1.0, "2,4,6"),
        ("R Row 1", 2.0, "1,3,7,9"),
        ("R Row 2", 1.5, "1,3,7,9"),
        ("R Row 3", 1.0, "2,4,6"),
    ):
        mask = table["Group ID"] == group
        table.loc[mask, "Debonded strand nos"] = nos
        table.loc[mask, "Left debond m"] = length
        table.loc[mask, "Right debond m"] = length
    return table


def test_lifting_audit_uses_section_builder_a_over_l_and_two_point_supports():
    geom = _railway_geometry()
    audit = railway_u_girder_lifting_stage_audit_dataframe(
        geometry=geom,
        settings=_stage_settings(),
        strand_table=_deboned_layout_table(),
        span_length_m=10.0,
    )

    assert not audit.empty
    left_lift = audit.loc[(audit["Station x (m)"] - 0.5).abs() < 1e-6].iloc[0]
    right_lift = audit.loc[(audit["Station x (m)"] - 9.5).abs() < 1e-6].iloc[0]
    assert "Lifting point a" in str(left_lift["Station type"])
    assert "Lifting point L-a" in str(right_lift["Station type"])
    assert left_lift["a/L basis"] == "a/L=0.050"
    assert float(left_lift["Lifting point a (m)"]) == pytest.approx(0.5)
    assert float(left_lift["Lifting point L-a (m)"]) == pytest.approx(9.5)
    assert float(left_lift["Support spacing (m)"]) == pytest.approx(9.0)
    assert float(left_lift["Reaction each (kN)"]) == pytest.approx(float(left_lift["Auto load w (kN/m)"]) * 10.0 / 2.0)
    assert float(left_lift["Lifting moment Mx (kN-m)"]) < 0.0


def test_lifting_audit_exposes_debond_transition_effective_strands():
    geom = _railway_geometry()
    audit = railway_u_girder_lifting_stage_audit_dataframe(
        geometry=geom,
        settings=_stage_settings(),
        strand_table=_deboned_layout_table(),
        span_length_m=10.0,
    ).set_index("Station x (m)")

    assert "Debond transition" in str(audit.loc[1.0, "Station type"])
    assert "Debond transition" in str(audit.loc[1.5, "Station type"])
    assert "Debond transition" in str(audit.loc[2.0, "Station type"])
    assert int(audit.loc[0.5, "Effective strands"]) < int(audit.loc[1.0, "Effective strands"])
    assert int(audit.loc[1.0, "Effective strands"]) < int(audit.loc[1.5, "Effective strands"])
    assert int(audit.loc[1.5, "Effective strands"]) < int(audit.loc[2.0, "Effective strands"])
    assert "step-function preview" in str(audit.loc[2.0, "Audit note"])


def test_lifting_audit_ui_source_contains_expected_guardrails():
    from pathlib import Path

    analysis_source = Path("concrete_pmm_pro/ui/analysis_page.py").read_text(encoding="utf-8")
    prestress_source = Path("concrete_pmm_pro/ui/prestress_page.py").read_text(encoding="utf-8")

    assert "Railway U-Girder lifting a/L + debonding audit" in analysis_source
    assert "two-point lifting model with end overhangs" in analysis_source
    assert "Debonded strand force is treated as a step-function preview" in analysis_source
    assert "Fully bonded throughout" in prestress_source
    assert "Debonded near ends" in prestress_source
