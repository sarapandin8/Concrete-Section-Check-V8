"""Verify the full app.py with exact uploaded bytes, including the former legacy path.

Run with CSP_QA_REPO / CSP_QA_OUT to verify an extracted release. AppTest
executes Streamlit controls; this does not claim visual browser verification.
"""
import io
import json
import os
import sys
import time
from pathlib import Path
from unittest.mock import patch

import pandas as pd
from streamlit.testing.v1 import AppTest

REPO = Path(os.environ.get('CSP_QA_REPO', Path(__file__).resolve().parents[1]))
OUT = Path(os.environ.get('CSP_QA_OUT', REPO/'qa/evidence/igird_csiimport2'))
OUT.mkdir(parents=True, exist_ok=True)
sys.path.insert(0, str(REPO))

from concrete_pmm_pro.ui import analysis_page as ap
from concrete_pmm_pro.ui.girder_csi_import import UPLOAD_LABEL
from concrete_pmm_pro.io.girder_csi_import import APP_COLUMNS, FORCE_MAP
from concrete_pmm_pro.io.project_io import project_from_json, apply_project_to_session_state
from concrete_pmm_pro.analysis.girder_axial_convention import (
    SETTINGS_KEY, COMPRESSION_POSITIVE, CSI_TENSION_POSITIVE,
)


class Uploaded(io.BytesIO):
    def __init__(self, data, name):
        super().__init__(data)
        self.name = name


def assert_ok(at):
    assert not at.exception, [e.message for e in at.exception]


def by_label(elements, label):
    return next(e for e in elements if e.label == label)


def new_app(*, legacy_convention=False):
    state = {}
    project = project_from_json((REPO/'qa/fixtures/I_Girder_20m_IGIRDER_FLEXSIGN1_CSiBridge_deck250.json').read_text())
    apply_project_to_session_state(project, state)
    at = AppTest.from_file(str(REPO/'app.py'))
    for key, value in state.items():
        at.session_state[key] = value
    at.session_state['_nav_active_workspace'] = 'Loads'
    # This old persisted choice used to route the user's workbook to the
    # incompatible Case Name / Station x parser. It must now be harmless.
    at.session_state['bridge_beam_uls_station_loads_format'] = 'App columns (legacy)'
    if legacy_convention:
        cfg = {'input_sign': COMPRESSION_POSITIVE}
        at.session_state[SETTINGS_KEY] = cfg
        metadata = dict(state.get('project_metadata') or {})
        metadata[SETTINGS_KEY] = cfg
        at.session_state['project_metadata'] = metadata
    return at


latest = REPO/'qa/fixtures/CSiBridge_Left_Exterior_Max_Min_latest.xlsx'
current_upload = Uploaded(latest.read_bytes(), 'Bridge_ULS_Left_Exterior_Max_Min_Template CSiBridge(1).xlsx')
seen = []


def upload(label, *args, **kwargs):
    seen.append((label, kwargs.get('key')))
    return current_upload if label == UPLOAD_LABEL else None


result = {'method': 'Full app.py Streamlit AppTest with original workbook bytes; no browser rendering claim'}
with patch('streamlit.file_uploader', side_effect=upload):
    at = new_app().run(timeout=30)
    assert_ok(at)
    assert sum(label == UPLOAD_LABEL for label, _ in seen) == 1
    assert not any(e.label == 'Import table format' for e in at.radio)
    assert by_label(at.selectbox, 'CSiBridge worksheet / girder').value == 'Left Exterior Girder'
    assert not by_label(at.button, 'Replace current rows').disabled
    assert any('80 rows · Max 40 · Min 40' in e.value for e in at.caption)
    assert any('Reference only' in str(e.value) for e in at.dataframe)
    by_label(at.button, 'Replace current rows').click().run(timeout=30)
    assert_ok(at)
    active = ap._active_beam_uls_demand_dataframe_from_session(at.session_state.filtered_state)
    source = pd.read_excel(io.BytesIO(latest.read_bytes()), sheet_name='Left Exterior Girder').iloc[1:]
    assert len(active) == len(source) == 80
    for csi, app in FORCE_MAP.items():
        assert active[app].tolist() == source[csi].astype(float).tolist()
    assert active['Station x (m)'].tolist() == source['Girder Distance'].astype(float).tolist()
    assert at.session_state[SETTINGS_KEY]['input_sign'] == CSI_TENSION_POSITIVE
    assert len(at.session_state['project_metadata']['workflow_load_tables']['beam_uls_loads_table']) == 80
    assert by_label(at.button, 'Append imported rows').disabled
    active.to_csv(OUT/'imported_analysis_80rows.csv', index=False)
    result.update({'source_filename': current_upload.name, 'selected_girder': 'Left Exterior Girder',
        'source_rows': 80, 'Max': 40, 'Min': 40, 'distinct_stations': 21,
        'exact_numeric_components_compared': 480, 'station_values_compared': 80,
        'single_uploader': True, 'previous_legacy_selection_ignored': True,
        'replace_applied': True, 'duplicate_append_blocked': True,
        'M2_V3_role': 'reference only', 'all_source_signs_preserved': True})

    # Incomplete source force must disable Apply and leave all current rows.
    damaged = pd.read_excel(io.BytesIO(latest.read_bytes()), sheet_name='Left Exterior Girder')
    damaged.loc[1, 'V3'] = None
    current_upload = Uploaded(damaged.to_csv(index=False).encode('utf-8-sig'), 'missing_V3.csv')
    before = active.copy(deep=True)
    at.run(timeout=30)
    assert_ok(at)
    assert by_label(at.button, 'Replace current rows').disabled
    assert any('all six force components' in e.value for e in at.error)
    pd.testing.assert_frame_equal(before, ap._active_beam_uls_demand_dataframe_from_session(at.session_state.filtered_state))
    result['missing_reference_force_blocked_without_mutation'] = True

    # Restore the actual workbook and use the real app navigation + button.
    current_upload = Uploaded(latest.read_bytes(), 'Bridge_ULS_Left_Exterior_Max_Min_Template CSiBridge(1).xlsx')
    at.session_state['_nav_active_workspace'] = 'Analysis'
    at.run(timeout=30)
    assert_ok(at)
    by_label(at.radio, 'Flexure stage').set_value('Final — Composite').run(timeout=30)
    assert_ok(at)
    started = time.perf_counter()
    by_label(at.button, 'Calculate Final Composite Flexure').click().run(timeout=60)
    elapsed = time.perf_counter() - started
    assert_ok(at)
    entry = at.session_state[ap._BEAM_ULS_MANUAL_CALC_CACHE_KEY]['Flexure — Final Composite']
    frame = entry['flexure_preview_df']
    assert len(frame) == 80 and frame['Case'].nunique() == 4
    assert entry['negative_mux_rows_excluded'] == 0 and entry['negative_mux_rows_screened'] == 1
    assert 'PASS' not in set(frame['Status'])
    for _, row in frame.iterrows():
        original = active.loc[(active['Case Name'] == row['Case']) & (active['Station x (m)'] == row['Station x (m)'])].iloc[0]
        for component in FORCE_MAP.values():
            unit = 'kN-m' if component in {'Mux', 'Tu', 'Muy'} else 'kN'
            assert row[f'Source {component} {unit}'] == original[component]
        assert row['Nu input kN'] == original['Nu']
        assert row['Nu kN'] == -original['Nu']
    dashboard = ap._igird_composite_flexure_dashboard_state(at.session_state.filtered_state)
    assert dashboard[0] == 'FAIL' and 'current' in dashboard[1], dashboard
    assert any('simultaneous Mu/Nu/Vu/Tu is not established by this table' in e.value for e in at.warning)
    assert any('Strand families — actual stress and force used' in e.value for e in at.markdown)
    assert any('Source Muy kN-m' in str(e.value) and 'Source Vux kN' in str(e.value) for e in at.dataframe)
    frame.drop(columns=['Strand development trace', 'Ordinary bar development trace'], errors='ignore').to_csv(OUT/'final_flexure_80rows.csv', index=False)
    fields = ['Case', 'Station x (m)', 'Source Excel row', 'Source ItemType', 'Source Mux kN-m',
        'Source Vuy kN', 'Source Tu kN-m', 'Source Muy kN-m', 'Source Vux kN', 'Source Nu kN',
        'Nu input kN', 'Nu kN', 'φMn kN-m', 'Status', 'Numerical status', 'Source coupling']
    (OUT/'final_flexure_80rows.json').write_text(frame[fields].to_json(orient='records', indent=2, force_ascii=False))
    result.update({'final_rows': len(frame), 'negative_rows_screened': 1,
        'final_flexure_button_seconds': elapsed, 'status_counts': frame['Status'].value_counts().to_dict(),
        'stored_trace_visible': True, 'all_six_components_retained_in_result_trace': True,
        'dashboard_reads_current_result': True})

    # The earlier multi-sheet export still defaults to the flexure-demand leader;
    # whole-bridge totals remain ineligible as an individual section demand.
    old_file = REPO/'qa/fixtures/CSiBridge_ULS_Girder_Max_Min.xlsx'
    current_upload = Uploaded(old_file.read_bytes(), old_file.name)
    many = new_app().run(timeout=30)
    assert_ok(many)
    assert by_label(many.selectbox, 'CSiBridge worksheet / girder').value == 'Left Exterior Girder'
    by_label(many.selectbox, 'CSiBridge worksheet / girder').select('Entire Bridge Section').run(timeout=30)
    assert_ok(many)
    assert by_label(many.button, 'Replace current rows').disabled
    result['multi_sheet_default_preserved'] = True
    result['wrong_scope_blocked'] = True

    # Existing app-column CSV enters the same uploader and retains its declared
    # Nu convention. M2/V3 reference values remain signed and nonzero.
    legacy = pd.DataFrame([[True, 2, 'Legacy ULS', -700, -20, 4, -15, 8, 12, 'reference signs']], columns=APP_COLUMNS)
    current_upload = Uploaded(legacy.to_csv(index=False).encode('utf-8-sig'), 'old_app.csv')
    old = new_app(legacy_convention=True).run(timeout=30)
    assert_ok(old)
    assert any('App station-load columns' in e.value for e in old.info)
    assert not by_label(old.button, 'Replace current rows').disabled
    by_label(old.button, 'Replace current rows').click().run(timeout=30)
    assert_ok(old)
    restored = ap._active_beam_uls_demand_dataframe_from_session(old.session_state.filtered_state)
    assert len(restored) == 1
    for component in FORCE_MAP.values():
        assert restored.iloc[0][component] == legacy.iloc[0][component]
    assert old.session_state[SETTINGS_KEY]['input_sign'] == COMPRESSION_POSITIVE
    assert by_label(old.button, 'Append imported rows').disabled
    result['legacy_app_columns_auto_detected'] = True
    result['legacy_axial_convention_preserved'] = True

result['streamlit_exceptions'] = 0
result['browser_visual_verification'] = 'NOT COMPLETED: AppTest executes the full app; no browser layout or drag-and-drop claim.'
(OUT/'ui_result.json').write_text(json.dumps(result, indent=2))
print(json.dumps(result, indent=2), flush=True)
