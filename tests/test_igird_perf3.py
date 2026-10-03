import pytest
import concrete_pmm_pro.ui.analysis_page as a
from concrete_pmm_pro.analysis.uls_strength_routing import beam_girder_uls_strength_route
from concrete_pmm_pro.core.models import LoadCase
from test_igird_uls2p_flexure_performance import _prestressed_bridge_input


def route():
    return beam_girder_uls_strength_route(is_bridge=True,is_building=False,project_design_code='AASHTO LRFD',code_edition='9th Edition')

@pytest.mark.parametrize('aashto',[False,True])
def test_same_section_reuses_cloud_but_checks_each_axial_force_and_direction(monkeypatch,aashto):
    inp=_prestressed_bridge_input();rt=route();cache={}
    name='run_aashto_lrfd_column_pmm_solver' if aashto else 'run_rc_pmm_solver'
    real=getattr(a,name);calls=[]
    def counted(value):
        calls.append(value);return real(value)
    monkeypatch.setattr(a,name,counted)
    capacities=[]
    for pu,mu in [(0,500_000_000),(250_000,700_000_000),(-100_000,-100_000_000)]:
        case=LoadCase(name='check',Pu_N=pu,Mux_Nmm=mu,Muy_Nmm=0,load_type='ULS')
        ai=inp.model_copy(update={'load_cases':[case]})
        cached=a._beam_uls_solve_flexure_capacity_state(ai,strength_route=rt,use_aashto_solver=aashto,pmm_cloud_cache=cache)
        monkeypatch.setattr(a,name,real)
        reference=a._beam_uls_solve_flexure_capacity_state(ai,strength_route=rt,use_aashto_solver=aashto)
        monkeypatch.setattr(a,name,counted)
        assert cached['state']==reference['state']=='ok'
        for key in ('nominal_capacity_nmm','routed_capacity_nmm','route_phi_value','result_warning_count'):
            assert cached[key]==reference[key]
        capacities.append(cached['routed_capacity_nmm'])
    assert len(calls)==1
    assert len(set(capacities))==3

@pytest.mark.parametrize('change',['geometry','concrete','rebar','prestress_force','prestress_area','prestress_count','prestress_bond','resolution','material'])
def test_changed_physical_inputs_rebuild_cloud(monkeypatch,change):
    inp=_prestressed_bridge_input();rt=route();cache={};calls=[];real=a.run_rc_pmm_solver
    def counted(value):
        calls.append(value);return real(value)
    monkeypatch.setattr(a,'run_rc_pmm_solver',counted)
    a._beam_uls_solve_flexure_capacity_state(inp,strength_route=rt,pmm_cloud_cache=cache)
    altered=inp.model_copy(deep=True)
    if change=='geometry':
        from concrete_pmm_pro.geometry.generators import rectangle
        altered.section_geometry=rectangle(width_mm=510,height_mm=1000)
    elif change=='concrete': altered.concrete_material.fc_MPa=50
    elif change=='rebar': altered.rebars[0].diameter_mm=22
    elif change=='prestress_force': altered.prestress_elements[0].pe_eff_n=130000
    elif change=='prestress_area': altered.prestress_elements[0].area_mm2=150
    elif change=='prestress_count': altered.prestress_elements[0].count=7
    elif change=='prestress_bond': altered.prestress_elements[0].bonded=False
    elif change=='resolution': altered.settings.neutral_axis_depth_steps=12
    elif change=='material': altered.rebar_materials[0].fy_MPa=420
    a._beam_uls_solve_flexure_capacity_state(altered,strength_route=rt,pmm_cloud_cache=cache)
    assert len(calls)==2 and len(cache)==2


def test_failed_cloud_is_not_cached_and_retry_can_recover(monkeypatch):
    inp=_prestressed_bridge_input();rt=route();cache={};real=a.run_rc_pmm_solver
    def broken(value):raise ValueError('bad section')
    monkeypatch.setattr(a,'run_rc_pmm_solver',broken)
    assert a._beam_uls_solve_flexure_capacity_state(inp,strength_route=rt,pmm_cloud_cache=cache)['state']=='solver_error'
    assert not cache
    monkeypatch.setattr(a,'run_rc_pmm_solver',real)
    assert a._beam_uls_solve_flexure_capacity_state(inp,strength_route=rt,pmm_cloud_cache=cache)['state']=='ok'
