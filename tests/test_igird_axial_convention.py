"""CSI source-sign regression and independent physical force-sign checks."""
import copy
import math
from pathlib import Path

import pandas as pd
import pytest

from concrete_pmm_pro.analysis.girder_axial_convention import (
    SETTINGS_KEY, CSI_TENSION_POSITIVE, COMPRESSION_POSITIVE, axial_trace,
    axial_convention, axial_demand_compression_positive_kN,
)
from concrete_pmm_pro.core.analysis import AnalysisSettings
from concrete_pmm_pro.io.project_io import (
    project_from_json, project_from_session_state, project_to_json, apply_project_to_session_state,
)
from concrete_pmm_pro.ui import analysis_page as ap
from test_igird_uls7_concurrent_vt import ready_state
from test_igird_uls6_torsion_general_procedure import _demand, _route


def declare(state, convention):
    state[SETTINGS_KEY] = {"input_sign": convention}
    return state


@pytest.mark.parametrize("raw,canonical,action", [(575.159,-575.159,"TENSION"),(-1.492,1.492,"COMPRESSION"),(0,0,"ZERO")])
def test_csi_force_direction_matches_physical_tension_compression(raw, canonical, action):
    state = declare({}, CSI_TENSION_POSITIVE)
    row = {"Nu":raw,"Mux":-33,"Muy":4,"Vuy":-7,"Vux":8,"Tu":-9}
    before = dict(row)
    trace = axial_trace(row,state)
    assert trace["Nu kN"] == canonical
    assert trace["Nu action"] == action
    assert trace["Nu AASHTO tension-positive kN"] == raw
    # Re-reading the same immutable source cannot invert it a second time.
    assert axial_trace(row,state) == trace
    assert row == before


def test_legacy_does_not_infer_csi_from_unrelated_crossbeam_contract():
    state = {"project_metadata":{"crossbeam_loads_station_force_contract":{"fea_program":"CSiBridge"}}}
    assert axial_convention(state) == {"input_sign":COMPRESSION_POSITIVE,"declared":False}
    assert axial_demand_compression_positive_kN({"Nu":50},state) == 50
    other = declare({"section_preset_key":"parametric_u_girder"},CSI_TENSION_POSITIVE)
    assert axial_demand_compression_positive_kN({"Nu":50},other) == 50


def test_invalid_declared_convention_cannot_fall_back_to_another_sign():
    with pytest.raises(ValueError):
        axial_convention({SETTINGS_KEY:{"input_sign":"TYPO"}})


@pytest.mark.parametrize("raw", [200,-200])
def test_every_uls_consumer_matches_independently_preconverted_force(raw):
    csi = declare(ready_state(),CSI_TENSION_POSITIVE)
    manual = declare(copy.deepcopy(csi),COMPRESSION_POSITIVE)
    # A conflicting generic PMM flag must not invert canonical I-Girder Nu.
    csi["analysis_settings"] = AnalysisSettings(compression_positive=False)
    source = _demand(x=10,mux=1000,vu=250,tu=180,nu=raw)
    converted = source.copy(deep=True)
    converted["Nu"] = -raw
    raw_before = source.copy(deep=True)
    a,_ = ap._beam_uls_flexure_analysis_input_for_station(csi,row=source.iloc[0],strength_route=_route())
    b,_ = ap._beam_uls_flexure_analysis_input_for_station(manual,row=converted.iloc[0],strength_route=_route())
    assert a.load_cases[0].Pu_N == b.load_cases[0].Pu_N == -raw*1000
    assert a.settings.compression_positive
    for fn,fields in [
        (ap._beam_uls_shear_check_dataframe,["Nu AASHTO kN","εs raw","φVn kN"]),
        (ap._beam_uls_torsion_check_dataframe,["Nu AASHTO kN","fpc for K MPa","K","φTn kN-m"]),
        (ap._beam_uls_combined_vt_check_dataframe,["Nu app kN","Nu AASHTO kN","Nu term kN","Longitudinal required kN"]),
    ]:
        left = fn(csi,source,strength_route=_route()).iloc[0]
        right = fn(manual,converted,strength_route=_route()).iloc[0]
        available = [f for f in fields if f in left.index]
        assert len(available) >= 2
        for field in available:
            v,w = float(left[field]),float(right[field])
            assert math.isnan(v) and math.isnan(w) or v == pytest.approx(w,rel=1e-10,abs=1e-9)
        assert left["Nu AASHTO kN"] == raw
    pd.testing.assert_frame_equal(source,raw_before)


def test_interpolated_and_synthetic_torsion_rows_preserve_input_sign():
    state = declare(ready_state(),CSI_TENSION_POSITIVE)
    source = pd.concat([_demand(x=0,nu=200),_demand(x=20,nu=100)],ignore_index=True)
    row = ap._beam_uls_interpolated_demand_row_for_case(source,case_name=source.iloc[0]["Case Name"],x_m=10)
    assert row["Nu"] == 150
    assert axial_demand_compression_positive_kN(row,state) == -150
    endpoints = ap._beam_uls_torsion_diagram_boundary_dataframe(state,source,strength_route=_route())
    assert list(endpoints["Nu AASHTO kN"]) == [200,100]


def test_convention_roundtrip_and_loading_legacy_clears_old_widgets_and_source():
    state = declare(ready_state(),CSI_TENSION_POSITIVE)
    state["beam_uls_loads_table"] = _demand(nu=200)
    p = project_from_session_state(state)
    target = {SETTINGS_KEY:{"input_sign":COMPRESSION_POSITIVE},"igird_axial_input_sign":COMPRESSION_POSITIVE}
    apply_project_to_session_state(project_from_json(project_to_json(p)),target)
    assert axial_convention(target)["input_sign"] == CSI_TENSION_POSITIVE
    assert "igird_axial_input_sign" not in target
    assert float(target["beam_uls_loads_table"].iloc[0]["Nu"]) == 200
    legacy = p.model_copy(update={"metadata":{k:v for k,v in p.metadata.items() if k!=SETTINGS_KEY}})
    apply_project_to_session_state(legacy,target)
    assert not axial_convention(target)["declared"]


def test_convention_change_invalidates_all_dependent_checks_even_for_zero_nu():
    state = ready_state()
    source = _demand(nu=0)
    for name in ("Flexure","Shear","Torsion","Shear + Torsion"):
        first = ap._beam_uls_check_input_hash(declare(state,CSI_TENSION_POSITIVE),source,strength_route=_route(),check_name=name)
        second = ap._beam_uls_check_input_hash(declare(state,COMPRESSION_POSITIVE),source,strength_route=_route(),check_name=name)
        assert first != second


def test_corrected_supplied_model_keeps_all_source_actions_and_has_correct_end_behavior():
    root = Path(__file__).resolve().parents[1]
    p = project_from_json((root/'qa/fixtures/I_Girder_20m_IGIRDER_FLEXSIGN1_CSiBridge_deck250.json').read_text())
    state = {}
    apply_project_to_session_state(p,state)
    source = ap._active_beam_uls_demand_dataframe_from_session(state)
    before = source.copy(deep=True)
    _,composite,_ = ap._beam_uls_final_composite_preparation(state)
    frame,_ = ap._beam_uls_flexure_preview_dataframe(composite,source,strength_route=_route(),
        prestress_force_stage="final",full_span_capacity=True,use_aashto_solver=True,apply_girder_development=True)
    assert len(frame) == len(source) == 21
    assert list(frame["Nu input kN"]) == list(source["Nu"])
    assert list(frame["Nu kN"]) == list(-source["Nu"])
    assert list(frame["Demand kN-m"]) == list(source["Mux"])
    left,right = frame.iloc[0],frame.iloc[-1]
    assert left["Nu action"] == "TENSION" and left["Numerical status"] == "NO EQUILIBRIUM"
    assert right["Nu action"] == "COMPRESSION" and right["Numerical status"] == "FAIL"
    assert 0 < right["φMn kN-m"] < right["Demand kN-m"]
    assert all(t["fpx_limit_MPa"]==0 for r in (left,right) for t in r["Strand development trace"])
    valid = frame[frame["Force residual N"].notna()]
    assert max(abs(valid["φPn kN"]-valid["Nu kN"])) < .000021
    pd.testing.assert_frame_equal(source,before)
