from __future__ import annotations

from pathlib import Path

import pytest

from concrete_pmm_pro.crossbeam.construction_stage import default_column_stage_rows
from concrete_pmm_pro.crossbeam.stressing_stage_frame import (
    build_crossbeam_linear_stage_model,
    run_crossbeam_linear_stage_response,
)
from concrete_pmm_pro.crossbeam.tendon import (
    TENDON_BOND_STATE_BONDED,
    TENDON_BOND_STATE_UNBONDED,
    default_tendon_system_rows,
    tendon_bond_state_summary,
    validate_tendon_system,
)
from concrete_pmm_pro.crossbeam.tendon_persistence import (
    CROSSBEAM_TENDON_METADATA_KEY,
    CROSSBEAM_TENDON_SCHEMA_VERSION,
    crossbeam_tendon_metadata_from_project,
)
from concrete_pmm_pro.core.concrete_materials import default_concrete_materials
from tests.test_crossbeam_ptloss3b2a1_hardening import _sources


def test_ptloss3b2a4_bond_state_is_explicit_and_not_inferred_from_location() -> None:
    rows = default_tendon_system_rows(4)
    assert all(row["Type"] == "Internal" for row in rows)
    assert tendon_bond_state_summary(rows)["status"] == "REVIEW REQUIRED"

    for row in rows:
        row["Bond state"] = TENDON_BOND_STATE_BONDED
    canonical, errors, warnings = validate_tendon_system(rows)
    assert not errors
    assert not warnings
    summary = tendon_bond_state_summary(canonical)
    assert summary["ready"] is True
    assert summary["labels"] == ["Internal — Bonded after grouting"]

    canonical[0]["Type"] = "External"
    canonical[0]["Bond state"] = TENDON_BOND_STATE_UNBONDED
    assert tendon_bond_state_summary(canonical)["ready"] is True


def test_ptloss3b2a4_external_bonded_combination_is_blocked() -> None:
    rows = default_tendon_system_rows(3)
    rows[0]["Type"] = "External"
    rows[0]["Bond state"] = TENDON_BOND_STATE_BONDED
    _canonical, errors, _warnings = validate_tendon_system(rows)
    assert any("External tendon cannot use Bonded after grouting" in issue for issue in errors)
    assert tendon_bond_state_summary(rows)["ready"] is False


def test_ptloss3b2a4_tendon_schema_records_new_bond_state_source() -> None:
    assert CROSSBEAM_TENDON_SCHEMA_VERSION == 3
    assert "Bond state" in default_tendon_system_rows(3)[0]


def test_ptloss3b2a4_schema1_project_migrates_without_inventing_bond_state() -> None:
    legacy_rows = default_tendon_system_rows(3)
    for row in legacy_rows:
        row.pop("Bond state", None)
    block, migrated, issues = crossbeam_tendon_metadata_from_project(
        {
            CROSSBEAM_TENDON_METADATA_KEY: {
                "schema_version": 1,
                "tendon_system": legacy_rows,
                "profile_points": [],
            }
        },
        length_m=20.0,
    )
    assert migrated is True
    assert not issues
    assert block is not None and block["schema_version"] == 3
    assert all(row["Bond state"] == "Not specified" for row in block["tendon_system"])


def test_ptloss3b2a4_response_event_audit_closes_centroid_axis_step() -> None:
    definitions, segments, profile, _system, post_anchor = _sources()
    model = build_crossbeam_linear_stage_model(
        length_m=20.0,
        segment_rows=segments,
        section_definitions=definitions,
        concrete_materials=default_concrete_materials(),
        column_rows=default_column_stage_rows(20.0),
        profile_rows=profile,
        crossbeam_stressing_strength_ratio=0.80,
    )
    result = run_crossbeam_linear_stage_response(
        model=model,
        profile_rows=profile,
        anchorage_station_rows=post_anchor,
    )
    rows = result["response_event_rows"]
    assert rows
    boundary = next(row for row in rows if row["s (m)"] == pytest.approx(3.0))
    assert boundary["Event type"] == "Section/Zone boundary"
    assert boundary["Equivalent nodal couple (kN-m; CCW +)"] == pytest.approx(0.0)
    assert abs(boundary["Centroid offset jump Δy (mm; up +)"]) > 1.0
    assert abs(boundary["Observed ΔM right-left (kN-m)"]) == pytest.approx(
        boundary["|N·Δy| axis-shift reference (kN-m)"], rel=1.0e-10
    )
    assert boundary["Interpretation sources"] == "local-centroid axis shift"

    column = next(row for row in rows if row["s (m)"] == pytest.approx(1.5))
    assert "Column centerline" in column["Event type"]
    assert "frame joint / column restraint" in column["Interpretation sources"]


def test_ptloss3b2a4_ui_uses_generic_labels_current_mesh_and_event_audit() -> None:
    source = Path("concrete_pmm_pro/ui/crossbeam_pages.py").read_text(encoding="utf-8")
    elastic = source.split("with elastic_shortening_tab:", 1)[1].split(
        "with time_dependent_tab:", 1
    )[0]
    assert "Linear stressing-stage response QA — fixed-base / no-contact" in elastic
    assert "PTLOSS3B2A2 adds explicit" not in source
    assert "PTLOSS3B2A1 hardened fixed-base response only" not in source
    assert "incremental tendon-group contact stages — post-anchor qa" in elastic.lower()
    assert "incremental tendon-group contact" in elastic.lower()
    assert "Tendon identity, final bond system, and stressing" in source
    assert "Apply to active tendons" in source
    assert '"Bond state": st.column_config.SelectboxColumn' in source
    assert "Moment-jump / response-event audit" in elastic
    assert 'linear_stage_result.get("response_event_rows", [])' in elastic
    assert "Active-project mesh sensitivity" in elastic
    assert "recomputed automatically when its input fingerprint changes" in elastic
    assert "Run linear-response mesh-sensitivity diagnostic" not in elastic
