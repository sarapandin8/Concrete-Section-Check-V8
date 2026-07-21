from __future__ import annotations

from pathlib import Path

import pytest

from concrete_pmm_pro.crossbeam.anchorage_set import (
    anchorage_set_end_rows,
    anchorage_set_station_rows,
    anchorage_set_summary,
)
from concrete_pmm_pro.crossbeam.prestress_loss import (
    CB_LOSS_ANCHORAGE_SET_MM_KEY,
    CB_LOSS_EP_MPA_KEY,
    CROSSBEAM_PRESTRESS_LOSS_METADATA_KEY,
    DEFAULT_ANCHORAGE_SET_MM,
    default_crossbeam_prestress_loss_settings,
    crossbeam_prestress_loss_settings_from_session_state,
    restore_crossbeam_prestress_loss_project_state,
)


def _linear_left_friction_rows() -> list[dict[str, object]]:
    # Accepted post-friction diagram: f(x) = 1400 - 10x MPa over 20 m.
    # With Ep = 200,000 MPa, mirrored-diagram seating compatibility gives
    # delta(mm) = 10,000 * La^2 / Ep = 0.05 La^2.
    rows = []
    for point, x_m, stress_mpa in (
        ("P1", 0.0, 1400.0),
        ("P2", 10.0, 1300.0),
        ("P3", 20.0, 1200.0),
    ):
        rows.append(
            {
                "Tendon ID": "T1",
                "Active": True,
                "Type": "Internal",
                "Jacking end": "Left",
                "Source end": "Left",
                "Point": point,
                "s (m)": x_m,
                "x from jack (m)": x_m,
                "K (/m)": 0.0,
                "Aps total (mm²)": 1000.0,
                "fpj (MPa)": 1400.0,
                "Pj (kN)": 1400.0,
                "Stress after friction (MPa)": stress_mpa,
                "P after friction (kN)": stress_mpa,
                "Status": "LOSS READY",
                "Blocking issue": "",
                "Review note": "",
            }
        )
    return rows


def _linear_both_end_friction_rows() -> list[dict[str, object]]:
    return [
        {
            "Tendon ID": "T1", "Active": True, "Type": "Internal", "Jacking end": "Both",
            "Source end": "Left (nearest)", "Point": "P1", "s (m)": 0.0, "x from jack (m)": 0.0,
            "K (/m)": 0.0, "Aps total (mm²)": 1000.0, "fpj (MPa)": 1400.0, "Pj (kN)": 1400.0,
            "Stress after friction (MPa)": 1400.0, "P after friction (kN)": 1400.0,
            "Status": "LOSS READY", "Blocking issue": "", "Review note": "",
        },
        {
            "Tendon ID": "T1", "Active": True, "Type": "Internal", "Jacking end": "Both",
            "Source end": "Left (nearest)", "Point": "P2", "s (m)": 10.0, "x from jack (m)": 10.0,
            "K (/m)": 0.0, "Aps total (mm²)": 1000.0, "fpj (MPa)": 1400.0, "Pj (kN)": 1400.0,
            "Stress after friction (MPa)": 1300.0, "P after friction (kN)": 1300.0,
            "Status": "LOSS READY", "Blocking issue": "", "Review note": "",
        },
        {
            "Tendon ID": "T1", "Active": True, "Type": "Internal", "Jacking end": "Both",
            "Source end": "Right (nearest)", "Point": "P3", "s (m)": 20.0, "x from jack (m)": 0.0,
            "K (/m)": 0.0, "Aps total (mm²)": 1000.0, "fpj (MPa)": 1400.0, "Pj (kN)": 1400.0,
            "Stress after friction (MPa)": 1400.0, "P after friction (kN)": 1400.0,
            "Status": "LOSS READY", "Blocking issue": "", "Review note": "",
        },
        {
            "Tendon ID": "T1", "Active": True, "Type": "Internal", "Jacking end": "Both",
            "Source end": "Right (nearest)", "Point": "P4", "s (m)": 15.0, "x from jack (m)": 5.0,
            "K (/m)": 0.0, "Aps total (mm²)": 1000.0, "fpj (MPa)": 1400.0, "Pj (kN)": 1400.0,
            "Stress after friction (MPa)": 1350.0, "P after friction (kN)": 1350.0,
            "Status": "LOSS READY", "Blocking issue": "", "Review note": "",
        },
        {
            "Tendon ID": "T1", "Active": True, "Type": "Internal", "Jacking end": "Both",
            "Source end": "Right (nearest)", "Point": "P2R", "s (m)": 10.0, "x from jack (m)": 10.0,
            "K (/m)": 0.0, "Aps total (mm²)": 1000.0, "fpj (MPa)": 1400.0, "Pj (kN)": 1400.0,
            "Stress after friction (MPa)": 1300.0, "P after friction (kN)": 1300.0,
            "Status": "LOSS READY", "Blocking issue": "", "Review note": "",
        },
    ]


def test_ptloss2_linear_force_diagram_matches_closed_form_area_compatibility() -> None:
    end_rows = anchorage_set_end_rows(
        _linear_left_friction_rows(),
        length_m=20.0,
        anchor_set_mm=5.0,
        ep_mpa=200000.0,
    )
    assert len(end_rows) == 1
    row = end_rows[0]
    assert row["Status"] == "PREVIEW READY + NOTE"
    assert row["Influence length (m)"] == pytest.approx(10.0, abs=1.0e-6)
    assert row["Max compatible set (mm)"] == pytest.approx(20.0)
    assert row["Zero movement stress (MPa)"] == pytest.approx(1300.0)
    assert row["Lock-off stress at anchorage (MPa)"] == pytest.approx(1200.0)
    assert row["Anchorage-set loss at anchorage (MPa)"] == pytest.approx(200.0)
    assert row["Anchorage-set loss at anchorage (kN)"] == pytest.approx(200.0)
    assert row["Anchorage-set loss at anchorage (%)"] == pytest.approx(100.0 * 200.0 / 1400.0)
    assert row["Stress integral to La (MPa·m)"] == pytest.approx(13500.0)
    assert row["One-side stress area (MPa·m)"] == pytest.approx(500.0)
    assert row["Mirrored stress-difference area (MPa·m)"] == pytest.approx(1000.0)
    assert row["Compatibility set check (mm)"] == pytest.approx(5.0)
    assert abs(row["Compatibility residual (mm)"]) < 1.0e-8


def test_ptloss2_station_trace_applies_only_inside_zero_movement_length() -> None:
    friction_rows = _linear_left_friction_rows()
    end_rows = anchorage_set_end_rows(
        friction_rows,
        length_m=20.0,
        anchor_set_mm=5.0,
        ep_mpa=200000.0,
    )
    station_rows = anchorage_set_station_rows(friction_rows, end_rows, length_m=20.0)
    by_point = {row["Point"]: row for row in station_rows}

    assert by_point["P1"]["P after anchorage set (kN)"] == pytest.approx(1200.0)
    assert by_point["P1"]["Anchorage-set loss (kN)"] == pytest.approx(200.0)
    assert by_point["P2"]["P after anchorage set (kN)"] == pytest.approx(1300.0)
    assert by_point["P2"]["Anchorage-set loss (kN)"] == pytest.approx(0.0)
    assert by_point["P3"]["P after anchorage set (kN)"] == pytest.approx(1200.0)
    assert by_point["P3"]["Anchorage-set loss (kN)"] == pytest.approx(0.0)



def test_ptloss2b_new_project_default_anchorage_set_is_six_mm_design_assumption() -> None:
    defaults = default_crossbeam_prestress_loss_settings()
    assert DEFAULT_ANCHORAGE_SET_MM == pytest.approx(6.0)
    assert defaults["anchorage_set_mm"] == pytest.approx(6.0)

def test_ptloss2_zero_set_keeps_component_input_required() -> None:
    end_rows = anchorage_set_end_rows(
        _linear_left_friction_rows(),
        length_m=20.0,
        anchor_set_mm=0.0,
        ep_mpa=200000.0,
    )
    summary = anchorage_set_summary(end_rows)

    assert end_rows[0]["Status"] == "INPUT REQUIRED"
    assert end_rows[0]["Influence length (m)"] is None
    assert summary["value"] == "INPUT REQUIRED"
    assert summary["calculated_end_count"] == 0


def test_ptloss2_rejects_set_that_requires_beyond_isolated_branch() -> None:
    end_rows = anchorage_set_end_rows(
        _linear_left_friction_rows(),
        length_m=20.0,
        anchor_set_mm=25.0,
        ep_mpa=200000.0,
    )
    row = end_rows[0]
    assert row["Status"] == "REVIEW REQUIRED"
    assert row["Influence length (m)"] is None
    assert row["Max compatible set (mm)"] == pytest.approx(20.0)
    assert "full-length/opposing-end interaction" in row["Blocking issue"]


def test_ptloss2_both_end_calculates_independent_local_branches_only_within_half_length() -> None:
    rows = anchorage_set_end_rows(
        _linear_both_end_friction_rows(),
        length_m=20.0,
        anchor_set_mm=2.5,
        ep_mpa=200000.0,
    )
    assert {row["Seating end"] for row in rows} == {"Left", "Right"}
    assert all(row["Status"] == "PREVIEW READY + NOTE" for row in rows)
    assert all(row["Branch limit (m)"] == pytest.approx(10.0) for row in rows)
    assert all(row["Influence length (m)"] == pytest.approx(50.0 ** 0.5, abs=1.0e-6) for row in rows)


def test_ptloss2_settings_persist_with_existing_crossbeam_loss_metadata() -> None:
    state = {
        CB_LOSS_ANCHORAGE_SET_MM_KEY: 7.0,
        CB_LOSS_EP_MPA_KEY: 197000.0,
    }
    metadata = crossbeam_prestress_loss_settings_from_session_state(state)
    restored_state: dict[str, object] = {}
    restored = restore_crossbeam_prestress_loss_project_state(
        {CROSSBEAM_PRESTRESS_LOSS_METADATA_KEY: metadata},
        restored_state,
    )

    assert metadata["schema_version"] == 2
    assert metadata["anchorage_set_mm"] == pytest.approx(7.0)
    assert metadata["ep_mpa"] == pytest.approx(197000.0)
    assert restored is not None
    assert restored_state[CB_LOSS_ANCHORAGE_SET_MM_KEY] == pytest.approx(7.0)
    assert restored_state[CB_LOSS_EP_MPA_KEY] == pytest.approx(197000.0)


def test_ptloss2_ui_activates_anchorage_subtab_without_releasing_pe_eff() -> None:
    source = Path("concrete_pmm_pro/ui/crossbeam_pages.py").read_text(encoding="utf-8")
    anchorage_block = source.split("with anchorage_set_tab:", maxsplit=1)[1].split(
        "with elastic_shortening_tab:", maxsplit=1
    )[0]

    assert "Anchorage Set / Draw-in — isolated preview" in anchorage_block
    assert "Adopted anchorage set Δa (mm)" in source
    assert "Detailed seating-end compatibility audit" in anchorage_block
    assert "P after anchor set (kN)" in anchorage_block
    assert "Anchorage-set decision summary" in anchorage_block
    assert "Formula, source & SI unit audit" in source
    assert "design assumption — verify PT supplier" in anchorage_block
    assert "Pe and " in anchorage_block and "Pe_eff remain locked" in anchorage_block
    assert "Guarded future component — no anchorage-set loss is calculated in PTLOSS1G." not in source


def test_ptloss2_ui_loss_defaults_use_valid_session_state_get_arity_and_include_new_fields() -> None:
    import ast

    source = Path("concrete_pmm_pro/ui/crossbeam_pages.py").read_text(encoding="utf-8")
    tree = ast.parse(source)
    target = next(
        node
        for node in tree.body
        if isinstance(node, ast.FunctionDef) and node.name == "_loss_setting_defaults_from_state"
    )

    get_calls = []
    dict_keys: set[str] = set()
    for node in ast.walk(target):
        if isinstance(node, ast.Dict):
            for key in node.keys:
                if isinstance(key, ast.Constant) and isinstance(key.value, str):
                    dict_keys.add(key.value)
        if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Attribute):
            continue
        if node.func.attr != "get":
            continue
        owner = node.func.value
        if not (
            isinstance(owner, ast.Attribute)
            and owner.attr == "session_state"
            and isinstance(owner.value, ast.Name)
            and owner.value.id == "st"
        ):
            continue
        get_calls.append(node)

    assert get_calls
    assert all(len(call.args) == 2 and not call.keywords for call in get_calls)
    assert {
        "internal_mu",
        "internal_k_per_m",
        "external_deviator_mu",
        "external_inadvertent_angle_rad",
        "anchorage_set_mm",
        "ep_mpa",
    }.issubset(dict_keys)
