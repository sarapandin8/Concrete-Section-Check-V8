"""Portable CSI input banks: exact values, project isolation and actual UI use."""
import base64
from copy import deepcopy
import gzip
import hashlib
import json
from pathlib import Path
from unittest.mock import patch

import numpy as np
import pandas as pd
import pytest
from streamlit.testing.v1 import AppTest

from concrete_pmm_pro.analysis import slab_review68 as engine
from concrete_pmm_pro.core.project import ProjectModel
from concrete_pmm_pro.io import slab_project74 as archive, slab_shell_import as source
from concrete_pmm_pro.io.project_io import (ProjectIOError, apply_project_to_session_state,
    project_from_json, project_from_session_state, project_to_json)
from test_slab_import67 import native_upload
from test_slab_shell55 import upload
from test_slab_shell56 import model_state

ROOT = Path(__file__).resolve().parents[1]


def round_trip(state):
    text = project_to_json(project_from_session_state(state))
    restored = {}
    apply_project_to_session_state(project_from_json(text), restored)
    return text, restored


def equal_packages(first, second):
    assert second.ready and second.signature == first.signature
    assert second.units == first.units and second.sources == first.sources
    assert second.notes == first.notes and second.tables.keys() == first.tables.keys()
    for name in first.tables:
        pd.testing.assert_frame_equal(first.tables[name], second.tables[name], check_exact=True)
    for name in first.summary:
        if isinstance(first.summary[name], pd.DataFrame):
            pd.testing.assert_frame_equal(first.summary[name], second.summary[name], check_exact=True)
        else:
            assert first.summary[name] == second.summary[name]


@pytest.mark.parametrize("static", [False, True])
def test_json_round_trip_preserves_all_tables_units_sources_steps_and_full_precision(static):
    package = source.parse_files([native_upload() if static else upload()])
    precise = np.nextafter(0.12345678901234566, 1.)
    package.tables['forces']['F11'] = precise
    package.tables['forces']['M12'] = -1.2345678901234568e-13
    package.tables['forces']['V23'] = 123456789.12345679
    package.tables['forces']['Extra note'] = ['~generated' if i % 2 else None for i in range(len(package.tables['forces']))]
    package.tables['frames'] = pd.DataFrame([{'Frame': 'F1', 'JointI': '~1', 'JointJ': '2', 'IsCurved': 'No'}])
    package.units['frames'] = {c: 'Text' for c in package.tables['frames']}
    state = {source.BANK_KEY: package, source.PENDING_KEY: package.signature,
        engine.RESULT_KEY: {'result': 'must not be archived'}}
    text, restored = round_trip(state)
    equal_packages(package, source.current_package(restored))
    assert restored[archive.RESTORED_KEY] and engine.RESULT_KEY not in restored
    assert 'must not be archived' not in text
    assert source.current_package(restored).tables['forces'].F11.iloc[0] == precise
    assert 'gzip+base64' in text


def test_exported_step_numbers_keep_distinct_static_corner_records():
    from test_slab_import67 import static_data
    data = static_data()
    data['forces'] = [deepcopy(data['forces'][0]), deepcopy(data['forces'][0])]
    data['forces'][1]['V13'] = 42.
    package = source.parse_files([native_upload(data, step_numbers=[0., 1.])])
    _, restored = round_trip({source.BANK_KEY: package})
    equal_packages(package, source.current_package(restored))


def test_loading_into_another_project_restores_inputs_and_discards_old_widgets_results():
    state = model_state()
    project = project_from_json(project_to_json(project_from_session_state(state)))
    previous = {'project_name': 'previous', source.BANK_KEY: 'old shell data',
        source.PENDING_KEY: ('old',), 'slab_shell55_uploads_9': 'old widget',
        engine.RESULT_KEY: {'D/C': 999}, 'slab_shell55_top65_report': b'old report'}
    apply_project_to_session_state(project, previous)
    equal_packages(state[source.BANK_KEY], source.current_package(previous))
    assert 'slab_shell55_uploads_9' not in previous
    assert engine.RESULT_KEY not in previous and 'slab_shell55_top65_report' not in previous


def test_old_json_without_shell_inputs_clears_previous_bank_and_remains_readable():
    _, state = round_trip(model_state())
    apply_project_to_session_state(project_from_json(project_to_json(ProjectModel())), state)
    assert source.current_package(state) is None
    assert not any(str(k).startswith('slab_shell55_') for k in state)


def test_clear_then_save_cannot_resurrect_archive_from_project_metadata():
    _, state = round_trip(model_state())
    assert archive.METADATA_KEY in state['project_metadata']
    state.pop(source.BANK_KEY)
    project = project_from_session_state(state)
    assert archive.METADATA_KEY not in project.metadata
    loaded = {}
    apply_project_to_session_state(project_from_json(project_to_json(project)), loaded)
    assert source.current_package(loaded) is None


def test_replacing_the_imported_package_replaces_saved_inputs_and_source_identities():
    _, state = round_trip(model_state())
    replacement = source.parse_files([native_upload()])
    state[source.BANK_KEY] = replacement
    state[source.PENDING_KEY] = replacement.signature
    _, loaded = round_trip(state)
    equal_packages(replacement, source.current_package(loaded))


def test_pending_file_picker_is_not_mistaken_for_a_committed_new_import():
    state = model_state()
    state[source.PENDING_KEY] = ('pending unimported file',)
    assert source.current_package(state) is None
    _, loaded = round_trip(state)
    equal_packages(state[source.BANK_KEY], source.current_package(loaded))


def test_cached_input_archive_updates_after_in_place_input_change_and_is_not_aliased():
    state = model_state()
    first = archive.input_metadata(state)
    with patch.object(archive.gzip, 'compress', side_effect=AssertionError('recompressed unchanged inputs')):
        assert archive.input_metadata(state) == first
    original = deepcopy(first)
    first['payload'] = 'mutated caller copy'
    assert archive.input_metadata(state) == original
    state[source.BANK_KEY].tables['forces']['V23'] = 13.123456789012345
    second = archive.input_metadata(state)
    assert second['sha256'] != original['sha256']
    assert archive.restore(second).tables['forces'].loc[0, 'V23'] == 13.123456789012345


def changed_payload(archive_value, change):
    result = deepcopy(archive_value)
    data = json.loads(gzip.decompress(base64.b64decode(result['payload'])))
    change(data)
    raw = json.dumps(data, separators=(',', ':'), allow_nan=False).encode()
    result.update(payload=base64.b64encode(gzip.compress(raw, mtime=0)).decode(),
        raw_bytes=len(raw), sha256=hashlib.sha256(raw).hexdigest())
    return result


@pytest.mark.parametrize('fault', ['checksum', 'base64', 'truncated', 'schema', 'size'])
def test_corrupt_embedded_package_is_rejected_before_existing_project_is_changed(fault):
    project = project_from_session_state(model_state())
    saved = project.metadata[archive.METADATA_KEY]
    if fault == 'checksum': saved['sha256'] = '0' * 64
    elif fault == 'base64': saved['payload'] = '%%%'
    elif fault == 'truncated': saved['payload'] = saved['payload'][:-8]
    elif fault == 'schema': saved['schema'] = 'future unsupported version'
    elif fault == 'size': saved['raw_bytes'] = archive.MAX_RAW_BYTES + 1
    state = {'project_name': 'keep current project', 'slab_shell55_package': 'keep inputs'}
    before = deepcopy(state)
    with pytest.raises(ProjectIOError, match='Saved slab shell inputs are invalid'):
        apply_project_to_session_state(project, state)
    assert state == before
    with pytest.raises(ProjectIOError, match='Saved slab shell inputs are invalid'):
        project_from_json(project_to_json(project))


@pytest.mark.parametrize('fault', ['units', 'missing table', 'duplicate corner', 'missing coordinate', 'missing axes'])
def test_restore_revalidates_input_correspondence_instead_of_trusting_a_saved_ready_flag(fault):
    original = archive.input_metadata(model_state())
    def change(data):
        if fault == 'units': data['units']['forces']['V23'] = 'N/mm'
        elif fault == 'missing table':
            data['tables'].pop('nodes');data['units'].pop('nodes')
        elif fault == 'duplicate corner': data['tables']['forces']['data'].append(data['tables']['forces']['data'][0])
        elif fault == 'missing coordinate': data['tables']['nodes']['data'] = []
        elif fault == 'missing axes': data['tables']['advanced']['data'] = []
    with pytest.raises(ValueError, match='Saved slab shell inputs are invalid'):
        archive.restore(changed_payload(original, change))


def test_recalculation_after_json_restore_has_identical_native_rows_and_check_results():
    state = model_state()
    before = engine.calculate(state)
    _, loaded = round_trip(state)
    assert engine.current(loaded) is None
    after = engine.calculate(loaded)
    for key in ('rows', 'summary', 'mat_envelopes', 'coverage', 'exclusion_counts'):
        pd.testing.assert_frame_equal(before[key], after[key], check_exact=True)
    for key in ('eligibility', 'governing_vectors', 'section_cuts'):
        pd.testing.assert_frame_equal(before['code_review'][key], after['code_review'][key], check_exact=True)
    assert before['fingerprint'] == after['fingerprint']


def test_actual_app_restores_ready_inputs_without_excel_then_clear_survives_save_load():
    _, state = round_trip(model_state())
    app = AppTest.from_file(str(ROOT/'app.py'), default_timeout=60)
    for key, value in state.items():app.session_state[key] = deepcopy(value)
    app.session_state['_nav_active_workspace'] = 'Loads'
    app.session_state['_nav_loads_subpage'] = 'Slab Shell Results'
    with patch.object(source, 'parse_files', side_effect=AssertionError('Excel upload or reparse was required')):
        app.run()
        assert not app.exception
        assert any('Restored from Project JSON' in c.value for c in app.caption)
        assert not app.button(key='slab_shell55_open_analysis').disabled
        app.button(key='slab_shell55_clear').click().run()
        assert not app.exception
        assert source.BANK_KEY not in app.session_state
        saved = project_from_session_state(app.session_state.filtered_state)
        assert archive.METADATA_KEY not in saved.metadata


def test_import_refreshes_sidebar_download_before_the_user_saves_the_project():
    import streamlit as st
    app = AppTest.from_file(str(ROOT/'app.py'), default_timeout=60)
    for key, value in model_state().items():app.session_state[key] = deepcopy(value)
    app.session_state['_nav_active_workspace'] = 'Loads'
    app.session_state['_nav_loads_subpage'] = 'Slab Shell Results'
    replacement = native_upload()
    original_upload, original_download = st.file_uploader, st.download_button
    downloads = []
    def choose_files(label, *args, **kwargs):
        return [replacement] if label.startswith('CSiBridge Excel files') else original_upload(label, *args, **kwargs)
    def capture_download(*args, **kwargs):
        if kwargs.get('key') == 'ui_commercial4_3_sidebar_save_project_json':
            downloads.append(kwargs['data'])
        return original_download(*args, **kwargs)
    with patch.object(st, 'file_uploader', side_effect=choose_files), \
         patch.object(st, 'download_button', side_effect=capture_download):
        app.run()
        assert not app.exception
        app.button(key='slab_shell55_import').click().run()
        assert not app.exception
    saved = project_from_json(downloads[-1])
    package = archive.restore(saved.metadata[archive.METADATA_KEY])
    assert package.signature == source.upload_signature([replacement])
    assert package.tables['forces'].StepType.eq('').all()
