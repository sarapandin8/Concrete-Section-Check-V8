"""Unchecked secondary bending must not receive full flexure acceptance."""
from copy import deepcopy
import math
from pathlib import Path

import pandas as pd
import pytest

from concrete_pmm_pro.analysis.igird_flexure_development import qualify_primary_axis_scope


@pytest.mark.parametrize('moment', [1.0, -2000.1935, float('nan'), float('inf')])
def test_secondary_bending_requires_review_without_altering_numerical_screen(moment):
    original = {'Status': 'PASS', 'Numerical status': 'PASS', 'φMn kN-m': 10000.0,
        'D/C value': .5, 'Nu kN': 200, 'Demand kN-m': 5000, 'Notes': 'Stored equilibrium.'}
    before = deepcopy(original)
    qualified = qualify_primary_axis_scope(original, moment)
    assert qualified['Status'] == 'REVIEW'
    assert qualified['Secondary-axis flexure gate'].startswith('REVIEW')
    for key in ['Numerical status', 'φMn kN-m', 'D/C value', 'Nu kN', 'Demand kN-m']:
        assert qualified[key] == original[key]
    assert original == before


@pytest.mark.parametrize('status,numerical,capacity,ratio', [
    ('FAIL','FAIL',10,1.35), ('FAIL','NO EQUILIBRIUM',float('nan'),float('inf')),
    ('REVIEW','SOURCE BLOCKED',float('nan'),float('nan'))])
def test_secondary_scope_never_downgrades_failure_or_fills_unavailable_capacity(status,numerical,capacity,ratio):
    result = qualify_primary_axis_scope({'Status':status,'Numerical status':numerical,
        'φMn kN-m':capacity,'D/C value':ratio}, 1231.4747)
    assert result['Status'] == status
    assert result['Numerical status'] == numerical
    assert result['φMn kN-m'] == capacity or math.isnan(result['φMn kN-m']) and math.isnan(capacity)
    assert result['D/C value'] == ratio or math.isnan(result['D/C value']) and math.isnan(ratio)


def test_zero_primary_moment_with_secondary_bending_is_not_an_accepted_section_preview():
    result = qualify_primary_axis_scope({'Status':'SECTION PREVIEW','Numerical status':'SECTION PREVIEW'}, 10)
    assert result['Status'] == 'REVIEW'
    assert result['Numerical status'] == 'SECTION PREVIEW'
    assert qualify_primary_axis_scope({'Status':'PASS'},0)['Status'] == 'PASS'


def test_production_developed_section_retains_resistance_and_signed_demands():
    from concrete_pmm_pro.io.project_io import apply_project_to_session_state,project_from_json
    from concrete_pmm_pro.ui import analysis_page as ap
    from concrete_pmm_pro.core.models import RebarMaterial
    root = Path(__file__).resolve().parents[1]
    state = {}
    apply_project_to_session_state(project_from_json((root/'qa/fixtures/I_Girder_20m.json').read_text()),state)
    state['rebar_materials'] = [RebarMaterial(name='SD40',fy_MPa=390,Es_MPa=200000)]
    state['igird_flexure_development_settings'] = {
        'bars_continuous_confirmed':True,'left_bar_anchored':True,'right_bar_anchored':True}
    route = ap._beam_uls_strength_route_from_state(state,is_bridge=True,is_building=False)
    source = pd.DataFrame([{'Active':True,'Station x (m)':10,'Case Name':'STATIC',
        'Mux':500,'Muy':0.0,'Nu':0,'Vuy':100,'Vux':0,'Tu':0,'Note':''}])
    first, _ = ap._beam_uls_flexure_preview_dataframe(state,source,strength_route=route,
        prestress_force_stage='final',use_aashto_solver=True,apply_girder_development=True)
    assert first.iloc[0]['Status'] == 'PASS'
    source.loc[0,'Muy'] = -2000.1935
    second, _ = ap._beam_uls_flexure_preview_dataframe(state,source,strength_route=route,
        prestress_force_stage='final',use_aashto_solver=True,apply_girder_development=True)
    assert second.iloc[0]['Status'] == 'REVIEW'
    assert second.iloc[0]['Numerical status'] == 'PASS'
    assert second.iloc[0]['Muy demand kN-m'] == -2000.1935
    for key in ['φMn kN-m','φPn kN','D/C value','Force residual N','Nu kN','Demand kN-m']:
        assert first.iloc[0][key] == second.iloc[0][key]


def test_stored_summary_shows_cases_and_true_coordinate_count_without_solving(monkeypatch):
    from concrete_pmm_pro.ui import igird_flexure_development as ui
    warnings, errors, frames = [], [], []
    monkeypatch.setattr(ui.st,'warning',warnings.append)
    monkeypatch.setattr(ui.st,'error',errors.append)
    monkeypatch.setattr(ui.st,'caption',lambda *args,**kwargs:None)
    monkeypatch.setattr(ui.st,'dataframe',lambda frame,**kwargs:frames.append(frame))
    frame = pd.DataFrame([
        {'Station x (m)':0,'Nu input kN':114.969,'Nu kN':-114.969,'Demand kN-m':0,
         'φMn kN-m':float('nan'),'D/C value':float('inf'),'Status':'FAIL','Numerical status':'NO EQUILIBRIUM',
         'Source OutputCase':'U1A','Source ItemType':'Max','Source LocType':'After',
         'Secondary-axis flexure gate':'NOT REQUIRED: Muy = 0','Muy demand kN-m':0,
         'Strand development trace':float('nan')},
        {'Station x (m)':0,'Nu input kN':-19.223,'Nu kN':19.223,'Demand kN-m':-27.1006,
         'φMn kN-m':20.0611295,'D/C value':1.3509,'Status':'FAIL','Numerical status':'FAIL',
         'Source OutputCase':'U2B','Source ItemType':'Min','Source LocType':'After',
         'Secondary-axis flexure gate':'REVIEW: biaxial flexure required','Muy demand kN-m':-1.9}])
    before = frame.copy(deep=True)
    ui.render_failure_summary(frame,stage='Final Composite')
    assert '1 numerical strength exceedance(s)' in errors[0]
    assert '1 resistance-unavailable row(s), at 1 station coordinate(s)' in errors[0]
    assert '1 displayed source row(s)' in warnings[0]
    assert frames[0]['Load case'].tolist() == ['U1A','U2B']
    assert frames[0]['Bound'].tolist() == ['Max','Min']
    assert frames[0].iloc[0]['φMn (kN-m)'] == 'Unavailable'
    assert frames[0].iloc[0]['D/C'] == 'Unavailable'
    pd.testing.assert_frame_equal(frame,before)
