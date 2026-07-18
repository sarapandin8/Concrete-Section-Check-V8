from __future__ import annotations

import ast
from pathlib import Path
from types import SimpleNamespace

from concrete_pmm_pro.crossbeam.tendon import (
    default_tendon_profile_points,
    default_tendon_system_rows,
)
from concrete_pmm_pro.crossbeam.tendon_persistence import (
    CB_ACTIVE_TENDONS_KEY,
    CB_PROFILE_REV_KEY,
    CB_PROFILE_ROWS_KEY,
    CB_TENDON_SYSTEM_REV_KEY,
    CB_TENDON_SYSTEM_ROWS_KEY,
)
from concrete_pmm_pro.ui import crossbeam_pages


def _data_editor_calls(function_name: str) -> list[ast.Call]:
    source_path = Path(crossbeam_pages.__file__)
    tree = ast.parse(source_path.read_text(encoding="utf-8"))
    function = next(
        node
        for node in tree.body
        if isinstance(node, ast.FunctionDef) and node.name == function_name
    )
    return [
        node
        for node in ast.walk(function)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == "data_editor"
    ]


def test_every_pt1_editable_table_has_first_edit_callback_and_args() -> None:
    system_editors = _data_editor_calls("render_crossbeam_tendon_system_page")
    profile_editors = _data_editor_calls("render_crossbeam_tendon_profile_page")

    assert len(system_editors) == 2
    assert len(profile_editors) == 1
    for call in system_editors + profile_editors:
        keywords = {item.arg for item in call.keywords}
        assert "on_change" in keywords
        assert "args" in keywords


def test_identity_material_and_profile_first_edits_commit_once(monkeypatch) -> None:
    system = default_tendon_system_rows(4)
    profile = default_tendon_profile_points(
        20.0,
        tendon_ids=[row["Tendon ID"] for row in system],
        width_mm=2500.0,
        height_mm=1500.0,
    )
    state = {
        "crossbeam_ui1_length_m": 20.0,
        CB_TENDON_SYSTEM_ROWS_KEY: system,
        CB_PROFILE_ROWS_KEY: profile,
        CB_ACTIVE_TENDONS_KEY: ["T1", "T2"],
        CB_TENDON_SYSTEM_REV_KEY: 0,
        CB_PROFILE_REV_KEY: 0,
    }
    monkeypatch.setattr(crossbeam_pages, "st", SimpleNamespace(session_state=state))

    identity_fallback = crossbeam_pages._tendon_identity_editor_rows(system)
    identity_key = "identity_first_edit"
    state[identity_key] = {
        "edited_rows": {0: {"Tendon ID": "PT-A", "Type": "External"}},
        "added_rows": [],
        "deleted_rows": [],
    }
    crossbeam_pages._commit_tendon_identity_editor(
        identity_key,
        system,
        identity_fallback,
    )

    assert state[CB_TENDON_SYSTEM_ROWS_KEY][0]["Tendon ID"] == "PT-A"
    assert state[CB_TENDON_SYSTEM_ROWS_KEY][0]["Type"] == "External"
    assert all(
        row["Tendon ID"] != "T1" for row in state[CB_PROFILE_ROWS_KEY]
    )
    assert sum(row["Tendon ID"] == "PT-A" for row in state[CB_PROFILE_ROWS_KEY]) == 3
    assert state[CB_ACTIVE_TENDONS_KEY] == ["PT-A", "T2"]

    material_fallback = crossbeam_pages._tendon_material_editor_rows(
        state[CB_TENDON_SYSTEM_ROWS_KEY]
    )
    material_key = "material_first_edit"
    state[material_key] = {
        "edited_rows": {0: {"Aps/strand mm²": 155.0, "fpj/fpu": 0.70}},
        "added_rows": [],
        "deleted_rows": [],
    }
    crossbeam_pages._commit_tendon_material_editor(
        material_key,
        state[CB_TENDON_SYSTEM_ROWS_KEY],
        material_fallback,
    )
    assert state[CB_TENDON_SYSTEM_ROWS_KEY][0]["Aps/strand mm²"] == 155.0
    assert state[CB_TENDON_SYSTEM_ROWS_KEY][0]["fpj/fpu"] == 0.70

    profile_fallback = [
        {key: value for key, value in row.items() if key != "s/L"}
        for row in state[CB_PROFILE_ROWS_KEY]
    ]
    profile_key = "profile_first_edit"
    state[profile_key] = {
        "edited_rows": {0: {"dtop (mm)": 333.0}},
        "added_rows": [],
        "deleted_rows": [],
    }
    crossbeam_pages._commit_tendon_profile_editor(profile_key, profile_fallback)
    assert state[CB_PROFILE_ROWS_KEY][0]["dtop (mm)"] == 333.0


def test_profile_dynamic_editor_can_add_and_delete_rows_on_first_commit(monkeypatch) -> None:
    system = default_tendon_system_rows()
    profile = default_tendon_profile_points(
        20.0,
        tendon_ids=[row["Tendon ID"] for row in system],
        width_mm=2500.0,
        height_mm=1500.0,
        t_left_mm=300.0,
        t_right_mm=300.0,
    )
    state = {
        "crossbeam_ui1_length_m": 20.0,
        CB_TENDON_SYSTEM_ROWS_KEY: system,
        CB_PROFILE_ROWS_KEY: profile,
        CB_ACTIVE_TENDONS_KEY: [row["Tendon ID"] for row in system],
        CB_TENDON_SYSTEM_REV_KEY: 0,
        CB_PROFILE_REV_KEY: 0,
    }
    monkeypatch.setattr(crossbeam_pages, "st", SimpleNamespace(session_state=state))

    fallback = [
        {
            "Delete row": False,
            **{key: value for key, value in row.items() if key != "s/L"},
        }
        for row in profile
    ]
    profile_key = "profile_add_first_commit"
    state[profile_key] = {
        "edited_rows": {},
        "added_rows": [
            {
                "Delete row": False,
                "Tendon ID": "T1",
                "Point": "P4",
                "s (m)": 5.0,
                "x lateral (mm)": -1100.0,
                "dtop (mm)": 650.0,
                "Curve role": "Low point",
            }
        ],
        "deleted_rows": [],
    }
    crossbeam_pages._commit_tendon_profile_editor(profile_key, fallback)
    assert any(
        row["Tendon ID"] == "T1" and row["Point"] == "P4" and row["s (m)"] == 5.0
        for row in state[CB_PROFILE_ROWS_KEY]
    )

    delete_fallback = [
        {
            "Delete row": False,
            **{key: value for key, value in row.items() if key != "s/L"},
        }
        for row in state[CB_PROFILE_ROWS_KEY]
    ]
    delete_index = next(
        index
        for index, row in enumerate(delete_fallback)
        if row["Tendon ID"] == "T1" and row["Point"] == "P4"
    )
    delete_key = "profile_delete_first_commit"
    state[delete_key] = {
        "edited_rows": {delete_index: {"Delete row": True}},
        "added_rows": [],
        "deleted_rows": [],
    }
    crossbeam_pages._commit_tendon_profile_editor(delete_key, delete_fallback)
    assert not any(
        row["Tendon ID"] == "T1" and row["Point"] == "P4"
        for row in state[CB_PROFILE_ROWS_KEY]
    )


def test_profile_preset_apply_replaces_only_selected_tendons(monkeypatch) -> None:
    system = default_tendon_system_rows()
    profile = default_tendon_profile_points(
        20.0,
        tendon_ids=[row["Tendon ID"] for row in system],
        width_mm=2500.0,
        height_mm=1500.0,
        t_left_mm=300.0,
        t_right_mm=300.0,
    )
    state = {
        CB_TENDON_SYSTEM_ROWS_KEY: system,
        CB_PROFILE_ROWS_KEY: profile,
        CB_PROFILE_REV_KEY: 0,
    }
    monkeypatch.setattr(crossbeam_pages, "st", SimpleNamespace(session_state=state))

    notice = crossbeam_pages._apply_tendon_profile_preset(
        state,
        length_m=20.0,
        tendon_ids=[row["Tendon ID"] for row in system],
        target_tendon_ids=["T1"],
        width_mm=2500.0,
        height_mm=1500.0,
        t_left_mm=300.0,
        t_right_mm=300.0,
        preset="Parabolic low-point",
        bend_offset_mm=200.0,
    )
    t1_rows = [row for row in state[CB_PROFILE_ROWS_KEY] if row["Tendon ID"] == "T1"]
    t2_rows = [row for row in state[CB_PROFILE_ROWS_KEY] if row["Tendon ID"] == "T2"]

    assert notice["profile_points"] == 5
    assert len(t1_rows) == 5
    assert len(t2_rows) == 3
    assert t1_rows[2]["dtop (mm)"] == 700.0
    assert state[CB_PROFILE_REV_KEY] == 1


def test_profile_quick_start_selection_callback_rewrites_table(monkeypatch) -> None:
    system = default_tendon_system_rows()
    profile = default_tendon_profile_points(
        20.0,
        tendon_ids=[row["Tendon ID"] for row in system],
        width_mm=2500.0,
        height_mm=1500.0,
        t_left_mm=300.0,
        t_right_mm=300.0,
    )
    state = {
        "crossbeam_ui1_length_m": 20.0,
        "section_parameters": {
            "width_mm": 2500.0,
            "height_mm": 1500.0,
            "t_left_mm": 300.0,
            "t_right_mm": 300.0,
        },
        crossbeam_pages.CB_PROFILE_PRESET_KEY: "Straight Tendon With Bends 1",
        crossbeam_pages.CB_PROFILE_PRESET_SPAN_KEY: "Multiple Span",
        crossbeam_pages.CB_PROFILE_PRESET_OFFSET_KEY: 200.0,
        crossbeam_pages.CB_PROFILE_PRESET_TARGETS_KEY: ["T1"],
        CB_TENDON_SYSTEM_ROWS_KEY: system,
        CB_PROFILE_ROWS_KEY: profile,
        CB_PROFILE_REV_KEY: 0,
    }
    monkeypatch.setattr(crossbeam_pages, "st", SimpleNamespace(session_state=state))

    crossbeam_pages._apply_selected_tendon_profile_preset_from_ui()
    t1_rows = [row for row in state[CB_PROFILE_ROWS_KEY] if row["Tendon ID"] == "T1"]
    t2_rows = [row for row in state[CB_PROFILE_ROWS_KEY] if row["Tendon ID"] == "T2"]

    assert state[crossbeam_pages.CB_PROFILE_PRESET_KEY] == "Straight Tendon With Bends"
    assert state[crossbeam_pages.CB_PROFILE_PRESET_SPAN_KEY] == "2 Span"
    assert [row["s (m)"] for row in t1_rows] == [
        0.0,
        2.5,
        7.5,
        10.0,
        12.5,
        17.5,
        20.0,
    ]
    assert any(row["Curve role"] == "High point" for row in t1_rows)
    assert len(t2_rows) == 3
    assert state[CB_PROFILE_REV_KEY] == 1
    assert state[crossbeam_pages.CB_PROFILE_PRESET_NOTICE_KEY]["action"] == "applied"
