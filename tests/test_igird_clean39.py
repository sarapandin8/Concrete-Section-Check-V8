"""Retired controls cannot dispatch an old model or replace physical inputs."""
from copy import deepcopy
from unittest.mock import patch

import pandas as pd
import pytest
from streamlit.testing.v1 import AppTest

from concrete_pmm_pro.ui import analysis_page as ap, igird_flexure_workspace as fw
from concrete_pmm_pro.ui import igird_coupled_model as legacy, igird_station36 as station
from concrete_pmm_pro.ui.igird_composite_inputs import input_plan
from test_igird_cover38 import fixture


@pytest.mark.parametrize('old_opt_in', [False, True])
def test_old_opt_in_and_enabled_project_never_dispatch_retired_calculation(old_opt_in):
    state, rows, route = fixture()
    state['igird_cover38_legacy_inputs'] = old_opt_in
    state['project_metadata'][legacy.KEY] = {
        'enabled': True, 'closure_db_mm': 32., 'closure_spacing_mm': 10.,
        'lap_available_mm': 200., 'closure_detail': '90-degree tension hooks',
    }
    physical = deepcopy(state['beam_girder_interface_shear_settings'])
    retired = deepcopy(state['project_metadata'][legacy.KEY])
    before = rows.copy(deep=True)
    with patch.object(legacy, 'calculate', side_effect=AssertionError('Retired model must never run')), \
         patch.object(fw.members, 'calculate_member', return_value={}) as section, \
         patch.object(ap, '_igird_interface_shear_dataframe', return_value=(pd.DataFrame(), [])) as interface, \
         patch.object(station, 'calculate', return_value={'status': 'MODEL BLOCKED'}) as current:
        result = fw.calculate_bundle(state, rows, route=route)
    assert section.call_count == interface.call_count == current.call_count == 1
    assert not result['coupled_research']['enabled']
    assert result['coupled_research']['accepted_phiTn_Nmm'] is None
    assert result['coupled_research']['accepted_VT_factor'] is None
    assert state['beam_girder_interface_shear_settings'] == physical
    assert state['project_metadata'][legacy.KEY] == retired
    pd.testing.assert_frame_equal(rows, before)


def test_opening_actual_workspace_with_old_opt_in_has_no_retired_form_or_solver():
    from test_igird_membercharts3 import model
    from concrete_pmm_pro.io.girder_load_bank import save_active
    from concrete_pmm_pro.analysis.igird_interface_connectors import INDEPENDENT_DOWELS
    state = model(); save_active(state)
    state['section_preset_key'] = 'parametric_i_girder'
    state['section_parameters'].update(deck_long_rebar_top_diameter_mm=16., deck_long_rebar_bottom_diameter_mm=16.)
    state['beam_girder_interface_shear_settings'] = {
        'connector_source': INDEPENDENT_DOWELS,
        'dowel_connection': {'slab_transverse_mesh': {face: {
            'Diameter_mm': 16., 'Spacing_mm': 150., 'Clear_cover_mm': 40., 'fy_MPa': 390.,
        } for face in ('top', 'bottom')}},
    }
    state['igird_cover38_legacy_inputs'] = True
    state['project_metadata'] = {**state.get('project_metadata', {}), legacy.KEY: {'enabled': True}}
    script = '''import streamlit as st
from concrete_pmm_pro.ui import analysis_page as ap, igird_flexure_workspace as fw
route=ap._beam_uls_strength_route_from_state(st.session_state,is_bridge=True,is_building=False)
fw.render_workspace(ap._active_beam_uls_demand_dataframe_from_session(st.session_state),route=route,code_label='AASHTO')
'''
    app = AppTest.from_string(script, default_timeout=60)
    for key, value in state.items(): app.session_state[key] = deepcopy(value)
    with patch.object(legacy, 'render_inputs', side_effect=AssertionError('Retired form')), \
         patch.object(legacy, 'render_result', side_effect=AssertionError('Retired results')), \
         patch.object(legacy, 'calculate', side_effect=AssertionError('Retired solver')):
        app.run()
        app.toggle(key='igird_flexure31_edit_inputs').set_value(True).run()
    assert not app.exception, [e.message for e in app.exception]
    assert [b.label for b in app.button if b.label.startswith('Calculate')] == ['Calculate Flexure']
    assert not any('legacy research' in t.label.lower() or 'coupled composite model' in t.label.lower() for t in app.toggle)
    assert not any('legacy research' in e.label.lower() or 'archived composite' in e.label.lower() for e in app.expander)
    assert any('Slab mesh' in e.label for e in app.expander)


def test_input_guidance_has_no_dead_end_opt_in_and_does_not_claim_completed_resistance():
    state, _, _ = fixture()
    plan = input_plan(state['beam_girder_interface_shear_settings'], params=state['section_parameters'], state=state)
    item = next(r for r in plan['pending'] if r['Step'] == 'Full composite Vn / Tn / V–T resistance')
    assert item['Status'] == 'MODEL DEVELOPMENT — DESIGN RESISTANCE UNAVAILABLE'
    assert 'nodal strength' in item['Meaning'] and 'tie anchorage' in item['Meaning']
    assert 'Enable under' not in str(plan) and 'COUPLED34' not in str(plan)
    assert plan['design_status'] == 'REVIEW'
