"""Independent mechanics, sufficient minimum proof and native FE cut sampling."""
from copy import deepcopy
from types import SimpleNamespace
from unittest.mock import patch
import numpy as np
import pandas as pd
import pytest
from concrete_pmm_pro.analysis import slab_aashto63 as code
from concrete_pmm_pro.analysis import slab_aashto62 as old
from concrete_pmm_pro.analysis.slab_aashto63_sections import ACTIONS,NATIVE,support_geometry,in_support,sample_faces
from concrete_pmm_pro.analysis.slab_connections59 import INCLUDED,REASON
from concrete_pmm_pro.analysis.slab_shell56 import GROUPS
from concrete_pmm_pro.io.slab_shell_import import BANK_KEY
from concrete_pmm_pro.visualization.slab_shell56 import element_envelope
from test_slab_shell56 import steel,model_state
from test_slab_connections59 import connected_state


def vector(**changes):
    row={'Thickness (mm)':350.,'Nx':0.,'Ny':0.,'Nxy':0.,'Mx':10.,'My':-10.,'Mxy':0.,'Vx':20.,'Vy':15.}
    row.update(changes)
    return pd.DataFrame([row])


def test_fixed_N_capacity_matches_independent_two_yielded_mats_hand_solution():
    s=steel();h=350.
    a=2*1000*390/(.85*35*1000)
    mr=.9*2*1000*390*(h/2-a/2)/1e6
    r=code.fixed_axial_resistance(np.array([h]),np.array([0.]),s,0,1)[0]
    assert r[0]==pytest.approx(mr,rel=.001)
    assert r[3]==pytest.approx(-mr,rel=.001)
    assert r[1]==pytest.approx(.9) and r[4]==pytest.approx(.9)


def test_fixed_N_does_not_reuse_radial_utilization_as_moment_capacity():
    s=steel();h=np.array([350.]);n=np.array([300.]);m=np.array([20.])
    radial=old.nm_ratios(h,n,m,s,0,1)[0,0]
    fixed=code.fixed_axial_resistance(h,n,s,0,1)[0,0]
    assert not np.isclose(fixed,20/radial,rtol=.01)
    check=old.nm_ratios(h,n,np.array([fixed]),s,0,1)[0,0]
    assert check==pytest.approx(1.,rel=.002)


def test_flexural_minimum_uses_133Mu_and_both_mats_at_same_Nu():
    s=steel();h=np.array([350.]);n=np.array([-200.]);m=np.array([-20.])
    capacity=code.fixed_axial_resistance(h,n,s,0,1)
    r=code.flexural_minimum(h,n,m,s,0,1,capacity)
    assert r['minimum required upper bound (kN·m/m)'][0]==pytest.approx(1.33*20)
    assert r['minimum Mr (kN·m/m)'][0]==pytest.approx(-capacity[0,3])
    assert r['flexural minimum status'][0]=='PASS'
    assert r['minimum phi'][0]==capacity[0,4]


def test_mcr_upper_bound_uses_US_modulus_of_rupture_and_gamma3_one():
    s=steel();h=np.array([350.]);n=np.array([0.]);m=np.array([120.])
    fr=.24*np.sqrt(35/6.894757293)
    sc=(1000/25.4)*(350/25.4)**2/6
    mcr=1.6*fr*sc*4.4482216152605*.0254
    r=code.flexural_minimum(h,n,m,s,0,1,code.fixed_axial_resistance(h,n,s,0,1))
    assert r['Mcr upper bound (kN·m/m)'][0]==pytest.approx(mcr,rel=1e-9)
    assert r['minimum required upper bound (kN·m/m)'][0]==pytest.approx(min(1.33*120,mcr))


def test_unknown_gamma3_cannot_create_a_false_FAIL_or_false_PASS():
    s=steel(area=100.)
    h=np.array([350.]);n=np.array([0.]);m=np.array([1000.])
    r=code.flexural_minimum(h,n,m,s,0,1,code.fixed_axial_resistance(h,n,s,0,1))
    assert r['minimum trial D/C'][0]>1
    assert r['flexural minimum status'][0]=='REVIEW'
    assert np.isnan(r['flexural minimum D/C'][0])


def test_compression_controlled_minimum_is_not_required():
    s=steel();h=np.array([350.]);n=np.array([-6500.]);m=np.array([10.])
    c=code.fixed_axial_resistance(h,n,s,0,1)
    assert c[0,2]<.002
    r=code.flexural_minimum(h,n,m,s,0,1,c)
    assert r['flexural minimum status'][0]=='NOT REQUIRED'
    assert r['flexural minimum D/C'][0]==0


def test_tie_uses_transition_phi_instead_of_unconditional_point_nine():
    s=steel();h=np.array([350.]);n=np.array([-5000.]);m=np.array([400.]);v=np.array([500.])
    r=code.directional_shear(h,n,m,v,s,0,1)
    phi=r['tie phi_f'][0]
    assert phi<.9
    expected=max(0,400000/(phi*r['dv (mm)'][0])-5000/(2*.75)+500/.9)
    assert r['tie required (kN/m)'][0]==pytest.approx(expected)


def test_development_uses_casting_position_cover_spacing_and_epoxy_upper_bound():
    s=steel();ld,rl=code.development_reference(np.array([500.]),s)
    basic=2.4*16*(390/6.894757293)/np.sqrt(35/6.894757293)
    np.testing.assert_allclose(rl[0],[1.3,1.,1.3,1.])
    np.testing.assert_allclose(ld[0],basic*np.array([1.56,1.2,1.7,1.5]))
    short=steel();short.diameter[:]=6.;short.fy[:]=100.
    assert code.development_reference(np.array([350.]),short)[0].min()>=304.8-1e-9


def test_temperature_and_spacing_are_checked_in_each_face_and_direction():
    s=steel();s.area[:]=[500.,1000.,1500.,2000.];s.spacing[:]=[200.,150.,125.,100.]
    r=code.section_checks(vector(),s).iloc[0]
    temperature=old.inputs.temperature_minimum(np.array([350.]),s.fy)[0]
    for i,group in enumerate(GROUPS):
        assert r[group+' temperature D/C']==pytest.approx(temperature[i]/s.area[i])
        assert r[group+' spacing D/C']==pytest.approx(s.spacing[i]/457.2)
    assert r['Longitudinal tension mat']=='Bottom' and r['Transverse tension mat']=='Top'
    assert r['Longitudinal As tension (mm²/m)']==1000.
    assert r['Transverse As tension (mm²/m)']==1500.


def test_mesh_not_added_as_shear_steel_even_if_both_mats_are_increased():
    s=steel();a=code.section_checks(vector(),s)
    more=deepcopy(s);more.area[:]*=3
    b=code.section_checks(vector(),more)
    assert a['Longitudinal Vn (kN/m)'].iloc[0]==b['Longitudinal Vn (kN/m)'].iloc[0]
    assert a['Transverse Vn (kN/m)'].iloc[0]==b['Transverse Vn (kN/m)'].iloc[0]


def cut_fixture():
    xy=np.array([[0.,0.],[1.,0.],[1.,1.],[0.,1.]])
    corners=pd.DataFrame({'Area':['A']*4,'AreaElem':['A-1']*4,'Joint':['a','b','c','d'],
        'X (m)':xy[:,0],'Y (m)':xy[:,1],'Z (m)':np.zeros(4),'Thickness (mm)':350+20*xy[:,1]})
    geometry=SimpleNamespace(corners=corners,parent_axes={'A':{'long':[1.,0.,0.]}})
    support={'Support':'G1','a':np.array([0.,0.]),'b':np.array([1.,0.]),
        'unit':np.array([1.,0.]),'normal':np.array([0.,1.]),'half_width':.3}
    rows=[]
    for case,offset in [('U1A',0.),('U2A',100.)]:
        f=corners.copy();f['OutputCase']=case;f['StepType']='Max';f['StepNum']=1.
        for j,col in enumerate([*ACTIONS,*NATIVE]):f[col]=offset+j+2*xy[:,0]+4*xy[:,1]
        f[INCLUDED]=True;f[REASON]='';rows.append(f)
    return pd.concat(rows,ignore_index=True),geometry,[support]


def test_cut_recovers_same_case_all_eight_affine_forces_at_actual_face():
    rows,geometry,supports=cut_fixture()
    face,recipes=sample_faces(rows,geometry,supports)
    assert len(face)==4 and len(recipes)==2
    assert face[INCLUDED].all() and np.allclose(face['Y (m)'],.3)
    for _,r in face.iterrows():
        offset=100 if r.OutputCase=='U2A' else 0
        for j,col in enumerate([*ACTIONS,*NATIVE]):assert r[col]==pytest.approx(offset+j+2*r['X (m)']+1.2)
        assert r['Thickness (mm)']==pytest.approx(356.)
    assert set(face['Source joint 1'])|set(face['Source joint 2'])==set('abcd')


def test_cut_does_not_average_across_elements_or_load_cases():
    rows,geometry,supports=cut_fixture()
    second=rows.copy();second.AreaElem='A-2';second[ACTIONS]=second[ACTIONS]+500
    corners=geometry.corners.copy();corners.AreaElem='A-2'
    geometry.corners=pd.concat((geometry.corners,corners),ignore_index=True)
    faces,_=sample_faces(pd.concat((rows,second),ignore_index=True),geometry,supports)
    l=faces.loc[(faces.AreaElem=='A-1')&faces.OutputCase.eq('U1A')].sort_values('X (m)')
    r=faces.loc[(faces.AreaElem=='A-2')&faces.OutputCase.eq('U1A')].sort_values('X (m)')
    np.testing.assert_allclose(r[ACTIONS].to_numpy()-l[ACTIONS].to_numpy(),500.)


def test_cut_cannot_use_previously_excluded_corner_to_reconstruct_design_force():
    rows,geometry,supports=cut_fixture()
    rows.loc[rows.Joint.eq('a'),INCLUDED]=False
    first,_=sample_faces(rows,geometry,supports)
    rows.loc[~rows[INCLUDED],ACTIONS]=1e12
    second,_=sample_faces(rows,geometry,supports)
    assert second.loc[second['X (m)'].eq(0),INCLUDED].eq(False).all()
    assert second.loc[second['X (m)'].eq(0),'Source incomplete'].all()
    pd.testing.assert_frame_equal(first.loc[first[INCLUDED]].reset_index(drop=True),second.loc[second[INCLUDED]].reset_index(drop=True))


def test_missing_case_corner_marks_only_affected_face_samples_unavailable():
    rows,geometry,supports=cut_fixture()
    rows=rows.loc[~(rows.Joint.eq('a')&rows.OutputCase.eq('U2A'))].copy()
    faces,_=sample_faces(rows,geometry,supports)
    bad=faces.loc[~faces[INCLUDED]]
    assert len(bad)==1 and bad.OutputCase.iloc[0]=='U2A'
    assert bad['Design exclusion'].iloc[0]=='Missing source corner/case'
    assert bad[ACTIONS].isna().all().all()


def test_footprint_is_geometric_finite_and_not_a_source_exclusion():
    _,_,supports=cut_fixture()
    points=np.array([[.5,.1],[.5,.3],[.5,.31],[1.1,.1]])
    assert in_support(points,supports).tolist()==[True,False,False,False]
    connections={'top_flange_mm':600.,'lines':pd.DataFrame([
        {'Connection':'Girder','ID':'G','X1 (m)':0.,'Y1 (m)':0.,'X2 (m)':1.,'Y2 (m)':0.},
        {'Connection':'Diaphragm','ID':'D','X1 (m)':0.,'Y1 (m)':0.,'X2 (m)':0.,'Y2 (m)':1.}])}
    assert len(support_geometry(connections))==1
    connections['top_flange_mm']=None
    assert support_geometry(connections)==[]


def test_new_calculation_retains_native_keys_forces_and_agreed_masks():
    state=connected_state();before=state[BANK_KEY].tables['forces'].copy(deep=True)
    baseline=old.calculate(state);result=code.calculate(state)
    pd.testing.assert_frame_equal(before,state[BANK_KEY].tables['forces'])
    cols=['Area','AreaElem','Joint','OutputCase','StepType',*NATIVE,INCLUDED,REASON]
    pd.testing.assert_frame_equal(baseline['rows'][cols],result['rows'][cols])
    assert result['design_rows']==baseline['design_rows'] and len(result['reinforcement_summary'])==4
    assert result['status']=='REVIEW REQUIRED'
    assert result['code_coverage'].loc[lambda f:f.Check.eq('Two-way / punching shear'),'Coverage'].iloc[0]=='REVIEW'
    assert result['rows'].loc[~result['rows'][INCLUDED],[c for c,_ in code.VIEWS.values()]].isna().all().all()


def test_support_faces_cannot_hide_a_missing_native_source_in_a_complete_map():
    state=connected_state();state[BANK_KEY].tables['forces']=state[BANK_KEY].tables['forces'].iloc[1:].copy()
    result=code.calculate(state)
    selected=element_envelope(code.map_adapter(result,'Shear · transverse'))
    assert result['incomplete'] and selected['Map incomplete'].any()


def test_no_research_solver_and_invalidation_on_existing_mat_change():
    from concrete_pmm_pro.analysis import slab_shell56 as research
    state=model_state()
    with patch.object(research,'calculate',side_effect=AssertionError('research must be explicit')):result=code.calculate(state)
    state[code.RESULT_KEY]=result
    assert code.current(state) is result and old.current(state) is None
    state['section_parameters']['deck_long_rebar_bottom_spacing_mm']=200.
    assert code.current(state) is None


def test_diaphragm_faces_use_native_thickness_and_keep_finite_plan_extent():
    _,_,supports=cut_fixture()
    connections={'top_flange_mm':None,'lines':pd.DataFrame([
        {'Connection':'Diaphragm','ID':'D1, D2','X1 (m)':.5,'Y1 (m)':0.,'X2 (m)':.5,'Y2 (m)':1.}])}
    package=SimpleNamespace(tables={'thickness':pd.DataFrame([
        {'Area':area,'Thick1':.4,'Thick2':.4,'Thick3':.4,'Thick4':.4} for area in ['D1','D2']])})
    s=support_geometry(connections,package)
    assert len(s)==1 and s[0]['Direction']=='Longitudinal' and s[0]['half_width']==.2
    assert in_support(np.array([[.4,.5],[.7,.5],[.4,1.1]]),s).tolist()==[True,False,False]
    rows,geometry,_=cut_fixture()
    faces,_=sample_faces(rows,geometry,s)
    assert len(faces)==8 and faces.Direction.eq('Longitudinal').all()
    np.testing.assert_allclose(sorted(faces['X (m)'].round(10).unique()),[.3,.7])
    # A variable / ambiguous merged width must remain unresolved.
    package.tables['thickness'].loc[1,'Thick3']=.5
    assert support_geometry(connections,package)==[]


def test_unavailable_in_scope_face_is_REVIEW_and_cannot_disappear_behind_PASS():
    result=code.calculate(connected_state())
    faces=result['support_faces']
    assert len(faces) and faces['Target in accepted scope'].any()
    assert not faces.loc[faces['Target in accepted scope'],INCLUDED].any()
    summary=result['summary'].set_index('Check').loc['Shear · transverse']
    assert summary.Status=='REVIEW' and summary['Review nodes']>0
    selected=element_envelope(code.map_adapter(result,'Shear · transverse'))
    assert selected['Map unresolved'].any()
    assert result['support_faces'][INCLUDED].eq(False).all()


def test_temperature_spacing_ceiling_also_applies_to_very_thick_slab_components():
    s=steel();s.spacing[:]=400.
    r=code.section_checks(vector(**{'Thickness (mm)':1000.}),s).iloc[0]
    assert r['Bar spacing D/C']==pytest.approx(400/304.8)
    assert all(r[g+' spacing limit (mm)']==pytest.approx(304.8) for g in GROUPS)
