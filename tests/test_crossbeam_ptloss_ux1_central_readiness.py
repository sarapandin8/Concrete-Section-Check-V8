from __future__ import annotations

import ast
from pathlib import Path

from concrete_pmm_pro.ui.crossbeam_pages import (
    _crossbeam_prestress_loss_readiness_rows,
)


def _base_kwargs() -> dict:
    return {
        "system_rows": [{"Tendon ID": "T1"}],
        "profile_rows": [{"Tendon ID": "T1", "s (m)": 0.0}],
        "friction_summary": {"blocking_issues": []},
        "anchorage_summary": {
            "blocking_issues": [],
            "active_seating_end_count": 2,
            "calculated_end_count": 2,
        },
        "lightweight_status": "CURRENT",
        "lightweight_ready": True,
        "lightweight_sources_ready": True,
        "lightweight_source_issues": [],
        "td_status": "CURRENT",
        "td_ready": True,
        "td_sources_ready": True,
        "td_source_issues": [],
        "summary_payload": {
            "effective_preview_ready": True,
            "projected_coverage_ready": True,
        },
    }


def test_missing_primary_sources_are_reported_without_visiting_component_tabs() -> None:
    rows = _crossbeam_prestress_loss_readiness_rows(
        system_rows=[],
        profile_rows=[],
    )

    assert [row["Loss stage"] for row in rows] == [
        "Tendon force source",
        "Tendon geometry source",
    ]
    assert all(row["Status"] == "BLOCKED" for row in rows)
    assert rows[0]["Where to fix"] == "Sections → Tendon System"
    assert rows[1]["Where to fix"] == "Sections → Tendon Profile"


def test_complete_loss_chain_has_no_false_blocker_or_pass_wording() -> None:
    rows = _crossbeam_prestress_loss_readiness_rows(**_base_kwargs())

    assert rows[-1]["Status"] == "CURRENT / CLOSED"
    assert all(row["Status"] != "PASS" for row in rows)
    assert not any(row["Status"] in {"BLOCKED", "STALE", "READY TO RUN"} for row in rows)


def test_exact_es_blocker_is_preserved_and_effective_handoff_remains_blocked() -> None:
    kwargs = _base_kwargs()
    kwargs.update(
        {
            "lightweight_status": "MISSING",
            "lightweight_ready": False,
            "lightweight_sources_ready": False,
            "lightweight_source_issues": [
                "Final tendon bond system is required.",
                "Final tendon bond system is required.",
            ],
            "td_status": "MISSING",
            "td_ready": False,
            "td_sources_ready": False,
            "td_source_issues": ["Run or refresh ES first."],
            "summary_payload": {
                "effective_preview_ready": False,
                "projected_coverage_ready": False,
            },
        }
    )

    rows = _crossbeam_prestress_loss_readiness_rows(**kwargs)
    by_stage = {row["Loss stage"]: row for row in rows}

    assert by_stage["Elastic Shortening"] == {
        "Loss stage": "Elastic Shortening",
        "Status": "BLOCKED",
        "Required action": "Final tendon bond system is required.",
        "Where to fix": "Prestress Loss → Elastic Shortening",
    }
    assert by_stage["Time-Dependent"]["Status"] == "BLOCKED"
    assert by_stage["Effective Prestress / FEA handoff"]["Status"] == "BLOCKED"


def test_normal_es_and_td_run_buttons_are_not_disabled_by_readiness() -> None:
    source_path = Path(__file__).parents[1] / "concrete_pmm_pro" / "ui" / "crossbeam_pages.py"
    tree = ast.parse(source_path.read_text(encoding="utf-8"))
    target_labels = {
        "Run Lightweight ES Analysis",
        "Run Event-Based Time-Step Preview",
        "Run Lightweight Time-Dependent Preview",
    }
    found: set[str] = set()

    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        if not isinstance(node.func, ast.Attribute) or node.func.attr != "button":
            continue
        labels = {
            constant.value
            for constant in ast.walk(node.args[0])
            if node.args and isinstance(constant, ast.Constant) and isinstance(constant.value, str)
        }
        matched = labels & target_labels
        if not matched:
            continue
        found.update(matched)
        assert "disabled" not in {keyword.arg for keyword in node.keywords}

    assert found == target_labels


def test_readiness_panel_is_placed_before_component_tabs() -> None:
    source_path = Path(__file__).parents[1] / "concrete_pmm_pro" / "ui" / "crossbeam_pages.py"
    source = source_path.read_text(encoding="utf-8")
    function = source.split("def render_crossbeam_prestress_loss_page()", 1)[1]

    assert function.index("readiness_placeholder = st.empty()") < function.index("st.tabs(")
    assert "opening every subtab to search for the cause is not required" in source
