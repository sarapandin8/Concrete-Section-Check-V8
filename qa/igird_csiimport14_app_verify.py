"""Actual app.py import and calculation acceptance using the byte-exact native export.

The archived 20 m section is a QA model, not the user's complete project.
This verifies source consumption, not acceptance of that section for this bridge.
"""
from copy import deepcopy
import hashlib
from io import BytesIO
import json
import logging
from pathlib import Path
import pickle
import sys
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import pandas as pd
from streamlit.testing.v1 import AppTest
from concrete_pmm_pro.io.girder_csi_import import APP_COLUMNS, FORCE_MAP, read_tables, source_info
from concrete_pmm_pro.io.girder_load_bank import ACTIVE_KEY, BANK_KEY
from concrete_pmm_pro.io.project_io import (
    apply_project_to_session_state, project_from_json, project_from_session_state, project_to_json,
)
from concrete_pmm_pro.ui import analysis_page as ap, igird_member_results as mr
from concrete_pmm_pro.ui.girder_csi_import import UPLOAD_LABEL

logging.getLogger('streamlit').setLevel(logging.ERROR)
OUT = ROOT / 'qa/evidence/igird_csiimport14'
OUT.mkdir(parents=True, exist_ok=True)
FIXTURE = ROOT / 'qa/fixtures/CSiBridge_Bridge_Object_Girder_Forces_CSIIMPORT14.xlsx'


class Uploaded(BytesIO):
    def __init__(self, payload, name):
        super().__init__(payload)
        self.name = name


def element(items, label):
    return next(item for item in items if item.label == label)


state = {}
apply_project_to_session_state(project_from_json(
    (ROOT / 'qa/fixtures/I_Girder_20m_IGIRDER_FLEXSIGN1_CSiBridge_deck250.json').read_text()), state)
at = AppTest.from_file(str(ROOT / 'app.py'), default_timeout=120)
for key, value in state.items():
    at.session_state[key] = deepcopy(value)
at.session_state['_nav_active_workspace'] = 'Loads'
files = [Uploaded(FIXTURE.read_bytes(), 'ULS_Girder Force uploaded to app.xlsx')]


def uploader(label, *args, **kwargs):
    return files if label == UPLOAD_LABEL else ([] if kwargs.get('accept_multiple_files') else None)


def run():
    at.run(timeout=120)
    assert not at.exception, [error.message for error in at.exception]


record = {'milestone':'IGIRDER.CSIIMPORT14', 'source_sha256':hashlib.sha256(FIXTURE.read_bytes()).hexdigest(),
          'section_model_scope':'Archived 20 m section used for QA; source forces unchanged; no user design acceptance.'}
with patch('streamlit.file_uploader', side_effect=uploader), patch.object(mr, 'calculate_member', wraps=mr.calculate_member) as calculator:
    run()
    assert len(at.multiselect) == 1
    assert at.multiselect[0].value == ['Bridge Object Girder Forces']
    assert element(at.button, 'Replace entire girder collection').disabled
    for checkbox in at.checkbox:
        if checkbox.label.startswith('I confirm member names') or checkbox.label.startswith('All tables use raw CSI P signs'):
            checkbox.set_value(True)
    run()
    assert not element(at.button, 'Replace entire girder collection').disabled
    element(at.button, 'Replace entire girder collection').click()
    run()
    bank = at.session_state[BANK_KEY].copy(deep=True)
    assert len(bank) == 640
    assert bank.groupby('Girder').size().to_dict() == {'BOBJ1 / Interior Girder 2':320,'BOBJ1 / Left Exterior Girder':320}
    native = read_tables(FIXTURE.read_bytes(), FIXTURE.name)['Bridge Object Girder Forces']
    for _, row in bank.iterrows():
        info = source_info(row)
        original = native.loc[info['row'] - 1]
        assert info['raw_fields'] == original.to_dict()
        assert row['Station x (m)'] == float(original['Distance'])
        for field, target in FORCE_MAP.items():
            assert row[target] == float(original[field])
    assert element(at.button, 'Add tables to girder collection').disabled
    for member in ['BOBJ1 / Interior Girder 2', 'BOBJ1 / Left Exterior Girder']:
        element(at.selectbox, 'Girder to design').set_value(member)
        element(at.button, 'Use this girder — all imported load cases').click()
        run()
        assert at.session_state[ACTIVE_KEY] == member
        assert len(at.session_state['beam_uls_loads_table']) == 320
        assert all(source_info(row)['girder'] == member.split(' / ',1)[1]
                   for _, row in at.session_state['beam_uls_loads_table'].iterrows())
    restored = {}
    apply_project_to_session_state(project_from_json(project_to_json(
        project_from_session_state(at.session_state.filtered_state))), restored)
    assert len(restored[BANK_KEY]) == 640
    assert sorted(restored[BANK_KEY]['Note']) == sorted(bank['Note'])
    record['import_replace_switch_project_json_duplicate_guard'] = 'PASS'
    assert calculator.call_count == 0

    # A native export missing a component must not route through app aliases.
    malformed = native.drop(columns='V3').to_csv(index=False).encode('utf-8-sig')
    files[:] = [Uploaded(malformed, 'missing_v3.csv')]
    before = pickle.dumps(at.session_state[BANK_KEY])
    run()
    assert element(at.button, 'Replace entire girder collection').disabled
    assert element(at.button, 'Add tables to girder collection').disabled
    assert any('all six' in error.value or 'P, V2, V3' in error.value for error in at.error)
    assert pickle.dumps(at.session_state[BANK_KEY]) == before
    record['incomplete_native_header_blocks_apply_without_bank_change'] = 'PASS'

    # App-column CSV exported from this exact bank remains partitioned on reload.
    files[:] = [Uploaded(bank.to_csv(index=False).encode('utf-8-sig'), 'all_girders.csv')]
    run()
    for checkbox in at.checkbox:
        if checkbox.label.startswith('I confirm member names') or checkbox.label.startswith('All tables use raw CSI P signs'):
            checkbox.set_value(True)
    run()
    element(at.button, 'Replace entire girder collection').click()
    run()
    reimported = at.session_state[BANK_KEY].copy(deep=True)
    assert len(reimported) == 640
    assert sorted(reimported['Note']) == sorted(bank['Note'])
    assert reimported.groupby('Girder').size().to_dict() == bank.groupby('Girder').size().to_dict()
    record['all_member_app_csv_reupload'] = 'PASS'
    assert calculator.call_count == 0

    # Return to the raw XLSX before checking the actual production calculation.
    files[:] = [Uploaded(FIXTURE.read_bytes(), 'ULS_Girder Force uploaded to app.xlsx')]
    run()
    element(at.button, 'Replace entire girder collection').click()
    run()
    bank = at.session_state[BANK_KEY].copy(deep=True)
    at.session_state['_nav_active_workspace'] = 'Analysis'
    run()
    element(at.radio, 'ULS check to calculate').set_value('Shear + Torsion')
    run()
    assert calculator.call_count == 0
    next(button for button in at.button if button.label.startswith('Calculate Shear + Torsion — all')).click()
    run()
    assert calculator.call_count == 2
    for member, cache in at.session_state[mr.CACHE_KEY].items():
        result = cache['Shear + Torsion']['result']
        assert not result.get('error'), result.get('error')
        combined = result['combined_vt_df']
        expected = bank[bank['Girder'].eq(member)]
        direct = combined[combined['Source Excel row'].notna()]
        assert len(direct) == 320
        assert set(direct['Source Excel row'].astype(int)) == {source_info(row)['row'] for _,row in expected.iterrows()}
        assert direct['Source Girder'].eq(member.split(' / ',1)[1]).all()
        assert 'PASS' not in set(combined['Status'])
        assert combined['Source coupling'].eq('ENVELOPE — REVIEW').all()
        for _,row in direct.iterrows():
            original = native.loc[int(row['Source Excel row']) - 1]
            for field,target in FORCE_MAP.items():
                unit = 'kN-m' if target in {'Mux','Muy','Tu'} else 'kN'
                assert row['Source '+target+' '+unit] == float(original[field])
        combined.to_csv(OUT / (member.split(' / ',1)[1].lower().replace(' ','_')+'.combined_vt_df.csv'), index=False)
    record['actual_app_calculation'] = {'check':'Shear + Torsion','physical_members':2,'source_rows':640,
                                       'all_source_vectors_and_reference_components_exact':True,'envelope_pass_blocked':True}
    record['loads_and_review_do_not_calculate'] = True
    bank.to_csv(OUT / 'CSiBridge_ULS_CSIIMPORT14_all_girders.csv', index=False, encoding='utf-8-sig')
    audit = []
    for _,row in bank.iterrows():
        info = source_info(row)
        audit.append({**info['raw_fields'],'Excel row':info['row'],'Physical member':row['Girder'],
                      'Case Name':row['Case Name'],'Source SHA256':info['source_sha256'],
                      **{column:row[column] for column in ['Station x (m)',*FORCE_MAP.values()]}})
    pd.DataFrame(audit).to_csv(OUT / 'CSiBridge_ULS_CSIIMPORT14_source_audit.csv', index=False, encoding='utf-8-sig')

(OUT / 'app_verification.json').write_text(json.dumps(record, ensure_ascii=False, indent=2)+'\n')
print(json.dumps(record, ensure_ascii=False, indent=2), flush=True)
