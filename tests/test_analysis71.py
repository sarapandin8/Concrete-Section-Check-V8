"""Currency must agree with input hashes, never with navigation or PASS text."""
from copy import deepcopy
from unittest.mock import patch

import pytest
import streamlit as st

import app
from concrete_pmm_pro.core.analysis import AnalysisModeSettings
from concrete_pmm_pro.reporting.analysis_current71 import ULS_FRAMES, current_uls_cache, pages, aggregate
from concrete_pmm_pro.state.dirty_state import input_group_hashes
from concrete_pmm_pro.ui import analysis_page as ap, girder_deflect70 as view
from concrete_pmm_pro.serviceability import girder_deflect70 as deflection
from concrete_pmm_pro.io.girder_deflect70 import BANK_KEY, ERROR_KEY
from test_girder_deflect70 import state as deflection_state
from test_girder_deflect69 import source_curves
from test_igird_uls5_result_summary import _base_state


@pytest.mark.parametrize('name', list(ULS_FRAMES))
def test_every_uls_check_is_rejected_in_summary_after_geometry_changes(name):
    state = _base_state()
    assert name in current_uls_cache(state)
    state['section_parameters'] = dict(state.get('section_parameters') or {}, Tslab_mm=333.)
    with patch.object(ap, '_beam_uls_calculate_selected_check', side_effect=AssertionError('solver rerun')):
        assert name not in current_uls_cache(state)
        assert name not in app._results_beam_uls_cache(state)
    rows = app._results_beam_uls_summary_rows(state)
    assert not any(row['Status'] == 'PASS' for row in rows)


def test_unsigned_and_wrong_version_uls_entries_cannot_be_promoted_to_current():
    state = _base_state()
    for name in ULS_FRAMES:
        state['_beam_girder_uls_manual_calculation_cache'][name].pop('input_hash',None)
    assert not current_uls_cache(state)
    state = _base_state()
    for name in ULS_FRAMES:
        state['_beam_girder_uls_manual_calculation_cache'][name]['result_version'] = 'old'
    assert not current_uls_cache(state)


def test_unusable_demand_does_not_break_read_only_status_or_reuse_a_cached_pass():
    state = _base_state()
    with patch.object(ap, '_active_beam_uls_demand_dataframe_from_session', side_effect=ValueError('Incomplete demand')):
        assert not current_uls_cache(state)
        assert aggregate(state)['label'] == 'Stale 0/4'


def test_global_visited_or_pass_flags_do_not_mean_any_page_has_been_calculated():
    state={'section_preset_key':'parametric_i_girder','analysis_status':'PASS','_perf_analysis_status':'Current'}
    result=aggregate(state)
    assert result['label']=='Not calculated 0/4' and not result['complete']
    assert result['pages']['Slab Reinforcement']['status']=='INPUTS MISSING'
    assert result['pages']['SLS Deflection / Camber']['status']=='NOT CALCULATED'


def test_current_deflection_does_not_certify_stress_uls_or_deck_and_view_state_is_not_an_input():
    state=deflection_state()
    state['section_preset_key']='parametric_i_girder'
    state['analysis_mode_settings']=AnalysisModeSettings(member_type='beam_girder')
    state[deflection.RESULT_KEY]=deflection.calculate(state,source_curves(),20.)
    state[view.VIEW_KEY]={'stage':'Service stage','girder':'Interior Girder 2'}
    state['girder_deflect70_ui_stage']='Transfer stage'
    result=aggregate(state)
    assert result['label']=='Partial 1/4' and not result['complete']
    assert 'Partial 1/4' in app._commercial_project_status_html(state)
    assert result['pages']['SLS Deflection / Camber']['status']=='CURRENT'
    state[ERROR_KEY]='invalid replacement'
    assert pages(state)['SLS Deflection / Camber']['status']=='STALE'


def test_service_import_and_criteria_are_engineering_inputs_for_dirty_state_but_views_are_not():
    state=deflection_state()
    before=input_group_hashes(state)
    state[view.VIEW_KEY]={'stage':'Service stage','girder':'Interior Girder 2'}
    assert input_group_hashes(state)==before
    state[BANK_KEY]['girders'][0]['rows'][2]['WebTop Vert']*=1.1
    assert input_group_hashes(state)['Loads']!=before['Loads']
    state[deflection.SETTINGS_KEY]['custom_limit_mm']=10.
    assert input_group_hashes(state)['Analysis settings']!=before['Analysis settings']


def test_explicit_upload_x_clears_inputs_and_remembered_view_does_not_change_results():
    state=deflection_state()
    state[ERROR_KEY]='pending bad upload'
    state[view.UPLOAD_KEY]=None
    with patch.object(st,'session_state',state):
        view._upload_changed()
    assert BANK_KEY not in state and ERROR_KEY not in state
    state={'girder_deflect70_ui_stage':'Service stage','girder_deflect70_ui_girder':'Interior Girder 2'}
    with patch.object(st,'session_state',state):view._remember_view()
    assert state[view.VIEW_KEY]=={'stage':'Service stage','girder':'Interior Girder 2'}
