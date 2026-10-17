"""Independent analytical limits, shared-force witnesses and acceptance gates."""
from dataclasses import replace
from copy import deepcopy
import math

import numpy as np
import pandas as pd
import pytest

from concrete_pmm_pro.analysis import igird_coupled_resistance as cr
from concrete_pmm_pro.ui.igird_coupled_model import matching_action, STATE_COLUMNS
from concrete_pmm_pro.ui.igird_flexure_gap_review import missing_capacity_table


def cell(**changes):
    base=cr.Cell(ao_mm2=200000.,ph_mm=3000.,dv_mm=1000.,contact_width_mm=600.,leg_spacing_mm=120.,
        girder_leg_N_per_mm=1000.,dowel_leg_N_per_mm=1000.,closure_N_per_mm=1000.,
        longitudinal_N=1.e8,diagonal_q_N_per_mm=1.e5,mu=1.,contact_MPa=1.e4,interface_MPa=1.e4)
    return replace(base,**changes)


@pytest.mark.parametrize("name",["girder_leg_N_per_mm","dowel_leg_N_per_mm","closure_N_per_mm"])
def test_pure_torsion_is_bredt_times_weakest_series_tie_not_sum(name):
    c=cell(**{name:250.})
    r=cr.nominal_torsion(c)
    assert r["ready"] and r["model_Tn_Nmm"]==pytest.approx(2*200000*250.)
    assert r["model_Tn_Nmm"] < 2*200000*(250+1000)


def test_pure_torsion_longitudinal_concurrent_force_limit():
    c=cell(longitudinal_N=100000.)
    r=cr.nominal_torsion(c)
    expected=2*c.ao_mm2*c.longitudinal_N/(.45*c.ph_mm*c.cot_theta)
    assert r["model_Tn_Nmm"]==pytest.approx(expected)
    assert r["longitudinal_increment_N"]==pytest.approx(c.longitudinal_N)


def test_diagonal_concrete_model_can_govern_before_steel():
    c=cell(diagonal_q_N_per_mm=100.)
    assert cr.nominal_torsion(c)["model_Tn_Nmm"]==pytest.approx(2*c.ao_mm2*100.)


def test_pure_shear_has_two_legs_and_no_vc_credit():
    c=cell(girder_leg_N_per_mm=100.)
    r=cr.solve(c,cr.Actions(1000.,0.))
    assert r["capacity_factor"]*1000.==pytest.approx(2*c.dv_mm*100.*c.cot_theta)


@pytest.mark.parametrize("fraction",[.1,.3,.5,.9])
def test_v_t_interaction_uses_same_leg_reserve(fraction):
    c=cell(girder_leg_N_per_mm=100.)
    vn=2*c.dv_mm*100.;tn=2*c.ao_mm2*100.
    r=cr.solve(c,cr.Actions(fraction*vn,(1-fraction)*tn))
    assert r["capacity_factor"]==pytest.approx(1.)
    assert r["truss_force_each_N_per_mm"]==pytest.approx(100.)


def test_opening_and_shear_share_clamping_tension_instead_of_independent_passes():
    c=cell(dowel_leg_N_per_mm=100.)
    a=cr.Actions(0.,0.,qx_N_per_mm=100.,opening_N_per_mm=100.)
    r=cr.solve(c,a)
    # sum C=sum T-lambda*n; q<=mu*C -> lambda<=2T/(n+q/mu).
    assert r["capacity_factor"]==pytest.approx(2*100/(100+100/c.mu))
    separate_shear=cr.solve(c,replace(a,opening_N_per_mm=0.))["capacity_factor"]
    separate_open=cr.solve(c,replace(a,qx_N_per_mm=0.))["capacity_factor"]
    assert r["capacity_factor"] < min(separate_shear,separate_open)


def test_pure_torque_retains_nonzero_opposing_interface_shears():
    c=cell(dowel_leg_N_per_mm=100.,mu=.05)
    r=cr.nominal_torsion(c)
    assert r["ready"]
    assert sum(r["friction_x_N_per_mm"])==pytest.approx(0.,abs=1e-8)
    assert min(r["friction_x_N_per_mm"]) < 0 < max(r["friction_x_N_per_mm"])
    assert r["mz_rebuilt_Nmm_per_mm"]==pytest.approx(c.leg_spacing_mm*r["torque_flow_q_N_per_mm"])
    # Closed form for the discrete, symmetric compression/friction strips.
    ymax=c.contact_width_mm/2-c.contact_width_mm/32/2
    q_limit=2*c.mu*c.dowel_leg_N_per_mm*ymax/c.leg_spacing_mm
    assert r["model_Tn_Nmm"]==pytest.approx(2*c.ao_mm2*q_limit)


def test_inscribed_friction_cone_cannot_exceed_circular_coulomb_cone():
    c=cell(dowel_leg_N_per_mm=100.)
    theta=math.pi/8
    r=cr.solve(c,cr.Actions(0.,0.,qx_N_per_mm=100*math.cos(theta),qy_N_per_mm=100*math.sin(theta)))
    assert r["capacity_factor"]==pytest.approx(2*math.cos(theta))
    for sx,sy,C in zip(r["friction_x_N_per_mm"],r["friction_y_N_per_mm"],r["contact_forces_N_per_mm"]):
        assert math.hypot(sx,sy) <= c.mu*C+1e-7


def test_contact_mesh_refines_toward_the_independent_continuous_couple_limit():
    c=cell(dowel_leg_N_per_mm=100.,mu=.05)
    values=[cr.nominal_torsion(c,cells=n)["model_Tn_Nmm"] for n in (16,32,64,128)]
    limit=2*c.ao_mm2*c.mu*c.dowel_leg_N_per_mm*c.contact_width_mm/c.leg_spacing_mm
    assert values==sorted(values)
    assert all(v<limit for v in values)
    assert abs(values[-1]-limit)/limit < .01
    assert (values[2]-values[1])/values[2] < .02


def test_signed_torque_symmetry_and_full_independent_witness():
    c=cell(girder_leg_N_per_mm=100.)
    a=cr.Actions(50000.,10000000.,qx_N_per_mm=30.,qy_N_per_mm=20.,opening_N_per_mm=20.,roll_Nmm_per_mm=100.)
    r=cr.solve(c,a)
    lam=r["capacity_factor"];y=np.array(r["contact_y_mm"]);t=np.array(r["tie_forces_N_per_mm"]);C=np.array(r["contact_forces_N_per_mm"])
    sx=np.array(r["friction_x_N_per_mm"]);sy=np.array(r["friction_y_N_per_mm"])
    assert t.sum()-C.sum()==pytest.approx(lam*a.opening_N_per_mm,abs=1e-6)
    assert np.dot([-c.leg_spacing_mm/2,c.leg_spacing_mm/2],t)-y@C==pytest.approx(lam*a.roll_Nmm_per_mm,abs=1e-5)
    assert sx.sum()==pytest.approx(lam*a.qx_N_per_mm,abs=1e-6)
    assert sy.sum()==pytest.approx(lam*a.qy_N_per_mm,abs=1e-6)
    assert -y@sx==pytest.approx(lam*(a.mz_Nmm_per_mm+c.leg_spacing_mm*a.tu_Nmm/(2*c.ao_mm2)),abs=1e-5)
    assert all(0<=v<=c.dowel_leg_N_per_mm+1e-7 for v in t)
    for key in ("equilibrium_relative","inequality_relative","bounds_relative","duality_relative"): assert r[key] < 1e-7
    positive=cr.solve(c,cr.Actions(0.,1.e6));negative=cr.solve(c,cr.Actions(0.,-1.e6))
    assert negative["capacity_factor"]==pytest.approx(positive["capacity_factor"])
    assert negative["mz_rebuilt_Nmm_per_mm"]==pytest.approx(-positive["mz_rebuilt_Nmm_per_mm"])


def test_fixed_m_n_consumes_same_longitudinal_resource():
    c=cell(longitudinal_N=100000.)
    a=cr.Actions(0.,1.e6,mu_Nmm=40.e6,nu_tension_N=20000.)
    r=cr.solve(c,a)
    available=100000-40.e6/c.dv_mm-.5*20000
    assert r["capacity_factor"]==pytest.approx(available/(.45*c.ph_mm*1.e6/(2*c.ao_mm2)))
    assert not cr.solve(c,replace(a,mu_Nmm=200.e6))["ready"]


def test_scale_invariance_and_capacity_monotonicity():
    c=cell(girder_leg_N_per_mm=120.)
    a=cr.Actions(100000.,10.e6,qx_N_per_mm=50.,opening_N_per_mm=30.)
    r=cr.solve(c,a)
    r2=cr.solve(c,cr.Actions(200000.,20.e6,qx_N_per_mm=100.,opening_N_per_mm=60.))
    assert r2["capacity_factor"]==pytest.approx(r["capacity_factor"]/2)
    stronger=replace(c,dowel_leg_N_per_mm=2000.)
    assert cr.solve(stronger,a)["capacity_factor"] >= r["capacity_factor"]-1e-8
    assert cr.nominal_torsion(stronger)["model_Tn_Nmm"]<=2*c.ao_mm2*c.girder_leg_N_per_mm


def test_factored_model_uses_explicit_supply_factors():
    c=cell(closure_N_per_mm=100.)
    nominal=cr.nominal_torsion(c)
    factored=cr.solve(c,cr.Actions(0.,1.e6),nominal=False)
    assert factored["capacity_factor"]==pytest.approx(.9*nominal["capacity_factor"])
    assert factored["factors"]=={"steel":.9,"contact_and_diagonal":.7,"interface":.9}


@pytest.mark.parametrize("name",["girder_leg_N_per_mm","dowel_leg_N_per_mm","closure_N_per_mm","longitudinal_N","diagonal_q_N_per_mm"])
def test_missing_strength_is_real_zero_and_never_a_pass(name):
    r=cr.nominal_torsion(cell(**{name:0.}))
    assert r["ready"] and r["model_Tn_Nmm"]==pytest.approx(0.)
    assert r["model_status"]=="MODEL EXCEEDED"
    assert r["accepted_phiTn_Nmm"] is None


@pytest.mark.parametrize("bad",[float("nan"),float("inf"),-1.,True])
def test_invalid_materials_are_rejected(bad):
    with pytest.raises(ValueError): cr.nominal_torsion(cell(contact_MPa=bad))


@pytest.mark.parametrize("bad",[float("nan"),float("inf"),True])
def test_unknown_action_is_not_zero(bad):
    with pytest.raises(ValueError): cr.solve(cell(),cr.Actions(1000.,bad))


def test_production_acceptance_cannot_be_enabled_by_numerical_pass():
    for r in (cr.nominal_torsion(cell()),cr.solve(cell(),cr.Actions(1.,0.)),cr.solve(cell(),cr.Actions(0.,0.))):
        assert r["production_status"]=="UNVALIDATED — REVIEW"
        assert r["accepted_phiTn_Nmm"] is r["accepted_VT_factor"] is None
    assert cr.PRODUCTION_VALIDATED is False
    assert any(r["Status"]=="NOT VALIDATED" for r in cr.validation_table())


def test_action_matching_rejects_wrong_member_envelope_name_duplicates_and_unknown_mz():
    row={"Girder":"G1","Case":"Exact app case","Station x (m)":10.,"qx_kN_per_m":1.,"qy_kN_per_m":0.,
         "n_kN_per_m":0.,"mx_kNm_per_m":0.,"mz_kNm_per_m":0.,"Source":"Interface free body F1"}
    assert matching_action([row],member="G1",case="Exact app case",x=10.)
    for key,val in (("Girder","G2"),("Case","Envelope U2A"),("Station x (m)",9.),("Source",""),("mz_kNm_per_m",None)):
        assert matching_action([{**row,key:val}],member="G1",case="Exact app case",x=10.) is None
    assert matching_action([row,row],member="G1",case="Exact app case",x=10.) is None


def test_gap_explanation_uses_actual_zero_development_and_does_not_change_rows():
    data={"Station x (m)":20.,"Capacity kN-m":float("nan"),"Numerical status":"NO EQUILIBRIUM",
          "Original CSI M3 kN-m":0.,"Original CSI P kN":.795,"Demand kN-m":-.151115,
          "Nu AASHTO tension-positive kN":.795,"Source OutputCase":"U1A","Source ItemType":"Max",
          "Strand development trace":[{"fpx_limit_MPa":0.}],"Ordinary bar development trace":[{"factor":0.}]}
    f=pd.DataFrame([data]);snapshot=deepcopy(f)
    t=missing_capacity_table(f)
    assert "zero developed tensile credit" in t.iloc[0]["Reason"]
    assert t.iloc[0]["Shift ΔM (kN-m)"]==pytest.approx(-.151115)
    pd.testing.assert_frame_equal(f,snapshot)
    t2=missing_capacity_table(pd.DataFrame([{**data,"Ordinary bar development trace":[{"factor":1.}],"Notes":"Different stored failure"}]))
    assert t2.iloc[0]["Reason"]=="Different stored failure"
    assert missing_capacity_table(pd.DataFrame([{**data,"Capacity kN-m":0.}])).empty


def adapter_fixture(*, kind="CONCURRENT", reference=True, secondary=0.):
    from test_igird_csiref26 import bound_row, source_row, seed
    from concrete_pmm_pro.ui import igird_coupled_model as ui,analysis_page as ap
    values={"P":100.,"V2":200.,"V3":secondary,"T":10.,"M2":0.,"M3":20.}
    row=(bound_row(values=values,kind=kind) if reference else source_row(values=values,kind=kind))
    rows=pd.DataFrame([row]);s=seed()
    s["project_metadata"][ui.KEY]={"enabled":True,"action_rows":[dict(zip(STATE_COLUMNS,
        [row["Girder"],row["Case Name"],10.,0.,0.,0.,0.,0.,"Known interface free body"]))]}
    route=ap._beam_uls_strength_route_from_state(s,is_bridge=True,is_building=False)
    trace={"resistance_origin":{"deck_top_y_mm":1850.,"target_y_mm":1000.,"target_local3_mm":0.},"detail_issues":["Synthetic central path hypothesis"]}
    return s,rows,route,trace


def test_actual_vector_is_transported_once_and_never_changes_raw_loads(monkeypatch):
    from concrete_pmm_pro.ui import igird_coupled_model as ui
    from concrete_pmm_pro.io.csi_force_reference import translate_row
    s,rows,route,trace=adapter_fixture();original=deepcopy(rows)
    monkeypatch.setattr(ui,"_context",lambda *a,**k:(cell(),deepcopy(trace)))
    result=ui.calculate(s,rows,route=route)
    witness=next(t["coupled"] for t in result["traces"] if "coupled" in t)
    expected=translate_row(rows.iloc[0],origin=trace["resistance_origin"])
    assert witness["actions"]["mu_Nmm"]==pytest.approx(expected["Mux"]*1.e6)
    assert witness["actions"]["nu_tension_N"]==pytest.approx(100000.)
    assert result["rows"][0]["Model V–T factor"] is not None
    assert result["accepted_phiTn_Nmm"] is result["accepted_VT_factor"] is None
    pd.testing.assert_frame_equal(rows,original)


@pytest.mark.parametrize("changes,reason",[
    ({"kind":"ENVELOPE"},"no verified concurrent"),
    ({"reference":False},"origin snapshot missing"),
    ({"secondary":1.},"secondary M2/V3"),
])
def test_source_origin_and_biaxial_gates_withhold_combined_factor(monkeypatch,changes,reason):
    from concrete_pmm_pro.ui import igird_coupled_model as ui
    s,rows,route,trace=adapter_fixture(**changes)
    monkeypatch.setattr(ui,"_context",lambda *a,**k:(cell(),deepcopy(trace)))
    result=ui.calculate(s,rows,route=route)
    assert result["rows"][0]["Model V–T factor"] is None
    assert reason in result["rows"][0]["V–T source"]
    assert not any("coupled" in t for t in result["traces"])


def test_ambiguity_or_missing_joint_actions_cannot_be_assumed_zero(monkeypatch):
    from concrete_pmm_pro.ui import igird_coupled_model as ui
    s,rows,route,trace=adapter_fixture()
    monkeypatch.setattr(ui,"_context",lambda *a,**k:(cell(),deepcopy(trace)))
    s["project_metadata"][ui.KEY]["action_rows"]=[]
    r=ui.calculate(s,rows,route=route)
    assert r["rows"][0]["Model V–T factor"] is None
    assert "interface free-body missing" in r["rows"][0]["V–T source"]


def test_new_model_inputs_stale_only_research_result_and_input_only_json_roundtrip():
    from concrete_pmm_pro.ui import igird_coupled_model as ui,igird_flexure_workspace as fw
    from concrete_pmm_pro.io.project_io import project_from_session_state,project_to_json,project_from_json,apply_project_to_session_state
    s,rows,route,_=adapter_fixture();base=fw.fingerprints(s,rows,route=route);old=ui.fingerprint(s,rows,route=route)
    s["project_metadata"][ui.KEY]["closure_db_mm"]=16.
    assert fw.fingerprints(s,rows,route=route)==base
    assert ui.fingerprint(s,rows,route=route)!=old
    s[fw.CACHE_KEY]={"research_numeric_result_must_not_persist":1234.}
    encoded=project_to_json(project_from_session_state(s))
    assert "research_numeric_result_must_not_persist" not in encoded
    restored={"igird_coupled34_flexure_enabled":False,"igird_coupled34_flexure_detail_0":"old widget"}
    apply_project_to_session_state(project_from_json(encoded),restored)
    assert ui.settings(restored)["closure_db_mm"]==16.
    assert not any(str(k).startswith("igird_coupled34_") for k in restored)


def test_boundary_zone_uses_weaker_supply_and_overlap_is_rejected():
    from concrete_pmm_pro.ui.igird_coupled_model import weakest_girder_zone
    z={"Active":True,"Zone":"left","x_start_m":0.,"x_end_m":10.,"Legs":2,"Diameter_mm":12.,"Spacing_mm":100.,"fy_MPa":390.}
    other={**z,"Zone":"right","x_start_m":10.,"x_end_m":20.,"Spacing_mm":200.}
    assert weakest_girder_zone([z,other],10.)["Zone"]=="right"
    assert weakest_girder_zone([other,z],10.)["Zone"]=="right"
    with pytest.raises(ValueError,match="overlap"):weakest_girder_zone([z,{**other,"x_start_m":9.}],10.)
    with pytest.raises(ValueError,match="covers"):weakest_girder_zone([z],11.)


def test_beam_only_output_cannot_supply_the_full_composite_demand(monkeypatch):
    from concrete_pmm_pro.ui import igird_coupled_model as ui
    from concrete_pmm_pro.io import csi_force_reference as ref
    from test_igird_csiref26 import CFG, source_row
    s,rows,route,trace=adapter_fixture()
    rows=ref.bind_reference(pd.DataFrame([source_row(values={"P":100.,"V2":200.,"V3":0.,"T":10.,"M2":0.,"M3":20.})]),{**CFG,"force_kind":"BEAM_ONLY"})
    monkeypatch.setattr(ui,"_context",lambda *a,**k:(cell(),deepcopy(trace)))
    r=ui.calculate(s,rows,route=route)
    assert r["rows"][0]["Model V–T factor"] is None
    assert "Beam-only" in r["rows"][0]["V–T source"]
