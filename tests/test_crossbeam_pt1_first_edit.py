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
