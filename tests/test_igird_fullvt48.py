"""Concurrent-row regressions and independent stored-witness balances.

These tests do not claim experimental structural validation.
"""
from copy import deepcopy
from dataclasses import replace
from unittest.mock import patch

import pytest

from concrete_pmm_pro.analysis import igird_composite_steel45 as e
from concrete_pmm_pro.ui import igird_composite_scan48 as scan,igird_composite_steel45 as ui,igird_modeltn47 as view
from concrete_pmm_pro.verification.igird_fullvt48 import audit_witness,design_evidence
from test_igird_composite_steel45 import supplies
from test_igird_uls6_torsion_general_procedure import _state


def row(ordinal,dc,*,torque=100.,status='MODEL REVIEW',exhausted=False):
    ready={'ready':True}
    return {'Girder':'I2','x (m)':2.+ordinal,'Case':'U2A','Source Excel row':491+ordinal,
        'Source input ordinal':ordinal,'Source StepType':'Min','Source location type':'Before',
        'Status':status,'source_CSI':{'Tu':torque},'calculation':{
            'model_VT_DC':dc,'model_V_only_actual_MN_DC':dc/2 if dc is not None else None,
            'model_T_only_actual_MN_DC':dc/3 if dc is not None else None,
            'model_Vn_kN':100.,'model_Tn_kNm':200.,
            'V':ready,'T':ready,'VT':{**ready,'capacity_exhausted':exhausted},'V_fixed_MN':ready,'T_fixed_MN':ready}}


def test_maximum_vt_utilization_can_govern_at_a_smaller_source_torque():
    a,b=row(0,1.55,torque=279.3),row(1,1.53,torque=286.8)
    saved=scan.summarize([a,b],[])
    assert saved['rows'][0]['Source Excel row']==491
    assert len(saved['station_rows'])==2
    assert saved['coverage'][0]['Interior scan status']=='COMPLETE'
    assert saved['rows'][0]['source_CSI']['Tu']==279.3
    assert a['calculation']['model_VT_DC']==1.55


def test_individual_action_governors_keep_their_entire_original_vector():
    a,b=row(0,1.55,torque=-279.3),row(1,.4,torque=286.8)
    b['calculation']['model_T_only_actual_MN_DC']=2.
    original=deepcopy([a,b]);saved=scan.summarize([a,b],[])
    assert saved['governing_rows'][1]['Source Excel row']==492
    assert saved['governing_rows'][2]['Source Excel row']==491
    assert [a,b]==original


def test_before_after_and_max_min_rows_are_not_collapsed_at_one_station():
    rows=[]
    for ordinal,(step,location) in enumerate([('Max','Before'),('Max','After'),('Min','Before'),('Min','After')]):
        item=row(ordinal,.1+ordinal);item.update({'x (m)':10.,'Source StepType':step,'Source location type':location})
        rows.append(item)
    saved=scan.summarize(rows,[])
    assert len(saved['station_rows'])==4
    assert saved['rows'][0]['Source StepType']=='Min'
    assert saved['rows'][0]['Source location type']=='After'


def test_blocked_row_cannot_be_hidden_by_a_small_numeric_governor():
    a=row(0,.4);b={**row(1,.2),'Status':'MODEL SOURCE BLOCKED','Reason':'Unverified envelope'}
    del b['calculation']
    saved=scan.summarize([a,b],[])
    assert saved['rows'][0]['Status']=='MODEL INCOMPLETE'
    assert saved['coverage'][0]['Blocked / incomplete rows']==1
    assert view.primary_frame(saved).iloc[0]['Status']=='MODEL INCOMPLETE'
    assert len(saved['station_rows'])==2


def test_zero_capacity_nonzero_demand_ranks_ahead_of_finite_ratios():
    saved=scan.summarize([row(0,2.),row(1,None,exhausted=True)],[])
    assert saved['rows'][0]['Source Excel row']==492
    assert view.primary_frame(saved).iloc[0]['Nominal V–T state']=='EXCEEDS NOMINAL'


def test_zero_action_demand_does_not_govern_only_because_its_unit_ray_is_exhausted():
    a,b=row(0,.4),row(1,.2)
    b['calculation']['model_T_only_actual_MN_DC']=0.
    b['calculation']['T_fixed_MN']={'ready':True,'capacity_exhausted':True}
    saved=scan.summarize([a,b],[])
    assert next(e for e in saved['governing_rows'] if e['Governing action']=='T')['Source input ordinal']==0


def test_end_exclusions_are_counted_and_do_not_claim_full_span_completion():
    excluded=[{'Girder':'I2','x (m)':0.,'Status':'OUTSIDE MODEL SCOPE'}]
    saved=scan.summarize([row(0,.3)],excluded)
    assert saved['coverage'][0]['Physical end rows excluded']==1
    assert saved['excluded_rows']==excluded
    assert 'Physical end' in saved['selection']


def test_hoop_supply_is_independent_of_the_threshold_result_and_demand():
    state=_state();original=deepcopy(state)
    with patch('concrete_pmm_pro.ui.analysis_page._beam_uls_torsion_result_for_row',
               side_effect=AssertionError('Demand screen cannot own steel supply')):
        hoop=ui.core_hoop_supply(state,x_m=10.)
    assert hoop['Ao mm2']>0 and hoop['ph mm']>0
    assert hoop['Closed loop confirmed'] and hoop['135° hook confirmed']
    assert hoop['At/s mm2/mm']>0
    assert state['beam_girder_torsion_settings']==original['beam_girder_torsion_settings']


def test_below_threshold_does_not_fabricate_a_missing_hoop():
    with pytest.raises(ValueError,match='I-hoop qualification'):
        ui.core_hoop_supply(_state(closed=False,ph_mm=0.),x_m=10.)


def test_unverified_source_row_remains_visible_as_blocked():
    import pandas as pd
    from test_igird_csiref26 import bound_row
    from test_igird_uls6_torsion_general_procedure import _route
    state=_state();state['section_parameters']={'composite_enabled':True}
    source=bound_row(step='Max',mode='unverified',kind='ENVELOPE')
    saved=ui.calculate(state,pd.DataFrame([source]),route=_route())
    assert len(saved['station_rows'])==1
    assert saved['station_rows'][0]['Status']=='MODEL SOURCE BLOCKED'
    assert saved['coverage'][0]['Interior scan status']=='INCOMPLETE'
    assert saved['rows'][0]['Status']=='MODEL INCOMPLETE'


def test_composite_shear_model_hash_tracks_its_physical_torsion_hoop_supply():
    from concrete_pmm_pro.ui import analysis_page as ap
    from test_igird_uls6_torsion_general_procedure import _route,_demand
    state=_state();state['section_parameters']={'composite_enabled':True}
    first=ap._beam_uls_check_input_hash(state,_demand(),strength_route=_route(),check_name='Shear')
    state['beam_girder_torsion_settings']['closed_loop_confirmed']=False
    changed=ap._beam_uls_check_input_hash(state,_demand(),strength_route=_route(),check_name='Shear')
    assert first!=changed


def test_fixed_mn_intercepts_are_distinct_from_pure_intercepts():
    s=supplies(bottom_longitudinal_N=100000.,top_girder_longitudinal_N=100000.,top_slab_longitudinal_N=100000.)
    r=e.calculate(s,vu_N=10000.,tu_Nmm=1e6,mu_Nmm=50e6,nu_tension_N=0.,held_action_intercepts=True)
    assert r['model_V_only_actual_MN_kN']<r['model_Vn_kN']
    assert r['model_T_only_actual_MN_kNm']<r['model_Tn_kNm']
    assert r['model_T_only_actual_MN_DC']==pytest.approx(1./r['model_T_only_actual_MN_kNm'])
    assert r['accepted_Tn_kNm'] is None


@pytest.mark.parametrize('v,t',[(100000.,10e6),(-100000.,10e6),(100000.,-10e6),(-100000.,-10e6)])
def test_independent_physical_unit_audit_of_all_action_signs(v,t):
    s=supplies()
    actions={'vu_N':v,'tu_Nmm':t,'mu_Nmm':20e6,'nu_tension_N':10000.}
    witness=e.solve(s,**actions)
    audit=audit_witness(s,witness,**actions)
    assert audit['status']=='PASS'
    assert audit['maximum_relative_error']<2e-7
    assert audit['structural_validation'] is False


@pytest.mark.parametrize('field',['core_V_N','U_V_N','core_T_Nmm','U_T_Nmm'])
def test_independent_audit_rejects_a_tampered_or_double_counted_resultant(field):
    s=supplies();actions={'vu_N':100000.,'tu_Nmm':10e6}
    witness=e.solve(s,**actions);witness[field]+=1e6
    assert audit_witness(s,witness,**actions)['status']=='FAIL'


def test_contact_mesh_convergence_for_an_interface_controlled_case():
    s=supplies(core_leg_N_per_mm=0.,mu=.05)
    values=[]
    for cells in (8,16,32,64):
        r=e.solve(s,vu_N=100000.,tu_Nmm=10e6,cells=cells)
        assert audit_witness(s,r,vu_N=100000.,tu_Nmm=10e6)['status']=='PASS'
        values.append(r['capacity_factor'])
    assert values[-1]>=values[0]-1e-9
    assert abs(values[-1]-values[-2])/values[-1]<.02


def test_passing_numerical_checks_and_user_flags_do_not_create_structural_validation():
    saved=scan.summarize([row(0,.4)],[])
    saved['station_rows'][0]['Maximum numerical residual']=1e-12
    evidence=design_evidence(saved)
    assert evidence['numerical_verification']['status']=='VERIFIED'
    assert evidence['independent_structural_validation'].startswith('NOT ESTABLISHED')
    assert evidence['accepted_Tn_kNm'] is None
    assert evidence['design_status']=='NOT ACCEPTED FOR FULL-COMPOSITE DESIGN'
