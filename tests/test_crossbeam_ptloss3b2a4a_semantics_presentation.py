from __future__ import annotations

from pathlib import Path

from concrete_pmm_pro.crossbeam.tendon import (
    TENDON_BOND_STATE_BONDED,
    TENDON_BOND_STATE_UNBONDED,
    default_tendon_system_rows,
    normalize_tendon_bond_state,
    tendon_bond_state_summary,
    validate_tendon_system,
)
from concrete_pmm_pro.crossbeam.tendon_persistence import (
    CROSSBEAM_TENDON_METADATA_KEY,
    CROSSBEAM_TENDON_SCHEMA_VERSION,
    crossbeam_tendon_metadata_from_project,
)


def test_ptloss3b2a4a_legacy_bond_labels_migrate_to_final_system_semantics() -> None:
    assert TENDON_BOND_STATE_BONDED == "Bonded after grouting"
    assert TENDON_BOND_STATE_UNBONDED == "Permanently unbonded"
    assert normalize_tendon_bond_state("Bonded / grouted") == TENDON_BOND_STATE_BONDED
    assert normalize_tendon_bond_state("Unbonded") == TENDON_BOND_STATE_UNBONDED

    legacy_rows = default_tendon_system_rows(3)
    legacy_rows[0]["Bond state"] = "Bonded / grouted"
    legacy_rows[1]["Bond state"] = "Unbonded"
    legacy_rows[2]["Bond state"] = "Not specified"
    block, migrated, issues = crossbeam_tendon_metadata_from_project(
        {
            CROSSBEAM_TENDON_METADATA_KEY: {
                "schema_version": 2,
                "tendon_system": legacy_rows,
                "profile_points": [],
            }
        },
        length_m=20.0,
    )
    assert CROSSBEAM_TENDON_SCHEMA_VERSION == 3
    assert migrated is True
    assert not issues
    assert block is not None
    assert [row["Bond state"] for row in block["tendon_system"]] == [
        "Bonded after grouting",
        "Permanently unbonded",
        "Not specified",
    ]


def test_ptloss3b2a4a_final_bond_system_stays_separate_from_location() -> None:
    rows = default_tendon_system_rows(3)
    rows[0]["Bond state"] = TENDON_BOND_STATE_BONDED
    rows[1]["Bond state"] = TENDON_BOND_STATE_UNBONDED
    rows[2]["Bond state"] = TENDON_BOND_STATE_UNBONDED
    canonical, errors, warnings = validate_tendon_system(rows)
    assert not errors
    assert not warnings
    summary = tendon_bond_state_summary(canonical)
    assert summary["ready"] is True
    assert summary["labels"] == [
        "Internal — Bonded after grouting",
        "Internal — Permanently unbonded",
    ]

    rows[0]["Type"] = "External"
    _canonical, errors, _warnings = validate_tendon_system(rows)
    assert any("External tendon cannot use Bonded after grouting" in issue for issue in errors)


def test_ptloss3b2a4a_ui_uses_intentional_bulk_selection_and_generic_scope_text() -> None:
    source = Path("concrete_pmm_pro/ui/crossbeam_pages.py").read_text(encoding="utf-8")
    tendon_ui = source.split("def render_crossbeam_tendon_system_page", 1)[1].split(
        "def render_crossbeam_segment_layout_page", 1
    )[0]
    elastic_ui = source.split("with elastic_shortening_tab:", 1)[1].split(
        "with time_dependent_tab:", 1
    )[0]

    assert "Select final bond system…" in source
    assert "Bulk final bond-system assignment" in tendon_ui
    assert "disabled=bulk_bond_system == CB_TENDON_BOND_BULK_PLACEHOLDER" in tendon_ui
    assert '"Final bond system", options=list(TENDON_BOND_STATE_OPTIONS)' in tendon_ui
    assert "Bonded after grouting’ describes the intended completed tendon system" in tendon_ui
    assert "CROSSBEAM.PTA1 force source only" not in tendon_ui
    assert "ACI 423.10R loss calculations" not in tendon_ui
    assert "Run Advanced Construction-Stage QA" in elastic_ui
    assert "continuous compression-only contact is PTLOSS3B2B" not in elastic_ui


def test_ptloss3b2a4a_normal_runtime_uses_compact_fcgp_audit_instead_of_full_event_tables() -> None:
    source = Path("concrete_pmm_pro/ui/crossbeam_pages.py").read_text(encoding="utf-8")
    elastic_ui = source.split("with elastic_shortening_tab:", 1)[1].split(
        "with time_dependent_tab:", 1
    )[0]
    assert "f_cgp evaluation audit" in elastic_ui
    assert "preferred_columns" in elastic_ui
    assert "Cumulative structural-response audit — display only" in elastic_ui
    assert "Moment-jump / response-event audit" not in elastic_ui

