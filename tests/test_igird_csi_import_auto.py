"""Regression coverage for the user's unchanged latest single-sheet export."""
from pathlib import Path

import pandas as pd
import pytest

from concrete_pmm_pro.io.girder_csi_import import (
    APP_COLUMNS, FORCE_MAP, append_errors, apply_source_gate, is_app_table, is_csi_table,
    prepare_csi_table, read_tables, source_info,
)
from concrete_pmm_pro.ui.analysis_page import _active_beam_uls_demand_dataframe_from_session
from concrete_pmm_pro.ui.loads_page import prepare_imported_workflow_load_table, _workflow_table_result

ROOT = Path(__file__).resolve().parents[1]
LATEST = ROOT / 'qa/fixtures/CSiBridge_Left_Exterior_Max_Min_latest.xlsx'


def latest():
    table = read_tables(LATEST.read_bytes(), LATEST.name)['Left Exterior Girder']
    return table, prepare_csi_table(table, sheet_name='Left Exterior Girder')


def test_latest_single_sheet_is_detected_and_every_component_reaches_analysis():
    tables = read_tables(LATEST.read_bytes(), LATEST.name)
    assert list(tables) == ['Left Exterior Girder']
    raw, parsed = latest()
    assert is_csi_table(raw) and not is_app_table(raw)
    assert not parsed.errors and parsed.counts == {'Max': 40, 'Min': 40}
    active = _active_beam_uls_demand_dataframe_from_session({'beam_uls_loads_table': parsed.frame})
    assert len(active) == 80 and active['Station x (m)'].nunique() == 21
    assert not active.duplicated(['Case Name', 'Station x (m)']).any()
    assert active['Station x (m)'].tolist() == raw.iloc[1:]['Girder Distance'].astype(float).tolist()
    for source, target in FORCE_MAP.items():
        assert active[target].tolist() == raw.iloc[1:][source].astype(float).tolist()
    assert active['Muy'].abs().gt(0).all() and active['Vux'].abs().gt(0).all()
    assert [source_info(row)['row'] for _, row in active.iterrows()] == list(range(3, 83))


def test_calculation_source_trace_keeps_reference_components_and_raw_signs():
    _, parsed = latest()
    result = parsed.frame[['Case Name', 'Station x (m)']].rename(columns={'Case Name': 'Case'})
    result['Status'] = 'PASS'
    result['Notes'] = 'Calculated'
    gated = apply_source_gate(result, parsed.frame)
    for target in FORCE_MAP.values():
        unit = 'kN-m' if target in {'Mux', 'Muy', 'Tu'} else 'kN'
        assert gated[f'Source {target} {unit}'].tolist() == parsed.frame[target].tolist()
    assert gated['Source Excel row'].tolist() == list(range(3, 83))
    assert gated['Status'].eq('REVIEW').all()


@pytest.mark.parametrize('component', list(FORCE_MAP))
def test_missing_any_source_component_cannot_be_applied(component):
    raw, _ = latest()
    raw.loc[2, component] = None  # First original data row, after the units row.
    parsed = prepare_csi_table(raw, sheet_name='Left Exterior Girder')
    assert parsed.errors  # UI must disable Apply; the incomplete row is never zero-filled.
    assert any('row 3' in message and 'all six' in message for message in parsed.errors)


@pytest.mark.parametrize('station', ['Station x (m)', 'Station s (m)', 's (m)', 'Distance (m)'])
def test_existing_app_csv_uses_the_same_header_detection_without_csi_reinterpretation(station):
    old = pd.DataFrame([{station: 2, 'Combo Name': 'Legacy ULS', 'Mx': -700,
        'Vy': -20, 'T': 4, 'My': -15, 'Vx': 8, 'N': 12, 'Note': 'reference signs'}])
    raw = read_tables(old.to_csv(index=False).encode('utf-8'), 'old.csv')['CSV']
    assert is_app_table(raw) and not is_csi_table(raw)
    normalized = prepare_imported_workflow_load_table(raw, APP_COLUMNS)
    valid = _workflow_table_result(normalized, table_name='legacy',
        numeric_columns=['Station x (m)', 'Mux', 'Vuy', 'Tu', 'Muy', 'Vux', 'Nu'],
        unique_key_columns=['Case Name', 'Station x (m)'])
    assert not valid.errors
    active = _active_beam_uls_demand_dataframe_from_session({'beam_uls_loads_table': normalized})
    assert active.iloc[0]['Mux'] == -700 and active.iloc[0]['Muy'] == -15
    assert active.iloc[0]['Nu'] == 12 and active.iloc[0]['Vux'] == 8
    assert active.iloc[0]['Note'] == 'reference signs'


def test_duplicate_append_matches_native_numeric_and_legacy_text_station_keys():
    _, parsed = latest()
    current = parsed.frame.iloc[:1].copy(deep=True)
    uploaded = current.copy(deep=True)
    uploaded['Station x (m)'] = '0'
    before = uploaded.copy(deep=True)
    assert append_errors(current, uploaded, current_is_csi=True)
    pd.testing.assert_frame_equal(uploaded, before)
