from __future__ import annotations

from math import atan, exp, hypot
from pathlib import Path

import pytest

from concrete_pmm_pro.crossbeam.prestress_loss import (
    AASHTO_INTERNAL_WOBBLE_K_PER_FT,
    AASHTO_POLYETHYLENE_DUCT_MU,
    CB_LOSS_EXTERNAL_INADVERTENT_ANGLE_KEY,
    CB_LOSS_EXTERNAL_MU_KEY,
    CB_LOSS_INTERNAL_K_PER_M_KEY,
    CB_LOSS_INTERNAL_MU_KEY,
    CROSSBEAM_PRESTRESS_LOSS_METADATA_KEY,
    DEFAULT_EXTERNAL_DEVIATOR_MU,
    DEFAULT_EXTERNAL_HDPE_LINED_CONSERVATIVE_MU,
    DEFAULT_EXTERNAL_INADVERTENT_ANGLE_RAD,
    DEFAULT_INTERNAL_WOBBLE_K_PER_M,
    EXTERNAL_HDPE_REVIEW_NOTE,
    EXTERNAL_NO_DEVIATOR_ISSUE,
    FT_PER_M,
    aashto_friction_wobble_station_rows,
    aashto_friction_wobble_summary,
    aashto_friction_wobble_tendon_summary_rows,
    crossbeam_prestress_loss_settings_from_session_state,
    restore_crossbeam_prestress_loss_project_state,
)


def _system_row(*, jacking_end: str = "Both", tendon_type: str = "Internal") -> list[dict[str, object]]:
    return [
        {
            "Tendon ID": "T1",
            "Active": True,
            "Type": tendon_type,
            "Strands": 19,
            "Aps/strand mm²": 140.0,
            "fpu MPa": 1860.0,
            "fpj/fpu": 0.75,
            "Jacking end": jacking_end,
        }
    ]


def _straight_profile() -> list[dict[str, object]]:
    return [
        {"Tendon ID": "T1", "Point": "P1", "s (m)": 0.0, "x lateral (mm)": 0.0, "dtop (mm)": 600.0, "Curve role": "Anchorage"},
        {"Tendon ID": "T1", "Point": "P2", "s (m)": 10.0, "x lateral (mm)": 0.0, "dtop (mm)": 600.0, "Curve role": "Profile point"},
        {"Tendon ID": "T1", "Point": "P3", "s (m)": 20.0, "x lateral (mm)": 0.0, "dtop (mm)": 600.0, "Curve role": "Anchorage"},
    ]


def _bent_3d_profile(*, middle_role: str = "Profile point") -> list[dict[str, object]]:
    return [
        {"Tendon ID": "T1", "Point": "P1", "s (m)": 0.0, "x lateral (mm)": 0.0, "dtop (mm)": 500.0, "Curve role": "Anchorage"},
        {"Tendon ID": "T1", "Point": "P2", "s (m)": 10.0, "x lateral (mm)": 1000.0, "dtop (mm)": 1500.0, "Curve role": middle_role},
        {"Tendon ID": "T1", "Point": "P3", "s (m)": 20.0, "x lateral (mm)": 0.0, "dtop (mm)": 500.0, "Curve role": "Anchorage"},
    ]


def test_ptloss1_default_k_converts_aashto_per_ft_to_per_m() -> None:
    assert DEFAULT_INTERNAL_WOBBLE_K_PER_M == pytest.approx(
        AASHTO_INTERNAL_WOBBLE_K_PER_FT * FT_PER_M
    )


def test_ptloss1_internal_both_end_uses_nearest_jacking_end_without_doubling_pj() -> None:
    rows = aashto_friction_wobble_station_rows(
        _straight_profile(),
        _system_row(jacking_end="Both"),
        length_m=20.0,
        internal_mu=0.20,
        internal_k_per_m=0.001,
    )
    midpoint = next(row for row in rows if row["Point"] == "P2")
    end = next(row for row in rows if row["Point"] == "P3")

    expected_ratio = exp(-0.001 * 10.0)
    assert midpoint["Source end"] == "Left (nearest)"
    assert midpoint["x from jack (m)"] == pytest.approx(10.0)
    assert midpoint["alpha total (rad)"] == pytest.approx(0.0)
    assert midpoint["K basis"] == "Internal: AASHTO K"
    assert midpoint["mu basis"] == "Internal duct mu"
    assert midpoint["P/Pj after friction"] == pytest.approx(expected_ratio)
    assert midpoint["P after friction (kN)"] == pytest.approx(midpoint["Pj (kN)"] * expected_ratio)
    assert end["Source end"] == "Right (nearest)"
    assert end["P after friction (kN)"] == pytest.approx(end["Pj (kN)"])


def test_ptloss1_internal_3d_curve_accumulates_vector_angular_change() -> None:
    rows = aashto_friction_wobble_station_rows(
        _bent_3d_profile(),
        _system_row(jacking_end="Left"),
        length_m=20.0,
        internal_mu=0.20,
        internal_k_per_m=0.0,
    )
    midpoint = next(row for row in rows if row["Point"] == "P2")
    vertical_change = abs(atan(-0.1) - atan(0.1))
    horizontal_change = abs(atan(-0.1) - atan(0.1))
    expected_alpha = hypot(vertical_change, horizontal_change)
    expected_ratio = exp(-0.20 * expected_alpha)

    assert midpoint["Source end"] == "Left"
    assert midpoint["alpha total (rad)"] == pytest.approx(expected_alpha)
    assert midpoint["P/Pj after friction"] == pytest.approx(expected_ratio)


def test_ptloss1_external_hdpe_lined_uses_conservative_mu_without_kx() -> None:
    rows = aashto_friction_wobble_station_rows(
        _bent_3d_profile(middle_role="Deviator"),
        _system_row(jacking_end="Left", tendon_type="External"),
        length_m=20.0,
        internal_mu=0.20,
        internal_k_per_m=0.50,
        external_deviator_mu=DEFAULT_EXTERNAL_DEVIATOR_MU,
        external_inadvertent_angle_rad=DEFAULT_EXTERNAL_INADVERTENT_ANGLE_RAD,
    )
    midpoint = next(row for row in rows if row["Point"] == "P2")
    vertical_change = abs(atan(-0.1) - atan(0.1))
    horizontal_change = abs(atan(-0.1) - atan(0.1))
    expected_alpha = hypot(vertical_change, horizontal_change)
    expected_ratio = exp(
        -DEFAULT_EXTERNAL_HDPE_LINED_CONSERVATIVE_MU
        * (expected_alpha + DEFAULT_EXTERNAL_INADVERTENT_ANGLE_RAD)
    )

    assert DEFAULT_EXTERNAL_HDPE_LINED_CONSERVATIVE_MU > AASHTO_POLYETHYLENE_DUCT_MU
    assert midpoint["K (/m)"] is None
    assert midpoint["K basis"] == "External: N/A, no Kx"
    assert "HDPE-lined" in midpoint["Equation"]
    assert midpoint["mu basis"] == "HDPE-lined: adopted 0.25"
    assert midpoint["Status"] == "LOSS READY + NOTE"
    assert midpoint["Issue"] == EXTERNAL_HDPE_REVIEW_NOTE
    assert midpoint["P/Pj after friction"] == pytest.approx(expected_ratio)


def test_ptloss1_external_without_deviator_requires_review_but_still_reports_calculated_loss() -> None:
    rows = aashto_friction_wobble_station_rows(
        _bent_3d_profile(),
        _system_row(jacking_end="Left", tendon_type="External"),
        length_m=20.0,
        internal_mu=0.20,
        internal_k_per_m=0.50,
        external_deviator_mu=DEFAULT_EXTERNAL_DEVIATOR_MU,
        external_inadvertent_angle_rad=DEFAULT_EXTERNAL_INADVERTENT_ANGLE_RAD,
    )
    midpoint = next(row for row in rows if row["Point"] == "P2")
    vertical_change = abs(atan(-0.1) - atan(0.1))
    horizontal_change = abs(atan(-0.1) - atan(0.1))
    expected_alpha = hypot(vertical_change, horizontal_change)
    expected_ratio = exp(-DEFAULT_EXTERNAL_HDPE_LINED_CONSERVATIVE_MU * expected_alpha)
    summary = aashto_friction_wobble_summary(rows)

    assert midpoint["Status"] == "REVIEW REQUIRED"
    assert midpoint["Blocking issue"] == EXTERNAL_NO_DEVIATOR_ISSUE
    assert midpoint["P/Pj after friction"] == pytest.approx(expected_ratio)
    assert summary["value"] == "REVIEW REQUIRED"
    assert summary["review_station_row_count"] == 3
    assert summary["worst_loss_percent"] == pytest.approx(100.0 * (1.0 - expected_ratio))


def test_ptloss1_summary_includes_external_review_note_rows_in_metrics() -> None:
    rows = aashto_friction_wobble_station_rows(
        _bent_3d_profile(middle_role="Deviator"),
        _system_row(jacking_end="Left", tendon_type="External"),
        length_m=20.0,
        internal_mu=0.20,
        internal_k_per_m=0.50,
        external_deviator_mu=DEFAULT_EXTERNAL_DEVIATOR_MU,
        external_inadvertent_angle_rad=DEFAULT_EXTERNAL_INADVERTENT_ANGLE_RAD,
    )
    midpoint = next(row for row in rows if row["Point"] == "P2")
    expected_ratio = midpoint["P/Pj after friction"]
    summary = aashto_friction_wobble_summary(rows)
    tendon_rows = aashto_friction_wobble_tendon_summary_rows(rows)

    assert summary["value"] == "LOSS READY + NOTES"
    assert summary["review_station_row_count"] == 0
    assert summary["review_note_station_row_count"] == 3
    assert summary["review_notes"] == [EXTERNAL_HDPE_REVIEW_NOTE]
    assert summary["worst_loss_percent"] == pytest.approx(100.0 * (1.0 - expected_ratio))
    assert summary["minimum_p_over_pj"] == pytest.approx(expected_ratio)
    assert tendon_rows[0]["Status"] == "LOSS READY + NOTE"
    assert tendon_rows[0]["Issue"] == EXTERNAL_HDPE_REVIEW_NOTE


def test_ptloss1_summary_reports_worst_traced_station_without_final_pe_claim() -> None:
    rows = aashto_friction_wobble_station_rows(
        _straight_profile(),
        _system_row(jacking_end="Left"),
        length_m=20.0,
        internal_mu=0.20,
        internal_k_per_m=0.001,
    )
    summary = aashto_friction_wobble_summary(rows)
    tendon_rows = aashto_friction_wobble_tendon_summary_rows(rows)

    assert summary["value"] == "LOSS READY"
    assert summary["worst_loss_percent"] == pytest.approx(100.0 * (1.0 - exp(-0.001 * 20.0)))
    assert tendon_rows[0]["Worst point"] == "P3"
    assert tendon_rows[0]["Status"] == "LOSS READY"


def test_ptloss1_settings_are_project_json_metadata_safe() -> None:
    state = {
        CB_LOSS_INTERNAL_MU_KEY: 0.18,
        CB_LOSS_INTERNAL_K_PER_M_KEY: 0.0007,
        CB_LOSS_EXTERNAL_MU_KEY: 0.27,
        CB_LOSS_EXTERNAL_INADVERTENT_ANGLE_KEY: 0.035,
    }
    metadata = crossbeam_prestress_loss_settings_from_session_state(state)
    restored_state = {
        CB_LOSS_INTERNAL_MU_KEY: 0.99,
    }

    restored = restore_crossbeam_prestress_loss_project_state(
        {CROSSBEAM_PRESTRESS_LOSS_METADATA_KEY: metadata},
        restored_state,
    )

    assert metadata["schema_version"] == 1
    assert restored is not None
    assert restored_state[CB_LOSS_INTERNAL_MU_KEY] == pytest.approx(0.18)
    assert restored_state[CB_LOSS_INTERNAL_K_PER_M_KEY] == pytest.approx(0.0007)
    assert restored_state[CB_LOSS_EXTERNAL_MU_KEY] == pytest.approx(0.27)
    assert restored_state[CB_LOSS_EXTERNAL_INADVERTENT_ANGLE_KEY] == pytest.approx(0.035)


def test_ptloss1_crossbeam_navigation_adds_prestress_loss_after_profile() -> None:
    app_source = Path("app.py").read_text(encoding="utf-8")
    assert (
        'return ["Section Builder", "Segment Layout", "Rebar", "Tendon System", '
        '"Tendon Profile", "Prestress Loss"]'
    ) in app_source
    assert "render_crossbeam_prestress_loss_page()" in app_source


def test_ptloss1_ui_uses_greek_symbols_and_separate_review_notes_table() -> None:
    source = Path("concrete_pmm_pro/ui/crossbeam_pages.py").read_text(encoding="utf-8")
    ptloss_table_source = source.split(
        'st.markdown("#### AASHTO friction/wobble station trace")',
        maxsplit=1,
    )[1].split(
        'st.markdown("#### Loss component roadmap")',
        maxsplit=1,
    )[0]

    assert '"Internal duct μ"' in source
    assert '"External HDPE-lined μ"' in source
    assert '"α (rad)"' in source
    assert '"μ": round(row["mu"], 4)' in source
    assert 'st.markdown("#### Station review / notes")' in source
    assert '"Issue": row["Issue"]' not in ptloss_table_source
