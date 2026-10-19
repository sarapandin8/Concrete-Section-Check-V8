"""Actual app.py acceptance checks on a project and native CSI SLS fixture.

Usage: python qa/igird_sls53_verify.py --project project.json --out /tmp/sls53
Outputs evidence externally; never inserts project results into its source ZIP.
"""
from copy import deepcopy
from io import BytesIO, StringIO
from pathlib import Path
from unittest.mock import patch
import argparse
import csv
import hashlib
import json
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import pandas as pd
import streamlit as st
from streamlit.testing.v1 import AppTest
from concrete_pmm_pro.io import girder_sls_import as source
from concrete_pmm_pro.io.project_io import (
    apply_project_to_session_state, project_from_json, project_to_json, project_from_session_state)
from concrete_pmm_pro.ui import analysis_page as ap, igird_sls53_results as results


def digest(frame):
    return hashlib.sha256(frame.to_csv(index=False, float_format='%.17g').encode()).hexdigest()


def native_import():
    fixture = json.loads((ROOT/'qa/fixtures/CSiBridge_SLS_Girder_Forces_SLSIMPORT23.json').read_text())
    csv_text = StringIO()
    csv.writer(csv_text).writerows(fixture['rows'])
    upload = BytesIO(csv_text.getvalue().encode('utf-8-sig'))
    upload.name = 'native_sls.csv'
    imported, errors = source.parse_files([upload])
    assert not errors, errors
    return imported


def verify(project, out):
    out.mkdir(parents=True, exist_ok=True)
    state = {}
    apply_project_to_session_state(project_from_json(project.read_text()), state)
    evidence = {'version': results.VERSION, 'project_sha256': hashlib.sha256(project.read_bytes()).hexdigest(),
        'native_fixture_rows': 240, 'native_fixture_girders': 2, 'runs': []}
    for native in [False, True]:
        local = deepcopy(state)
        if native:
            source.replace_stage(local, native_import(), stage='Service stage')
        members = source.members(local.get(source.BANK_KEY, [])) or ['Current girder']
        for member in members:
            if native:
                source.activate_member(local, member)
            app = AppTest.from_file(str(ROOT/'app.py'), default_timeout=120)
            for k, v in local.items():
                app.session_state[k] = deepcopy(v)
            app.session_state['_nav_active_workspace'] = 'Analysis'
            app.session_state['_nav_analysis_subpage'] = 'SLS / Stress & Cracking'
            figures = []
            real_plot = st.plotly_chart
            def plot(fig, *args, **kwargs):
                figures.append(fig)
                return real_plot(fig, *args, **kwargs)
            def run():
                app.run(timeout=120)
                assert not app.exception, [e.message for e in app.exception]
                assert not app.error, [e.value for e in app.error]
            started = time.monotonic()
            uls_before = digest(pd.DataFrame(local['beam_uls_loads_table']))
            with patch.object(st, 'plotly_chart', side_effect=plot), patch.object(ap,
                '_girder_full_length_sls_stage_rows', wraps=ap._girder_full_length_sls_stage_rows) as engine:
                run()
                assert engine.call_count == 0 and not figures
                next(b for b in app.button if b.key == 'igird_sls53_calculate').click()
                run()
                assert len(figures) == 1
                calculated_seconds = time.monotonic() - started
                widget_counts = {k: len(getattr(app, k)) for k in
                    ['selectbox', 'radio', 'checkbox', 'number_input', 'expander']}
                result = app.session_state[results.RUNTIME_KEY]
                signature = result['signature']
                summary = deepcopy(result['summary'])
                count = engine.call_count
                assert count == 4
                for stage, stored in result['stages'].items():
                    next(r for r in app.radio if r.label == 'Stage to review').set_value(stage)
                    run()
                    for case in stored['cases']:
                        next(s for s in app.selectbox if s.label == 'Load case to review').set_value(case)
                        run()
                        assert engine.call_count == count
                    if stage == 'Service stage' and any(r.label == 'Concrete component' for r in app.radio):
                        next(r for r in app.radio if r.label == 'Concrete component').set_value('CIP / topping')
                        run()
                    assert app.session_state['result_summary_beam_girder_sls_stage_summary_rows'] == summary
                    assert app.session_state[results.HANDOFF_KEY] == signature
                assert all(list(fig.layout.xaxis.range) == [0., 20.] for fig in figures)
                for workspace in ['Result Summary', 'Report / QA']:
                    app.session_state['_nav_active_workspace'] = workspace
                    run()
                    assert engine.call_count == count
                assert digest(pd.DataFrame(app.session_state['beam_uls_loads_table'])) == uls_before
                exported = project_to_json(project_from_session_state(app.session_state.filtered_state))
                assert results.RUNTIME_KEY not in exported and results.HANDOFF_KEY not in exported
                restored = {}
                apply_project_to_session_state(project_from_json(exported), restored)
                if native:
                    assert source.active_member(restored) == member
                    assert len(restored[source.BANK_KEY]) == 240
            hashes = {}
            for stage, stored in result['stages'].items():
                hashes[stage] = {}
                for case, data in stored['cases'].items():
                    hashes[stage][case] = {'raw': digest(data['raw']), 'split': digest(data['split']),
                        'stations': len(data['raw'])}
            run_record = {'kind': 'native_fixture' if native else 'original_project_auto_loads',
                'member': member, 'calculate_engine_calls': count, 'review_extra_engine_calls': 0,
                'initial_and_calculate_seconds': round(calculated_seconds, 3),
                'summary': summary, 'frame_digests': hashes,
                'widget_counts': widget_counts,
                'uls_unchanged': True, 'json_input_only': True, 'summary_report_read_only': True}
            evidence['runs'].append(run_record)
    (out/'app_checks.json').write_text(json.dumps(evidence, ensure_ascii=False, indent=2, default=str))
    print(json.dumps({'status': 'PASS', 'runs': len(evidence['runs']), 'output': str(out/'app_checks.json')}))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--project', required=True, type=Path)
    parser.add_argument('--out', required=True, type=Path)
    args = parser.parse_args()
    verify(args.project, args.out)
