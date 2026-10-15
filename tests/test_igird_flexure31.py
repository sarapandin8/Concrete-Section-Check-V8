"""Scope integrity, missing-capacity plotting and the single-command workflow."""
from copy import deepcopy
import math
import json
from unittest.mock import patch

import pandas as pd
import pytest
from plotly.utils import PlotlyJSONEncoder

from concrete_pmm_pro.ui import analysis_page as ap, igird_flexure_workspace as fw
from concrete_pmm_pro.ui import igird_maxmin_charts as mm
from concrete_pmm_pro.io.girder_load_bank import ACTIVE_KEY, BANK_KEY, save_active
from concrete_pmm_pro.io.project_io import project_from_session_state, project_to_json, apply_project_to_session_state, project_from_json


def stored_frame():
    return pd.DataFrame([{
        "Case": "U1", "Station x (m)": x, "Governing x": f"{x:.3f} m",
        "Demand kN-m": mu, "Capacity kN-m": cap, "Utilization value": dc,
        "D/C value": dc, "φMn kN-m": cap, "Capacity plot sign": 1.,
        "Numerical status": status, "Status": status,
        "Original CSI M3 kN-m": raw, "Original CSI P kN": 10.,
        "Source OutputCase": "U1", "Source ItemType": "Max", "Source LocType": "After",
    } for x, mu, cap, dc, status, raw in [
        (0., 2., float("nan"), float("inf"), "NO EQUILIBRIUM", 0.),
        (.4, 10., 100., .1, "PASS", 8.),
        (10., 50., 100., .5, "PASS", 48.),
        (19.6, 10., 100., .1, "PASS", 8.),
        (20., 2., 1., 2., "FAIL", 0.),
    ]])


def test_unavailable_resistance_and_real_exceedance_are_different_blockers():
    frame = stored_frame(); before = frame.copy(deep=True)
    check = fw.decision(frame)
    assert check == {"status": "FAIL", "exceeded": 1, "unavailable": 1, "review": 1, "ratio": 2.}
    pd.testing.assert_frame_equal(frame, before)


def test_a_true_zero_capacity_with_nonzero_demand_is_still_a_strength_failure():
    frame = stored_frame().iloc[[0]].copy()
    frame["Capacity kN-m"] = 0.
    check = fw.decision(frame)
    assert check["exceeded"] == 1 and check["unavailable"] == 0
    assert math.isinf(check["ratio"]) and check["status"] == "FAIL"


def test_cut_end_scope_never_excludes_near_support_stations_or_changes_raw_rows():
    frame = stored_frame(); before = frame.copy(deep=True)
    assessed, ends = fw.assessment_frames(frame, length=20, separate_ends=True)
    assert assessed["Station x (m)"].tolist() == [.4, 10., 19.6]
    assert ends["Station x (m)"].tolist() == [0., 20.]
    assert fw.decision(assessed)["status"] == "PASS"
    pd.testing.assert_frame_equal(frame, before)
    assert fw.decision(frame)["status"] == "FAIL"


def test_cut_end_separation_is_unavailable_when_the_load_axis_starts_at_a_bearing():
    from concrete_pmm_pro.analysis.igird_flexure_development import SETTINGS_KEY
    assert fw.zero_L_are_cut_ends({}, length=20)
    assert not fw.zero_L_are_cut_ends({SETTINGS_KEY: {"left_extension_m": .4}}, length=20)
    assert not fw.zero_L_are_cut_ends({"section_parameters": {"igird_end_sections": {
        "enabled": True, "coordinate_mode": "custom", "left_end_x_m": .4, "right_end_x_m": 19.6}}}, length=20)


def test_separate_end_review_cannot_become_overall_composite_pass():
    bundle = {"section": {"flexure_preview_df": stored_frame(), "Be_strength_verified": True},
              "interface": {"interface_status": "PASS"}}
    row = fw.summary_row("G1", bundle, length=20, separate_ends=True)
    assert row["Section"] == "PASS" and row["Max available D/C"] == "0.500"
    assert row["Overall"] == "REVIEW" and row["Cut ends"] == "SEPARATE REVIEW"
    assert fw.summary_row("G1", bundle, length=20)["Overall"] == "FAIL"


def test_empty_assessed_span_cannot_pass_and_missing_source_is_not_filled():
    frame = stored_frame().iloc[[0, 4]]
    assessed, _ = fw.assessment_frames(frame, length=20, separate_ends=True)
    assert fw.decision(assessed)["status"] == "NOT CALCULATED"
    missing = fw.endpoint_reference_table(frame.drop(columns=["Original CSI M3 kN-m"]), length=20)
    assert missing["CSI M3 (kN-m)"].isna().all()


def test_reference_audit_explains_a_nonzero_design_moment_when_raw_m3_is_zero():
    frame = stored_frame(); before = frame.copy(deep=True)
    table = fw.endpoint_reference_table(frame, length=20)
    assert table["CSI M3 (kN-m)"].tolist() == [0., 0.]
    assert table["Reference shift ΔM (kN-m)"].tolist() == [2., 2.]
    assert table["Design Mux (kN-m)"].tolist() == [2., 2.]
    pd.testing.assert_frame_equal(frame, before)


def test_capacity_gap_is_explicit_and_a_real_isolated_capacity_point_is_visible():
    frame = stored_frame().iloc[[0, 1, 2, 3, 4]].copy()
    frame.loc[[0, 2, 4], ["Capacity kN-m", "φMn kN-m"]] = float("nan")
    rows = frame.rename(columns={"Case": "Case Name", "Demand kN-m": "Mux"})
    before = frame.copy(deep=True)
    fig = ap._make_beam_uls_flexure_preview_figure(rows, frame, code_label="AASHTO", member_length_m=20)
    capacity = next(t for t in fig.data if t.name == "φMn")
    assert math.isnan(capacity.y[0]) and math.isnan(capacity.y[2])
    assert capacity.connectgaps is False
    points = next(t for t in fig.data if t.name == "φMn stored point")
    assert list(points.x) == [.4, 19.6] and list(points.y) == [100., 100.]
    assert {i["x_m"] for i in fig.layout.meta["flexure_gap_intervals"]} == {0, 10, 20}
    pd.testing.assert_frame_equal(frame, before)


def test_a_valid_other_curve_prevents_common_gap_shading():
    from concrete_pmm_pro.visualization.igird_uls_chart_display import mark_flexure_gap_segments
    import plotly.graph_objects as go
    frame = pd.DataFrame({"__x_m": [0, 0, 10, 10], "__capacity_kNm": [float("nan"), 10., 20., 20.]})
    fig = go.Figure(); mark_flexure_gap_segments(fig, frame)
    assert fig.layout.meta["flexure_gap_intervals"] == []


def test_scope_control_uses_assessed_rows_while_capacity_and_source_paths_stay_original():
    from qa.igird_maxmin10_model import native_model
    from test_igird_membercharts3 import model
    state = model(); state.update(native_model(second_lc=False))
    name, rows = next(iter(fw.members.member_inputs(state).items()))
    frame = pd.concat([stored_frame().assign(Case=case) for case in rows["Case Name"].unique()], ignore_index=True)
    family = mm.csi_bound_families(rows)[0]
    package = {"rows": rows, "result": {"flexure_preview_df": frame}}
    original = mm.make_bound_figures(state, package, family=family, member=name,
        check_name="Flexure", code_label="AASHTO", view=mm.DEMAND_VIEW)
    assessed, _ = fw.assessment_frames(frame, length=20, separate_ends=True)
    scoped = mm.make_bound_figures(state, {**package, "control_frame": assessed, "scope_label": "Span scope"},
        family=family, member=name, check_name="Flexure", code_label="AASHTO", view=mm.DEMAND_VIEW)
    for step in original:
        for left, right in zip(original[step].data, scoped[step].data):
            assert json.dumps(left.to_plotly_json(), cls=PlotlyJSONEncoder, sort_keys=True) == json.dumps(right.to_plotly_json(), cls=PlotlyJSONEncoder, sort_keys=True)
        assert scoped[step].layout.meta["igird_maxmin_member_control"]["D/C or ratio"] == "0.500"
        assert scoped[step].layout.meta["igird_maxmin_assessment_scope"] == "Span scope"


def test_one_command_runs_both_checks_and_review_never_runs_a_solver():
    from streamlit.testing.v1 import AppTest
    from test_igird_membercharts3 import model
    state = model(); save_active(state)
    script = """
import streamlit as st
from concrete_pmm_pro.ui import analysis_page as ap, igird_flexure_workspace as fw
route=ap._beam_uls_strength_route_from_state(st.session_state,is_bridge=True,is_building=False)
fw.render_workspace(ap._active_beam_uls_demand_dataframe_from_session(st.session_state),route=route,code_label='AASHTO')
"""
    app = AppTest.from_string(script, default_timeout=90)
    for key, value in state.items(): app.session_state[key] = deepcopy(value)
    with patch.object(fw.members, "calculate_member", wraps=fw.members.calculate_member) as section, \
            patch.object(ap, "_igird_interface_shear_dataframe", wraps=ap._igird_interface_shear_dataframe) as interface:
        app.run(); assert not app.exception
        assert section.call_count == interface.call_count == 0
        assert [b.label for b in app.button] == ["Calculate Flexure"]
        app.button(key="igird_flexure31_calculate").click().run()
        assert not app.exception, [e.message for e in app.exception]
        assert section.call_count == interface.call_count == 2
        assert len(app.get("plotly_chart")) == 1
        for view in (fw.UTILIZATION, fw.SOURCE, fw.INTERFACE, fw.DEMAND):
            app.radio(key="igird_flexure31_view").set_value(view).run()
            assert not app.exception, [e.message for e in app.exception]
            assert len(app.get("plotly_chart")) == 1
            assert section.call_count == interface.call_count == 2
        app.selectbox(key="igird_flexure31_end_scope").set_value(fw.SEPARATE).run()
        assert not app.exception
        assert section.call_count == interface.call_count == 2
        assert app.session_state["project_metadata"][fw.POLICY_KEY]["end_treatment"] == "separate_review"
        payload = project_to_json(project_from_session_state(app.session_state.filtered_state))
        assert fw.CACHE_KEY not in payload
        assert "beam_girder_uls_manual_calculation_cache" not in payload
        assert "separate_review" in payload
        app.toggle(key="igird_flexure31_edit_inputs").set_value(True).run()
        assert not app.exception
        assert [b.label for b in app.button] == ["Calculate Flexure"]


def test_loading_another_project_clears_old_review_scope_and_runtime_results():
    from test_igird_membercharts3 import model
    state = model()
    payload = project_to_json(project_from_session_state(state))
    state["igird_flexure31_end_scope"] = fw.SEPARATE
    state[fw.CACHE_KEY] = {"old project": "must not survive load"}
    apply_project_to_session_state(project_from_json(payload), state)
    assert "igird_flexure31_end_scope" not in state and fw.CACHE_KEY not in state
    assert fw.POLICY_KEY not in state["project_metadata"]

