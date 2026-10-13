"""Independent geometry, equilibrium, load-preservation and acceptance tests."""
from copy import deepcopy
import math
import pandas as pd
import pytest
from concrete_pmm_pro.analysis import igird_end_sections as ends
from concrete_pmm_pro.geometry.generators import parametric_i_girder
from concrete_pmm_pro.geometry.summary import to_shapely_polygon
from concrete_pmm_pro.geometry.torsion_hoop import derive_closed_hoop_centerline
from concrete_pmm_pro.ui import analysis_page as ap,igird_station_section as station,igird_shear_section
from test_igird_uls7_concurrent_vt import ready_state
from test_igird_uls6_torsion_general_procedure import _route,_demand

def model(**settings):
    state=ready_state()
    state['section_geometry']=parametric_i_girder(B1_mm=600.,B2_mm=600.,D1_mm=1500.,D2_mm=150.,D3_mm=150.,D5_mm=250.,D6_mm=150.,T1_mm=200.,T2_mm=200.,C1_mm=0.)
    state['rebars']=[b.model_copy(update={'y_mm':-650. if b.y_mm<800 else 650.}) for b in state['rebars']]
    state['section_parameters'].update({'B1_mm':600.,'Be_mm':1200.,'Tslab_mm':350.,ends.SETTINGS_KEY:{'enabled':True,
        'left_solid_m':1.5,'right_solid_m':1.5,'left_taper_m':.25,'right_taper_m':.25,'width_mm':600.,
        'hoop_confirmed':True,'d_region_confirmed':True,'load_reference_confirmed':True,**settings}})
    state[ap._IGIRDER_TORSION_ZONE_SETTINGS_KEY]=[{'Zone':'Full span','Use for Torsion':True,'Closed Loop':True,'135° Hook':True}]
    return state
def demand(x,**actions):
    return _demand(x=x,mux=actions.pop('mux',500.),vu=actions.pop('vu',200.),tu=actions.pop('tu',200.),**actions).iloc[0].to_dict()

@pytest.mark.parametrize('x,region,width',[(0,'LEFT SOLID END',600),(1.5,'LEFT SOLID END',600),(1.625,'LEFT TAPER',400),
    (1.75,'I SECTION',200),(10,'I SECTION',200),(18.375,'RIGHT TAPER',400),(18.5,'RIGHT SOLID END',600),(20,'RIGHT SOLID END',600)])
def test_real_polygon_web_width_and_region(x,region,width):
    state=model();local=station.at_station(state,x)
    assert local[station.TRACE_KEY]['Section region']==region
    assert ap._beam_uls_web_width_mm(local['section_geometry'])[0]==pytest.approx(width)
    assert to_shapely_polygon(local['section_geometry']).covers(to_shapely_polygon(state['section_geometry']))

def test_solid_rectangle_ao_and_actual_hoop_match_independent_equations():
    geom=station.at_station(model(),1)['section_geometry'];hoop=derive_closed_hoop_centerline(geom,clear_cover_mm=40,bar_diameter_mm=12)
    assert hoop.ph_mm==pytest.approx(2*((600-92)+(1500-92)))
    r=ap._beam_uls_igird_aashto_solid_torsion_geometry(geom,settings={'closed_loop_confirmed':True,'ph_mm':hoop.ph_mm})
    be=600*1500/(2*(600+1500))
    assert r['Acp mm2']==pytest.approx(900000)
    assert r['Ao mm2']==pytest.approx((600-be)*(1500-be))
    assert r['Ao mm2']!=pytest.approx(.85*((600-92)*(1500-92)))

def test_taper_area_is_linear_and_optional_chamfer_is_real_geometry():
    state=model();p=[to_shapely_polygon(station.at_station(state,x)['section_geometry']) for x in (1.5,1.625,1.75)]
    assert p[1].area==pytest.approx((p[0].area+p[2].area)/2)
    assert to_shapely_polygon(station.at_station(model(chamfer_mm=20),1)['section_geometry']).area==pytest.approx(900000-4*.5*20**2)

def test_asymmetric_ends_and_abrupt_boundary_use_narrower_section():
    state=model(left_solid_m=2,right_solid_m=.5,left_taper_m=0,right_taper_m=.5)
    assert station.at_station(state,1.999)[station.TRACE_KEY]['Solid fill fraction']==1
    assert station.at_station(state,2)[station.TRACE_KEY]['Section region']=='I SECTION'
    assert station.at_station(state,19.25)[station.TRACE_KEY]['Section region']=='RIGHT TAPER'

@pytest.mark.parametrize('settings',[{'left_solid_m':10,'right_solid_m':10},{'width_mm':199},{'left_taper_m':-1},
    {'right_end_x_m':21},{'left_end_x_m':20},{'chamfer_mm':300},{'left_solid_m':float('nan')}])
def test_invalid_inputs_block_capacity_instead_of_falling_back_to_i(settings):
    r=ap._beam_uls_shear_result_for_row(model(**settings),demand(1),strength_route=_route())
    assert r['Status']=='REVIEW' and r['Section region']=='UNAVAILABLE' and math.isnan(r['φVn kN'])

def test_physical_cut_ends_keep_load_axis_and_strand_sleeve_origin():
    state=model(left_end_x_m=.025,right_end_x_m=19.975)
    assert ends.development_coordinates(state,1.025,20)==pytest.approx((1,19.95))
    f=station.strand_families(state,state['girder_strand_layout_table'],y_min_mm=-750,span_m=20,stage='final',settings={})[0]
    assert f.left_bond_start_m==pytest.approx(.025) and f.right_bond_end_m==pytest.approx(19.975)
    assert f.bonded_distance_mm(1.025)==pytest.approx(1000)
    r=ap._beam_uls_shear_result_for_row(state,demand(0),strength_route=_route())
    assert r['Section region']=='UNAVAILABLE' and math.isnan(r['φVn kN'])

def test_station_shear_and_torsion_use_local_geometry_and_code_equations():
    state=model();row=demand(1);before=deepcopy(state)
    s=ap._beam_uls_shear_result_for_row(state,row,strength_route=_route());t=ap._beam_uls_igird_torsion_result_for_row(state,row,strength_route=_route())
    assert s['bw mm']==600 and s['φVn kN']>0 and t['φTn kN-m']>0
    ksi=6.894757293168361
    vc=.0316*s['β']*math.sqrt(45/ksi)*ksi*600*s['dv mm']/1000
    vs=s['Av/s mm2/mm']*s['fy MPa']*s['dv mm']*s['cotθ']/1000;limit=.25*45*600*s['dv mm']/1000
    assert s['φVn kN']==pytest.approx(s['φ']*min(vc+vs,limit))
    assert t['Ao mm2']==pytest.approx((600-900000/4200)*(1500-900000/4200))
    assert t['φTn kN-m']==pytest.approx(2*t['Ao mm2']*t['At/s mm2/mm']*t['fy MPa']*t['cotθ']*t['φ']/1e6)
    assert row==demand(1) and state['section_geometry'].model_dump()==before['section_geometry'].model_dump()
    assert igird_shear_section.RUNTIME_KEY not in state

def test_composite_depth_contexts_are_isolated_between_end_taper_and_body():
    state=model();state[igird_shear_section.RUNTIME_KEY]={};values=[]
    for x in (1.25,1.625,10.,1.25):
        d=igird_shear_section.depth_values(state,row=demand(x),strength_route=_route());assert d['h mm']==1850 and d['dv_mm']>0;values.append(d)
    assert values[0]==values[3]
    caches=state[igird_shear_section.RUNTIME_KEY]['endsection_runtime'];assert len(caches)==3
    assert sorted(ap._beam_uls_web_width_mm(c['section']['web_geometry'])[0] for c in caches.values())==[200,400,600]

def test_flexure_rebuilds_section_context_by_station_and_preserves_source_actions():
    state=model();source=pd.DataFrame([demand(x,mux=800) for x in (1.25,1.625,10,18.75)]);before=source.copy(deep=True)
    _,composite,_=ap._beam_uls_final_composite_preparation(state)
    frame,_=ap._beam_uls_developed_igird_flexure_dataframe(composite,source,strength_route=_route(),prestress_force_stage='final')
    assert frame['Section region'].tolist()==['LEFT SOLID END','LEFT TAPER','I SECTION','RIGHT SOLID END']
    assert frame['Capacity kN-m'].notna().all() and frame.iloc[0]['Moment reference y mm']!=frame.iloc[2]['Moment reference y mm']
    pd.testing.assert_frame_equal(source,before);assert state['section_geometry'].metadata.get('end_section_region') is None

def test_profile_disabled_retains_exact_existing_solver_outputs():
    state=model(enabled=False);old=deepcopy(state);old['section_parameters'].pop(ends.SETTINGS_KEY)
    for check in (ap._beam_uls_shear_check_dataframe,ap._beam_uls_torsion_check_dataframe,ap._beam_uls_combined_vt_check_dataframe):
        source=pd.DataFrame([demand(10)]);pd.testing.assert_frame_equal(check(state,source,strength_route=_route()),check(old,source,strength_route=_route()))

def test_missing_head_confirmation_withholds_pass_but_preserves_fail():
    local=station.at_station(model(hoop_confirmed=False,d_region_confirmed=False),1)
    for status,expected in (('PASS','REVIEW'),('FAIL','FAIL')):
        r=station.annotate({'Status':status,'φTn kN-m':100},local,check_name='Torsion')
        assert r['Status']==expected and r['φTn kN-m']==100 and 'D-region' in r['Notes'] and 'closed hoop' in r['Notes']

def test_building_and_column_workflows_do_not_adopt_bridge_end_profile():
    from concrete_pmm_pro.core.analysis import AnalysisModeSettings
    state=model()
    for member in ('building_beam_girder','column_pier_pmm','portal_frame_crossbeam'):
        state['analysis_mode_settings']=AnalysisModeSettings(member_type=member)
        assert not ends.enabled(state) and station.at_station(state,1) is state

def test_saved_graph_region_and_boundaries_are_read_only():
    from unittest.mock import patch
    from concrete_pmm_pro.ui.igird_combined_vt import calculation_trace
    state=model();source=pd.DataFrame([demand(x) for x in (1.25,1.625,10)])
    from concrete_pmm_pro.io.girder_csi_import import tag_app_source
    source=tag_app_source(source,source_name='ENDSECTION18 hypothetical static QA',sheet_name='QA',
        source_mode='static',concurrency_confirmed=True,
        evidence='Analytically specified simultaneous static actions for the geometry-plot test')
    frame=ap._beam_uls_combined_vt_check_dataframe(state,source,strength_route=_route());before=frame.copy(deep=True)
    with patch.object(station,'at_station',side_effect=AssertionError('Drawing saved results must not solve')):
        fig=ap._make_beam_uls_combined_vt_utilization_figure(frame,code_label='AASHTO LRFD',member_length_m=20);trace=calculation_trace(frame.iloc[0].to_dict())
    assert fig.layout.meta['station_geometry']==ends.RESULT_VERSION
    assert {float(s.x0) for s in fig.layout.shapes if s.line.dash=='dot'}=={1.5,1.75,18.25,18.5}
    assert any('Section=%{customdata[3]}' in str(t.hovertemplate) for t in fig.data) and trace['Step'].eq('Local precast geometry').any()
    pd.testing.assert_frame_equal(frame,before)

def test_hash_and_project_roundtrip_include_inputs_but_not_station_runtime():
    from concrete_pmm_pro.io.project_io import project_from_session_state,project_to_json,project_from_json,apply_project_to_session_state
    state=model();source=pd.DataFrame([demand(1)]);before=ap._beam_uls_check_input_hash(state,source,strength_route=_route(),check_name='Shear')
    state['section_parameters'][ends.SETTINGS_KEY]['left_solid_m']=2
    assert ap._beam_uls_check_input_hash(state,source,strength_route=_route(),check_name='Shear')!=before
    text=project_to_json(project_from_session_state(state));restored={};apply_project_to_session_state(project_from_json(text),restored)
    assert restored['section_parameters'][ends.SETTINGS_KEY]==state['section_parameters'][ends.SETTINGS_KEY]
    assert station.LOCAL_X not in text and igird_shear_section.RUNTIME_KEY not in text

def test_coarse_load_grid_samples_actual_taper_only_for_capacity_diagram():
    state=model();source=pd.DataFrame([demand(x) for x in (0,1,2,10,18,19,20)]);before=source.copy(deep=True)
    expanded=station.geometry_diagram_demands(state,source)
    assert {1.5,1.625,1.75,18.25,18.375,18.5}.issubset(set(expanded['Station x (m)']))
    assert expanded.loc[expanded['Station x (m)'].eq(1.625),'Note'].str.contains('diagram only').all()
    rows=ap._beam_uls_shear_check_dataframe(state,source,strength_route=_route())
    diagram=ap._beam_uls_igird_shear_diagram_capacity_dataframe(state,source,rows,strength_route=_route());r=diagram[diagram['Governing x'].eq('1.625 m')].iloc[0]
    assert r['bw mm']==400 and r['Diagram only'] and math.isnan(r['D/C value']) and 'Interpolated actions' in r['Diagram source type']
    assert set(rows['Governing x'])==set(ap._format_beam_uls_x(x) for x in before['Station x (m)']);pd.testing.assert_frame_equal(source,before)

def test_conflicting_same_case_force_vectors_never_create_geometry_samples():
    source=pd.DataFrame([demand(1,vu=100),demand(1,vu=200),demand(2)])
    pd.testing.assert_frame_equal(station.geometry_diagram_demands(model(),source),source)
