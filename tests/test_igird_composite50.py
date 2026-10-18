"""Whole-interface force balance and AASHTO series-reference verification.

Analytical limits and independently reconstructed forces are software checks,
not evidence validating the U/slab torsion stress field.
"""
from copy import deepcopy
from dataclasses import replace
import math
import pytest

from concrete_pmm_pro.analysis import igird_composite_steel45 as engine
from concrete_pmm_pro.analysis.igird_interface50 import check
from concrete_pmm_pro.verification.igird_fullvt48 import audit_witness
from concrete_pmm_pro.ui import igird_shear49 as view
from test_igird_composite_steel45 import supplies


def reference(**changes):
    args=dict(vu_kN=800.,bvi_mm=600.,dv_interface_mm=1400.,fc_weaker_MPa=35.,
        avf_mm2_per_m=2*math.pi*12**2/4/100*1000,fy_MPa=390.,
        surface_key='roughened_girder_slab',anchor_dimensions_ready=True,
        anchorage_declared=True,effective_width_verified=True,
        shear_trace={'Vn kN':2685.,'φVn kN':2282.25})
    return check(**{**args,**changes})


def test_entire_composite_shear_must_pass_through_the_interface():
    # Two 100 N/mm connector legs, mu=1, d_interface=1000 mm give
    # V <= 2*100*1*1000 = 200 kN irrespective of the large I-hoop supply.
    s=supplies(interface_dv_mm=1000.,core_leg_N_per_mm=1e4)
    w=engine.solve(s,vu_N=1000.,tu_Nmm=0.)
    assert w['capacity_factor']==pytest.approx(200.)
    assert w['core_V_N']>0
    assert sum(w['contact_qx_N_per_mm'])==pytest.approx((w['core_V_N']+w['U_V_N'])/1000.)
    assert w['interface_flow_basis']=='WHOLE COMPOSITE V / d_interface'
    assert audit_witness(s,w,vu_N=1000.,tu_Nmm=0.)['status']=='PASS'


def test_interface_lever_arm_is_independent_of_web_depth():
    s=supplies(interface_dv_mm=1000.,core_leg_N_per_mm=1e4)
    assert engine.solve(replace(s,interface_dv_mm=1500.),vu_N=1000.,tu_Nmm=0.)['capacity_factor']==pytest.approx(300.)
    assert engine.solve(replace(s,core_dv_mm=2000.),vu_N=1000.,tu_Nmm=0.)['capacity_factor']==pytest.approx(200.)


def test_removing_connectors_removes_cracked_composite_shear_transfer_not_standalone_I_resistance():
    s=supplies(interface_dv_mm=1000.,u_leg_N_per_mm=0.)
    w=engine.solve(s,vu_N=1000.,tu_Nmm=0.)
    assert w['capacity_exhausted'] and w['capacity_factor']==pytest.approx(0.)
    assert engine.solve(s,vu_N=0.,tu_Nmm=1e6)['capacity_factor']>0
    assert w['accepted_Vn_kN'] is None


@pytest.mark.parametrize('v,t',[(100e3,10e6),(-100e3,10e6),(100e3,-10e6),(-100e3,-10e6)])
def test_signed_source_vectors_and_shared_U_force_are_independently_audited(v,t):
    s=supplies(interface_dv_mm=1250.)
    actions=dict(vu_N=v,tu_Nmm=t,mu_Nmm=20e6,nu_tension_N=10000.)
    w=engine.solve(s,**actions)
    assert audit_witness(s,w,**actions)['status']=='PASS'
    assert sum(w['contact_qx_N_per_mm'])==pytest.approx((w['core_V_N']+w['U_V_N'])/1250.)
    # Replacing whole-V joint shear by the former U-only value must fail,
    # even when the net shear/torque resultants themselves are untouched.
    bad=deepcopy(w);excess=w['core_V_N']/1250./len(w['contact_qx_N_per_mm'])
    bad['contact_qx_N_per_mm']=[q-excess for q in bad['contact_qx_N_per_mm']]
    assert audit_witness(s,bad,**actions)['status']=='FAIL'
    assert w['accepted_Tn_kNm'] is None


@pytest.mark.parametrize('depth',[0.,-1.,float('nan'),True])
def test_invalid_interface_depth_cannot_fall_back_to_web_depth(depth):
    with pytest.raises(ValueError,match='interface_dv_mm'):
        engine.solve(supplies(interface_dv_mm=depth),vu_N=1000.,tu_Nmm=0.)


def test_code_series_reference_includes_concrete_but_never_sums_web_and_joint_strengths():
    r=reference();ksi=6.894757293168361
    avf=2*math.pi*12**2/4/100*1000
    q=min(.28*ksi*600+avf*390/1000,.30*35*600,1.8*ksi*600)
    assert r['q_nominal_kN_per_m']==pytest.approx(q)
    assert r['q_total_kN_per_m']==pytest.approx(800000/1400.)
    assert r['Vn_interface_equivalent_kN']==pytest.approx(q*1400/1000.)
    assert r['reference_Vn_series_kN']==pytest.approx(min(2685.,q*1400/1000.))
    assert r['reference_phiVn_series_kN']==pytest.approx(min(.85*2685.,.9*q*1400/1000.))
    assert r['accepted_Vn_kN'] is None and r['U_vertical_shear_credit_in_code_reference'] is False


def test_weak_surface_or_missing_anchorage_reduces_joint_reference_and_retains_gates():
    strong=reference();weak=reference(surface_key='clean_not_roughened')
    assert weak['reference_phiVn_series_kN']<strong['reference_phiVn_series_kN']
    missing=reference(anchor_dimensions_ready=False,anchorage_declared=False,effective_width_verified=False)
    assert missing['Avf_credited_mm2_per_m']==0 and len(missing['unresolved_gates'])==3
    assert missing['production_status']=='REFERENCE — REVIEW'


def test_ui_joint_table_reconstructs_whole_V_and_keeps_actual_and_capacity_load_levels_separate():
    s=supplies(interface_dv_mm=1250.)
    calc=engine.calculate(s,vu_N=100e3,tu_Nmm=10e6,mu_Nmm=0.,nu_tension_N=0.,held_action_intercepts=True)
    item={'calculation':calc,'actions':{'vu_N':100e3},'interface_reference':reference(),
        'shear_trace':{'Vc kN':600.,'Vs kN':2085.}}
    row=view.interface_frame(item).iloc[0]
    assert row['At actual |Vu|: q (kN/m)']==pytest.approx(80.)
    assert row['At nominal Vn: q (kN/m)']==pytest.approx(row['Reconstructed q (kN/m)'])
    assert len(view.code_reference_frame(item))==3
