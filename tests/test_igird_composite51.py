"""Actual hook-plane geometry and exact Calculate-only reuse regressions."""
from copy import deepcopy
from dataclasses import replace
import math
from unittest.mock import patch
import pytest

from concrete_pmm_pro.analysis import igird_composite_steel45 as engine
from concrete_pmm_pro.analysis.igird_u_anchorage51 import evaluate
from concrete_pmm_pro.ui.igird_combined_vt import nominal_fps_key
from concrete_pmm_pro.ui.igird_u_anchorage51 import plane_frame, make_figure
from test_igird_composite_steel45 import supplies
from test_igird_uls7_concurrent_vt import ready_state
from concrete_pmm_pro.core.analysis import AnalysisInput


def inputs():
    return dict(detail={'slab_ldh_available_mm':200.,'hook_inside_bend_mm':72.,
        'slab_transverse_mesh':{f:{'Diameter_mm':16.,'Clear_cover_mm':40.} for f in ('top','bottom')}},
        params={**{f'deck_long_rebar_{f}_diameter_mm':16. for f in ('top','bottom')},
            **{f'deck_long_rebar_{f}_cover_mm':56. for f in ('top','bottom')}},
        slab_thickness_mm=350.,slab_bottom_y_mm=750.,db_mm=12.,spacing_mm=200.,
        anchorage={'hook_required_mm':190.,'status':'DIMENSION CHECKS MET'},
        inventory=[{'component':'slab','y_mm':814.},{'component':'slab','y_mm':1036.}],
        calculation={'supplies':{'u_leg_N_per_mm':200.},
            'VT':{'ready':True,'U_force_each_N_per_mm':[100.,200.]}})


def test_actual_hook_plane_differs_from_joint_development_and_does_not_become_a_node():
    args=inputs();original=deepcopy(args);r=evaluate(**args)
    assert args==original
    assert r['hook_depth_E_mm']==150.
    assert r['straight_leg_top_above_joint_mm']==152.
    assert r['latest_fully_developed_exit_above_joint_mm']==10.
    bottom=next(p for p in r['planes'] if p['plane']=='bottom transverse')
    assert bottom['above_joint_mm']==48.
    assert bottom['hook_available_from_plane_mm']==152.
    assert bottom['exit_drop_from_plane_needed_mm']==38.
    assert bottom['on_straight_U_leg'] and not bottom['full_yield_hook_length_at_this_plane']
    top=next(p for p in r['planes'] if p['plane']=='top transverse')
    assert top['above_joint_mm']==302. and not top['on_straight_U_leg']
    assert r['actual_node_face_area_mm2'] is None
    assert r['actual_node_exit_above_joint_mm'] is None
    assert r['torsion_enclosure_verified'] is False
    assert r['changes_nominal_resistance'] is False
    assert r['accepted_composite_capacity'] is None


def test_force_units_are_per_actual_bar_leg_at_model_capacity():
    r=evaluate(**inputs());left,right=r['U_forces']
    assert left['force_at_model_capacity_kN_per_bar']==20.
    assert right['force_at_model_capacity_kN_per_bar']==40.
    assert left['ceiling_kN_per_bar']==40.
    assert left['witness']=='VT'


@pytest.mark.parametrize('thickness,expected_E',[(300.,100.),(400.,200.)])
def test_geometry_responds_to_slab_thickness_and_preserves_measured_B(thickness,expected_E):
    args=inputs();args['slab_thickness_mm']=thickness
    args['inventory'][1]['y_mm']=750.+thickness-64.
    r=evaluate(**args)
    assert r['hook_depth_E_mm']==expected_E
    assert r['hook_outside_above_joint_mm']==200.


@pytest.mark.parametrize('field,value',[('spacing_mm',0.),('db_mm',True),('slab_bottom_y_mm',float('nan'))])
def test_unknown_geometry_cannot_become_a_qualified_node(field,value):
    args=inputs();args[field]=value
    with pytest.raises(ValueError):evaluate(**args)


def test_mismatched_longitudinal_cover_and_analysis_inventory_is_detected():
    args=inputs();args['inventory'][0]['y_mm']+=1.
    with pytest.raises(ValueError,match='inventory'):evaluate(**args)


def test_a_plane_with_sufficient_length_is_still_not_node_validation():
    args=inputs();args['detail']['slab_ldh_available_mm']=250.
    r=evaluate(**args)
    bottom=next(p for p in r['planes'] if p['plane']=='bottom transverse')
    assert bottom['full_yield_hook_length_at_this_plane']
    assert r['status']=='NODAL TRANSFER UNVERIFIED'
    assert r['torsion_enclosure_verified'] is False


def test_geometry_view_is_a_stored_result_reader_without_a_solver():
    r=evaluate(**inputs())
    with patch.object(engine,'solve',side_effect=AssertionError('View must not solve')):
        assert len(plane_frame(r))==4
        fig=make_figure(r,width_mm=100.)
        assert len(fig.data)==6
        assert fig.layout.yaxis.title.text.startswith('Height above')


def test_exact_LP_reuse_preserves_five_witnesses_and_detaches_mutable_outputs():
    s=supplies(interface_dv_mm=1000.);cache=engine.SolveCache()
    args=dict(vu_N=100e3,tu_Nmm=10e6,mu_Nmm=20e6,nu_tension_N=0.,held_action_intercepts=True)
    baseline=engine.calculate(s,**args)
    first=engine.calculate(s,**args,solve_cache=cache)
    second=engine.calculate(s,**args,solve_cache=cache)
    assert baseline==first==second
    assert cache.misses==5 and cache.hits==5
    first['VT']['contact_qx_N_per_mm'][0]+=10.
    assert second==engine.calculate(s,**args,solve_cache=cache)


def test_small_supply_and_action_changes_cannot_reuse_rounded_LP_results():
    s=supplies();cache=engine.SolveCache()
    cache.solve(s,vu_N=1000.,tu_Nmm=0.)
    cache.solve(replace(s,u_ao_mm2=s.u_ao_mm2+1e-7),vu_N=1000.,tu_Nmm=0.)
    cache.solve(s,vu_N=1000.+1e-7,tu_Nmm=0.)
    assert cache.misses==3 and cache.hits==0
    with pytest.raises(ValueError):cache.solve(s,vu_N=True,tu_Nmm=0.)


def test_nominal_fps_reuse_owns_exact_axial_target_boundary_and_section():
    state=ready_state()
    inp=AnalysisInput(section_geometry=state['section_geometry'],concrete_material=state['concrete_material'],
        rebars=state['rebars'],rebar_materials=state['rebar_materials'])
    args=dict(moment_sign=1.,axial_nominal_N=0.,tension_y_mid_mm=800.)
    base=nominal_fps_key(inp,**args)
    assert base!=nominal_fps_key(inp,**{**args,'axial_nominal_N':1e-7})
    assert base!=nominal_fps_key(inp,**{**args,'tension_y_mid_mm':800.+1e-7})
    assert base!=nominal_fps_key(inp,**{**args,'moment_sign':-1.})
    changed=inp.model_copy(deep=True);changed.rebars[0].y_mm+=1e-7
    assert base!=nominal_fps_key(changed,**args)


def test_batch_nominal_fps_with_changed_axial_force_matches_individual_rows(monkeypatch):
    import pandas as pd
    from concrete_pmm_pro.ui import igird_combined_vt as vt
    from concrete_pmm_pro.io.girder_csi_import import tag_app_source
    from test_igird_uls6_torsion_general_procedure import _demand, _route
    state=ready_state()
    rows=tag_app_source(pd.concat([_demand(x=10.,mux=1000.,vu=200.,tu=200.,nu=0.),
        _demand(x=10.,mux=1000.,vu=200.,tu=200.,nu=100.)],ignore_index=True),
        source_name='Exact axial QA',sheet_name='QA',source_mode='static',
        concurrency_confirmed=True,evidence='Defined simultaneous static vectors')
    targets=[];real=vt.nominal_tension_fps
    def capture(*a,**kw):
        targets.append(kw['axial_nominal_N'])
        return real(*a,**kw)
    monkeypatch.setattr(vt,'nominal_tension_fps',capture)
    batch=vt.check_dataframe(state,rows,strength_route=_route())
    assert len(targets)==2 and len(set(targets))==2
    for i in range(2):
        single=vt.check_dataframe(state,rows.iloc[[i]],strength_route=_route())
        for key in ('fps nominal min MPa','fps c mm','θ cot','Longitudinal D/C value'):
            assert batch.iloc[i][key]==pytest.approx(single.iloc[0][key])
