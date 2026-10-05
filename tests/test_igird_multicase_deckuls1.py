"""Independent source-vector and physical deck development acceptance tests."""
import copy
import math
from io import BytesIO
import pandas as pd
import pytest
from concrete_pmm_pro.io.girder_csi_import import prepare_csi_table,source_info,apply_source_gate,read_tables,append_errors
from concrete_pmm_pro.analysis.igird_crack_spacing import crack_spacing_source
from concrete_pmm_pro.analysis.igird_deck_development import station_bar_factors
from concrete_pmm_pro.analysis.igird_flexure_development import ordinary_bar_limits,SectionEquilibrium
from concrete_pmm_pro.ui import analysis_page as ap
from concrete_pmm_pro.ui import igird_shear_section as section
from test_igird_shearcomp1 import composite_state
from test_igird_uls5_shear_general_procedure import _demand,_route


def raw(step='Static'):
    return pd.DataFrame([{'Girder Distance':x,'StepType':step,'OutputCase':'ULS1','P':-5,'V2':50-x,
        'V3':2,'T':3+x,'M2':4,'M3':100*x} for x in (0,10,20)])


def deck_state():
    s=composite_state()
    s['section_parameters'].update({'deck_long_rebar_credit_positive_mn':True,'deck_long_rebar_fy_MPa':390.,
        'deck_long_rebar_Es_MPa':200000.,'deck_long_rebar_top_diameter_mm':16.,'deck_long_rebar_bottom_diameter_mm':20.,
        'deck_long_rebar_top_spacing_mm':150.,'deck_long_rebar_bottom_spacing_mm':200.,
        'deck_long_rebar_top_cover_mm':40.,'deck_long_rebar_bottom_cover_mm':40.,
        'deck_long_rebar_top_fy_MPa':390.,'deck_long_rebar_bottom_fy_MPa':490.,
        'deck_long_rebar_top_continuous_confirmed':True,'deck_long_rebar_bottom_continuous_confirmed':True})
    return s


@pytest.mark.parametrize('step,mode,confirmed,expected',[
    ('Static','static',True,'CONCURRENT'),('Step','static',True,'CONCURRENT'),
    ('Max','static',True,'ENVELOPE'),('Min','static',True,'ENVELOPE'),
    ('Max','correspondence',True,'CONCURRENT'),('Min','correspondence',True,'CONCURRENT'),
    ('Static','static',False,'UNVERIFIED'),('Max','unverified',True,'ENVELOPE')])
def test_source_gate_never_infers_concurrency_from_case_or_max(step,mode,confirmed,expected):
    imp=prepare_csi_table(raw(step),sheet_name='Left Exterior Girder',source_mode=mode,
        concurrency_confirmed=confirmed,evidence='CSI export setting documented')
    assert not imp.errors
    assert {source_info(r)['kind'] for _,r in imp.frame.iterrows()}=={expected}
    result=pd.DataFrame([{'Case':r['Case Name'],'Station x (m)':r['Station x (m)'],'Status':'PASS','Notes':''} for _,r in imp.frame.iterrows()])
    gated=apply_source_gate(result,imp.frame)
    assert set(gated.Status)==({'PASS'} if expected=='CONCURRENT' else {'REVIEW'})


def test_concurrent_declaration_requires_evidence_and_failure_is_retained():
    imp=prepare_csi_table(raw(),sheet_name='Left Girder',source_mode='static',concurrency_confirmed=True)
    assert source_info(imp.frame.iloc[0])['kind']=='UNVERIFIED'
    result=pd.DataFrame([{'Case':imp.frame.iloc[0]['Case Name'],'Station x (m)':0,'Status':'FAIL','Notes':''}])
    assert apply_source_gate(result,imp.frame).iloc[0].Status=='FAIL'


def test_multiple_files_and_steps_preserve_original_vectors_and_identity():
    combined=[]
    for file,sign in [('A.xlsx',1),('B.xlsx',-1)]:
        t=raw('Step');t['StepNum']=[1,1,1];t['M3']*=sign
        combined.append(prepare_csi_table(t,sheet_name='Left Girder',source_name=file).frame)
        t['StepNum']=2
        combined.append(prepare_csi_table(t,sheet_name='Left Girder',source_name=file).frame)
    allrows=pd.concat(combined,ignore_index=True)
    assert len(allrows)==12
    assert not append_errors(combined[0],pd.concat(combined[1:]),current_is_csi=True)
    assert allrows.Mux.tolist()==[0,1000,2000,0,1000,2000,0,-1000,-2000,0,-1000,-2000]
    assert len(allrows['Case Name'].unique())==4


def test_deck_layer_geometry_area_grades_and_construction_untouched():
    s=deck_state(); original=copy.deepcopy(s)
    prep,cs,_=ap._beam_uls_final_composite_preparation(s)
    assert prep.ready and len(prep.deck_rebars)==2
    assert [b.area_mm2 for b in prep.deck_rebars]==pytest.approx([math.pi*16**2/4*2400/150,math.pi*20**2/4*2400/200])
    assert [b.y_mm for b in prep.deck_rebars]==[1820-40-8,1600+40+10]
    assert {m.fy_MPa for m in prep.deck_rebar_materials}=={390,490}
    assert not original.get('rebars') and not s.get('rebars')
    assert len(cs['rebars'])==2


def test_deck_independent_cutoff_and_anchor_cannot_inherit_girder_anchors():
    s=deck_state();prep,cs,_=ap._beam_uls_final_composite_preparation(s)
    factors,ready,trace=station_bar_factors(s,cs['rebars'],cs['rebar_materials'],x_m=0,span_m=20,girder_factor=1.)
    assert ready and factors==[0.,0.]
    s['section_parameters']['deck_long_rebar_top_left_anchored']=True
    s['section_parameters']['deck_long_rebar_top_start_m']=2.
    f,_,_=station_bar_factors(s,cs['rebars'],cs['rebar_materials'],x_m=1,span_m=20,girder_factor=1.)
    assert f[0]==0.
    f,_,t=station_bar_factors(s,cs['rebars'],cs['rebar_materials'],x_m=2.1,span_m=20,girder_factor=1.)
    assert f[0]==1. and t[0]['db_mm']==16.
    # Bottom actual db=20 is used, never the equivalent smeared diameter.
    assert t[1]['db_mm']==20.


def test_unconfirmed_deck_excluded_from_vt_stiffness_not_implicitly_confirmed():
    s=deck_state();s['section_parameters']['deck_long_rebar_top_continuous_confirmed']=False
    prep,cs,_=ap._beam_uls_final_composite_preparation(s)
    f,ready,_=station_bar_factors(s,cs['rebars'],cs['rebar_materials'],x_m=10,span_m=20,girder_factor=1.)
    assert f[0]==0 and f[1]==1 and not ready


@pytest.mark.parametrize('face', ['top','bottom'])
def test_deck_ld_below_minimum_is_rejected(face):
    s=deck_state();s['section_parameters']['deck_long_rebar_'+face+'_ld_mm']=200.
    _,cs,_=ap._beam_uls_final_composite_preparation(s)
    with pytest.raises(ValueError,match='12-in'):
        station_bar_factors(s,cs['rebars'],cs['rebar_materials'],x_m=10,span_m=20,girder_factor=1.)


def test_deck_changes_depth_and_negative_section_equilibrium():
    s=deck_state();row=_demand(10).iloc[0].to_dict()
    d=section.depth_values(s,row=row,strength_route=_route())
    assert len(d['Deck development trace'])==2 and d['Depth source status']=='PASS'
    assert abs(d['Depth force residual N']) < 1e-5
    _,cs,_=ap._beam_uls_final_composite_preparation(s)
    inp,_=ap._beam_uls_flexure_analysis_input_for_station(cs,row=row,strength_route=_route(),capacity_direction=-1.,prestress_force_stage='final')
    context=SectionEquilibrium(inp,-1.)
    result=context.solve(0.)
    assert result['phiMn_Nmm'] > 0
    factors,_=ordinary_bar_limits(context,x_m=10,span_m=20,settings={},params=cs['section_parameters'],girder_fc_mpa=45.)
    assert factors==[1,1]


def test_invalid_overlapping_deck_layers_block_preparation():
    s=deck_state();s['section_parameters']['deck_long_rebar_top_cover_mm']=170.
    prep,cs,_=ap._beam_uls_final_composite_preparation(s)
    assert not prep.ready and cs is None


@pytest.mark.parametrize('dv,ag',[(100,20),(1500,20),(4000,10)])
def test_source_unit_crack_spacing_matches_independent_inches(dv,ag):
    s={'section_parameters':{'shear_aggregate_confirmed':True,'shear_max_aggregate_mm':ag}}
    out=crack_spacing_source(s,dv_mm=dv)
    expected=min(max((dv/25.4)*1.38/(ag/25.4+.63),12),80)*25.4
    assert out['sxe mm']==pytest.approx(expected)
    s['section_parameters']['shear_verified_sx_mm']=500
    assert not crack_spacing_source(s,dv_mm=dv)['ready']


def test_below_minimum_can_calculate_numeric_capacity_but_detailing_still_fails():
    s=composite_state();s['section_parameters'].update(shear_aggregate_confirmed=True,shear_max_aggregate_mm=20.)
    # Actual test fixture uses DB12; huge spacing makes Av/s < minimum.
    key=ap.SHEAR_LAYOUT_STATE_KEY if hasattr(ap,'SHEAR_LAYOUT_STATE_KEY') else 'beam_girder_uls_shear_layout_table'
    from concrete_pmm_pro.ui import analysis_page
    for name,val in s.items():
        if isinstance(val,pd.DataFrame) and 'Spacing_mm' in val:
            val.loc[:,'Spacing_mm']=2000.
    out=ap._beam_uls_shear_result_for_row(s,_demand(10).iloc[0].to_dict(),strength_route=_route())
    assert math.isfinite(out['φVn kN'])
    assert out['Detailing status']=='FAIL' and out['Status']=='FAIL'


def test_json_roundtrip_keeps_deck_and_source_but_old_layer_widgets_cannot_leak():
    from concrete_pmm_pro.io.project_io import (project_from_session_state,project_to_json,project_from_json,apply_project_to_session_state)
    from concrete_pmm_pro.core.analysis import AnalysisModeSettings
    s=deck_state()
    s.update(project_name='Deck source QA',section_preset_key='parametric_i_girder',analysis_mode_settings=AnalysisModeSettings(member_type='beam_girder'))
    s['beam_uls_loads_table']=prepare_csi_table(raw(),sheet_name='Left Girder',source_name='ULS.xlsx',
        source_mode='static',concurrency_confirmed=True,evidence='QA factored static').frame
    project=project_from_session_state(s)
    restored={}
    apply_project_to_session_state(project_from_json(project_to_json(project)),restored)
    assert restored['section_parameters']['deck_long_rebar_top_fy_MPa']==390
    assert restored['section_parameters']['deck_long_rebar_bottom_fy_MPa']==490
    assert source_info(restored['beam_uls_loads_table'].iloc[0])['kind']=='CONCURRENT'
    restored['parametric_i_girder_deck_long_rebar_top_left_anchored']=True
    project.section_parameters={}
    apply_project_to_session_state(project,restored)
    assert 'parametric_i_girder_deck_long_rebar_top_left_anchored' not in restored


def test_deck_changes_stale_all_final_uls_caches_but_not_source_forces():
    s=deck_state();d=_demand(10)
    before={check:ap._beam_uls_check_input_hash(s,d,strength_route=_route(),check_name=check) for check in ('Shear','Torsion','Shear + Torsion')}
    s['section_parameters']['deck_long_rebar_top_spacing_mm']=100.
    after={check:ap._beam_uls_check_input_hash(s,d,strength_route=_route(),check_name=check) for check in before}
    assert all(before[k]!=after[k] for k in before)


def test_support_inside_face_without_cl_still_classifies_midspan_correctly():
    from concrete_pmm_pro.analysis.igird_shear_support import station_region,SETTINGS_KEY
    state={SETTINGS_KEY:{'locations_confirmed':True,'offset_reference':'inside_face','left_offset_m':.4,'right_offset_m':.4}}
    assert station_region(state,x_m=10,span_m=20,h_mm=1750)['Support region']=='SECTIONAL REGION'
    assert station_region(state,x_m=0,span_m=20,h_mm=1750)['Support region status']=='REVIEW'


def test_chart_endpoint_sharing_never_crosses_uploaded_files():
    from concrete_pmm_pro.visualization.igird_uls_chart_display import native_csi_diagram_rows
    a=prepare_csi_table(raw('Max'),sheet_name='Left Girder',source_name='A.xlsx').frame
    b=prepare_csi_table(raw('Max'),sheet_name='Left Girder',source_name='B.xlsx').frame
    only_middle=a.loc[a['Station x (m)'].eq(10)].copy()
    context=pd.concat([only_middle,b],ignore_index=True)
    drawn=native_csi_diagram_rows(only_middle,member_length_m=20,source_context_df=context)
    assert drawn['Station x (m)'].tolist()==[10]


def test_negative_combined_uses_deck_in_both_longitudinal_force_and_strain():
    from test_igird_uls7_concurrent_vt import ready_state,check,physical
    s=ready_state();s['section_parameters'].update(deck_state()['section_parameters'])
    r=physical(check(s,mux=-100.,vu=100.,tu=200.))
    deck_as=math.pi*16**2/4*2400/150+math.pi*20**2/4*2400/200
    girder_as=2*math.pi*20**2/4
    expected_force=2*math.pi*20**2/4*390+math.pi*16**2/4*2400/150*390+math.pi*20**2/4*2400/200*490
    assert r['As developed tension mm2']==pytest.approx(girder_as+deck_as)
    assert r['As fy kN']==pytest.approx(expected_force/1000)
    assert r['εs denominator N']==pytest.approx((girder_as+deck_as)*200000)
    assert r['Section basis']=='FINAL COMPOSITE'
    assert r['Prestress dominance status']=='FAIL'


def test_untagged_app_upload_needs_source_evidence_and_keeps_existing_bounds():
    from concrete_pmm_pro.io.girder_csi_import import tag_app_source
    native=prepare_csi_table(raw('Max'),sheet_name='Left Girder').frame
    declared=tag_app_source(native,source_name='copy.csv',sheet_name='CSV',source_mode='correspondence',
        concurrency_confirmed=True,evidence='QA override attempt')
    assert source_info(declared.iloc[0])['kind']=='ENVELOPE'
    native['Note']='User annotation'
    unverified=tag_app_source(native,source_name='copy.csv',sheet_name='CSV')
    assert source_info(unverified.iloc[0])['kind']=='ENVELOPE'
    assert 'User annotation' in unverified.iloc[0]['Note']
