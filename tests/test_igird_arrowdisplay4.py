"""Regression coverage for Arrow-invalid mixed station audit fields."""
import copy
import json

import pandas as pd
import pyarrow as pa
import pytest

from concrete_pmm_pro.io.girder_load_bank import BANK_KEY
from concrete_pmm_pro.ui.igird_member_results import calculate_member, member_inputs
from concrete_pmm_pro.ui.result_table_display import result_table_for_display
from test_igird_multicase_deckuls1 import deck_state
from test_igird_uls6_torsion_general_procedure import _state, _route, _demand


def mixed_member_model():
    """Calculated, below-threshold and zero-demand stations in each case."""
    state = _state()
    state['section_parameters'] = deck_state()['section_parameters']
    rows = []
    for member, factor in [('Exterior Girder', 1.), ('Interior Girder 2', 1.3)]:
        for case in ['ULS1', 'ULS2']:
            for x, tu in [(5., 500.), (10., 10.), (18., 0.)]:
                row = _demand(x=x, tu=tu * factor, vu=400. * factor).iloc[0].to_dict()
                row.update({'Girder': member, 'Case Name': member + ' / ' + case})
                rows.append(row)
    state[BANK_KEY] = pd.DataFrame(rows)
    return state


@pytest.mark.parametrize('nested', [[], [{'Layer': 'Deck top', 'factor': .5, 'ready': False}],
                                    {'Layer': 'Deck bottom', 'factor': 1.}, (1., 2.)])
@pytest.mark.parametrize('nested_first', [True, False])
def test_nested_audit_and_placeholder_serialize_in_either_row_order(nested, nested_first):
    values = [nested, '-'] if nested_first else ['-', nested]
    frame = pd.DataFrame({'Deck development trace': values})
    original = copy.deepcopy(frame)
    display = result_table_for_display(frame)
    table = pa.Table.from_pandas(display, preserve_index=False)
    assert table.num_rows == 2
    idx = 0 if nested_first else 1
    assert json.loads(display.iloc[idx, 0]) == (list(nested) if isinstance(nested, tuple) else nested)
    assert display.iloc[1 - idx, 0] == '-'
    pd.testing.assert_frame_equal(frame, original)


def test_mixed_flags_preserve_false_nulls_and_typed_numeric_columns():
    frame = pd.DataFrame({
        'Closed loop confirmed': [True, '-', False, None],
        'Deck development trace': [[], '-', pd.NA, None],
        'D/C value': [.125, float('inf'), float('nan'), 1.],
        'Source row': pd.Series([1, 2, None, 4], dtype='Int64'),
        'Active': [True, False, True, False],
    })
    original = copy.deepcopy(frame)
    display = result_table_for_display(frame)
    assert display['Closed loop confirmed'].iloc[:3].tolist() == ['True', '-', 'False']
    assert pd.isna(display['Closed loop confirmed'].iloc[3])
    assert display['Deck development trace'].iloc[0] == '[]'
    assert display['Deck development trace'].iloc[2:].isna().all()
    for col in ['D/C value', 'Source row', 'Active']:
        pd.testing.assert_series_equal(display[col], frame[col])
    pa.Table.from_pandas(display, preserve_index=False)
    pd.testing.assert_frame_equal(frame, original)


@pytest.mark.parametrize('order', [(0, 1, 2), (1, 0, 2), (2, 1, 0)])
def test_real_torsion_mixed_threshold_rows_keep_complete_solver_data(order):
    source = pd.concat([_demand(x=5., tu=500.), _demand(x=10., tu=10.),
                        _demand(x=18., tu=0.)], ignore_index=True).iloc[list(order)].copy()
    result = calculate_member(_state(), source, check_name='Torsion', route=_route())
    frame = result['torsion_check_df']
    assert {'BELOW THRESHOLD', 'NO DEMAND'}.issubset(set(frame['Status']))
    assert any(isinstance(v, list) for v in frame['Deck development trace'])
    assert '-' in frame['Deck development trace'].tolist()
    with pytest.raises((pa.ArrowInvalid, pa.ArrowTypeError)):
        pa.Table.from_pandas(frame)
    original = copy.deepcopy(frame)
    display = result_table_for_display(frame)
    pa.Table.from_pandas(display, preserve_index=False)
    pd.testing.assert_series_equal(display['φTn kN-m'], frame['φTn kN-m'])
    pd.testing.assert_series_equal(display['D/C value'], frame['D/C value'])
    pd.testing.assert_frame_equal(result['torsion_check_df'], original)


@pytest.mark.parametrize('check', ['Flexure', 'Shear', 'Torsion', 'Shear + Torsion'])
def test_all_member_result_frames_serialize_without_altering_source_or_cache(check):
    state = mixed_member_model()
    original = copy.deepcopy(state)
    for member, source in member_inputs(state).items():
        result = calculate_member(state, source, check_name=check, route=_route())
        assert 'error' not in result
        for frame in result.values():
            if not isinstance(frame, pd.DataFrame):
                continue
            before = copy.deepcopy(frame)
            display = result_table_for_display(frame)
            pa.Table.from_pandas(display, preserve_index=False)
            if 'Case' in display:
                assert display['Case'].dropna().str.startswith(member + ' / ').all()
            for name in frame.select_dtypes(include=['number', 'bool']).columns:
                pd.testing.assert_series_equal(display[name], frame[name])
            pd.testing.assert_frame_equal(frame, before)
    pd.testing.assert_frame_equal(state[BANK_KEY], original[BANK_KEY])
    assert state['section_parameters'] == original['section_parameters']


def test_empty_result_table_remains_empty_with_original_columns():
    frame = pd.DataFrame(columns=['Case', 'Deck development trace'])
    display = result_table_for_display(frame)
    pd.testing.assert_frame_equal(display, frame)
    assert display is not frame
    pa.Table.from_pandas(display, preserve_index=False)
