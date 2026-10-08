"""Reports retain actual member/case actions, control and unresolved gates."""
from copy import deepcopy
from contextlib import ExitStack
from pathlib import Path
from unittest.mock import patch

import pandas as pd
import pytest

from concrete_pmm_pro.ui import analysis_page as ap, igird_member_results as mr
from concrete_pmm_pro.ui import igird_uls_report as report
from concrete_pmm_pro.ui.igird_case_review import FRAME_KEYS, controlling_result
from concrete_pmm_pro.io.girder_load_bank import activate_member, ACTIVE_KEY
from concrete_pmm_pro.io.project_io import apply_project_to_session_state, project_from_json
from test_igird_casecontrol5 import review_model


@pytest.fixture(scope='module')
def calculated_state():
    state = {}
    apply_project_to_session_state(project_from_json(Path('qa/evidence/igird_vtqa1/hypothetical_verified_input_qa.json').read_text()), state)
    state.update(review_model())
    activate_member(state, 'Exterior Girder')
    route = ap._beam_uls_strength_route_from_state(state, is_bridge=True, is_building=False)
    state[mr.CACHE_KEY] = {}
    for member, rows in mr.member_inputs(state).items():
        state[mr.CACHE_KEY][member] = {}
        for check in FRAME_KEYS:
            result = mr.calculate_member(state, rows, check_name=check, route=route)
            assert not result.get('error'), result
            state[mr.CACHE_KEY][member][check] = {
                'input_hash': mr.result_hash(state, rows, check_name=check, route=route), 'result': result}
    return state


@pytest.fixture
def state(calculated_state):
    return deepcopy(calculated_state)


def no_report_solvers():
    stack = ExitStack()
    for name in ('_beam_uls_calculate_selected_check', '_beam_uls_flexure_preview_dataframe',
                 '_beam_uls_igird_torsion_diagram_capacity_dataframe'):
        stack.enter_context(patch.object(ap, name, side_effect=AssertionError('Report cannot solve')))
    stack.enter_context(patch.object(mr, 'calculate_member', side_effect=AssertionError('Report cannot calculate members')))
    return stack


@pytest.mark.parametrize('check', list(FRAME_KEYS))
def test_two_members_two_cases_use_stored_production_values_without_solving(state, check):
    before = deepcopy(state)
    with no_report_solvers():
        packages = report.current_check_packages(state, check)
        assert set(packages) == {'Exterior Girder', 'Interior Girder 2'}
        for member, package in packages.items():
            for case in (member+' / ULS1', member+' / ULS2'):
                fig = report.make_package_figure(state, package, member=member,
                    check_name=check, code_label='AASHTO LRFD 9th Edition', case=case)
                assert fig.layout.meta['igird_report_member'] == member
                assert fig.layout.meta['igird_report_case'] == case
                assert fig.layout.meta['review_case'] == case
                assert fig.layout.title.text.startswith('Girder: '+member+'<br>')
                assert fig.layout.xaxis.range == (0., 20.)
                assert len(fig.layout.meta['igird_report_note']) == 3
                if check == 'Shear':
                    assert not any(str(t.name).startswith('Demand Vuy') for t in fig.data)
                    assert any(t.name == 'Vu demand' for t in fig.data)
                    assert case in next(iter(fig.layout.meta['shear_case_legend'].values()))
                for trace in fig.data:
                    if str(trace.name).startswith(('φMn', '±φVn', '±φTn', 'Max D/C')):
                        assert all(row[0] == case for row in trace.customdata)
                frame = package['result'][FRAME_KEYS[check]]
                control = controlling_result(frame.loc[frame['Case'].eq(case)], check)
                stored = fig.layout.meta['igird_report_selected_control']
                assert stored['Basis'] == control['basis']
                assert stored['Station'] == str((control['row'] or {}).get('Governing x', '-'))
    assert state[ACTIVE_KEY] == before[ACTIVE_KEY]
    pd.testing.assert_frame_equal(state['igird_uls_member_bank'], before['igird_uls_member_bank'], check_exact=True)
    pd.testing.assert_frame_equal(state['beam_uls_loads_table'], before['beam_uls_loads_table'], check_exact=True)
    for member, checks in state[mr.CACHE_KEY].items():
        for name, entry in checks.items():
            for key, value in entry['result'].items():
                old = before[mr.CACHE_KEY][member][name]['result'][key]
                if isinstance(value, pd.DataFrame):
                    pd.testing.assert_frame_equal(value, old, check_exact=True)
                else:
                    assert value == old


@pytest.mark.parametrize('check', list(FRAME_KEYS))
def test_unsaved_active_load_edits_hide_stale_diagrams_without_switching_member(state, check):
    state['beam_uls_loads_table'].loc[:, 'Mux'] = 987654.
    assert set(report.current_check_packages(state, check)) == {'Interior Girder 2'}
    assert report.make_current_report_figure(state, check_name=check,
        member='Exterior Girder', code_label='QA') is None


@pytest.mark.parametrize('check', list(FRAME_KEYS))
def test_old_versions_are_hidden_and_single_table_manual_cache_remains_supported(state, check):
    member = 'Exterior Girder'
    entry = state[mr.CACHE_KEY][member][check]
    owner = report.CHECK_LABELS[check]
    ap._beam_uls_store_manual_result(state, owner, input_hash=entry['input_hash'], result=entry['result'])
    state[mr.CACHE_KEY] = {}
    state['igird_uls_member_bank'] = []
    assert set(report.current_check_packages(state, check)) == {member}
    assert report.make_current_report_figure(state, check_name=check, member=member, code_label='QA') is not None
    state[ap._BEAM_ULS_MANUAL_CALC_CACHE_KEY][owner]['result_version'] = 'old'
    assert not report.current_check_packages(state, check)


@pytest.mark.parametrize('check', list(FRAME_KEYS))
def test_automatic_report_case_is_the_actual_control_and_unknown_case_is_rejected(state, check):
    package = report.current_check_packages(state, check)['Exterior Girder']
    control = controlling_result(package['result'][FRAME_KEYS[check]], check)
    fig = report.make_package_figure(state, package, member='Exterior Girder', check_name=check, code_label='QA')
    assert fig.layout.meta['igird_report_case'] == control['row']['Case']
    assert report.make_package_figure(state, package, member='Exterior Girder',
        check_name=check, code_label='QA', case='Unrelated case') is None


def test_selected_passing_case_does_not_hide_failure_in_another_case(state):
    package = report.current_check_packages(state, 'Flexure')['Exterior Girder']
    frame = package['result']['flexure_preview_df']
    frame.loc[frame.Case.eq('Exterior Girder / ULS1'), 'Status'] = 'FAIL'
    frame.loc[frame.Case.eq('Exterior Girder / ULS2'), 'Status'] = 'PASS'
    fig = report.make_package_figure(state, package, member='Exterior Girder',
        check_name='Flexure', code_label='QA', case='Exterior Girder / ULS2')
    assert fig.layout.meta['igird_report_selected_control']['Failed rows'] == 0
    assert fig.layout.meta['igird_report_member_control']['Failed rows'] > 0
    assert 'All cases:' in fig.layout.meta['igird_report_note'][2]
    assert 'FAIL' in fig.layout.meta['igird_report_note'][2]


def test_combined_missing_numeric_row_remains_a_gap_and_source_review(state):
    package = report.current_check_packages(state, 'Shear + Torsion')['Exterior Girder']
    frame = package['result']['combined_vt_df']
    selected = frame.Case.eq('Exterior Girder / ULS2') & frame['Governing x'].eq('10.000 m')
    assert selected.any()
    for column in ('Stress D/C value', 'Transverse D/C value', 'Longitudinal D/C value', 'Spacing D/C', 'Overall D/C value'):
        frame.loc[selected, column] = float('nan')
    frame.loc[selected, 'Status'] = 'REVIEW'
    frame.loc[selected, 'Calculation status'] = 'PARTIAL'
    fig = report.make_package_figure(state, package, member='Exterior Girder', check_name='Shear + Torsion',
        code_label='QA', case='Exterior Girder / ULS2')
    assert fig.layout.meta['overview_gap_stations'][0]['classification'] == 'UNAVAILABLE'
    trace = next(t for t in fig.data if t.name == 'Max D/C')
    assert pd.isna(trace.y[list(trace.x).index(10.)])
    assert trace.connectgaps is False
    assert fig.layout.meta['igird_report_selected_control']['Rows requiring review'] > 0


def test_error_or_empty_results_are_not_reportable(state):
    state[mr.CACHE_KEY]['Exterior Girder']['Shear']['result'] = {'error': 'Missing model'}
    state[mr.CACHE_KEY]['Interior Girder 2']['Shear']['result']['shear_check_df'] = pd.DataFrame()
    assert not report.current_check_packages(state, 'Shear')
    assert not report.current_check_packages({'section_preset_key': 'other'}, 'Torsion')


def test_torsion_without_finite_resistance_is_labelled_as_investigation_only(state):
    package = report.current_check_packages(state, 'Torsion')['Exterior Girder']
    package['result']['torsion_diagram_capacity_df'].loc[:, 'φTn kN-m'] = float('nan')
    before = package['result']['torsion_check_df'].copy(deep=True)
    fig = report.make_package_figure(state, package, member='Exterior Girder',
        check_name='Torsion', code_label='QA', case='Exterior Girder / ULS1')
    assert 'investigation threshold' in fig.layout.meta['igird_report_note'][0]
    assert 'φTn is unavailable' in fig.layout.meta['igird_report_note'][0]
    pd.testing.assert_frame_equal(package['result']['torsion_check_df'], before, check_exact=True)
