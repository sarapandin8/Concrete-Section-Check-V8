from __future__ import annotations

from pathlib import Path

import pandas as pd

from concrete_pmm_pro.ui.rebar_page import (
    REBAR_TABLE_COLUMNS,
    apply_generated_perimeter_layout_state,
    rebar_editor_tables_equal,
)


def _generated_table() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "Active": True,
                "Label": "B1",
                "x_mm": -100.0,
                "y_mm": -200.0,
                "Bar Size": "DB20",
                "Diameter_mm": 20.0,
                "Material": "SD40",
                "Count": 1,
                "Note": "Auto perimeter",
            },
            {
                "Active": True,
                "Label": "B2",
                "x_mm": 100.0,
                "y_mm": -200.0,
                "Bar Size": "DB20",
                "Diameter_mm": 20.0,
                "Material": "SD40",
                "Count": 1,
                "Note": "Auto perimeter",
            },
        ]
    )


def test_apply_generated_perimeter_layout_commits_generated_rows_to_rebar_table() -> None:
    state = {
        "rebar_table": pd.DataFrame(columns=REBAR_TABLE_COLUMNS),
        "rebar_editor_revision": 3,
        "rebar_input_mode": "Auto perimeter layout",
    }

    applied = apply_generated_perimeter_layout_state(state, _generated_table())

    assert list(applied.columns) == REBAR_TABLE_COLUMNS
    assert len(state["rebar_table"]) == 2
    assert state["rebar_table"]["Label"].tolist() == ["B1", "B2"]
    assert state["rebar_table"]["Active"].tolist() == [True, True]
    assert state["rebar_editor_revision"] == 4
    assert state["rebar_input_mode"] == "Manual table"
    assert "Applied 2 generated bar row(s)" in state["rebar_apply_status"]


def test_apply_generated_perimeter_layout_clears_stale_data_editor_state() -> None:
    stale_editor = pd.DataFrame(columns=REBAR_TABLE_COLUMNS)
    state = {
        "rebar_data_editor_0": stale_editor,
        "rebar_data_editor_1": stale_editor,
        "unrelated_key": "keep",
        "rebar_editor_revision": 1,
    }

    apply_generated_perimeter_layout_state(state, _generated_table())

    assert "rebar_data_editor_0" not in state
    assert "rebar_data_editor_1" not in state
    assert state["unrelated_key"] == "keep"
    assert state["rebar_editor_revision"] == 2


def test_apply_generated_perimeter_layout_matches_editor_contract_after_commit() -> None:
    state: dict[str, object] = {}

    applied = apply_generated_perimeter_layout_state(state, _generated_table())

    assert rebar_editor_tables_equal(applied, state["rebar_table"])


def test_auto_perimeter_bar_center_offset_default_is_50_mm() -> None:
    source = Path("concrete_pmm_pro/ui/rebar_page.py").read_text(encoding="utf-8")

    offset_label = source.index('"Bar center offset (mm)"')
    offset_control = source[offset_label : offset_label + 260]

    assert "value=50.0" in offset_control
    assert "Default controls: 50 mm to bar center" in source
