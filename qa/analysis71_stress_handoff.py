"""Verify actual-project SLS stress navigation is read-only and stays current."""
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
    from concrete_pmm_pro.ui import analysis_page as ap, igird_sls53_results as stress
    before = hashlib.sha256(project.read_bytes()).hexdigest()
    with tempfile.TemporaryDirectory(prefix='csp-analysis71-stress-') as temporary:
        wrapper = Path(temporary)/'stress_app.py'
        wrapper.write_text(f'''from pathlib import Path
import runpy,sys
import streamlit as st
sys.path.insert(0,{str(root)!r})
from concrete_pmm_pro.io.project_io import apply_project_to_session_state,project_from_json
if not st.session_state.get('_qa71_stress_loaded'):
    apply_project_to_session_state(project_from_json(Path({str(project.resolve())!r}).read_text()),st.session_state)
    st.session_state['_nav_active_workspace']='Analysis'
    st.session_state['_nav_analysis_subpage']='SLS / Stress & Cracking'
    st.session_state['_qa71_stress_loaded']=True
runpy.run_path({str(root/'app.py')!r},run_name='__main__')
''')
        app = AppTest.from_file(str(wrapper), default_timeout=120)
        with patch.object(ap, '_girder_full_length_sls_stage_rows', wraps=ap._girder_full_length_sls_stage_rows) as solver:
            app.run(timeout=120)
            assert not app.exception, [e.message for e in app.exception]
            assert solver.call_count == 0
            app.button(key='igird_sls53_calculate').click().run(timeout=120)
            assert not app.exception, [e.message for e in app.exception]
            calculated = solver.call_count
            assert calculated == 4
            original = stress.fingerprint(app.session_state.filtered_state)
            route_states = []
            for workspace in ['Result Summary', 'Report / QA', 'Analysis']:
                app.session_state['_nav_active_workspace'] = workspace
                app.run(timeout=120)
                assert not app.exception, [e.message for e in app.exception]
                current = stress.current(app.session_state.filtered_state) is not None
                assert current and solver.call_count == calculated
                assert stress.fingerprint(app.session_state.filtered_state) == original
                route_states.append({'workspace': workspace, 'current': current, 'stage_engine_calls': solver.call_count})
    assert hashlib.sha256(project.read_bytes()).hexdigest() == before
    evidence = {'actual_full_app': True, 'source_sha256': before, 'source_file_modified': False,
        'calculate_commands': 1, 'stage_engine_calls': calculated, 'hidden_solver_reruns': False,
        'input_fingerprint_unchanged_on_navigation': True, 'routes': route_states}
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
