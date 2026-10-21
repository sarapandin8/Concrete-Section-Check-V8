"""Actual app navigation, form transaction and read-only chart/report views."""
from copy import deepcopy
from pathlib import Path
from unittest.mock import patch

import pandas as pd
from streamlit.testing.v1 import AppTest

from concrete_pmm_pro.analysis import slab_top65 as top, slab_shear64 as accepted
from concrete_pmm_pro.analysis import slab_review68 as active
from test_slab_shell56 import model_state

ROOT = Path(__file__).resolve().parents[1]


def app():
    test = AppTest.from_file(str(ROOT/'app.py'), default_timeout=60)
    for key, value in model_state().items():
        test.session_state[key] = deepcopy(value)
    test.session_state['_nav_active_workspace'] = 'Analysis'
    test.session_state['_nav_analysis_subpage'] = 'Slab Reinforcement'
    return test


def clean(test):
    test.run(timeout=60)
    assert not test.exception, [e.message for e in test.exception]


def test_one_command_all_views_both_chart_modes_and_report_never_rerun_mechanics():
    test = app()
    with patch.object(accepted, 'calculate', wraps=accepted.calculate) as solver:
        clean(test)
        assert solver.call_count == 0
        test.button(key='slab_shell55_aashto62_calculate').click()
        clean(test)
        assert solver.call_count == 1
        original = test.session_state[top.RESULT_KEY]['summary'].copy(deep=True)
        for view in top.VIEWS:
            group = 'One-way shear' if view.startswith(('Shear ·', 'Flexural shear tie ·')) else 'Reinforcement'
            test.radio(key='slab_shell55_shear64_group').set_value(group)
            clean(test)
            test.selectbox(key='slab_shell55_aashto62_view').set_value(view)
            test.selectbox(key='slab_shell55_top65_chart').set_value('Station D/C')
            clean(test)
            assert len(test.get('plotly_chart')) == 1
        test.button(key='slab_shell55_top65_prepare_report').click()
        clean(test)
        assert solver.call_count == 1
        assert test.session_state['slab_shell55_top65_report'][0] == test.session_state[active.RESULT_KEY]['fingerprint']
        pd.testing.assert_frame_equal(original, test.session_state[top.RESULT_KEY]['summary'])


def test_load_basis_form_keeps_page_saves_inputs_and_reuses_unchanged_shell_checks():
    test = app()
    with patch.object(accepted, 'calculate', wraps=accepted.calculate) as solver:
        clean(test)
        test.button(key='slab_shell55_aashto62_calculate').click()
        clean(test)
        original = test.session_state[top.RESULT_KEY]['rows'].copy(deep=True)
        test.selectbox(key='slab_shell55_top65_method').set_value('equivalent_udl')
        test.number_input(key='slab_shell55_top65_ballast').set_value(450.)
        test.number_input(key='slab_shell55_top65_pressure').set_value(80.)
        test.button(key='slab_shell55_aashto62_calculate').click()
        clean(test)
        assert solver.call_count == 1
        assert test.session_state['_nav_analysis_subpage'] == 'Slab Reinforcement'
        result = test.session_state[top.RESULT_KEY]
        assert result['load_basis']['ballast_mm'] == 450.
        assert result['load_basis']['method'] == 'equivalent_udl'
        assert result['load_basis_status'] == 'SOURCE MATCHED'
        pd.testing.assert_frame_equal(original, result['rows'])


def test_result_summary_and_report_use_stored_top_slab_results_only():
    test = app()
    clean(test)
    test.button(key='slab_shell55_aashto62_calculate').click()
    clean(test)
    with patch.object(top, 'calculate', side_effect=AssertionError('solver reran')), \
         patch.object(accepted, 'calculate', side_effect=AssertionError('solver reran')):
        for workspace in ('Result Summary', 'Report / QA'):
            test.session_state['_nav_active_workspace'] = workspace
            clean(test)
            text = '\n'.join(item.value for item in test.markdown)
            assert 'Top slab ULS' in text
