"""Numerical equivalence and physical invalidation for calculation-local reuse."""
from dataclasses import asdict
import math

import pandas as pd
import pytest
from shapely.geometry import Polygon

from concrete_pmm_pro.analysis import pmm_solver as s
from concrete_pmm_pro.analysis.capacity_check import check_uls_demands_against_rc_pmm
from concrete_pmm_pro.analysis.pmm_prepared import PreparedFlexureCloud, PreparedPMMCheck
from concrete_pmm_pro.analysis.pmm_section_cache import PMMSectionCache, compression_membership
from concrete_pmm_pro.analysis.strain_compatibility import is_point_inside_compression_block
from concrete_pmm_pro.core.models import LoadCase
from concrete_pmm_pro.ui import analysis_page as a
from concrete_pmm_pro.visualization import pmm_dashboard as p
from test_igird_uls2p_flexure_performance import _prestressed_bridge_input
from test_igird_perf3 import route


@pytest.mark.parametrize("aashto", [False, True])
@pytest.mark.parametrize("prestress", ["active", "passive", "unbonded", "off", "no_fpy", "no_fpu"])
def test_all_point_fields_warnings_and_info_equal_to_scalar_sweep(aashto, prestress):
    ai = _prestressed_bridge_input()
    element = ai.prestress_elements[0]
    if prestress == "passive": element.pe_eff_n = 0; element.initial_stress_mpa = 0
    if prestress == "unbonded": element.bonded = False
    if prestress == "off": ai.settings.include_prestress = False
    if prestress == "no_fpy": element.fpy_mpa = None
    if prestress == "no_fpu": element.fpu_mpa = None
    solver = s.run_aashto_lrfd_column_pmm_solver if aashto else s.run_rc_pmm_solver
    reference = solver(ai)
    cache = PMMSectionCache()
    assert solver(ai, section_cache=cache).model_dump() == reference.model_dump()
    assert solver(ai, section_cache=cache).model_dump() == reference.model_dump()
    assert cache.build_count == cache.hit_count == 1


@pytest.mark.parametrize("change", ["geometry", "fc", "ecu", "beta", "bar_x", "bar_y", "bar_area",
                                  "bar_material", "fy", "es", "bar_order", "include_rebars", "subtract", "angles", "depths"])
def test_changed_concrete_rebar_or_sweep_input_rebuilds_base(change):
    ai = _prestressed_bridge_input()
    cache = PMMSectionCache()
    s.run_rc_pmm_solver(ai, section_cache=cache)
    changed = ai.model_copy(deep=True)
    if change == "geometry":
        from concrete_pmm_pro.geometry.generators import rectangle
        changed.section_geometry = rectangle(width_mm=510, height_mm=1000)
    if change == "fc": changed.concrete_material.fc_MPa = 50
    if change == "ecu": changed.concrete_material.ecu = .0035
    if change == "beta": changed.concrete_material.beta1 = .75
    if change == "bar_x": changed.rebars[0].x_mm += 10
    if change == "bar_y": changed.rebars[0].y_mm += 10
    if change == "bar_area": changed.rebars[0].diameter_mm = 22
    if change == "bar_material":
        changed.rebar_materials.append(changed.rebar_materials[0].model_copy(update={"name": "other", "fy_MPa": 500}))
        changed.rebars[0].material_name = "other"
    if change == "fy": changed.rebar_materials[0].fy_MPa = 500
    if change == "es": changed.rebar_materials[0].Es_MPa = 190000
    if change == "bar_order": changed.rebars.reverse()
    if change == "include_rebars": changed.settings.include_rebars = False
    if change == "subtract": changed.settings.subtract_rebar_displaced_concrete = False
    if change == "angles": changed.settings.neutral_axis_angle_steps = 16
    if change == "depths": changed.settings.neutral_axis_depth_steps = 12
    assert s.run_rc_pmm_solver(changed, section_cache=cache).model_dump() == s.run_rc_pmm_solver(changed).model_dump()
    assert cache.build_count == 2


@pytest.mark.parametrize("change", ["prestress_force", "prestress_count", "prestress_y", "prestress_bond", "phi", "nu"])
def test_independent_strand_phi_and_demand_changes_reuse_only_base(change):
    ai = _prestressed_bridge_input()
    cache = PMMSectionCache()
    s.run_rc_pmm_solver(ai, section_cache=cache)
    changed = ai.model_copy(deep=True)
    if change == "prestress_force": changed.prestress_elements[0].initial_stress_mpa = 1100
    if change == "prestress_count": changed.prestress_elements[0].count = 6
    if change == "prestress_y": changed.prestress_elements[0].y_mm = -350
    if change == "prestress_bond": changed.prestress_elements[0].bonded = False
    if change == "phi": changed.settings.use_phi_factor = False
    if change == "nu": changed.load_cases[0].Pu_N = 250000
    assert s.run_rc_pmm_solver(changed, section_cache=cache).model_dump() == s.run_rc_pmm_solver(changed).model_dump()
    assert cache.build_count == cache.hit_count == 1


def test_bulk_predicate_keeps_outer_and_hole_boundaries_and_invalid_geometry():
    region = Polygon([(0,0),(10,0),(10,10),(0,10)], holes=[[(3,3),(7,3),(7,7),(3,7)]])
    xy = ((0.,0.),(1.,1.),(3.,5.),(5.,5.),(10.,5.),(-1.,5.),(float("nan"),1.))
    for geometry in [region, Polygon(), None, Polygon([(0,0),(2,2),(2,0),(0,2)])]:
        assert compression_membership(geometry, xy) == tuple(is_point_inside_compression_block(x,y,geometry) for x,y in xy)


def test_failed_sweep_does_not_publish_partial_base(monkeypatch):
    cache = PMMSectionCache()
    real = s.prestress_stress_mpa
    def broken(*args, **kwargs): raise RuntimeError("interrupted")
    monkeypatch.setattr(s, "prestress_stress_mpa", broken)
    with pytest.raises(RuntimeError): s.run_rc_pmm_solver(_prestressed_bridge_input(), section_cache=cache)
    assert cache.build_count == 0
    monkeypatch.setattr(s, "prestress_stress_mpa", real)
    s.run_rc_pmm_solver(_prestressed_bridge_input(), section_cache=cache)
    assert cache.build_count == 1


@pytest.mark.parametrize("pu", [-100000, 0, 250000, 100000000])
@pytest.mark.parametrize("moments", [(5e8,0),(-1e8,0),(1e8,1e8),(0,0)])
def test_prepared_demand_summary_preserves_capacity_methods_warnings_and_results(pu, moments):
    cloud = s.run_rc_pmm_solver(_prestressed_bridge_input())
    loads = [LoadCase(name="check", Pu_N=pu, Mux_Nmm=moments[0], Muy_Nmm=moments[1], load_type="ULS")]
    prepared = PreparedPMMCheck(cloud)
    assert asdict(check_uls_demands_against_rc_pmm(cloud, loads, prepared=prepared)) == asdict(check_uls_demands_against_rc_pmm(cloud, loads))


def test_prepared_cloud_cannot_be_used_for_a_different_result():
    ai = _prestressed_bridge_input()
    cloud = s.run_rc_pmm_solver(ai)
    with pytest.raises(ValueError, match="different physical"):
        check_uls_demands_against_rc_pmm(s.run_rc_pmm_solver(ai), ai.load_cases, prepared=PreparedPMMCheck(cloud))


def test_full_flexure_state_reuses_preparation_and_retains_each_nu_and_sign():
    ai = _prestressed_bridge_input()
    clouds, prepared, base = {}, {}, PMMSectionCache()
    for pu, mu in [(0,5e8),(250000,7e8),(-100000,-1e8)]:
        ai.load_cases = [LoadCase(name="check", Pu_N=pu, Mux_Nmm=mu, Muy_Nmm=0, load_type="ULS")]
        fast = a._beam_uls_solve_flexure_capacity_state(ai, strength_route=route(), use_aashto_solver=True,
                    pmm_cloud_cache=clouds, section_cache=base, prepared_cloud_cache=prepared)
        reference = a._beam_uls_solve_flexure_capacity_state(ai, strength_route=route(), use_aashto_solver=True)
        assert fast == reference
    assert len(clouds) == len(prepared) == base.build_count == 1


def test_prepared_slice_duplicate_only_exact_and_fallback_keep_all_metadata():
    rows = [{"theta_rad":theta,"c_mm":depth,"phiPn_kN":pu,"phiPn_capped_kN":pu,
             "phiMnx_kNm":100*math.cos(theta)*depth,"phiMny_kNm":100*math.sin(theta)*depth,
             "strain_condition":"tension","extra":None}
            for theta in [2*math.pi*i/12 for i in range(12)] for depth,pu in [(1,100),(2,100)]]
    for df in [pd.DataFrame(rows), pd.DataFrame(rows).iloc[:2], pd.DataFrame(rows).iloc[:0]]:
        prepared = p.PreparedPMMSlice(df)
        for pu in [99,100,101,100]:
            expected = p.pmm_slice_at_pu(df, pu)
            actual = prepared.at_pu(pu)
            pd.testing.assert_frame_equal(actual, expected, check_exact=True)
            assert actual.attrs == expected.attrs
            if not actual.empty: actual.iloc[0,0] = 999
            again = prepared.at_pu(pu)
            pd.testing.assert_frame_equal(again, expected, check_exact=True)
