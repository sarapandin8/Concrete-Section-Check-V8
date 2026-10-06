"""Real Streamlit/Arrow verification, including the original mixed-row failure.

Run from the project root: python qa/igird_arrowdisplay4_ui_verify.py
"""
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

from concrete_pmm_pro.ui import igird_member_results as mr

logging.getLogger('streamlit.dataframe_util').setLevel(logging.CRITICAL)

setup = '''
import sys
sys.path.insert(0, 'tests')
import streamlit as st
from test_igird_arrowdisplay4 import mixed_member_model
from test_igird_uls6_torsion_general_procedure import _route
from concrete_pmm_pro.io.girder_load_bank import activate_member
from concrete_pmm_pro.ui import igird_member_results as mr
if 'qa_initialized' not in st.session_state:
    st.session_state.update(mixed_member_model())
    activate_member(st.session_state, 'Exterior Girder')
    st.session_state['qa_initialized'] = True
    st.session_state['qa_calls'] = 0
'''

# Remove only the display adapter to reproduce the accepted baseline's failure.
with patch.object(mr, 'result_table_for_display', lambda frame: frame):
    before = AppTest.from_string(setup + '''
mr.render_collection(check_name='Torsion', route=_route(), code_label='AASHTO LRFD 9th Edition')
''', default_timeout=60).run()
    next(b for b in before.button if b.label.startswith('Calculate Torsion — all')).click().run()
    assert before.exception
    assert any('Deck development trace' in e.message for e in before.exception)
    baseline_error = before.exception[0].message

calculate = mr.calculate_member


def counted(*args, **kwargs):
    st.session_state['qa_calls'] += 1
    return calculate(*args, **kwargs)


checks = []
with patch.object(mr, 'calculate_member', counted):
    at = AppTest.from_string(setup + '''
check = st.radio('QA check', ['Flexure', 'Shear', 'Torsion', 'Shear + Torsion'], key='qa_check')
mr.render_collection(check_name=check, route=_route(), code_label='AASHTO LRFD 9th Edition')
''', default_timeout=60).run()
    assert not at.exception
    assert at.session_state['qa_calls'] == 0
    for check in ['Flexure', 'Shear', 'Torsion', 'Shear + Torsion']:
        at.radio(key='qa_check').set_value(check).run()
        next(b for b in at.button if b.label.startswith('Calculate ' + check + ' — all')).click().run()
        assert not at.exception, [e.message for e in at.exception]
        titles = [json.loads(p.proto.spec)['layout']['title']['text'] for p in at.get('plotly_chart')]
        for member in ['Exterior Girder', 'Interior Girder 2']:
            assert any('Girder: ' + member in t for t in titles), titles
        audits = [d.value for d in at.dataframe if 'Deck development trace' in d.value]
        for frame in audits:
            assert frame['Deck development trace'].dropna().map(lambda v: isinstance(v, str)).all()
        if check == 'Torsion':
            assert len(audits) == 2
            for frame in audits:
                assert frame['Deck development trace'].str.startswith('[').any()
                assert frame['Deck development trace'].eq('-').any()
        calls = at.session_state['qa_calls']
        at.run()
        assert not at.exception
        assert at.session_state['qa_calls'] == calls
        if check in {'Shear', 'Torsion'}:
            views = [r for r in at.radio if r.label == 'Chart view']
            assert len(views) == 2
            for view in views:
                view.set_value('Selected case — demand / capacity')
            at.run()
            assert not at.exception
            assert len(at.selectbox) == 2
            assert at.session_state['qa_calls'] == calls
            for selector in at.selectbox:
                selector.set_value(selector.options[-1])
            at.run()
            assert not at.exception
            assert at.session_state['qa_calls'] == calls
        checks.append({'check': check, 'named_girders': 2, 'arrow_exceptions': 0,
                       'redraw_solver_calls': 0, 'audit_tables_with_trace': len(audits)})
    calls = at.session_state['qa_calls']
    bank = at.session_state['igird_uls_member_bank'].copy()
    bank.loc[bank['Girder'].eq('Interior Girder 2'), 'Mux'] = 999.
    at.session_state['igird_uls_member_bank'] = bank
    at.run()
    assert not at.exception
    assert at.session_state['qa_calls'] == calls
    assert any('STALE' in w.value and 'Interior Girder 2' in w.value for w in at.warning)
    assert all('Interior Girder 2' not in json.loads(p.proto.spec)['layout']['title']['text']
               for p in at.get('plotly_chart'))

evidence = {'python': sys.version.split()[0], 'pandas': pd.__version__,
            'streamlit': st.__version__, 'pyarrow': pa.__version__,
            'baseline_error_reproduced': baseline_error, 'checks': checks,
            'stale_member_result_hidden': True}
path = Path(f'qa/evidence/igird_arrowdisplay4/ui_verification_python{sys.version_info.major}{sys.version_info.minor}.json')
path.parent.mkdir(parents=True, exist_ok=True)
path.write_text(json.dumps(evidence, ensure_ascii=False, indent=2) + '\n')
print(json.dumps(evidence, ensure_ascii=False))
