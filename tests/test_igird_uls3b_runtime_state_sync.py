from types import SimpleNamespace
from pathlib import Path

import pandas as pd
import pytest

import concrete_pmm_pro.ui.analysis_page as analysis_page


def _preview(status: str = "PASS") -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "Check": "Flexure",
                "Status": status,
                "Demand kN-m": 1000.0,
                "Capacity kN-m": 7000.0,
                "Utilization value": 1000.0 / 7000.0,
                "Demand": "1,000.00 kN-m",
                "Capacity": "φMn = 7,000.00 kN-m",
                "Utilization": "D/C 0.143",
                "Case": "Strength I",
                "Governing x": "10.000 m",
            }
        ]
    )


def test_uls3b_construction_runtime_state_uses_current_stage_owned_pass(monkeypatch: pytest.MonkeyPatch) -> None:
    demand = SimpleNamespace(
        structural_route_ready=True,
        acceptance_ready=True,
        factors_ready=True,
    )
    construction_df = pd.DataFrame([{"Mux": 100.0}])
    state = {
        "beam_girder_uls_lazy_check": "Flexure",
        "beam_girder_composite_flexure_stage": "Construction — Noncomposite",
        analysis_page._BEAM_ULS_MANUAL_CALC_CACHE_KEY: {
            "Flexure — Construction": {
                "input_hash": "construction-current",
                "flexure_preview_df": _preview("PASS"),
            }
        },
    }
    monkeypatch.setattr(analysis_page, "_beam_uls_strength_route_from_state", lambda *args, **kwargs: object())
    monkeypatch.setattr(analysis_page, "_beam_uls_construction_demand_from_state", lambda _state: (demand, construction_df, []))
    monkeypatch.setattr(analysis_page, "_beam_uls_construction_flexure_hash", lambda *args, **kwargs: "construction-current")

    value, detail, style = analysis_page._igird_composite_flexure_dashboard_state(state)

    assert value == "PASS"
    assert "current" in detail.casefold()
    assert style == "ready"


def test_uls3b_final_runtime_state_reports_review_when_interface_shear_pending(monkeypatch: pytest.MonkeyPatch) -> None:
    active_df = pd.DataFrame(
        [
            {"Active": True, "Case Name": "Strength I", "Mux": 0.0},
            {"Active": True, "Case Name": "Strength I", "Mux": 1000.0},
        ]
    )
    state = {
        "beam_girder_uls_lazy_check": "Flexure",
        "beam_girder_composite_flexure_stage": "Final — Composite",
        analysis_page._BEAM_ULS_MANUAL_CALC_CACHE_KEY: {
            "Flexure — Final Composite": {
                "input_hash": "final-current",
                "flexure_preview_df": _preview("PASS"),
                "Be_strength_verified": True,
                "interface_shear_status": "PENDING",
            }
        },
    }
    monkeypatch.setattr(analysis_page, "_beam_uls_strength_route_from_state", lambda *args, **kwargs: object())
    monkeypatch.setattr(analysis_page, "_active_beam_uls_demand_dataframe_from_session", lambda _state: active_df)
    monkeypatch.setattr(analysis_page, "_beam_uls_final_composite_flexure_hash", lambda *args, **kwargs: "final-current")

    value, detail, style = analysis_page._igird_composite_flexure_dashboard_state(state)

    assert value == "REVIEW"
    assert "interface shear" in detail.casefold()
    assert style == "warning"


def test_uls3b_runtime_state_marks_stale_stage_cache(monkeypatch: pytest.MonkeyPatch) -> None:
    demand = SimpleNamespace(
        structural_route_ready=True,
        acceptance_ready=True,
        factors_ready=True,
    )
    construction_df = pd.DataFrame([{"Mux": 100.0}])
    state = {
        "beam_girder_uls_lazy_check": "Flexure",
        "beam_girder_composite_flexure_stage": "Construction — Noncomposite",
        analysis_page._BEAM_ULS_MANUAL_CALC_CACHE_KEY: {
            "Flexure — Construction": {
                "input_hash": "old",
                "flexure_preview_df": _preview("PASS"),
            }
        },
    }
    monkeypatch.setattr(analysis_page, "_beam_uls_strength_route_from_state", lambda *args, **kwargs: object())
    monkeypatch.setattr(analysis_page, "_beam_uls_construction_demand_from_state", lambda _state: (demand, construction_df, []))
    monkeypatch.setattr(analysis_page, "_beam_uls_construction_flexure_hash", lambda *args, **kwargs: "new")

    value, detail, style = analysis_page._igird_composite_flexure_dashboard_state(state)

    assert value == "STALE"
    assert "does not match current inputs" in detail
    assert style == "warning"


def test_uls3b_ui_routes_dashboard_and_reruns_after_both_flexure_calculations() -> None:
    root = Path(__file__).resolve().parents[1]
    source = (root / "concrete_pmm_pro" / "ui" / "analysis_page.py").read_text(encoding="utf-8")

    assert "def _igird_composite_flexure_dashboard_state" in source
    assert "_igird_composite_flexure_dashboard_state(st.session_state)" in source
    assert source.count("IGIRDER.ULS3B:") >= 2
    final_block = source.split('if run_final:', 1)[1].split('final_command_slot.markdown(', 1)[0]
    construction_block = source.split('if run_construction:', 1)[1].split('construction_command_slot.markdown(', 1)[0]
    assert 'rerun = getattr(st, "rerun", None)' in final_block
    assert 'rerun = getattr(st, "rerun", None)' in construction_block
