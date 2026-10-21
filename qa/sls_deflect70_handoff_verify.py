"""Real-app upload input and stage/girder/Summary/Report handoff verification."""
from pathlib import Path
import argparse
import hashlib
import json
import sys
import tempfile
from unittest.mock import patch

from streamlit.testing.v1 import AppTest


def run(project, workbook, output):
    root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(root))
    from concrete_pmm_pro.serviceability import girder_deflect70 as engine
    hashes = {str(p): hashlib.sha256(p.read_bytes()).hexdigest() for p in [project, workbook]}
    with tempfile.TemporaryDirectory(prefix='csp-deflect70-handoff-') as temporary:
        wrapper = Path(temporary) / 'handoff_app.py'
        wrapper.write_text(f'''from pathlib import Path
import runpy,sys
import streamlit as st
sys.path.insert(0,{str(root)!r})
from concrete_pmm_pro.io.project_io import apply_project_to_session_state,project_from_json
from concrete_pmm_pro.io.girder_deflect70 import parse_workbook,BANK_KEY
if not st.session_state.get('_deflect70_handoff_inputs'):
    apply_project_to_session_state(project_from_json(Path({str(project.resolve())!r}).read_text()),st.session_state)
    path=Path({str(workbook.resolve())!r})
    st.session_state[BANK_KEY]=parse_workbook(path.read_bytes(),path.name)
    st.session_state['_nav_active_workspace']='Analysis'
    st.session_state['_nav_analysis_subpage']='SLS Deflection / Camber'
    st.session_state['_deflect70_handoff_inputs']=True
runpy.run_path({str(root/'app.py')!r},run_name='__main__')
''')
        app = AppTest.from_file(str(wrapper), default_timeout=120)
        with patch.object(engine, 'calculate', wraps=engine.calculate) as solver:
            app.run(timeout=120)
            assert not app.exception, [e.message for e in app.exception]
            assert solver.call_count == 0
            app.button(key='girder_deflect70_calculate').click().run(timeout=120)
            assert not app.exception, [e.message for e in app.exception]
            assert solver.call_count == 1
            for stage in ['Construction stage', 'Service stage', 'Transfer stage', 'Service stage']:
                app.radio(key='girder_deflect70_ui_stage').set_value(stage).run(timeout=120)
                assert not app.exception, [e.message for e in app.exception]
                assert len(app.get('plotly_chart')) == 1 and solver.call_count == 1
            app.selectbox(key='girder_deflect70_ui_girder').set_value('Interior Girder 2').run(timeout=120)
            for workspace in ['Result Summary', 'Report / QA', 'Analysis']:
                app.session_state['_nav_active_workspace'] = workspace
                app.run(timeout=120)
                assert not app.exception, [e.message for e in app.exception]
                assert engine.current(app.session_state.filtered_state) is not None
                assert solver.call_count == 1
            result = app.session_state[engine.RESULT_KEY]
    assert all(hashlib.sha256(Path(p).read_bytes()).hexdigest() == h for p, h in hashes.items())
    evidence = {'milestone': engine.VERSION, 'actual_full_app': True, 'source_files_unchanged': True,
        'calculation_invocations': solver.call_count, 'three_stage_and_girder_navigation': True,
        'summary_and_report_results_current': True, 'hidden_solver_reruns': False,
        'service_import_available': result['service_available'], 'girders': result['girders'],
        'status': result['status'], 'full_deflection_acceptance': False}
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(evidence, indent=2))
    print(json.dumps(evidence, indent=2), flush=True)
    return evidence


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--project', type=Path, required=True)
    parser.add_argument('--workbook', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    run(args.project, args.workbook, args.output)
