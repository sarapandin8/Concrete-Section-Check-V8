"""Check the chosen model, stale-result isolation, and review-only UI semantics."""
from copy import deepcopy
from unittest.mock import MagicMock, patch

import pytest

from concrete_pmm_pro.ui import igird_modeltn47 as view
from concrete_pmm_pro.ui import igird_composite_steel45 as storage


def snapshot(dc=1.535770637):
    ready = {'ready': True, 'active_limits': ['shared concrete flow budget']}
    calc = {'model_Tn_kNm': 277.475425974, 'model_Vn_kN': 1437.5926782, 'model_VT_DC': dc,
        'V': ready, 'T': ready, 'VT': ready, 'supplies': {},
        'accepted_Tn_kNm': None, 'accepted_Vn_kN': None, 'accepted_VT_factor': None}
    return {'enabled': True, 'rows': [{'Girder': 'Interior 2', 'x (m)': 18., 'Case': 'U2A',
        'Source StepType': 'Max', 'Source Excel row': 556, 'Status': 'MODEL REVIEW',
        'calculation': calc, 'without_U': {**calc, 'model_Tn_kNm': 252.110093822},
        'without_slab_longitudinal': {**calc, 'model_Tn_kNm': 252.110093822},
        'baseline_code_check': {'Tn_transverse_kNm': 321.11441725},
        'inventory': [], 'source_CSI': {'Tu': 286.8371}}]}


def test_primary_capacity_is_with_u_and_slab_not_i_hoop_or_ablation():
    result = snapshot()
    original = deepcopy(result)
    row = view.primary_frame(result).iloc[0]
    assert row['Model Tn · U + slab (kN-m)'] == pytest.approx(277.475425974)
    assert row['Model nominal V–T D/C'] == pytest.approx(1.535770637)
    assert row['Case / step'] == 'U2A / Max'
    assert row['Status'] == 'MODEL REVIEW'
    assert row['Nominal V–T state'] == 'EXCEEDS NOMINAL'
    assert result == original


def test_numerically_under_one_remains_review_and_no_phi_or_pass_is_inferred():
    frame = view.primary_frame(snapshot(.938279742))
    assert frame.iloc[0]['Nominal V–T state'] == 'WITHIN NOMINAL'
    assert frame.iloc[0]['Status'] == 'MODEL REVIEW'
    assert not any('φ' in c or 'phi' in c for c in frame.columns)
    assert 'PASS' not in frame.to_string()


def test_partial_and_blocked_models_do_not_fall_back_to_larger_baseline_capacity():
    result = snapshot()
    del result['rows'][0]['calculation']
    result['rows'][0]['Status'] = 'MODEL BLOCKED'
    row = view.primary_frame(result).iloc[0]
    assert row['Model Tn · U + slab (kN-m)'] is None
    assert row['Nominal V–T state'] == 'UNAVAILABLE'
    assert row['Status'] == 'MODEL BLOCKED'
    result = snapshot(.4)
    result['rows'][0]['calculation']['VT'] = {'ready': False}
    result['rows'][0]['Status'] = 'MODEL INCOMPLETE'
    assert view.primary_frame(result).iloc[0]['Status'] == 'MODEL INCOMPLETE'


def test_zero_model_capacity_is_preserved_without_dividing_by_zero():
    result = snapshot(None)
    result['rows'][0]['calculation']['model_Tn_kNm'] = 0.
    row = view.primary_frame(result).iloc[0]
    assert row['Model Tn · U + slab (kN-m)'] == 0.
    assert row['Nominal V–T state'] == 'UNAVAILABLE'


def test_collection_uses_current_fingerprints_and_shows_unavailable_member():
    state = {}
    saved = snapshot()
    storage.detach_review(state, {storage.KEY: saved}, fingerprint='current')
    result = view.collection_snapshot(state, {'BOBJ1 / Interior 2': 'current', 'Exterior': 'stale'})
    frame = view.primary_frame(result)
    assert len(frame) == 2
    assert frame.iloc[0]['Model Tn · U + slab (kN-m)'] == pytest.approx(277.475425974)
    assert frame.iloc[0]['Girder'] == 'BOBJ1 / Interior 2'
    assert saved['rows'][0]['Girder'] == 'Interior 2'
    assert frame.iloc[1]['Status'] == 'NOT CALCULATED'
    assert state[storage.RUNTIME_KEY]['current'] == saved


def test_overview_and_member_render_only_stored_model_no_solver_or_design_cache_write():
    result = snapshot()
    original = deepcopy(result)
    with patch('streamlit.markdown'), patch('streamlit.warning'), patch('streamlit.caption'), \
         patch('streamlit.info'), patch('streamlit.dataframe') as table, patch('streamlit.json'), \
         patch('streamlit.write'), patch('streamlit.latex'), \
         patch('streamlit.expander', return_value=MagicMock()), \
         patch('concrete_pmm_pro.ui.analysis_page._render_analysis_summary_strip') as cards, \
         patch('concrete_pmm_pro.analysis.igird_composite_steel45.calculate', side_effect=AssertionError('No render solve')), \
         patch('concrete_pmm_pro.ui.igird_composite_steel45.calculate', side_effect=AssertionError('No render solve')):
        view.render_overview(result)
        storage.render(result)
    assert table.call_args_list[0].args[0].iloc[0]['Model Tn · U + slab (kN-m)'] == pytest.approx(277.475425974)
    assert cards.call_args.args[0][0]['value'] == '277.475 kN-m'
    assert result == original


def test_missing_current_model_is_visible_without_solver_or_reference_substitution():
    with patch('streamlit.markdown'), patch('streamlit.warning'), patch('streamlit.caption'), \
         patch('streamlit.info') as info, patch('streamlit.dataframe') as table:
        view.render(None)
    assert info.called
    assert not table.called


def test_collection_member_code_primary_does_not_request_research_model():
    from concrete_pmm_pro.ui import igird_member_results as members
    saved = snapshot()
    state = {storage.RUNTIME_KEY: {'current': saved}}
    with patch.object(members.st, 'session_state', state), \
         patch.object(storage, 'render') as model, \
         patch.object(members.st, 'expander', return_value=MagicMock()), \
         patch.object(members.st, 'caption'), \
         patch.object(members, '_render_reference_member_result') as reference:
        events = []
        model.side_effect = lambda result: events.append(('model', result))
        reference.side_effect = lambda **kwargs: events.append(('reference', kwargs))
        members._render_member_result(member='Interior 2', result={}, all_rows=None, control={},
            cache={'Interior 2': {'Torsion': {'input_hash': 'current'}}}, check_name='Torsion', code_label='AASHTO')
    assert len(events)==1 and events[0][0]=='reference'
    assert not model.called
