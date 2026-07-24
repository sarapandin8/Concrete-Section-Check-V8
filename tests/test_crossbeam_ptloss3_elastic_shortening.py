from __future__ import annotations

import math

from concrete_pmm_pro.crossbeam.elastic_shortening import (
    average_sequence_factor,
    elastic_shortening_average_loss_mpa,
    elastic_shortening_sequence_rows,
    elastic_shortening_station_rows,
    elastic_shortening_summary,
    group_sequence_factor,
    stressing_group_summary,
    symmetric_stressing_group_rows,
)
from concrete_pmm_pro.crossbeam.tendon import (
    default_tendon_profile_points,
    default_tendon_system_rows,
)


def _default_sources():
    system = default_tendon_system_rows(8)
    ids = [f"T{i}" for i in range(1, 9)]
    profile = default_tendon_profile_points(
        20.0,
        tendon_ids=ids,
        width_mm=2500.0,
        height_mm=1500.0,
        t_left_mm=300.0,
        t_right_mm=300.0,
    )
    return system, profile


def test_published_segmental_reference_average_formula_reproduces_91_31_mpa() -> None:
    # Elastic shortening(2).pdf reference values: N=16, Ep=197000 MPa,
    # Eci=36669 MPa, f_cgp=36.26 MPa -> 91.31 MPa average ES.
    loss = elastic_shortening_average_loss_mpa(
        group_count=16,
        ep_mpa=197000.0,
        eci_mpa=36669.0,
        fcgp_mpa=36.26,
    )
    assert math.isclose(loss, 91.3137629878, rel_tol=0.0, abs_tol=1e-9)


def test_default_crossbeam_resolves_four_symmetric_pairs_from_eight_tendons() -> None:
    system, profile = _default_sources()
    groups = symmetric_stressing_group_rows(profile, system, length_m=20.0)
    assert [row["Tendons"] for row in groups] == [
        "T1 + T5",
        "T2 + T6",
        "T3 + T7",
        "T4 + T8",
    ]
    assert all(row["Status"] == "PAIR READY" for row in groups)
    summary = stressing_group_summary(groups)
    assert summary["ready"] is True
    assert summary["group_count"] == 4
    assert summary["active_tendon_count"] == 8


def test_pair_sequence_factor_does_not_count_mutual_loss_inside_same_pair() -> None:
    # Four simultaneous pairs are four stressing operations, not eight
    # individually sequential tendon operations.
    assert math.isclose(average_sequence_factor(4), 0.375)
    assert [group_sequence_factor(4, i) for i in range(1, 5)] == [0.75, 0.5, 0.25, 0.0]
    assert not math.isclose(average_sequence_factor(4), average_sequence_factor(8))


def test_crossbeam_pair_preview_uses_group_count_instead_of_raw_tendon_count() -> None:
    system, profile = _default_sources()
    groups = symmetric_stressing_group_rows(profile, system, length_m=20.0)
    summary = elastic_shortening_summary(
        groups,
        ep_mpa=197000.0,
        eci_mpa=36669.0,
        fcgp_mpa=36.26,
    )
    assert summary["value"] == "PREVIEW READY"
    assert math.isclose(summary["average_factor"], 0.375)
    assert math.isclose(summary["average_loss_mpa"], 73.0510103902, rel_tol=0.0, abs_tol=1e-9)
    assert math.isclose(summary["max_sequence_loss_mpa"], 146.1020207805, rel_tol=0.0, abs_tol=1e-9)
    rows = summary["sequence_rows"]
    assert [row["Sequence factor"] for row in rows] == [0.75, 0.5, 0.25, 0.0]


def test_stage_stress_is_a_hard_source_gate_without_fcgp() -> None:
    system, profile = _default_sources()
    groups = symmetric_stressing_group_rows(profile, system, length_m=20.0)
    summary = elastic_shortening_summary(
        groups,
        ep_mpa=195000.0,
        eci_mpa=31500.0,
        fcgp_mpa=None,
    )
    assert summary["value"] == "SOURCE BLOCKED"
    assert summary["component_status"] == "STAGE STRESS REQUIRED"
    assert summary["average_loss_mpa"] is None


def test_geometry_mismatch_prevents_symmetric_pair_release() -> None:
    system, profile = _default_sources()
    # Break T5 depth symmetry relative to T1.
    for row in profile:
        if row["Tendon ID"] == "T5" and row["Point"] == "P2":
            row["dtop (mm)"] += 25.0
    groups = symmetric_stressing_group_rows(profile, system, length_m=20.0)
    summary = stressing_group_summary(groups)
    assert summary["ready"] is False
    assert any("pair" in issue.lower() or "mismatch" in issue.lower() for issue in summary["issues"])


def test_post_es_station_chain_starts_from_post_anchorage_state_not_fpj() -> None:
    sequence_rows = [
        {
            "Group ID": "G1",
            "Left tendon": "T1",
            "Right tendon": "T5",
            "Status": "PAIR READY",
            "ΔfpES (MPa)": 20.0,
        }
    ]
    anchorage_rows = [
        {
            "Tendon ID": "T1",
            "s (m)": 10.0,
            "Aps total (mm²)": 2660.0,
            "fpj (MPa)": 1395.0,
            "Stress after anchorage set (MPa)": 1250.0,
            "P after anchorage set (kN)": 3325.0,
        }
    ]
    rows = elastic_shortening_station_rows(anchorage_rows, sequence_rows)
    assert len(rows) == 1
    assert math.isclose(rows[0]["Stress after ES (MPa)"], 1230.0)
    assert math.isclose(rows[0]["P after ES (kN)"], 2660.0 * 1230.0 / 1000.0)
    # Explicitly prove the chain did not restart from fpj=1395 MPa.
    assert not math.isclose(rows[0]["Stress after ES (MPa)"], 1395.0 - 20.0)


def test_ptloss3_ui_exposes_pair_stressing_and_keeps_fcgp_source_gated() -> None:
    from pathlib import Path

    source = Path("concrete_pmm_pro/ui/crossbeam_pages.py").read_text(encoding="utf-8")
    elastic_block = source.split("with elastic_shortening_tab:", maxsplit=1)[1].split(
        "with time_dependent_tab:", maxsplit=1
    )[0]
    assert "Elastic Shortening — construction/stressing-stage source foundation" in elastic_block
    assert "symmetric tendon pair is one simultaneous stressing group" in elastic_block
    assert "Source-derived f_cgp remains BLOCKED" in elastic_block
    assert "P after anchorage set" in elastic_block
    assert "it never restarts from fpj" in elastic_block
    assert "Pe/Pe_eff" in elastic_block


def test_ptloss3_override_settings_round_trip_in_project_metadata() -> None:
    import pytest

    from concrete_pmm_pro.crossbeam.prestress_loss import (
        CB_LOSS_ES_ECI_OVERRIDE_ENABLED_KEY,
        CB_LOSS_ES_ECI_OVERRIDE_MPA_KEY,
        CB_LOSS_ES_FCGP_OVERRIDE_ENABLED_KEY,
        CB_LOSS_ES_FCGP_OVERRIDE_MPA_KEY,
        CROSSBEAM_PRESTRESS_LOSS_METADATA_KEY,
        crossbeam_prestress_loss_settings_from_session_state,
        restore_crossbeam_prestress_loss_project_state,
    )

    state = {
        CB_LOSS_ES_FCGP_OVERRIDE_ENABLED_KEY: True,
        CB_LOSS_ES_FCGP_OVERRIDE_MPA_KEY: 32.5,
        CB_LOSS_ES_ECI_OVERRIDE_ENABLED_KEY: True,
        CB_LOSS_ES_ECI_OVERRIDE_MPA_KEY: 34000.0,
    }
    metadata = crossbeam_prestress_loss_settings_from_session_state(state)
    restored_state: dict[str, object] = {}
    restored = restore_crossbeam_prestress_loss_project_state(
        {CROSSBEAM_PRESTRESS_LOSS_METADATA_KEY: metadata}, restored_state
    )
    assert metadata["schema_version"] == 5
    assert metadata["es_fcgp_override_enabled"] is True
    assert metadata["es_fcgp_override_mpa"] == pytest.approx(32.5)
    assert metadata["es_eci_override_enabled"] is True
    assert metadata["es_eci_override_mpa"] == pytest.approx(34000.0)
    assert restored is not None
    assert restored_state[CB_LOSS_ES_FCGP_OVERRIDE_ENABLED_KEY] is True
    assert restored_state[CB_LOSS_ES_FCGP_OVERRIDE_MPA_KEY] == pytest.approx(32.5)
    assert restored_state[CB_LOSS_ES_ECI_OVERRIDE_ENABLED_KEY] is True
    assert restored_state[CB_LOSS_ES_ECI_OVERRIDE_MPA_KEY] == pytest.approx(34000.0)


def test_ptloss3b1_column_shapes_and_derived_properties_are_axis_aligned() -> None:
    from concrete_pmm_pro.crossbeam.construction_stage import (
        COLUMN_SHAPE_CIRCULAR,
        COLUMN_SHAPE_RECT_CHAMFER,
        COLUMN_SHAPE_RECT_FILLET,
        column_section_properties,
    )

    chamfer = column_section_properties(
        {
            "Shape": "Rectangular — Equal Chamfer 4 Corners",
            "Btrans (mm)": 2000.0,
            "Blong (mm)": 1500.0,
            "Corner (mm)": 100.0,
            "f'c (MPa)": 35.0,
        }
    )
    assert chamfer["ready"] is True
    assert math.isclose(chamfer["Area (mm²)"], 2000.0 * 1500.0 - 2.0 * 100.0**2)
    assert chamfer["I22 (mm⁴)"] > 0.0
    assert chamfer["I33 (mm⁴)"] > chamfer["I22 (mm⁴)"]

    fillet = column_section_properties(
        {
            "Shape": COLUMN_SHAPE_RECT_FILLET,
            "Btrans (mm)": 2000.0,
            "Blong (mm)": 1500.0,
            "Corner (mm)": 100.0,
            "f'c (MPa)": 35.0,
        }
    )
    assert fillet["ready"] is True
    assert math.isclose(
        fillet["Area (mm²)"],
        2000.0 * 1500.0 - (4.0 - math.pi) * 100.0**2,
        rel_tol=0.0,
        abs_tol=1e-6,
    )

    circular = column_section_properties(
        {"Shape": "Circular", "Diameter (mm)": 1600.0, "f'c (MPa)": 35.0}
    )
    assert circular["ready"] is True
    assert math.isclose(circular["Area (mm²)"], math.pi * 1600.0**2 / 4.0)
    assert math.isclose(circular["I22 (mm⁴)"], math.pi * 1600.0**4 / 64.0)
    assert math.isclose(circular["I22 (mm⁴)"], circular["I33 (mm⁴)"])


def test_ptloss3b1_temporary_support_is_full_length_compression_only_contact() -> None:
    from concrete_pmm_pro.crossbeam.construction_stage import temporary_support_source

    source = temporary_support_source(20.0)
    assert source["start_s_m"] == 0.0
    assert source["end_s_m"] == 20.0
    assert source["initial_state"] == "IN CONTACT"
    assert source["behavior"] == "COMPRESSION-ONLY"
    assert source["lift_off"] == "AUTOMATIC"
    assert "tensile reaction" in source["note"]


def test_ptloss3b1_pair_sequence_is_user_source_separate_from_geometry_pair_order() -> None:
    from concrete_pmm_pro.crossbeam.construction_stage import (
        normalize_pair_sequence,
        stressing_pair_sequence_rows,
    )

    system, profile = _default_sources()
    groups = symmetric_stressing_group_rows(profile, system, length_m=20.0)
    adopted = normalize_pair_sequence(["G3", "G1", "G4", "G2"], groups)
    assert adopted == ["G3", "G1", "G4", "G2"]
    rows = stressing_pair_sequence_rows(groups, adopted)
    assert [row["Group ID"] for row in rows] == adopted
    assert [row["Sequence"] for row in rows] == [1, 2, 3, 4]


def test_ptloss3b1_stage_source_requires_physical_inputs_but_keeps_solver_locked() -> None:
    from concrete_pmm_pro.crossbeam.construction_stage import (
        COLUMN_SHAPE_CIRCULAR,
        CONSTRUCTION_METHOD_PRECAST,
        construction_stage_readiness,
    )

    system, profile = _default_sources()
    groups = symmetric_stressing_group_rows(profile, system, length_m=20.0)
    columns = [
        {
            "Column ID": "C1",
            "Station s (m)": 0.0,
            "Height (m)": 8.0,
            "Shape": "Circular",
            "Diameter (mm)": 1600.0,
            "f'c (MPa)": 35.0,
        },
        {
            "Column ID": "C2",
            "Station s (m)": 20.0,
            "Height (m)": 8.0,
            "Shape": "Circular",
            "Diameter (mm)": 1600.0,
            "f'c (MPa)": 35.0,
        },
    ]
    summary = construction_stage_readiness(
        construction_method=CONSTRUCTION_METHOD_PRECAST,
        crossbeam_fc_mpa=45.0,
        stressing_strength_ratio=0.80,
        closure_required_mpa=50.0,
        column_rows=columns,
        length_m=20.0,
        group_rows=groups,
        pair_sequence=["G1", "G2", "G3", "G4"],
    )
    assert summary["ready"] is True
    assert summary["status"] == "DESIGN SOURCE READY — SOLVER NOT YET RELEASED"
    assert summary["solver_status"].startswith("LOCKED")
    assert summary["temporary_support"]["behavior"] == "COMPRESSION-ONLY"


def test_ptloss3b1_project_metadata_round_trip_includes_stage_source() -> None:
    from concrete_pmm_pro.crossbeam.prestress_loss import (
        CB_LOSS_ES_CLOSURE_REQUIRED_MPA_KEY,
        CB_LOSS_ES_COLUMN_ROWS_KEY,
        CB_LOSS_ES_CONSTRUCTION_METHOD_KEY,
        CB_LOSS_ES_PAIR_SEQUENCE_KEY,
        CB_LOSS_ES_STRESSING_STRENGTH_RATIO_KEY,
        CROSSBEAM_PRESTRESS_LOSS_METADATA_KEY,
        crossbeam_prestress_loss_settings_from_session_state,
        restore_crossbeam_prestress_loss_project_state,
    )

    columns = [{"Column ID": "C1", "Station s (m)": 0.0, "Height (m)": 8.0}]
    state = {
        CB_LOSS_ES_CONSTRUCTION_METHOD_KEY: "Precast Segmental",
        CB_LOSS_ES_STRESSING_STRENGTH_RATIO_KEY: 0.8,
        CB_LOSS_ES_CLOSURE_REQUIRED_MPA_KEY: 50.0,
        CB_LOSS_ES_COLUMN_ROWS_KEY: columns,
        CB_LOSS_ES_PAIR_SEQUENCE_KEY: ["G2", "G1"],
    }
    metadata = crossbeam_prestress_loss_settings_from_session_state(state)
    assert metadata["schema_version"] == 5
    assert metadata["es_column_rows"] == columns
    assert metadata["es_pair_sequence"] == ["G2", "G1"]
    restored: dict[str, object] = {}
    restore_crossbeam_prestress_loss_project_state(
        {CROSSBEAM_PRESTRESS_LOSS_METADATA_KEY: metadata}, restored
    )
    assert restored[CB_LOSS_ES_CONSTRUCTION_METHOD_KEY] == "Precast Segmental"
    assert restored[CB_LOSS_ES_COLUMN_ROWS_KEY] == columns
    assert restored[CB_LOSS_ES_PAIR_SEQUENCE_KEY] == ["G2", "G1"]



def test_ptloss3b1a_design_readiness_does_not_require_future_field_test_results() -> None:
    from concrete_pmm_pro.crossbeam.construction_stage import (
        COLUMN_SHAPE_CIRCULAR,
        CONSTRUCTION_METHOD_PRECAST,
        construction_stage_readiness,
    )

    system, profile = _default_sources()
    groups = symmetric_stressing_group_rows(profile, system, length_m=20.0)
    columns = [
        {
            "Column ID": "C1",
            "Station s (m)": 0.0,
            "Height (m)": 8.0,
            "Shape": "Circular",
            "Diameter (mm)": 1600.0,
            "f'c (MPa)": 35.0,
        },
        {
            "Column ID": "C2",
            "Station s (m)": 20.0,
            "Height (m)": 8.0,
            "Shape": "Circular",
            "Diameter (mm)": 1600.0,
            "f'c (MPa)": 35.0,
        },
    ]
    summary = construction_stage_readiness(
        construction_method=CONSTRUCTION_METHOD_PRECAST,
        crossbeam_fc_mpa=45.0,
        stressing_strength_ratio=0.80,
        closure_required_mpa=50.0,
        column_rows=columns,
        length_m=20.0,
        group_rows=groups,
        pair_sequence=["G1", "G2", "G3", "G4"],
    )
    assert summary["ready"] is True
    assert summary["strength_status"] == "DESIGN CRITERION DEFINED"
    assert summary["closure_status"] == "DESIGN CRITERION DEFINED"


def test_ptloss3b1a_legacy_column_dimensions_migrate_to_btrans_blong() -> None:
    from concrete_pmm_pro.crossbeam.construction_stage import canonical_column_stage_rows

    rows = canonical_column_stage_rows(
        [
            {
                "Column ID": "C1",
                "Station s (m)": 0.0,
                "Height (m)": 8.0,
                "B local-2 (mm)": 1200.0,
                "H local-3 (mm)": 1800.0,
                "f'c (MPa)": 35.0,
            }
        ],
        length_m=20.0,
    )
    assert math.isclose(rows[0]["Btrans (mm)"], 1200.0)
    assert math.isclose(rows[0]["Blong (mm)"], 1800.0)
    assert "B local-2 (mm)" not in rows[0]
    assert "H local-3 (mm)" not in rows[0]

def test_ptloss3b1c_relocates_member_construction_and_column_source_to_section_builder() -> None:
    from pathlib import Path

    crossbeam_source = Path("concrete_pmm_pro/ui/crossbeam_pages.py").read_text(encoding="utf-8")
    section_builder_source = Path("concrete_pmm_pro/ui/section_builder.py").read_text(encoding="utf-8")
    elastic_block = crossbeam_source.split("with elastic_shortening_tab:", maxsplit=1)[1].split(
        "with time_dependent_tab:", maxsplit=1
    )[0]
    assert 'st.markdown("##### Column / support-line layout")' not in elastic_block
    assert "Column plan-section preview" not in elastic_block
    assert 'st.selectbox(\n                "Construction method"' not in elastic_block
    assert "Geometry editing is owned by Section Builder" in elastic_block
    assert "COMPRESSION-ONLY" in elastic_block
    assert "Stressing pair sequence" in elastic_block
    assert "Stage solver" in elastic_block and "LOCKED" in elastic_block
    assert "render_crossbeam_construction_support_source_workspace" in section_builder_source
    assert "_render_crossbeam_construction_support_workspace(settings)" in section_builder_source
    assert "Crossbeam Construction & Support Configuration" in crossbeam_source
    assert "Btrans — Normal to Crossbeam axis" in crossbeam_source
    assert "Blong — Along Crossbeam axis" in crossbeam_source



def test_ptloss3b1b_column_plan_preview_is_compact_and_axis_aware() -> None:
    from concrete_pmm_pro.ui.crossbeam_pages import _column_plan_section_preview_figure

    rect = _column_plan_section_preview_figure(
        {
            "Column ID": "C1",
            "Shape": "Rectangular — Equal Chamfer 4 Corners",
            "Btrans (mm)": 1200.0,
            "Blong (mm)": 1800.0,
            "Corner (mm)": 150.0,
        }
    )
    assert rect.layout.height == 270
    assert len(rect.data) == 1
    texts = " ".join(str(item.text or "") for item in rect.layout.annotations)
    assert "Btrans = 1,200 mm" in texts
    assert "Blong = 1,800 mm" in texts
    assert "CROSSBEAM AXIS, s" in texts
    assert "Chamfer c = 150 mm" in texts

    circle = _column_plan_section_preview_figure(
        {
            "Column ID": "C2",
            "Shape": "Circular",
            "Diameter (mm)": 1500.0,
        }
    )
    assert circle.layout.height == 270
    circle_texts = " ".join(str(item.text or "") for item in circle.layout.annotations)
    assert "D = 1,500 mm" in circle_texts
    assert "CROSSBEAM AXIS, s" in circle_texts


def test_ptloss3b1c_default_columns_and_closure_seed_match_adopted_project_defaults() -> None:
    from concrete_pmm_pro.crossbeam.construction_stage import (
        DEFAULT_PRECAST_CLOSURE_STRENGTH_MPA,
        default_column_stage_rows,
    )
    from concrete_pmm_pro.crossbeam.prestress_loss import default_crossbeam_prestress_loss_settings

    rows = default_column_stage_rows(20.0)
    assert len(rows) == 2
    assert rows[0]["Station s (m)"] == 1.5
    assert rows[1]["Station s (m)"] == 18.5
    for row in rows:
        assert row["Height (m)"] == 10.0
        assert row["Btrans (mm)"] == 2000.0
        assert row["Blong (mm)"] == 2000.0
        assert row["Corner (mm)"] == 200.0
        assert row["Diameter (mm)"] == 2000.0
        assert row["f'c (MPa)"] == 35.0
    settings = default_crossbeam_prestress_loss_settings()
    assert settings["es_closure_required_mpa"] == DEFAULT_PRECAST_CLOSURE_STRENGTH_MPA == 50.0



def test_cip1b_short_member_column_seed_uses_ordered_quarter_points() -> None:
    from concrete_pmm_pro.crossbeam.construction_stage import default_column_stage_rows

    rows = default_column_stage_rows(2.0)
    assert [row["Station s (m)"] for row in rows] == [0.5, 1.5]


def test_ptloss3b1c_segment_elevation_uses_real_column_width_along_s() -> None:
    from concrete_pmm_pro.ui.crossbeam_pages import _elevation_figure

    segments = [
        {
            "Segment": "S1",
            "x_start_m": 0.0,
            "x_end_m": 20.0,
            "Section ID": "CB-S01",
            "Section name": "Solid",
            "Section role": "Solid",
            "Section type / preset": "PC Crossbeam — Rectangular Solid with Bottom Fillets",
        }
    ]
    columns = [
        {
            "Column ID": "C1",
            "Station s (m)": 5.0,
            "Height (m)": 10.0,
            "Shape": "Rectangular — Equal Chamfer 4 Corners",
            "Btrans (mm)": 3000.0,
            "Blong (mm)": 2000.0,
            "Corner (mm)": 200.0,
            "Diameter (mm)": 2000.0,
            "f'c (MPa)": 35.0,
        },
        {
            "Column ID": "C2",
            "Station s (m)": 15.0,
            "Height (m)": 10.0,
            "Shape": "Circular",
            "Diameter (mm)": 2000.0,
            "f'c (MPa)": 35.0,
        },
    ]
    fig = _elevation_figure(segments, 20.0, columns)
    rects = [shape for shape in fig.layout.shapes if getattr(shape, "type", None) == "rect"]
    support_rects = [shape for shape in rects if float(shape.y0) < 0.0]
    assert len(support_rects) == 2
    widths = sorted(round(float(shape.x1) - float(shape.x0), 6) for shape in support_rects)
    assert widths == [2.0, 2.0]
    annotation_text = " ".join(str(a.text or "") for a in fig.layout.annotations)
    assert "C1" in annotation_text and "Blong 2.000 m" in annotation_text
    assert "C2" in annotation_text and "Ø2.000 m" in annotation_text


def test_ptloss3b1d_column_axis_lock_uses_i_perp_s_for_s_vertical_frame_bending() -> None:
    from concrete_pmm_pro.crossbeam.construction_stage import column_section_properties

    props = column_section_properties(
        {
            "Shape": "Rectangular — Equal Chamfer 4 Corners",
            "Btrans (mm)": 1000.0,
            "Blong (mm)": 2000.0,
            "Corner (mm)": 0.0,
            "f'c (MPa)": 35.0,
        }
    )
    expected_perp = 1000.0 * 2000.0**3 / 12.0
    expected_parallel = 2000.0 * 1000.0**3 / 12.0
    assert math.isclose(props["I_perp_s (mm⁴)"], expected_perp)
    assert math.isclose(props["I_parallel_s (mm⁴)"], expected_parallel)
    assert props["I_perp_s (mm⁴)"] == props["I22 (mm⁴)"]
    assert props["I_parallel_s (mm⁴)"] == props["I33 (mm⁴)"]
    assert props["I_perp_s (mm⁴)"] > props["I_parallel_s (mm⁴)"]


def test_ptloss3b1d_support_footprint_qa_detects_hollow_overlap_and_uses_blong() -> None:
    import pytest

    from concrete_pmm_pro.crossbeam.construction_stage import column_support_footprint_summary

    columns = [
        {
            "Column ID": "C1",
            "Station s (m)": 5.0,
            "Height (m)": 10.0,
            "Shape": "Rectangular — Equal Chamfer 4 Corners",
            "Btrans (mm)": 4000.0,
            "Blong (mm)": 2000.0,
            "Corner (mm)": 200.0,
            "Diameter (mm)": 2000.0,
            "f'c (MPa)": 35.0,
        }
    ]
    segments = [
        {"Segment": "S1", "x_start_m": 0.0, "x_end_m": 4.5, "Section role": "Solid"},
        {"Segment": "S2", "x_start_m": 4.5, "x_end_m": 8.0, "Section role": "Hollow"},
    ]
    summary = column_support_footprint_summary(columns, segments, length_m=8.0)
    row = summary["rows"][0]
    assert row["Footprint width (m)"] == pytest.approx(2.0)  # Blong, not Btrans
    assert row["s_left (m)"] == pytest.approx(4.0)
    assert row["s_right (m)"] == pytest.approx(6.0)
    assert row["Status"] == "REVIEW"
    assert "S2" in row["Hollow segment(s)"]
    assert summary["ready"] is False


def test_ptloss3b1d_support_footprint_qa_accepts_solid_region() -> None:
    from concrete_pmm_pro.crossbeam.construction_stage import column_support_footprint_summary

    columns = [
        {
            "Column ID": "C1",
            "Station s (m)": 2.0,
            "Height (m)": 10.0,
            "Shape": "Circular",
            "Btrans (mm)": 2000.0,
            "Blong (mm)": 2000.0,
            "Corner (mm)": 200.0,
            "Diameter (mm)": 2000.0,
            "f'c (MPa)": 35.0,
        }
    ]
    segments = [
        {"Segment": "S1", "x_start_m": 0.0, "x_end_m": 4.0, "Section role": "Solid"},
        {"Segment": "S2", "x_start_m": 4.0, "x_end_m": 8.0, "Section role": "Hollow"},
    ]
    summary = column_support_footprint_summary(columns, segments, length_m=8.0)
    assert summary["ready"] is True
    assert summary["compatible_count"] == 1
    assert summary["rows"][0]["Width source"] == "Diameter D"
    assert summary["rows"][0]["Solid segment(s)"] == "S1"


def test_ptloss3b1d_section_builder_places_member_sources_before_section_specific_workspace() -> None:
    from pathlib import Path

    source = Path("concrete_pmm_pro/ui/section_builder.py").read_text()
    member = source.index("_render_crossbeam_member_geometry_workspace(settings)")
    support = source.index("_render_crossbeam_construction_support_workspace(settings)")
    columns = source.index("parameter_col, preview_col = st.columns")
    assert member < support < columns
