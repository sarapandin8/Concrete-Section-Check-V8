"""Analytical cage limit, physical-vector invariance and provenance gates.

These verify software / declared idealization, not actual structural validity.
"""
from copy import deepcopy
from dataclasses import replace
import json
import math
from unittest.mock import patch

import numpy as np
import pandas as pd
import pytest
from shapely.geometry import box
from streamlit.testing.v1 import AppTest

from concrete_pmm_pro.analysis import igird_station36_truss as tr
from concrete_pmm_pro.analysis.igird_station36_steel import strand_ties,positions
from concrete_pmm_pro.analysis.igird_station36_recommendations import propose
from concrete_pmm_pro.io import csi_force_reference as ref
from concrete_pmm_pro.io.project_io import project_from_json,project_from_session_state,project_to_json,apply_project_to_session_state
from concrete_pmm_pro.ui import igird_station36 as ui,analysis_page as ap,igird_flexure_workspace as fw
from test_igird_csiref26 import seed,bound_row
from test_igird_joint29 import cfg
from test_igird_detail35 import current


def cage(**changes):
    kwargs=dict(cover_mm=40.,db_mm=12.,spacing_mm=100.,fy_MPa=400.,fc_MPa=1000.,nominal=True,
        longitudinal=[{'x_mm':x,'y_mm':y,'capacity_N':1e9,'label':f'b{x}/{y}'} for x,y in [(-154,-154),(-154,154),(154,-154),(154,154)]])
    kwargs.update(changes)
    return tr.core_cage(box(-200,-200,200,200),**kwargs)


def test_square_closed_cage_matches_independent_thin_wall_tie_equation():
    model=cage();pitch=model.trace['pitch_mm'];edge=308.;ao=edge**2;at=math.pi*12**2/4
    # q=At*fy*cot(theta)/s; each physical hoop leg counted ONCE.
    expected=2*ao*at*400/100*pitch/edge
    r=tr.solve(model,[0.]*6)
    assert r['model_T_limit_Nmm']==pytest.approx(expected,rel=1e-9)
    assert r['model_T_limit_Nmm']<2*expected
    assert r['accepted_phiTn_Nmm'] is r['accepted_VT_factor'] is r['full_composite_Tn_Nmm'] is None


def test_both_torsion_directions_and_nominal_supply_scaling():
    a=tr.solve(cage(),[0.]*6);b=tr.solve(cage(),[0.]*6,torsion_sign=-1.)
    assert a['model_T_limit_Nmm']==pytest.approx(b['model_T_limit_Nmm'])
    f=tr.solve(cage(nominal=False),[0.]*6)
    assert f['model_T_limit_Nmm']==pytest.approx(.9*a['model_T_limit_Nmm'])


def test_six_concurrent_actions_rebuilt_from_end_forces_and_actual_supports_only():
    m=cage();held=[1234.,100000.,20000.,123.,1000000.,5000000.]
    r=tr.solve(m,held);expected=held.copy();expected[3]=r['model_T_limit_Nmm']
    assert r['rebuilt_wrench_N_Nmm']==pytest.approx(expected,abs=1e-6)
    reactions=np.array(r['support_reactions_N']).ravel()
    assert all(reactions[i]==0 for i in range(len(reactions)) if i not in m.fixed_dofs)
    external=np.zeros_like(m.nodes);external[m.end_nodes]=r['end_tractions_N']
    total=external+reactions.reshape(-1,3)
    assert total.sum(axis=0)==pytest.approx([0,0,0],abs=1e-6)
    assert np.cross(m.nodes,total).sum(axis=0)==pytest.approx([0,0,0],abs=1e-5)
    for key in ('equilibrium_relative','resource_relative','bounds_relative','duality_relative','global_relative'):assert r[key]<1e-8


def test_change_of_section_origin_preserves_physical_torque_limit():
    h=[1000.,20000.,10000.,0.,1e6,2e6];d=70.;z=30.
    a=tr.solve(cage(),h)
    moved=h.copy();moved[5]+=d*h[0];moved[4]-=z*h[0]
    b=tr.solve(cage(origin_y_mm=d,origin_local3_mm=z),moved)
    assert b['model_T_limit_Nmm']==pytest.approx(a['model_T_limit_Nmm']-d*h[2]+z*h[1],rel=1e-8)


def test_secondary_shear_and_bending_are_not_ignored_or_zeroed():
    m=cage();a=tr.solve(m,[0.]*6)
    b=tr.solve(m,[0,0,1e5,0,2e6,0])
    assert b['model_T_limit_Nmm']<a['model_T_limit_Nmm']
    assert b['held_wrench_N_Nmm'][2]==1e5 and b['held_wrench_N_Nmm'][4]==2e6


def test_concrete_diagonals_share_the_same_cell_budget():
    m=cage(fc_MPa=5.);r=tr.solve(m,[0.]*6)
    assert r['ready']
    forces=np.array(r['member_forces_N'])
    use=m.resource_matrix@forces
    assert np.max(use/m.resource_limits)<=1+1e-9
    assert sum(m.trace['concrete_cell_areas_mm2'])==pytest.approx(160000.)
    loose=replace(m,resource_limits=m.resource_limits*2.)
    assert tr.solve(loose,[0.]*6)['model_T_limit_Nmm']>=r['model_T_limit_Nmm']


def test_actual_steel_embedding_preserves_its_position_and_force_moment():
    bar={'x_mm':41.,'y_mm':-76.,'capacity_N':1234.,'label':'offset bar'}
    m=cage(longitudinal=[bar])
    i=m.labels.index('offset bar / bay 0');col=m.matrix[:,i].reshape(-1,3)
    assert col[:4].sum(axis=0)==pytest.approx([1.,0,0])
    # (0, CSI2=y=-76, CSI3=x=41) x (1,0,0).
    assert np.cross(m.nodes[:4],col[:4]).sum(axis=0)==pytest.approx([0.,41.,76.])
    assert m.bounds[i]==(0,1234.)
    bad=cage(longitudinal=[{**bar,'x_mm':500.}])
    assert not bad.trace['longitudinal_ledger'][0]['embedded']
    assert not any('offset bar' in label for label in bad.labels)


def test_infeasible_domain_withholds_capacity_instead_of_returning_zero():
    r=tr.solve(cage(),[1e12,0,0,0,0,0])
    assert not r['ready'] and r['model_T_limit_Nmm'] is None
    assert r['status']=='SIGNED T DOMAIN INFEASIBLE'


@pytest.mark.parametrize('bad',[[0,0],[0,0,0,True,0,0],[0,0,0,0,float('nan'),0]])
def test_invalid_actions_fail_closed(bad):
    with pytest.raises(ValueError):tr.solve(cage(),bad)


def strand_row(**changes):
    r={'Active':True,'Group ID':'R1','No. Strands':3,'Strand x positions mm':'-50,0,50',
        'Strand Size':'12.7 mm','Area/Strand_mm2':100.,'Pe_eff_final/strand_kN':100.,
        'y_mm_from_bottom':75.,'Left debond m':2.,'Right debond m':2.,'Debonded strand nos':'2'}
    r.update(changes);return r


def test_prestress_tie_ceiling_and_sleeve_keep_individual_x_positions():
    r=strand_ties([strand_row()],x_m=18.,span_m=20.,y_min_mm=-750.,depth_mm=1500.,fy_tie_MPa=390.,settings={})
    assert [v['x_mm'] for v in r]==[-50.,0.,50.]
    assert r[1]['capacity_N']==0 and r[1]['debonded']
    assert r[0]['capacity_N']>0 and r[2]['capacity_N']==pytest.approx(r[0]['capacity_N'])
    assert r[0]['tie_stress_ceiling_MPa']==1390. # fpe+fy, not fpu
    assert r[0]['developed_stress_MPa']<=1390.


def test_strand_development_uses_physical_cut_ends_after_coordinate_shift():
    kwargs={'span_m':20.,'y_min_mm':-750.,'depth_mm':1500.,'fy_tie_MPa':390.,'settings':{}}
    a=strand_ties([strand_row()],x_m=18.,**kwargs)
    b=strand_ties([strand_row()],x_m=22.,left_cut_m=4.,right_cut_m=24.,**kwargs)
    assert [v['capacity_N'] for v in a]==pytest.approx([v['capacity_N'] for v in b])
    assert [v['bonded_distance_mm'] for v in a]==[v['bonded_distance_mm'] for v in b]


@pytest.mark.parametrize('text',['-50,50','-50,0,nan','0,0,0',''])
def test_missing_or_ambiguous_strand_positions_do_not_collapse_to_centre(text):
    with pytest.raises(ValueError):positions(text,3)


def test_recommendations_fix_geometry_preserve_actual_supplies_and_do_not_verify_flags():
    interface={'connector_source':'dowels_same_zoning','connectors_cross_and_anchored':False,
        'dowel_connection':current(row_spacing_mm=120.,girder_ld_available_mm=1400.)}
    params={'T2_mm':200.,'Tslab_mm':350.,'girder_fc_MPa':45.,'deck_fc_MPa':35.,
        'deck_long_rebar_top_cover_mm':50.,'deck_long_rebar_top_diameter_mm':16.,'deck_long_rebar_top_fy_MPa':390.}
    rows=[strand_row(**{'Strand x positions mm':'-50,0,50,100','Computed spacing_mm':50.,'Row center x_mm':0.,'Debonded strand nos':'2,4'})]
    original=deepcopy((interface,params,rows))
    new,strands,ledger=propose(interface,params,rows,dowel_db_mm=12,dowel_fy_MPa=390,mesh_proposal={'Diameter_mm':12,'Spacing_mm':150})
    d=new['dowel_connection']
    assert d['row_spacing_mm']==100 and (200-100-12)/2==44
    assert d['hook_top_depth_mm']==150 and d['slab_ldh_available_mm']==200 and d['hook_inside_bend_mm']==72
    assert d['slab_transverse_mesh']['top']['Clear_cover_mm']==66
    assert new['connectors_cross_and_anchored'] is False
    assert strands[0]['No. Strands']==3 and strands[0]['Pe_eff_final/strand_kN']==100.
    assert strands[0]['Strand x positions mm']=='-50,0,50' and strands[0]['Debonded strand nos']=='2'
    assert (interface,params,rows)==original and ledger['status']=='PROPOSED DESIGN — NOT AS-BUILT'


def test_selection_compares_transported_torsion_and_preserves_source_rows():
    s=seed();a=bound_row(values={'P':0.,'V2':0.,'V3':0.,'T':100.,'M2':25.,'M3':100.})
    b=bound_row(values={'P':0.,'V2':0.,'V3':300.,'T':99.,'M2':75.,'M3':100.})
    a['Case Name']='A';b['Case Name']='B';rows=pd.DataFrame([a,b]);before=deepcopy(rows)
    picked,trace=ui.select_station(s,rows)
    assert picked[3]['Case Name']=='B' and picked[3]['Tu']>100
    assert picked[3]['Muy']==75 and picked[3]['Vux']==300 and trace['eligible']==2
    pd.testing.assert_frame_equal(rows,before)


@pytest.mark.parametrize('changes',[{'kind':'ENVELOPE'},{'reference':False}])
def test_unverified_sources_cannot_enter_station_model(changes):
    from test_igird_coupled34 import adapter_fixture
    s,rows,route,_=adapter_fixture(**changes)
    picked,trace=ui.select_station(s,rows)
    assert picked is None and trace['excluded']


@pytest.mark.parametrize('column',['Muy','Vux'])
def test_missing_secondary_actions_are_unknown_instead_of_assumed_zero(column):
    row=bound_row();row.pop(column)
    picked,trace=ui.select_station(seed(),pd.DataFrame([row]))
    assert picked is None and 'unknown is not zero' in trace['excluded'][0]['reason']


def test_settings_and_proposals_roundtrip_but_numeric_witnesses_do_not_persist():
    s=seed();s['project_metadata'][ui.KEY]={'enabled':True}
    s['project_metadata'][ui.RECOMMENDATIONS]={'status':'PROPOSED','changes':[{'Previous':'120','Proposed':'100'}]}
    s[fw.CACHE_KEY]={'station36_research':{'numerical_witness_do_not_save':999}}
    text=project_to_json(project_from_session_state(s));assert 'numerical_witness_do_not_save' not in text
    restored={'igird_station36_enabled':False}
    apply_project_to_session_state(project_from_json(text),restored)
    assert ui.settings(restored)['enabled'] and 'igird_station36_enabled' not in restored
    assert restored['project_metadata'][ui.RECOMMENDATIONS]['changes'][0]['Previous']=='120'


def test_station_inputs_and_rendering_never_call_solver_or_change_production_hash():
    s=seed();rows=pd.DataFrame([bound_row()]);route=ap._beam_uls_strength_route_from_state(s,is_bridge=True,is_building=False)
    old=fw.fingerprints(s,rows,route=route);h=ui.fingerprint(s,rows,route=route)
    s['project_metadata'][ui.KEY]={'enabled':True}
    assert fw.fingerprints(s,rows,route=route)==old and ui.fingerprint(s,rows,route=route)!=h
    script="""
import streamlit as st
from concrete_pmm_pro.ui.igird_station36 import render_inputs
render_inputs(st.session_state)
"""
    with patch.object(tr,'solve',side_effect=AssertionError('Rendering cannot solve')):
        app=AppTest.from_string(script).run()
        assert not app.exception and not app.button
        app.toggle[0].set_value(True).run()
        assert not app.exception and app.session_state['project_metadata'][ui.KEY]['enabled']
