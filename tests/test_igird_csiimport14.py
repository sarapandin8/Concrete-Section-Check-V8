"""Direct native Bridge Object Girder Forces import, with full row fidelity."""
import csv
import hashlib
from io import StringIO
from pathlib import Path

import pandas as pd
import pytest

from concrete_pmm_pro.io.girder_csi_import import (
    APP_COLUMNS, FORCE_MAP, apply_source_gate, is_csi_table, is_native_bridge_table,
    prepare_csi_table, read_tables, source_info, split_member_tables, tag_app_source,
)
from concrete_pmm_pro.io.girder_load_bank import (
    ACTIVE_KEY, BANK_KEY, activate_member, merge_bank, save_active,
)
from concrete_pmm_pro.io.project_io import (
    apply_project_to_session_state, project_from_json, project_from_session_state, project_to_json,
)
from concrete_pmm_pro.analysis.girder_axial_convention import CSI_TENSION_POSITIVE, SETTINGS_KEY
from concrete_pmm_pro.ui.loads_page import prepare_imported_workflow_load_table
from concrete_pmm_pro.ui.analysis_page import _active_beam_uls_demand_dataframe_from_session

FILE = Path(__file__).resolve().parents[1] / 'qa/fixtures/CSiBridge_Bridge_Object_Girder_Forces_CSIIMPORT14.xlsx'
SHEET = 'Bridge Object Girder Forces'
DIGEST = 'd29e5af119bc94d3ce74acf6ee51978cd0ccb9b012a649ee26b32d1b0521a2c2'


@pytest.fixture(scope='module')
def native():
    payload = FILE.read_bytes()
    assert hashlib.sha256(payload).hexdigest() == DIGEST
    return read_tables(payload, FILE.name)[SHEET]


@pytest.fixture(scope='module')
def parsed(native):
    results = []
    for group in split_member_tables(native, sheet_name=SHEET):
        result = prepare_csi_table(group.frame, sheet_name=SHEET, source_name=FILE.name)
        assert not result.errors
        frame = result.frame.copy()
        frame['Case Name'] = group.name + ' / ' + frame['Case Name']
        frame['Girder'] = group.name
        results.append((group, result, frame))
    return results


def test_shared_sheet_partitions_complete_disjoint_source_rows(native, parsed):
    assert len(native) == 641  # 640 data rows and one declared units row
    assert [group.name for group, _, _ in parsed] == [
        'BOBJ1 / Left Exterior Girder', 'BOBJ1 / Interior Girder 2']
    indices = []
    for group, result, frame in parsed:
        assert len(frame) == 320
        assert result.counts == {'Max': 160, 'Min': 160}
        assert frame['Case Name'].nunique() == 16
        assert frame['Station x (m)'].nunique() == 21
        assert not frame.duplicated(['Case Name', 'Station x (m)']).any()
        assert group.frame.attrs == native.attrs
        indices += group.frame.index[1:].tolist()
    assert len(set(indices)) == 640
    assert sorted(indices) == native.index[1:].tolist()


def test_every_original_cell_unit_sign_excel_row_and_hash_is_retained(native, parsed):
    units = native.iloc[0].to_dict()
    for group, result, frame in parsed:
        raw = group.frame.iloc[1:]
        assert frame['Station x (m)'].tolist() == raw['Distance'].astype(float).tolist()
        for source, target in FORCE_MAP.items():
            assert frame[target].tolist() == raw[source].astype(float).tolist()
            assert result.audit[source].tolist() == raw[source].tolist()
        for (_, mapped), (index, original) in zip(frame.iterrows(), raw.iterrows()):
            info = source_info(mapped)
            assert info['raw_fields'] == original.to_dict()
            assert info['units'] == units
            assert info['row'] == index + 1
            assert info['header_row'] == 2
            assert info['table'] == 'TABLE:  Bridge Object Girder Forces'
            assert info['source_sha256'] == DIGEST
            assert info['bridge_object'] == original['BridgeObj']
            assert info['girder'] == original['Girder']
            assert info['section_cut'] == original['SectCutNum']
            assert info['location_type'] == original['LocType']
            assert info['case_type'] == original['CaseType']
            assert info['case'] == original['OutputCase']
            assert info['step'] == original['StepType']
            assert info['kind'] == 'ENVELOPE'
            assert not info['concurrency_confirmed']
        assert set(raw['OutputCase']) == {'U1A', 'U1B', 'U2A', 'U2B'}
        assert set(raw['LocType']) == {'Before', 'After'}


def test_before_after_are_distinct_vectors_at_the_same_station(parsed):
    group, _, frame = parsed[0]
    same = frame[frame['Station x (m)'].eq(1)]
    pairs = [(row, source_info(row)) for _, row in same.iterrows()]
    before = next(row for row, info in pairs if info['case'] == 'U1A' and info['step'] == 'Max' and info['location_type'] == 'Before')
    after = next(row for row, info in pairs if info['case'] == 'U1A' and info['step'] == 'Max' and info['location_type'] == 'After')
    assert before['Case Name'] != after['Case Name']
    assert before['Vuy'] != after['Vuy']
    assert source_info(before)['section_cut'] != source_info(after)['section_cut']


def test_unsplit_native_table_cannot_mix_two_physical_members(native):
    result = prepare_csi_table(native, sheet_name=SHEET)
    assert result.frame.empty
    assert any('multiple BridgeObj / Girder' in message for message in result.errors)


def test_same_girder_label_on_two_bridge_objects_is_partitioned_separately(parsed):
    first = parsed[0][0].frame.copy()
    second = first.iloc[1:3].copy()
    second['BridgeObj'] = 'BOBJ2'
    second.index = [1000, 1001]
    raw = pd.concat([first, second])
    groups = split_member_tables(raw, sheet_name=SHEET)
    assert [group.name for group in groups] == ['BOBJ1 / Left Exterior Girder', 'BOBJ2 / Left Exterior Girder']
    assert len(groups[1].frame) == 3  # units plus two BOBJ2 rows


@pytest.mark.parametrize('field', ['BridgeObj','Girder','SectCutNum','LocType','OutputCase','CaseType','StepType'])
def test_blank_native_source_identity_blocks_import(field, parsed):
    raw = parsed[0][0].frame.iloc[:2].copy()
    raw.loc[raw.index[1], field] = None
    result = prepare_csi_table(raw, sheet_name=SHEET)
    assert result.frame.empty
    assert any(field in message and 'row 4' in message for message in result.errors)


@pytest.mark.parametrize('field', ['BridgeObj','Girder','SectCutNum','LocType','OutputCase','CaseType','StepType','P','V2','V3','T','M2','M3','Distance'])
def test_incomplete_native_headers_never_fall_through_to_app_aliases(field, parsed):
    raw = parsed[0][0].frame.iloc[:2].drop(columns=field)
    assert is_native_bridge_table(raw)
    result = prepare_csi_table(raw, sheet_name=SHEET)
    assert result.errors and result.frame.empty


def test_all_numeric_cells_blank_are_an_error_not_a_silently_dropped_source_row(parsed):
    raw = parsed[0][0].frame.iloc[:2].copy()
    raw.loc[raw.index[1], ['Distance', *FORCE_MAP]] = None
    result = prepare_csi_table(raw, sheet_name=SHEET)
    assert result.errors and result.frame.empty
    assert any('row 4' in message for message in result.errors)


def test_native_units_are_required_and_unknown_units_are_rejected(parsed):
    raw = parsed[0][0].frame.iloc[:2].copy()
    assert any('units row' in message for message in prepare_csi_table(raw.iloc[1:], sheet_name=SHEET).errors)
    raw.loc[raw.index[0], 'V2'] = 'kg'
    result = prepare_csi_table(raw, sheet_name=SHEET)
    assert any('unsupported unit' in message for message in result.errors)
    raw.loc[raw.index[0], 'Distance'] = 'unsupported length'
    groups = split_member_tables(raw, sheet_name=SHEET)
    assert len(groups) == 1 and groups[0].girder != 'Text'
    assert any('distance unit' in message for message in prepare_csi_table(groups[0].frame, sheet_name=SHEET).errors)


def test_normalized_units_do_not_replace_original_cells(parsed):
    raw = parsed[0][0].frame.iloc[:2].copy()
    raw.loc[raw.index[0], 'Distance'] = 'mm'
    raw.loc[raw.index[0], ['P','V2','V3']] = 'N'
    raw.loc[raw.index[0], ['T','M2','M3']] = 'N-mm'
    raw.loc[raw.index[1], 'Distance'] = 1000
    result = prepare_csi_table(raw, sheet_name=SHEET)
    assert not result.errors and result.frame.iloc[0]['Station x (m)'] == 1
    for field, target in FORCE_MAP.items():
        factor = .001 if field in {'P','V2','V3'} else 1e-6
        assert result.frame.iloc[0][target] == pytest.approx(float(raw.iloc[1][field]) * factor)
    assert source_info(result.frame.iloc[0])['raw_fields'] == raw.iloc[1].to_dict()


def test_native_csv_title_with_fewer_cells_keeps_units_and_all_members(native):
    stream = StringIO(newline='')
    writer = csv.writer(stream)
    writer.writerow(['TABLE:  Bridge Object Girder Forces'])
    writer.writerow(native.columns)
    writer.writerows(native.itertuples(index=False, name=None))
    payload = stream.getvalue().encode('utf-8-sig')
    raw = read_tables(payload, 'native.csv')['CSV']
    groups = split_member_tables(raw, sheet_name='CSV')
    assert len(groups) == 2
    for group in groups:
        result = prepare_csi_table(group.frame, sheet_name='CSV')
        assert not result.errors and len(result.frame) == 320
        assert source_info(result.frame.iloc[0])['source_sha256'] == hashlib.sha256(payload).hexdigest()


def test_extra_fields_step_precedence_and_identical_rows_are_preserved(parsed):
    raw = parsed[0][0].frame.iloc[:2].copy()
    raw['ItemType'] = ['Text', 'Legacy label']
    raw['Export remark'] = ['Text', 'Quoted, original\nremark']
    duplicate = raw.iloc[1:].copy()
    duplicate.index = [1000]
    result = prepare_csi_table(pd.concat([raw, duplicate]), sheet_name=SHEET)
    assert not result.errors and len(result.frame) == 2
    assert result.frame['Case Name'].nunique() == 2
    assert result.audit['ItemType'].tolist() == ['Legacy label', 'Legacy label']
    assert result.audit['Export remark'].tolist() == ['Quoted, original\nremark'] * 2
    assert [source_info(row)['occurrence'] for _,row in result.frame.iterrows()] == [1,2]
    assert all(source_info(row)['step'] == 'Max' for _,row in result.frame.iterrows())


@pytest.mark.parametrize('station_label', ['Station x (m)','Governing x','formatted metres'])
def test_calculation_trace_identifies_exact_member_cut_location_and_force_vector(parsed, station_label):
    for group, _, frame in parsed:
        result = frame[['Case Name','Station x (m)']].rename(columns={'Case Name':'Case','Station x (m)':station_label})
        if station_label == 'formatted metres':
            result['Governing x'] = result.pop(station_label).map(lambda x:f'{x:.3f} m')
        result['Status'] = 'PASS'
        result.loc[0, 'Status'] = 'FAIL'
        result['D/C value'] = .5
        gated = apply_source_gate(result, frame)
        assert gated.loc[0, 'Status'] == 'FAIL'
        assert gated.loc[1:, 'Status'].eq('REVIEW').all()
        assert gated['D/C value'].eq(.5).all()
        assert gated['Source Girder'].eq(group.girder).all()
        for field, label in [('section_cut','SectCutNum'),('location_type','LocType'),('case','OutputCase'),('step','StepType')]:
            assert gated['Source '+label].tolist() == [source_info(row)[field] for _,row in frame.iterrows()]
        assert gated['Source SHA256'].eq(DIGEST).all()


def test_rounded_station_ambiguity_and_interpolated_rows_do_not_inherit_wrong_source_cut(parsed):
    source = parsed[0][2].iloc[:2].copy()
    source['Case Name'] = 'same case'
    source['Station x (m)'] = [1.0001,1.0002]
    ambiguous = pd.DataFrame([{'Case':'same case','Governing x':'1.000 m','Status':'PASS','Station type':'LOAD STATION'}])
    assert 'Source Excel row' not in apply_source_gate(ambiguous,source)
    exact = ambiguous.assign(**{'Source row':1})
    gated = apply_source_gate(exact,source)
    assert gated.loc[0,'Source Excel row'] == source_info(source.iloc[1])['row']
    assert gated.loc[0,'Source station x (m)'] == 1.0002
    critical = exact.assign(**{'Station type':'CRITICAL SHEAR SECTION'})
    assert 'Source Excel row' not in apply_source_gate(critical,source)


def test_bank_switch_analysis_consumer_json_and_duplicate_guard_keep_every_vector(parsed):
    bank = pd.concat([frame for _,_,frame in parsed], ignore_index=True)
    state = {BANK_KEY:bank, SETTINGS_KEY:{'input_sign':CSI_TENSION_POSITIVE}}
    for member in bank['Girder'].unique():
        activate_member(state, member)
        active = _active_beam_uls_demand_dataframe_from_session(state)
        expected = bank[bank['Girder'].eq(member)]
        for column in APP_COLUMNS:
            assert active[column].tolist() == expected[column].tolist()
        save_active(state)
    restored = {}
    apply_project_to_session_state(project_from_json(project_to_json(project_from_session_state(state))), restored)
    save_active(restored)
    assert restored[ACTIVE_KEY] == bank.iloc[-1]['Girder']
    assert len(restored[BANK_KEY]) == 640
    for member in bank['Girder'].unique():
        activate_member(restored, member)
        expected = bank[bank['Girder'].eq(member)]
        for column in APP_COLUMNS:
            assert restored['beam_uls_loads_table'][column].tolist() == expected[column].tolist()
    with pytest.raises(ValueError, match='Duplicate'):
        merge_bank(bank, bank, append=True)


def test_all_member_app_csv_reimport_preserves_source_notes_members_and_signed_components(parsed):
    bank = pd.concat([frame for _,_,frame in parsed], ignore_index=True)
    raw = read_tables(bank.to_csv(index=False).encode('utf-8-sig'), 'all.csv')['CSV']
    assert not is_csi_table(raw) and not is_native_bridge_table(raw)
    groups = split_member_tables(raw, sheet_name='CSV')
    assert [group.name for group in groups] == bank['Girder'].unique().tolist()
    for group in groups:
        frame = prepare_imported_workflow_load_table(group.frame, APP_COLUMNS)
        frame = tag_app_source(frame, source_name='all.csv', sheet_name='CSV', source_mode='correspondence', concurrency_confirmed=True, evidence='reupload')
        expected = bank[bank['Girder'].eq(group.name)]
        active = _active_beam_uls_demand_dataframe_from_session({'beam_uls_loads_table':frame})
        for column in ['Note','Case Name','Station x (m)', *FORCE_MAP.values()]:
            assert active[column].tolist() == expected[column].tolist()
        assert all(source_info(row)['kind'] == 'ENVELOPE' for _,row in frame.iterrows())
