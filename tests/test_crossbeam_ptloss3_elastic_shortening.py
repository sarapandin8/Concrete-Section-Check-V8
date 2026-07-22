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
    assert "Elastic Shortening — symmetric-pair stressing foundation" in elastic_block
    assert "symmetric tendon pair is one simultaneous stressing group" in elastic_block
    assert "source-derived f_cgp is intentionally BLOCKED" in elastic_block
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
    assert metadata["schema_version"] == 3
    assert metadata["es_fcgp_override_enabled"] is True
    assert metadata["es_fcgp_override_mpa"] == pytest.approx(32.5)
    assert metadata["es_eci_override_enabled"] is True
    assert metadata["es_eci_override_mpa"] == pytest.approx(34000.0)
    assert restored is not None
    assert restored_state[CB_LOSS_ES_FCGP_OVERRIDE_ENABLED_KEY] is True
    assert restored_state[CB_LOSS_ES_FCGP_OVERRIDE_MPA_KEY] == pytest.approx(32.5)
    assert restored_state[CB_LOSS_ES_ECI_OVERRIDE_ENABLED_KEY] is True
    assert restored_state[CB_LOSS_ES_ECI_OVERRIDE_MPA_KEY] == pytest.approx(34000.0)
