from __future__ import annotations

from pathlib import Path

import pytest

from concrete_pmm_pro.crossbeam.construction_stage import (
    default_column_stage_rows,
    temporary_support_source,
)
from concrete_pmm_pro.crossbeam.section_library import (
    default_section_definitions,
    migrate_segment_rows_to_library,
)
from concrete_pmm_pro.crossbeam.stressing_stage_contact import (
    run_crossbeam_gravity_contact_qa,
)
from concrete_pmm_pro.crossbeam.stressing_stage_frame import (
    build_crossbeam_linear_stage_model,
)
from concrete_pmm_pro.crossbeam.tendon import default_tendon_profile_points
from concrete_pmm_pro.crossbeam.workflow import default_crossbeam_segment_rows
from concrete_pmm_pro.core.concrete_materials import default_concrete_materials


def _default_contact_result() -> dict:
    length_m = 20.0
    definitions = default_section_definitions()
    segments = migrate_segment_rows_to_library(
        default_crossbeam_segment_rows(length_m), definitions
    )
    profile = default_tendon_profile_points(
        length_m,
        tendon_ids=[f"T{i}" for i in range(1, 9)],
        width_mm=2500.0,
        height_mm=1500.0,
        t_left_mm=300.0,
        t_right_mm=300.0,
    )
    model = build_crossbeam_linear_stage_model(
        length_m=length_m,
        segment_rows=segments,
        section_definitions=definitions,
        concrete_materials=default_concrete_materials(),
        column_rows=default_column_stage_rows(length_m),
        profile_rows=profile,
    )
    return run_crossbeam_gravity_contact_qa(model=model)


def test_ptloss3b2b1a_contact_rows_expose_mesh_aware_line_reaction() -> None:
    result = _default_contact_result()
    assert result["ready"] is True
    rows = result["contact_rows"]
    assert len(rows) == 41
    assert result["total_contact_tributary_length_m"] == pytest.approx(20.0)
    assert rows[0]["tributary_length_m"] == pytest.approx(0.25)
    assert rows[-1]["tributary_length_m"] == pytest.approx(0.25)
    assert all(row["line_reaction_kN_per_m"] is not None for row in rows)

    integrated_line_reaction = sum(
        row["line_reaction_kN_per_m"] * row["tributary_length_m"]
        for row in rows
    )
    assert integrated_line_reaction == pytest.approx(
        result["total_contact_reaction_N"] / 1000.0,
        rel=1.0e-12,
    )


def test_ptloss3b2b1a_support_source_declares_released_gravity_route_and_locked_prestress() -> None:
    source = temporary_support_source(20.0)
    assert source["vertical_model"] == "RIGID VERTICAL CONTACT"
    assert "released gravity and incremental post-anchor tendon-group QA" in source["note"]
    assert "Source-derived f_cgp and Elastic Shortening remain locked" in source["note"]
    assert "future stage solver" not in source["note"]


def test_ptloss3b2b1a_ui_uses_line_reaction_and_complete_static_contact_audit() -> None:
    source = Path("concrete_pmm_pro/ui/crossbeam_pages.py").read_text(encoding="utf-8")
    elastic = source.split("with elastic_shortening_tab:", 1)[1].split(
        "with time_dependent_tab:", 1
    )[0]
    assert "Equivalent Falsework Line Reaction — Self-Weight Stage" in elastic
    assert "q_i = R_i / L_trib,i" in elastic
    assert "Raw nodal reaction Rnode" in elastic
    assert "Active-project contact stations — complete static print audit" in elastic
    assert "contact_chunk_size = 14" in elastic
    assert "st.table(pd.DataFrame(chunk))" in elastic
    assert "ptloss3b2-contact-audit-anchor" in elastic
    assert "RIGID COMPRESSION-ONLY" in elastic
    assert "no spring stiffness or support compression" in elastic
    assert "gravity + incremental prestress active-set released; f_cgp locked" in elastic
    assert "Falsework Contact Reaction — Self-Weight Stage" not in elastic


def test_ptloss3b2b1a_display_zero_normalizes_negative_zero() -> None:
    source = Path("concrete_pmm_pro/ui/crossbeam_pages.py").read_text(encoding="utf-8")
    assert "def _display_zero" in source
    assert "contact_max_penetration = _display_zero" in source
