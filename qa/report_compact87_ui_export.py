"""Exercise the actual Streamlit report button with a calculated QA state.

The input pickle must be a trusted, locally generated QA fixture. No figure
renderer, report builder, document layout or download payload is replaced.
"""
from __future__ import annotations

import argparse
from copy import deepcopy
from hashlib import sha256
from io import BytesIO
import json
import logging
from pathlib import Path
import pickle
from unittest.mock import patch
from zipfile import ZipFile

from docx import Document
from streamlit.runtime.memory_media_file_storage import MemoryMediaFileStorage
from streamlit.testing.v1 import AppTest

from concrete_pmm_pro.ui import analysis_page as ap, igird_member_results as mr
from concrete_pmm_pro.ui.bg40_report import ARTIFACT_KEY
from tests.test_report_all82 import no_solvers


def main():
    for name in ('streamlit.runtime.scriptrunner_utils.script_run_context',
                 'streamlit.runtime.memory_media_file_storage',
                 'streamlit.runtime.media_file_manager',
                 'streamlit.runtime.scriptrunner.script_runner',
                 'streamlit.deprecation_util', 'streamlit.dataframe_util'):
        logging.getLogger(name).setLevel(logging.ERROR)
    parser = argparse.ArgumentParser()
    parser.add_argument('--state', required=True, type=Path)
    parser.add_argument('--out', required=True, type=Path)
    args = parser.parse_args()
    with args.state.open('rb') as source:
        state, example = pickle.load(source)
    state = deepcopy(state)
    meta = example.metadata
    state.update(report_title=meta.report_title, project_name=meta.project_name,
                 report_prepared_by=meta.prepared_by, report_checked_by=meta.checked_by,
                 report_revision=meta.revision, report_date=meta.report_date,
                 report_note=meta.note)
    # Previously saved content choices must not opt out of the full default.
    state.update(bg40_80_figures=False, report_include_figures=False,
                 report_include_appendices=False, report_max_table_rows=5)
    app = AppTest.from_file(str(Path(__file__).resolve().parents[1] / 'app.py'), default_timeout=600)
    for key, value in state.items():
        app.session_state[key] = value
    app.session_state['_nav_active_workspace'] = 'Report / QA'
    print('Opening the actual Report / QA workspace', flush=True)
    app.run(timeout=600)
    assert not app.exception, [x.message for x in app.exception]
    assert not app.checkbox
    assert not any(x.label == 'Build Draft Word Report' for x in app.button)
    captured = []
    load_file = MemoryMediaFileStorage.load_and_get_id
    def capture_download(self, data, mimetype, kind, filename=None):
        if filename == 'Concrete_Section_Pro_Calculation_Report_BG40.docx':
            captured.append(data)
        return load_file(self, data, mimetype, kind, filename)
    print('Clicking Create Word report; all real figures are rendered', flush=True)
    next(x for x in app.button if x.key == 'bg40_80_build').click()
    with no_solvers(), patch.object(mr, 'calculate_member', side_effect=AssertionError('Report cannot solve')), \
         patch.object(ap, '_beam_uls_calculate_selected_check', side_effect=AssertionError('Report cannot solve')), \
         patch.object(ap, '_girder_full_length_sls_stage_rows', side_effect=AssertionError('Report cannot solve stress')), \
         patch.object(MemoryMediaFileStorage, 'load_and_get_id', capture_download):
        app.run(timeout=600)
    assert not app.exception, [x.message for x in app.exception]
    assert not app.error, ([x.value for x in app.error], [x.value for x in app.text])
    artifact = app.session_state[ARTIFACT_KEY]
    download = next(x for x in app.get('download_button') if x.key == 'bg40_80_download')
    assert download.proto.url and captured
    assert captured[-1] == artifact['docx'], 'The download payload must be the complete Word file'
    assert all(f['status'] == 'EMBEDDED' for f in artifact['figures'])
    document = Document(BytesIO(captured[-1]))
    assert len(document.inline_shapes) == len(artifact['figures'])
    assert document._element.xpath('.//m:oMath')
    from concrete_pmm_pro.reporting.bg40_template import ROOT
    with ZipFile(BytesIO(captured[-1])) as actual, ZipFile(ROOT / 'BG40_R10_Template.docx') as template:
        assert actual.read('word/styles.xml') == template.read('word/styles.xml')
        assert actual.read('word/theme/theme1.xml') == template.read('word/theme/theme1.xml')
    args.out.mkdir(parents=True, exist_ok=True)
    report_path = args.out / 'CSP87_Compact_Report_From_App.docx'
    report_path.write_bytes(captured[-1])
    assert artifact['compact'] and artifact['evidence'] is None
    assert not any(x.key == 'bg40_80_evidence' for x in app.get('download_button'))
    # Source archive must never delay the default Word export.
    for _ in range(3):
        with patch('concrete_pmm_pro.ui.bg40_report.build_workflow_report', side_effect=AssertionError('Idle rebuild')), no_solvers():
            app.run(timeout=600)
        assert not app.exception
    if example.workflow_key == 'column':
        next(x for x in app.button if x.key == 'bg40_87_prepare_evidence').click()
        with no_solvers():
            app.run(timeout=600)
        assert not app.exception and not app.error
        assert app.session_state[ARTIFACT_KEY]['evidence']
        with ZipFile(BytesIO(app.session_state[ARTIFACT_KEY]['evidence'])) as evidence:
            assert evidence.read('Calculation_Report_BG40.docx') == artifact['docx']
    result = {'download_payload_sha256': sha256(captured[-1]).hexdigest(),
        'download_payload_matches_artifact': True, 'native_static_renderer': True,
        'post_export_document_edits': False, 'content_selection_widgets': len(app.checkbox),
        'figures': len(document.inline_shapes), 'native_equations': len(document._element.xpath('.//m:oMath')),
        'compact_default': True, 'automatic_source_archive': False, 'reopens_without_rebuild': 3,
        'tables': len(document.tables), 'chapters': artifact['chapters'],
        'engineering_status': artifact['status'], 'original_styles_and_theme_preserved': True,
        'workflow': example.workflow_key, 'source_fixture': args.state.name}
    (args.out / 'UI_Export_Validation.json').write_text(json.dumps(result, indent=2), encoding='utf-8')
    print(json.dumps(result, indent=2), flush=True)


if __name__ == '__main__':
    main()
