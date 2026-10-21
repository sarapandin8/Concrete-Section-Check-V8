"""Verify the real app's one-calculation stage/Summary/Report handoff.

Run against either a working tree or an independently extracted release ZIP.
The supplied project is read without edits; solver results are runtime-only.
"""
from pathlib import Path
import argparse
import hashlib
import json
import sys
import tempfile
from unittest.mock import patch

from streamlit.testing.v1 import AppTest


def run(project, output):
    root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(root))
    from concrete_pmm_pro.serviceability import girder_deflect69 as engine
    original_hash = hashlib.sha256(project.read_bytes()).hexdigest()
    with tempfile.TemporaryDirectory(prefix='csp-deflect69-handoff-') as temporary:
        wrapper = Path(temporary) / 'handoff_app.py'
        wrapper.write_text(f'''from pathlib import Path
import runpy,sys
import streamlit as st
sys.path.insert(0,{str(root)!r})
from concrete_pmm_pro.io.project_io import apply_project_to_session_state,project_from_json
if not st.session_state.get('_deflect69_handoff_inputs'):
    apply_project_to_session_state(project_from_json(Path({str(project.resolve())!r}).read_text()),st.session_state)
    st.session_state['_nav_active_workspace']='Analysis'
    st.session_state['_nav_analysis_subpage']='SLS Deflection / Camber'
    st.session_state['_deflect69_handoff_inputs']=True
runpy.run_path({str(root/'app.py')!r},run_name='__main__')
''')
        app = AppTest.from_file(str(wrapper), default_timeout=120)
        with patch.object(engine, 'calculate', wraps=engine.calculate) as solver:
            app.run(timeout=120)
            assert not app.exception, [e.message for e in app.exception]
            assert solver.call_count == 0
            app.button(key='girder_deflect69_calculate').click().run(timeout=120)
            assert not app.exception, [e.message for e in app.exception]
            assert solver.call_count == 1
            for stage in ['Construction stage', 'Service stage', 'Transfer stage']:
                app.radio(key='girder_deflect69_ui_stage').set_value(stage).run(timeout=120)
                assert not app.exception, [e.message for e in app.exception]
                assert len(app.get('plotly_chart')) == 1
                assert solver.call_count == 1
            for workspace in ['Result Summary', 'Report / QA', 'Analysis']:
                app.session_state['_nav_active_workspace'] = workspace
                app.run(timeout=120)
                assert not app.exception, [e.message for e in app.exception]
                assert engine.current(app.session_state.filtered_state) is not None
                assert solver.call_count == 1
            result = app.session_state[engine.RESULT_KEY]
    assert hashlib.sha256(project.read_bytes()).hexdigest() == original_hash
    evidence = {'milestone': engine.VERSION, 'actual_full_app': True,
        'original_project_sha256': original_hash, 'source_project_unchanged': True,
        'calculation_invocations': solver.call_count, 'three_stage_navigation': True,
        'summary_and_report_results_current': True, 'hidden_solver_reruns': False,
        'live_source_missing': not result['live_available'],
        'limit_mm': result['limit_mm'], 'status': result['status'],
        'full_deflection_acceptance': result['full_deflection_acceptance']}
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(evidence, indent=2))
    print(json.dumps(evidence, indent=2), flush=True)
    return evidence


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--project', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    run(args.project, args.output)
