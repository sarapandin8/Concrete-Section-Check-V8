"""Real Streamlit case/member controls, stored-result integrity and chart capture.

Run from the project root: python qa/igird_casecontrol5_ui_verify.py
The hypothetical two-girder fixture is QA data, not a design approval.
"""
from contextlib import ExitStack
from copy import deepcopy
import json
import logging
from pathlib import Path
import sys
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, 'tests')

import pandas as pd
import pyarrow as pa
import streamlit as st
from streamlit.testing.v1 import AppTest

from concrete_pmm_pro.io.girder_load_bank import BANK_KEY, ACTIVE_KEY
from concrete_pmm_pro.ui import analysis_page as ap, igird_member_results as mr
from concrete_pmm_pro.ui.igird_case_review import FRAME_KEYS, AUTO_CASE, ALL_CASES, controlling_result
from concrete_pmm_pro.ui.result_table_display import result_table_for_display

OUT = Path('qa/evidence/igird_compact6')
OUT.mkdir(parents=True, exist_ok=True)
logging.getLogger('streamlit').setLevel(logging.ERROR)

setup = '''
import sys
sys.path.insert(0, 'tests')
import streamlit as st
from test_igird_casecontrol5 import review_model
from test_igird_uls6_torsion_general_procedure import _route
from concrete_pmm_pro.io.girder_load_bank import activate_member
from concrete_pmm_pro.ui import igird_member_results as mr
if 'qa_initialized' not in st.session_state:
    st.session_state.update(review_model())
    activate_member(st.session_state, 'Exterior Girder')
    st.session_state['qa_initialized'] = True
    st.session_state['qa_calls'] = 0
check = st.radio('QA check', ['Flexure', 'Shear', 'Torsion', 'Shear + Torsion'], key='qa_check')
mr.render_collection(check_name=check, route=_route(), code_label='AASHTO LRFD 9th Edition')
'''

calculate = mr.calculate_member
render = ap._render_beam_uls_browser_plotly_figure
figures = []


def counted(*args, **kwargs):
    st.session_state['qa_calls'] += 1
    return calculate(*args, **kwargs)


def capture(fig, **kwargs):
    figures.append(deepcopy(fig))
    render(fig, **kwargs)


def ok(at):
    assert not at.exception, [e.message for e in at.exception]


def rerun(at):
    figures.clear()
    at.run(timeout=60)
    ok(at)


def element(items, label):
    return next(item for item in items if item.label == label)


def audit(at, member):
    expander = element(at.expander, 'Stored check rows / source audit — ' + member)
    assert len(expander.dataframe) == 1
    return expander.dataframe[0].value


def check_display(at, check, shown, cases):
    for member in shown:
        stored = at.session_state[mr.CACHE_KEY][member][check]['result'][FRAME_KEYS[check]]
        expected = stored if cases[member] is None else stored.loc[stored['Case'].eq(cases[member])]
        pd.testing.assert_frame_equal(audit(at, member).reset_index(drop=True), result_table_for_display(expected).reset_index(drop=True),
                                      check_dtype=False, check_exact=True)
        member_figures = [fig for fig in figures if fig.layout.title.text.startswith('Girder: ' + member + '<br>')]
        assert member_figures, [fig.layout.title.text for fig in figures]
        if cases[member] is not None:
            assert all(fig.layout.meta['review_case'] == cases[member] for fig in member_figures)
        assert all(tuple(fig.layout.xaxis.range) == (0., 20.) for fig in member_figures)
    for member in {'Exterior Girder', 'Interior Girder 2'} - set(shown):
        assert all(not fig.layout.title.text.startswith('Girder: ' + member + '<br>') for fig in figures)


def readonly_guards(stack):
    for function in ('_beam_uls_calculate_selected_check', '_beam_uls_flexure_preview_dataframe',
                     '_beam_uls_final_composite_preparation', '_beam_uls_igird_torsion_diagram_capacity_dataframe'):
        stack.enter_context(patch.object(ap, function, side_effect=AssertionError('Result review must not solve: ' + function)))


records = []
with patch.object(mr, 'calculate_member', counted), patch.object(ap, '_render_beam_uls_browser_plotly_figure', capture):
    at = AppTest.from_string(setup, default_timeout=60).run()
    ok(at)
    assert at.session_state['qa_calls'] == 0
    bank_before = deepcopy(at.session_state[BANK_KEY])
    active_before = at.session_state[ACTIVE_KEY]
    loads_before = deepcopy(at.session_state['beam_uls_loads_table'])
    for check in FRAME_KEYS:
        at.radio(key='qa_check').set_value(check)
        rerun(at)
        figures.clear()
        next(button for button in at.button if button.label.startswith('Calculate ' + check + ' — all')).click().run()
        ok(at)
        calls = at.session_state['qa_calls']
        cache_before = deepcopy(at.session_state[mr.CACHE_KEY])
        names = list(mr.member_inputs(at.session_state.filtered_state))
        auto = {member: controlling_result(cache_before[member][check]['result'][FRAME_KEYS[check]], check)['row']['Case']
                for member in names}
        check_display(at, check, names, auto)
        # Capture the real review figures, including girder and selected case identity.
        for i, fig in enumerate(figures):
            stem = check.lower().replace(' + ', '_').replace(' ', '_') + '_auto_' + str(i)
            fig.write_json(str(OUT / (stem + '.plotly.json')))
            fig.write_image(str(OUT / (stem + '.png')), width=1440, height=560, scale=1)
        with ExitStack() as stack:
            readonly_guards(stack)
            # Each member's named case must change both tables and all figures.
            for suffix in ('ULS1', 'ULS2'):
                chosen = {member: member + ' / ' + suffix for member in names}
                for member in names:
                    element(at.selectbox, 'Load case to review — ' + member).set_value(chosen[member])
                rerun(at)
                check_display(at, check, names, chosen)
                if check in {'Shear', 'Torsion'}:
                    for view in [radio for radio in at.radio if radio.label == 'Chart view']:
                        view.set_value('Selected case — demand / capacity')
                    rerun(at)
                    check_display(at, check, names, chosen)
                    assert not any(selector.label == 'Case for diagram' for selector in at.selectbox)
                    for view in [radio for radio in at.radio if radio.label == 'Chart view']:
                        view.set_value('Overview — utilization')
                    rerun(at)
            for member in names:
                element(at.selectbox, 'Load case to review — ' + member).set_value(ALL_CASES)
            rerun(at)
            check_display(at, check, names, dict.fromkeys(names))
            if check == 'Flexure':
                for expander in at.expander:
                    if expander.label.startswith('Calculation trace / Equations — Final Composite'):
                        expander.selectbox[0].set_value(5)
                rerun(at)
                for member in names:
                    element(at.selectbox, 'Load case to review — ' + member).set_value(member + ' / ULS2')
                rerun(at)
                check_display(at, check, names, {member: member + ' / ULS2' for member in names})
                assert all(selector.value in range(3) for selector in at.selectbox if selector.label == 'Stored station')
            # Every girder remains available in a collapsed member panel.
            assert not any(radio.label == 'Girder results view' for radio in at.radio)
            assert not any(selector.label == 'Girder to review' for selector in at.selectbox)
            for member in names:
                panel = element(at.expander,'Girder: '+member)
                assert not panel.proto.expanded
                assert len(panel.get('plotly_chart')) >= 1
                element(at.selectbox,'Load case to review — '+member).set_value(AUTO_CASE)
            rerun(at)
            check_display(at,check,names,auto)
            assert at.session_state[ACTIVE_KEY] == active_before
            # The legacy route is now explicit and defaults to off per check.
            details = at.toggle(key='igird_compact_details_'+check)
            assert not details.value
            assert at.session_state['qa_calls'] == calls
            for member in names:
                for key, frame in cache_before[member][check]['result'].items():
                    if isinstance(frame, pd.DataFrame):
                        pd.testing.assert_frame_equal(at.session_state[mr.CACHE_KEY][member][check]['result'][key], frame,
                                                      check_exact=True)
            pd.testing.assert_frame_equal(at.session_state[BANK_KEY], bank_before, check_exact=True)
            pd.testing.assert_frame_equal(at.session_state['beam_uls_loads_table'], loads_before, check_exact=True)
        records.append({'check': check, 'automatic_case_by_girder': auto, 'named_cases_per_girder': 2,
                        'all_case_review': True, 'all_girder_panels_collapsed': True,
                        'review_solver_calls': 0, 'stored_results_and_loads_unchanged': True})
    # Old three-mode widget state must not bypass the unified collection.
    at.session_state['igird_member_results_view'] = 'Selected girder — detailed checks'
    rerun(at)
    assert len([expander for expander in at.expander if expander.label.startswith('Girder: ')]) == 2
    assert not at.toggle(key='igird_compact_details_Shear + Torsion').value
    # Changing one member's forces invalidates only that member's displayed results.
    with ExitStack() as stack:
        readonly_guards(stack)
        bank = deepcopy(at.session_state[BANK_KEY])
        bank.loc[bank['Girder'].eq('Interior Girder 2'), 'Mux'] = 999.
        at.session_state[BANK_KEY] = bank
        rerun(at)
        assert any('STALE' in warning.value and 'Interior Girder 2' in warning.value for warning in at.warning)
        summary = next(frame.value for frame in at.dataframe if 'Result state' in frame.value)
        stale = summary.loc[summary.Girder.eq('Interior Girder 2')].iloc[0]
        assert stale['Result state'] == 'STALE' and pd.isna(stale['D/C or ratio'])
        assert all('Girder: Interior Girder 2<br>' not in fig.layout.title.text for fig in figures)
        assert at.session_state['qa_calls'] == calls

evidence = {'release': 'IGIRDER.COMPACT6', 'status': 'PASS', 'python': sys.version.split()[0],
            'pandas': pd.__version__, 'streamlit': st.__version__, 'pyarrow': pa.__version__,
            'checks': records, 'stale_member_summary_has_no_old_ratio': True,
            'streamlit_exceptions': 0, 'scope': 'Real Streamlit collection workspace with controlled QA fixture; not live deployment'}
(OUT / 'ui_verification.json').write_text(json.dumps(evidence, ensure_ascii=False, indent=2) + '\n')
print(json.dumps(evidence, ensure_ascii=False), flush=True)
