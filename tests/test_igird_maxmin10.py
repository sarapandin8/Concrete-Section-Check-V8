"""Native Max/Min grouping, all source vectors, paired cached resistance/gates."""
from contextlib import ExitStack
from copy import deepcopy
import json
from pathlib import Path
from unittest.mock import patch

import pandas as pd
import pytest

from concrete_pmm_pro.io.girder_csi_import import SOURCE_TAG, prepare_csi_table, read_tables
from concrete_pmm_pro.ui import analysis_page as ap, igird_member_results as mr
from concrete_pmm_pro.ui import igird_maxmin_charts as mm, igird_uls_report as report
from concrete_pmm_pro.ui.igird_case_review import FRAME_KEYS, controlling_result, summary_record
from qa.igird_maxmin10_model import calculate_native_model


@pytest.fixture
def native():
    path = Path('qa/fixtures/CSiBridge_ULS_Girder_Max_Min.xlsx')
    return prepare_csi_table(read_tables(path.read_bytes(), path.name)['Left Exterior Girder'],
        sheet_name='Left Exterior Girder', case_name='U2A', source_name=path.name).frame


@pytest.fixture(scope='module')
def calculated():
    return calculate_native_model()


def no_solvers():
    stack = ExitStack()
    for name in ('_beam_uls_calculate_selected_check', '_beam_uls_flexure_preview_dataframe',
                 '_beam_uls_final_composite_preparation', '_beam_uls_igird_torsion_diagram_capacity_dataframe',
                 '_beam_uls_igird_shear_diagram_capacity_dataframe'):
        stack.enter_context(patch.object(ap, name, side_effect=AssertionError('Chart review must not calculate')))
    stack.enter_context(patch.object(mr, 'calculate_member', side_effect=AssertionError('Chart review must not calculate')))
    return stack


def retag(rows, **changes):
    rows = rows.copy(deep=True)
    for index, row in rows.iterrows():
        info = json.loads(row['Note'].split(SOURCE_TAG, 1)[1])
        info.update(changes)
        rows.at[index, 'Note'] = SOURCE_TAG+json.dumps(info)
    return rows


def test_native_family_has_all_40_max_40_min_rows_and_both_occurrences(native):
    before = native.copy(deep=True)
    families, choices = mm.review_choices(native, native['Case Name'].unique())
    assert len(families) == 1 and len(choices) == 1
    family = families[0]
    for step in ('Max', 'Min'):
        assert len(family.groups[step]) == 2
        assert len(mm.select_cases(native, family.groups[step], column='Case Name')) == 40
    assert len(family.cases) == 4
    pd.testing.assert_frame_equal(native, before, check_exact=True)


def test_bound_classification_uses_metadata_even_when_max_is_negative_min_positive(native):
    native.loc[native['Case Name'].str.contains('/ Max /'), ['Mux', 'Vuy', 'Tu']] = -42.
    native.loc[native['Case Name'].str.contains('/ Min /'), ['Mux', 'Vuy', 'Tu']] = 42.
    family = mm.csi_bound_families(native)[0]
    assert mm.select_cases(native, family.groups['Max'], column='Case Name').Tu.eq(-42.).all()
    assert mm.select_cases(native, family.groups['Min'], column='Case Name').Tu.eq(42.).all()


@pytest.mark.parametrize('field,value', [('case', 'U3'), ('source_file', 'Different.xlsx'),
    ('sheet', 'Other Girder'), ('distance_column', 'Layout Line Distance'),
    ('step_number', '2'), ('control', 'Torsion'), ('source_mode', 'correspondence'),
    ('kind', 'CONCURRENT'), ('evidence', 'Different correspondence record')])
def test_different_source_families_do_not_supply_each_others_min(native, field, value):
    is_min = native['Case Name'].str.contains('/ Min /')
    other = retag(native.loc[is_min], **{field:value})
    families = mm.csi_bound_families(pd.concat([native.loc[~is_min], other]))
    assert len(families) == 2
    assert all(not (f.groups['Max'] and f.groups['Min']) for f in families)


@pytest.mark.parametrize('invalid', ['', pd.NA, SOURCE_TAG+'{}', SOURCE_TAG+'not json'])
def test_unqualified_or_partly_tagged_series_is_not_grouped_by_its_name(native, invalid):
    native['Note'] = invalid
    assert not mm.csi_bound_families(native)


def test_conflicting_series_metadata_excludes_complete_series(native):
    index = native.index[0]
    native.loc[[index], 'Note'] = retag(native.loc[[index]], case='Unrelated').Note
    families = mm.csi_bound_families(native)
    assert all(native.loc[index, 'Case Name'] not in f.cases for f in families)


@pytest.mark.parametrize('changes', [{'row':0}, {'occurrence':0}, {'kind':'UNKNOWN'}])
def test_invalid_identity_is_not_qualified_as_a_native_bound(native, changes):
    assert not mm.csi_bound_families(retag(native, **changes))


@pytest.mark.parametrize('check', list(FRAME_KEYS))
@pytest.mark.parametrize('view', [mm.DEMAND_VIEW, mm.UTILIZATION_VIEW])
def test_each_member_lc_has_separate_bound_figures_and_unchanged_stored_control(calculated, check, view):
    state = deepcopy(calculated)
    before = deepcopy(state)
    with no_solvers():
        packages = report.current_check_packages(state, check)
        assert set(packages) == {'Left Exterior Girder', 'Interior Girder 2'}
        for member, package in packages.items():
            families = mm.csi_bound_families(package['rows'])
            assert len(families) == 2
            for family in families:
                figures = mm.make_bound_figures(state, package, family=family, member=member,
                    check_name=check, code_label='AASHTO LRFD 9th Edition', view=view)
                assert list(figures) == ['Max', 'Min']
                for step, fig in figures.items():
                    meta = fig.layout.meta
                    assert meta['igird_maxmin_member'] == member
                    assert meta['igird_maxmin_lc'] == family.source['case']
                    assert meta['igird_maxmin_step'] == step
                    assert set(meta['igird_maxmin_cases']) == set(family.groups[step])
                    assert fig.layout.title.text.startswith('Girder: '+member+'<br>')
                    assert check in fig.layout.title.text and step in fig.layout.title.text
                    assert fig.layout.xaxis.range == (0., 20.)
                    stored = mm.select_cases(package['result'][FRAME_KEYS[check]], family.groups[step])
                    assert meta['igird_maxmin_selected_control'] == summary_record(controlling_result(stored, check))
                    assert meta['igird_maxmin_member_control'] == summary_record(controlling_result(package['result'][FRAME_KEYS[check]], check))
                    selected_control = controlling_result(stored, check)
                    if selected_control['basis'] != 'NO NUMERIC D/C':
                        marker = meta['igird_maxmin_control_marker']
                        assert marker['Case'] == selected_control['row']['Case']
                        assert marker['x_m'] == float(selected_control['row']['Governing x'].replace(' m',''))
                        assert marker['Ratio'] == meta['igird_maxmin_selected_control']['D/C or ratio']
                        annotation = next(a for a in fig.layout.annotations if a.name == 'igird_maxmin_control')
                        assert annotation.x == marker['x_m'] and annotation.yref == 'paper'
                    assert not any(str(t.name).startswith(('Gov.','Governing')) for t in fig.data)
                    assert len(meta['igird_report_note']) == 3
                    if view == mm.DEMAND_VIEW and check != 'Shear + Torsion':
                        component, label = {'Flexure':('Mux','Mux'), 'Shear':('Vuy','Vu'), 'Torsion':('Tu','Tu')}[check]
                        demands = [t for t in fig.data if str(t.name).startswith(label+' '+step+' ')]
                        assert len(demands) == 2, [t.name for t in fig.data]
                        source = mm.select_cases(package['rows'], family.groups[step], column='Case Name')
                        plotted = {(str(custom[1]), int(custom[3]), float(x)): float(y)
                                   for trace in demands for x,y,custom in zip(trace.x,trace.y,trace.customdata)}
                        for _, row in source.iterrows():
                            info = json.loads(row.Note.split(SOURCE_TAG,1)[1])
                            assert plotted[(row['Case Name'],info['row'],row['Station x (m)'])] == row[component]
                    if check == 'Torsion' and view == mm.UTILIZATION_VIEW:
                        assert all(row['Case'] in family.groups[step] for row in meta['torsion_utilization_audit'])
    for member, checks in state[mr.CACHE_KEY].items():
        for name, entry in checks.items():
            old = before[mr.CACHE_KEY][member][name]
            assert entry['input_hash'] == old['input_hash']
            for key, value in entry['result'].items():
                if isinstance(value, pd.DataFrame):
                    pd.testing.assert_frame_equal(value, old['result'][key], check_exact=True)
    pd.testing.assert_frame_equal(state['igird_uls_member_bank'], before['igird_uls_member_bank'], check_exact=True)
    pd.testing.assert_frame_equal(state['beam_uls_loads_table'], before['beam_uls_loads_table'], check_exact=True)


@pytest.mark.parametrize('check', ['Flexure', 'Shear', 'Torsion'])
def test_missing_min_is_explicit_and_has_no_fabricated_curve(calculated, check):
    state = deepcopy(calculated)
    package = report.current_check_packages(state, check)['Left Exterior Girder']
    family = mm.csi_bound_families(package['rows'])[0]
    package['rows'] = mm.select_cases(package['rows'], family.groups['Max'], column='Case Name')
    family = mm.csi_bound_families(package['rows'])[0]
    with no_solvers():
        figures = mm.make_bound_figures(state, package, family=family, member='Left Exterior Girder',
            check_name=check, code_label='QA')
    assert figures['Max'] is not None and figures['Min'] is None


@pytest.mark.parametrize('check', list(FRAME_KEYS))
@pytest.mark.parametrize('view', [mm.DEMAND_VIEW, mm.UTILIZATION_VIEW])
def test_imported_min_without_stored_checks_is_demand_only_or_unavailable(calculated, check, view):
    state = deepcopy(calculated)
    package = report.current_check_packages(state, check)['Left Exterior Girder']
    family = mm.csi_bound_families(package['rows'])[0]
    package['result'][FRAME_KEYS[check]] = mm.select_cases(package['result'][FRAME_KEYS[check]], family.groups['Max'])
    with no_solvers():
        figures = mm.make_bound_figures(state, package, family=family, member='Left Exterior Girder',
            check_name=check, code_label='QA', view=view)
    if view == mm.UTILIZATION_VIEW or check == 'Shear + Torsion':
        assert figures['Min'] is None
    else:
        assert figures['Min'].layout.meta['igird_maxmin_stored_rows'] == 0
        assert figures['Min'].layout.meta['igird_maxmin_selected_control']['Basis'] == 'NO NUMERIC D/C'
        assert not any(t.name in {'φMn','±φVn','±φTn'} for t in figures['Min'].data)


@pytest.mark.parametrize('check,capacity', [('Flexure','Capacity kN-m'), ('Shear','φVn kN'), ('Torsion','φTn kN-m')])
def test_each_bound_uses_its_own_resistance_and_retains_missing_cache(calculated, check, capacity):
    state = deepcopy(calculated)
    package = report.current_check_packages(state, check)['Left Exterior Girder']
    family = mm.csi_bound_families(package['rows'])[0]
    key = FRAME_KEYS[check] if check == 'Flexure' else check.lower()+'_diagram_capacity_df'
    cached = package['result'][key]
    cached.loc[cached.Case.isin(family.groups['Max']), capacity] = 111.
    cached.loc[cached.Case.isin(family.groups['Min']), capacity] = 222.
    cached.loc[cached.Case.isin(family.groups['Min']) & cached['Governing x'].eq('10.000 m'), capacity] = float('nan')
    if check == 'Shear':
        critical = package['result']['shear_critical_section_df']
        critical.loc[critical.Case.isin(family.groups['Max']), capacity] = 111.
        critical.loc[critical.Case.isin(family.groups['Min']), capacity] = 222.
    with no_solvers():
        figures = mm.make_bound_figures(state, package, family=family, member='Left Exterior Girder',
            check_name=check, code_label='QA')
    label = {'Flexure':'φMn','Shear':'±φVn','Torsion':'±φTn'}[check]
    for step, value in [('Max',111.), ('Min',222.)]:
        traces = [t for t in figures[step].data if t.name == label]
        assert traces
        assert all(abs(y) == value for t in traces for y in t.y if pd.notna(y))
    assert any(pd.isna(y) for t in figures['Min'].data if t.name == label for x,y in zip(t.x,t.y) if x == 10.)
    assert figures['Min'].layout.meta['unavailable_capacity']
    assert not figures['Max'].layout.meta.get('unavailable_capacity')


def test_control_can_be_min_longitudinal_not_the_largest_raw_torsion(calculated):
    state = deepcopy(calculated)
    package = report.current_check_packages(state, 'Torsion')['Left Exterior Girder']
    family = mm.csi_bound_families(package['rows'])[0]
    frame = package['result']['torsion_check_df']
    for column in ('D/C value', 'At D/C', 'Al utilization', 'Detailing D/C value', 'Spacing D/C'):
        frame[column] = .2
    mask = frame.Case.eq(family.groups['Min'][1]) & frame['Governing x'].eq('10.000 m')
    frame.loc[mask, 'Al utilization'] = 1.8
    frame.loc[mask, 'Status'] = 'FAIL'
    with no_solvers():
        figures = mm.make_bound_figures(state, package, family=family, member='Left Exterior Girder',
            check_name='Torsion', code_label='QA')
    assert mm.anchor_case(family, frame, 'Torsion') == family.groups['Min'][1]
    for fig in figures.values():
        assert fig.layout.meta['igird_maxmin_member_control']['Controlling load case'] == family.groups['Min'][1]
        assert fig.layout.meta['igird_maxmin_member_control']['D/C or ratio'] == '1.800'
        assert 'Min' in fig.layout.meta['igird_report_note'][2]
    assert figures['Min'].layout.meta['igird_maxmin_control_marker']['x_m'] == 10.
    assert figures['Min'].layout.meta['igird_maxmin_control_marker']['Component'] == 'Torsion longitudinal steel'


def test_export_names_are_compact_unique_and_identify_bound(native):
    family = mm.csi_bound_families(native)[0]
    names = [mm.export_name(check, 'Very long member name '*10, family, step)
             for check in FRAME_KEYS for step in ('Max', 'Min')]
    assert len(set(names)) == 8
    assert all(len(name) < 150 for name in names)
