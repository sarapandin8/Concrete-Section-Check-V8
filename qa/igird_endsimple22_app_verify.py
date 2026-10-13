"""Actual app.py: simple end dimensions, declared concurrent forces and manual ULS."""
from copy import deepcopy
from io import BytesIO
from pathlib import Path
from unittest.mock import patch
import argparse
import json
import pickle
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import pandas as pd
from streamlit.testing.v1 import AppTest
from concrete_pmm_pro.analysis.igird_end_sections import SETTINGS_KEY, cut_ends
from concrete_pmm_pro.io.project_io import (
    apply_project_to_session_state, project_from_json,
    project_from_session_state, project_to_json,
)
from concrete_pmm_pro.io.girder_csi_import import source_info
from concrete_pmm_pro.io.girder_load_bank import BANK_KEY
from concrete_pmm_pro.ui.girder_csi_import import UPLOAD_LABEL
from concrete_pmm_pro.ui import analysis_page as ap, igird_member_results as mr
from concrete_pmm_pro.ui.igird_combined_vt import concurrent_source_allowed

parser = argparse.ArgumentParser()
parser.add_argument('--internal', required=True)
args = parser.parse_args()
internal = Path(args.internal).resolve()
assert not internal.is_relative_to(ROOT)
internal.mkdir(parents=True, exist_ok=True)

state = {}
apply_project_to_session_state(project_from_json(
    (ROOT / 'qa/evidence/igird_vtqa1/hypothetical_verified_input_qa.json').read_text()), state)
state['_nav_active_workspace'] = 'Loads'


class Upload(BytesIO):
    def __init__(self):
        super().__init__((ROOT / 'qa/fixtures/CSiBridge_Bridge_Object_Girder_Forces_CSIIMPORT14.xlsx').read_bytes())
        self.name = 'native.xlsx'


def upload(label, *args, **kwargs):
    return [Upload()] if label == UPLOAD_LABEL else ([] if kwargs.get('accept_multiple_files') else None)


at = AppTest.from_file(str(ROOT / 'app.py'), default_timeout=240)
for key, value in state.items():
    at.session_state[key] = deepcopy(value)


def run():
    at.run(timeout=240)
    assert not at.exception, [e.message for e in at.exception]


def config():
    return at.session_state['section_parameters'][SETTINGS_KEY]


def number(label, value):
    next(x for x in at.number_input if x.label == label).set_value(value)
    run()


def canonical(frame):
    frame = pd.DataFrame(frame).copy(deep=True)
    for key in ['Station x (m)', 'Mux', 'Nu', 'Vuy', 'Tu', 'Muy', 'Vux']:
        frame[key] = pd.to_numeric(frame[key]).astype(float)
    return frame.reset_index(drop=True)


records = {}
with patch('streamlit.file_uploader', side_effect=upload), patch.object(mr, 'calculate_member', wraps=mr.calculate_member) as calculate:
    run()
    next(x for x in at.radio if x.label == 'Force source').set_value('CSI Correspondence'); run()
    next(x for x in at.button if x.label == 'Import loads').click(); run()
    bank = canonical(at.session_state[BANK_KEY])
    assert len(bank) == 640 and bank.apply(lambda r: concurrent_source_allowed(source_info(r)), axis=1).all()
    records['importsimple21_preserved'] = True

    at.session_state['_nav_active_workspace'] = 'Sections'; run()
    next(x for x in at.checkbox if x.label == 'Enable solid precast end sections').check(); run()
    assert config()['same_ends'] and config()['coordinate_mode'] == 'span'
    assert not any('physical end x' in x.label for x in at.number_input)
    assert config()['left_end_x_m'] == 0 and config()['right_end_x_m'] == 20
    assert not any(config()[key] for key in ('hoop_confirmed', 'd_region_confirmed', 'load_reference_confirmed'))
    number('Solid length at each end (m)', 1.6)
    assert config()['left_solid_m'] == config()['right_solid_m'] == 1.6
    number('Solid length at each end (m)', 1.5)
    assert calculate.call_count == 0
    saved = project_to_json(project_from_session_state(at.session_state.filtered_state))
    restored = {}
    apply_project_to_session_state(project_from_json(saved), restored)
    assert restored['section_parameters'][SETTINGS_KEY] == config()
    assert cut_ends(restored['section_parameters'], 20) == (0.0, 20.0)
    assert '_igird_endsection_local_x' not in saved
    records['simple_input_and_project_roundtrip'] = True

    # External visual QA checkpoint; do not put browser screenshots/checkpoints in the release.
    buttons = {b.key for b in at.button}
    (internal / 'builder_seed.pkl').write_bytes(pickle.dumps({
        k: v for k, v in at.session_state.filtered_state.items() if k not in buttons
    }))

    at.session_state['_nav_active_workspace'] = 'Analysis'; run()
    next(x for x in at.radio if x.label == 'ULS check to calculate').set_value('Shear + Torsion'); run()
    assert calculate.call_count == 0
    print('Full app input flow PASS; starting manual V+T for two girders.', flush=True)
    next(x for x in at.button if x.label.startswith('Calculate Shear + Torsion — all')).click(); run()
    assert calculate.call_count == 2
    summaries = []
    for member, entry in at.session_state[mr.CACHE_KEY].items():
        result = entry['Shear + Torsion']['result']
        assert not result.get('error'), result.get('error')
        frame = result['combined_vt_df']
        assert len(frame) == 320 and frame['Overall D/C value'].notna().any()
        assert not frame['Status'].eq('SOURCE BLOCKED').any()
        assert frame['Section region'].eq('LEFT SOLID END').any()
        assert frame['Section region'].eq('RIGHT SOLID END').any()
        assert frame['End section acceptance'].eq('REVIEW').all()
        assert not frame['Status'].eq('PASS').any()
        summaries.append({'member': member, 'rows': len(frame),
            'regions': frame['Section region'].value_counts().to_dict(),
            'statuses': frame['Status'].value_counts().to_dict(),
            'finite_ratios': int(frame['Overall D/C value'].notna().sum())})
    pd.testing.assert_frame_equal(canonical(at.session_state[BANK_KEY]), bank, check_dtype=False)
    records['all_six_actions_and_original_source_notes_preserved'] = True
    records['manual_calculation_without_review_checkbox'] = summaries
    buttons = {b.key for b in at.button}
    (internal / 'calculated_seed.pkl').write_bytes(pickle.dumps({
        k: v for k, v in at.session_state.filtered_state.items() if k not in buttons
    }))
    print('Manual V+T flow PASS: 2 girders / 640 original rows; pending reviews preserved.', flush=True)

    cache = pickle.dumps(at.session_state[mr.CACHE_KEY])
    for page in ['Result Summary', 'Report / QA']:
        at.session_state['_nav_active_workspace'] = page; run()
        assert calculate.call_count == 2
        assert pickle.dumps(at.session_state[mr.CACHE_KEY]) == cache
    records['summary_and_report_remain_read_only'] = True
    at.session_state['_nav_active_workspace'] = 'Sections'; run()
    number('Solid length at each end (m)', 1.6)
    at.session_state['_nav_active_workspace'] = 'Analysis'; run()
    next(x for x in at.radio if x.label == 'ULS check to calculate').set_value('Shear + Torsion'); run()
    route = ap.beam_girder_uls_strength_route(is_bridge=True, is_building=False,
        project_design_code='AASHTO LRFD', code_edition='AASHTO LRFD 9th Edition')
    for member, rows in mr.member_inputs(at.session_state.filtered_state).items():
        fingerprint = mr.result_hash(at.session_state.filtered_state, rows, check_name='Shear + Torsion', route=route)
        assert mr.current_result(at.session_state[mr.CACHE_KEY], member, 'Shear + Torsion', fingerprint) is None
    assert calculate.call_count == 2 and any('STALE' in str(d.value) for d in at.dataframe)
    records['dimension_edit_requires_explicit_recalculation'] = True

out = ROOT / 'qa/evidence/igird_endsimple22'
out.mkdir(parents=True, exist_ok=True)
(out / 'app_checks.json').write_text(json.dumps(records, indent=2) + '\n')
print(json.dumps(records, indent=2), flush=True)
