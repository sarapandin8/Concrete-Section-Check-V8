"""Physical-vector invariance, interval enclosure, persistence and UI routing."""
from copy import deepcopy
from io import BytesIO
from itertools import product
import json
from pathlib import Path
from unittest.mock import patch
import numpy as np
import pandas as pd
import pytest
from streamlit.testing.v1 import AppTest
from concrete_pmm_pro.io import csi_force_reference as ref
from concrete_pmm_pro.io.girder_csi_import import SOURCE_TAG, source_info
from concrete_pmm_pro.io.project_io import (
    project_from_json, project_from_session_state, project_to_json, apply_project_to_session_state,
)
from concrete_pmm_pro.ui import analysis_page as ap
from concrete_pmm_pro.ui import csi_reference_analysis as adapter
from concrete_pmm_pro.ui.csi_force_reference import save_profile
from concrete_pmm_pro.core.models import SectionGeometry, Point2D
from concrete_pmm_pro.analysis.igird_composite_flexure import _composite_geometry

ROOT = Path(__file__).resolve().parents[1]
CFG = ref.canonical_profile({"depth_below_deck_top_m": .6156,
    "source_top_y_m": 1.85, "source_cg_y_m": 1.2344,
    "vertical_location": "CG of Full Bridge Section", "basis": "User CSI section properties"})
RAW = dict(zip(ref.FIELDS, [200., 300., 100., 40., 50., 600.]))
COORDS = [(-300,-750),(300,-750),(300,-500),(100,-350),(100,450),(300,600),
    (300,750),(-300,750),(-300,600),(-100,450),(-100,-350),(-300,-500)]
I = SectionGeometry(name="I", outer_polygon=[Point2D(x=x,y=y) for x,y in COORDS])


def source_row(values=None, *, step="Static", mode="static", kind="CONCURRENT"):
    values = values or RAW
    info = {"source_sha256": "fixture", "source_file": "fixture.csv", "sheet": "Interior Girder 1",
        "case": "DL", "step": step, "source_mode": mode, "kind": kind,
        "concurrency_confirmed": kind == "CONCURRENT", "evidence": "fixture source contract",
        "occurrence": 1, "location_type": "After", "girder": "Interior Girder 1",
        "raw_fields": values, "row": 4}
    return {"Girder": "Interior Girder 1", "Active": True, "Station x (m)": 10.,
        "Case Name": "DL / " + step, **{ref.ULS_MAP[f]: n for f,n in values.items()},
        "Note": SOURCE_TAG + json.dumps(info)}


def bound_row(**kwargs):
    return ref.bind_reference(pd.DataFrame([source_row(**kwargs)]), CFG).iloc[0].to_dict()


def seed():
    state = {}
    path = ROOT / "qa/evidence/igird_vtqa1/hypothetical_verified_input_qa.json"
    apply_project_to_session_state(project_from_json(path.read_text()), state)
    return state


def test_cross_product_signs_and_round_trip():
    shifted = ref.transport(RAW, r2_m=.1, r3_m=.2)
    assert shifted["T"] == pytest.approx(-10)
    assert shifted["M2"] == pytest.approx(10)
    assert shifted["M3"] == pytest.approx(580)
    assert ref.transport(shifted, r2_m=-.1, r3_m=-.2) == pytest.approx(RAW)


def test_linear_interval_enclosure_equals_all_corner_extrema():
    bounds = {f: [n-10, n+20] for f,n in RAW.items()}
    enclosed = ref.transport_bounds(bounds, r2_m=-.32, r3_m=.21)
    corners = [ref.transport(dict(zip(ref.FIELDS, vals)), r2_m=-.32, r3_m=.21)
        for vals in product(*[bounds[f] for f in ref.FIELDS])]
    for f in ref.FIELDS:
        assert enclosed[f] == pytest.approx((min(v[f] for v in corners), max(v[f] for v in corners)))


def test_source_snapshot_keeps_raw_fields_and_is_not_rebound_on_future_import():
    original = pd.DataFrame([source_row()])
    bound = ref.bind_reference(original, CFG)
    pd.testing.assert_frame_equal(original.drop(columns="Note"), bound.drop(columns="Note"))
    assert ref.configured_profile({"project_metadata": {ref.SETTINGS_KEY: CFG}})["depth_below_deck_top_m"] == .6156
    other = ref.bind_reference(bound, {"depth_below_deck_top_m": .4})
    assert source_info(other.iloc[0])[ref.SNAPSHOT_KEY]["depth_below_deck_top_m"] == .6156
    rebound = ref.bind_reference(bound, {"depth_below_deck_top_m": .4}, replace=True)
    assert source_info(rebound.iloc[0])[ref.SNAPSHOT_KEY]["depth_below_deck_top_m"] == .4
    assert source_info(rebound.iloc[0])["raw_fields"] == RAW


def test_real_section_origins_and_changed_deck_geometry():
    comp = _composite_geometry(I, be_mm=1200, tslab_mm=350)
    origin = ref.geometry_origin(comp, includes_deck=True)
    row = ref.translate_row(bound_row(), origin=origin)
    assert origin["target_y_mm"] == pytest.approx(393.0851063829787)
    assert row[ref.RUNTIME_KEY]["r2_m"] == pytest.approx(.0913148936170213)
    bigger = _composite_geometry(I, be_mm=1200, tslab_mm=450)
    revised = ref.translate_row(bound_row(), origin=ref.geometry_origin(bigger, includes_deck=True))
    assert row["Tu"] != revised["Tu"]
    assert source_info(revised)[ref.SNAPSHOT_KEY]["depth_below_deck_top_m"] == .6156


def test_runtime_transport_is_idempotent_and_retargets_from_source():
    row = bound_row()
    first = ref.translate_row(row, origin={"deck_top_y_mm": 1100, "target_y_mm": 393., "target_local3_mm": 0})
    repeated = ref.translate_row(first, origin={"deck_top_y_mm": 1100, "target_y_mm": 393., "target_local3_mm": 0})
    other = ref.translate_row(first, origin={"deck_top_y_mm": 1100, "target_y_mm": -36., "target_local3_mm": 0})
    direct = ref.translate_row(row, origin={"deck_top_y_mm": 1100, "target_y_mm": -36., "target_local3_mm": 0})
    for col in ref.ULS_MAP.values():
        assert first[col] == pytest.approx(repeated[col])
        assert other[col] == pytest.approx(direct[col])


def test_analysis_only_direction_edit_is_not_lost_on_retarget():
    row = ref.translate_row(bound_row(), origin={"deck_top_y_mm": 1100, "target_y_mm": 393.})
    edited = {**row, "Mux": row["Mux"] + 25.}
    retargeted = ref.translate_row(edited, origin={"deck_top_y_mm": 1100, "target_y_mm": 393.})
    assert retargeted["Mux"] == pytest.approx(edited["Mux"])


def test_envelope_pairing_does_not_claim_a_simultaneous_vector():
    rows = [source_row({f:n+20 for f,n in RAW.items()},step="Max",mode="unverified",kind="ENVELOPE"),
        source_row({f:n-10 for f,n in RAW.items()},step="Min",mode="unverified",kind="ENVELOPE")]
    prepared = ref.prepare_analysis_frame(ref.bind_reference(pd.DataFrame(rows), CFG))
    out = ref.translate_row(prepared.iloc[0], origin={"deck_top_y_mm": 1100, "target_y_mm": 393.})
    assert out[ref.RUNTIME_KEY]["mode"] == "INTERVAL BOUND"
    assert "no simultaneous" in out[ref.RUNTIME_KEY]["concurrency_basis"]
    checked = ref.qualify_result({"Status":"PASS"}, out, check_name="Flexure")
    assert checked["Status"] == "REVIEW"
    single = ref.translate_row(bound_row(step="Max", mode="unverified", kind="ENVELOPE"),
        origin={"deck_top_y_mm":1100, "target_y_mm":393.})
    assert single[ref.RUNTIME_KEY]["mode"] == "BLOCKED" and np.isnan(single["Mux"])
    repeated = ref.translate_row(single, origin={"deck_top_y_mm":1100, "target_y_mm":0.})
    assert repeated[ref.RUNTIME_KEY]["mode"] == "BLOCKED"


def test_declared_correspondence_is_retained_as_a_declared_contract():
    row = ref.translate_row(bound_row(step="Max", mode="correspondence"),
        origin={"deck_top_y_mm":1100, "target_y_mm":393.})
    assert row[ref.RUNTIME_KEY]["mode"] == "EXACT"
    assert row[ref.RUNTIME_KEY]["concurrency_basis"] == "Declared correspondence"


def section_points(n=6, thickness=.35, mixed=False):
    rows = [["Shape","Point","Material","X","Y"],["Reference Point","","",5.5,1.5+thickness]]
    shapes = [("Structural Polygon 1","C35" if mixed else "C45",
        [(0,1.5),(11,1.5),(11,1.5+thickness),(0,1.5+thickness)])]
    shapes += [(f"Structural Polygon {i+2}","C45",[(i+1,0),(i+1.2,0),(i+1.2,1.5),(i+1,1.5)]) for i in range(n)]
    for name, mat, coords in shapes:
        rows += [[name if i == 0 else "",i+1,mat if i == 0 else "",x,y] for i,(x,y) in enumerate(coords)]
    import csv
    from io import StringIO
    out=StringIO();csv.writer(out).writerows(rows)
    return out.getvalue().encode()


def test_automatic_reference_from_full_section_tracks_number_of_girders_and_slab():
    six = ref.profile_from_payload(section_points(), "points.csv")
    eight = ref.profile_from_payload(section_points(8), "points.csv")
    thick = ref.profile_from_payload(section_points(thickness=.45), "points.csv")
    assert six["structural_polygon_count"] == 7
    assert eight["structural_polygon_count"] == 9
    assert eight["depth_below_deck_top_m"] > six["depth_below_deck_top_m"]
    assert thick["depth_below_deck_top_m"] != six["depth_below_deck_top_m"]
    expected = 1.85 - (11*.35*1.675 + 6*.3*.75)/(11*.35+6*.3)
    assert six["depth_below_deck_top_m"] == pytest.approx(expected)


def test_multi_material_reference_requires_reported_csi_cg():
    with pytest.raises(ValueError, match="Multiple"):
        ref.profile_from_payload(section_points(mixed=True), "points.csv")
    data=section_points(mixed=True)+b"Ycg,1.2344\n"
    cfg=ref.profile_from_payload(data,"points.csv")
    assert cfg["depth_below_deck_top_m"] == pytest.approx(.6156)


def test_reference_rejects_unrotated_global_section_cut_and_unknown_schema():
    with pytest.raises(ValueError, match="girder-local"):
        ref.canonical_profile({"depth_below_deck_top_m": .6156, "axes": "GLOBAL"})
    with pytest.raises(ValueError, match="schema"):
        ref.canonical_profile({"depth_below_deck_top_m": .6156, "schema": "unknown"})


def test_reported_csi_cg_uses_declared_section_coordinate_units():
    import csv
    from io import StringIO
    rows = list(csv.reader(StringIO(section_points(mixed=True).decode())))
    for row in rows[1:]:
        row[3], row[4] = str(float(row[3]) * 1000), str(float(row[4]) * 1000)
    rows.insert(1, ["", "", "", "mm", "mm"])
    rows.append(["Ycg", "1234.4"])
    payload = StringIO()
    csv.writer(payload).writerows(rows)
    cfg = ref.profile_from_payload(payload.getvalue().encode(), "points_mm.csv")
    assert cfg["source_top_y_m"] == pytest.approx(1.85)
    assert cfg["source_cg_y_m"] == pytest.approx(1.2344)
    assert cfg["depth_below_deck_top_m"] == pytest.approx(.6156)


def test_force_equivalence_and_sls_sign_conversion():
    row = bound_row()
    sls = {**row, **{ref.SLS_MAP[f]: (-n if f == "P" else n) for f,n in RAW.items()}}
    origin = {"deck_top_y_mm":1100,"target_y_mm":393.}
    u=ref.translate_row(row,origin=origin);s=ref.translate_row(sls,origin=origin,sls=True)
    assert s["N"] == -u["Nu"] and s["Mx"] == u["Mux"] and s["My"] == u["Muy"]


def test_full_girder_torsion_cannot_be_certified_by_i_hoop_only():
    row=ref.translate_row(bound_row(),origin={"deck_top_y_mm":1100,"target_y_mm":-36.})
    out=ref.qualify_result({"Status":"PASS","Overall status":"PASS"},row,check_name="Torsion")
    assert out["Status"] == out["Overall status"] == "REVIEW"
    assert "I-girder hoop" in out["Reference review"]


def test_json_roundtrip_retains_source_origin_without_changing_load_numbers():
    state=seed()
    from concrete_pmm_pro.io.girder_load_bank import BANK_KEY, activate_member
    state[BANK_KEY] = pd.DataFrame([source_row()])
    activate_member(state, "Interior Girder 1")
    save_profile(state,CFG)
    before=pd.DataFrame(state["beam_uls_loads_table"]).copy(deep=True)
    restored={}
    apply_project_to_session_state(project_from_json(project_to_json(project_from_session_state(state))),restored)
    assert ref.configured_profile(restored)["depth_below_deck_top_m"] == .6156
    after=pd.DataFrame(restored["beam_uls_loads_table"])
    pd.testing.assert_frame_equal(before,after,check_dtype=False)
    assert all(source_info(r).get(ref.SNAPSHOT_KEY) for _,r in after.iterrows() if source_info(r))


def test_ui_save_has_no_confirmation_checkboxes_and_leaves_numerical_loads_raw():
    script="""
import streamlit as st
from concrete_pmm_pro.ui.csi_force_reference import render_settings
render_settings(key_prefix='qa')
"""
    at=AppTest.from_string(script).run(timeout=30)
    assert not at.exception and not at.checkbox
    at.number_input[0].set_value(.6156)
    next(b for b in at.button if b.label.startswith("Save CSI reference")).click()
    at.run(timeout=30)
    assert not at.exception
    assert ref.configured_profile(at.session_state.filtered_state)["depth_below_deck_top_m"] == .6156


def test_composite_flexure_consumer_uses_transported_moment_once():
    state=seed()
    state["section_geometry"]=I
    state["section_parameters"]={**state["section_parameters"],"Be_mm":1200.,
        "Tslab_mm":350.,"deck_fc_MPa":35.,"composite_enabled":True}
    _,composite,notes=ap._beam_uls_final_composite_preparation(state)
    assert composite is not None,notes
    route=ap.beam_girder_uls_strength_route(is_bridge=True,is_building=False,
        project_design_code="AASHTO LRFD",code_edition="2020")
    row=bound_row()
    once=adapter.convert_for_check(composite,row,check_name="Flexure")
    ai,notes=ap._beam_uls_flexure_analysis_input_for_station(composite,row=once,strength_route=route)
    assert ai is not None,notes
    assert ai.load_cases[0].Mux_Nmm/1e6 == pytest.approx(once["Mux"])
    assert ai.load_cases[0].Pu_N == pytest.approx(-RAW["P"]*1000)


def test_vt_trace_declares_both_resistance_origins():
    state=seed()
    state["section_geometry"]=I
    state["section_parameters"]={**state["section_parameters"],"Be_mm":1200.,
        "Tslab_mm":350.,"deck_fc_MPa":35.,"composite_enabled":True}
    out=adapter.convert_for_check(state,bound_row(),check_name="Shear + Torsion")
    cols=ref.trace_columns(out)
    assert cols["Resistance O y mm"] == pytest.approx(393.0851063829787)
    assert cols["T resistance O y mm"] == pytest.approx(-36.53846153846154)
    assert out["Tu"] == pytest.approx(RAW["T"]+(1.1-.6156+.03653846153846154)*RAW["V3"])
    assert ref.qualify_result({"Status":"PASS"},out,check_name="Shear + Torsion")["Status"] == "REVIEW"


def test_plot_demand_matches_the_calculated_resistance_origin():
    row=bound_row()
    results=pd.DataFrame([{"Case":row["Case Name"],"Source station x (m)":10.,
        "Governing x":"10.000 m","Demand kN-m":580.,"Reference version":ref.VERSION}])
    plotted=adapter.aligned_plot_source(pd.DataFrame([row]),results,column="Mux")
    assert plotted.iloc[0]["Mux"] == 580 and row["Mux"] == 600
