"""Independent geometry, support-scope, input transaction and numerical regressions."""
from copy import deepcopy
from io import BytesIO
import json
from types import SimpleNamespace
from unittest.mock import patch
from zipfile import ZipFile

import numpy as np
import pandas as pd
import pytest
from shapely.geometry import Point, shape

from concrete_pmm_pro.analysis import slab_track77 as track, slab_top65 as top, slab_review68 as active
from concrete_pmm_pro.io.project_io import project_from_json, project_to_json, project_from_session_state, apply_project_to_session_state
from test_slab_punch76_auto import app, state


def bridge(angle=0.):
    c, s = np.cos(angle), np.sin(angle)
    rotation = np.array([[c, s], [-s, c]])
    local = np.array([[0., -5.5], [20., -5.5], [20., 5.5], [0., 5.5]])
    xy = local@rotation
    xyz = np.column_stack((xy, np.zeros(4)))
    corners = pd.DataFrame({'AreaElem': ['E1']*4, 'Joint': ['1', '2', '3', '4'],
                            'X (m)': xy[:, 0], 'Y (m)': xy[:, 1]})
    geometry = SimpleNamespace(elements={'E1': xyz},
        parent_axes={'A1': {'long': [c, s, 0.]}}, corners=corners)
    supports = [{'Support': f'Girder {i+1}', 'Kind': 'Girder',
                 'a': np.array([0., y])@rotation, 'b': np.array([20., y])@rotation,
                 'half_width': .3} for i, y in enumerate([-3.7, -2.5, -1.3, 1.3, 2.5, 3.7])]
    return {'geometry': geometry, 'supports': supports}


def enabled(**kwargs):
    return {**track.DEFAULT, 'enabled': True, **kwargs}


def test_20m_six_girder_section_matches_independent_width_and_area_accounting():
    r = track.calculate(bridge(), enabled())
    assert r['distributed_width_m'] == pytest.approx(2.6)
    assert list(r['tracks']['Offset from deck CL (m)']) == [-2.5, 2.5]
    assert list(r['tracks']['Girder contacts']) == [3, 3]
    assert r['tracks']['Within outer girder extent'].all()
    # 20*11=220; six 0.6 m contacts =72; clear directly loaded bays=48.
    assert r['area_m2'][track.SUPPORTED] == pytest.approx(72.)
    assert r['area_m2'][track.DIRECT] == pytest.approx(48.)
    assert r['area_m2'][track.SPREAD] == pytest.approx(0., abs=1e-9)
    assert sum(r['area_m2'].values()) == pytest.approx(220.)
    fractions = r['elements'].filter(like=' fraction').iloc[0]
    assert fractions.sum() == pytest.approx(1.)
    assert fractions[track.SUPPORTED+' fraction'] == pytest.approx(72/220)
    assert shape(r['zones'][track.DIRECT]).covers(Point(10., 1.9))
    assert not shape(r['zones'][track.SUPPORTED]).covers(Point(10., 1.9))
    assert not r['code_exemption'] and not r['actions_changed'] and not r['full_deck_acceptance']
    assert r['local_train_punching_status'] == 'NOT CALCULATED'


@pytest.mark.parametrize('angle', [.47, -1.1])
def test_rotated_imported_axes_produce_identical_physical_areas(angle):
    first = track.calculate(bridge(), enabled())
    second = track.calculate(bridge(angle), enabled())
    assert second['area_m2'] == pytest.approx(first['area_m2'])
    np.testing.assert_allclose(second['elements'].filter(like=' fraction'),
                               first['elements'].filter(like=' fraction'), atol=1e-10)


def test_depth_changes_geometry_only_and_missing_contact_width_creates_no_exclusion():
    b = bridge(); b['supports'] = []
    zero = track.calculate(b, enabled(depth_mm=0.))
    deeper = track.calculate(b, enabled(depth_mm=450.))
    assert zero['area_m2'][track.DIRECT] == pytest.approx(80.)
    assert zero['area_m2'][track.SPREAD] == pytest.approx(0.)
    assert deeper['distributed_width_m'] == pytest.approx(2.9)
    assert deeper['area_m2'][track.SUPPORTED] == 0
    assert deeper['area_m2'][track.SPREAD] == pytest.approx(36.)
    assert any('No flange exclusion' in x for x in deeper['notes'])


@pytest.mark.parametrize('changes', [{'width_m': 0}, {'depth_mm': -1}, {'count': 2.5},
    {'spacing_m': float('nan')}, {'offset_m': True}, {'enabled': 'yes'}, {'version': 2},
    {'width_m': 6., 'spacing_m': 5.}])
def test_invalid_geometry_is_rejected_without_overwriting_committed_inputs(changes):
    s = {'project_metadata': {track.CONFIG_KEY: enabled()}}
    before = deepcopy(s)
    with pytest.raises(ValueError):
        track.save(s, changes)
    assert s == before


def test_outside_physical_footprint_requires_review_and_never_rescales_it_into_the_deck():
    r = track.calculate(bridge(), enabled(offset_m=6.))
    assert not r['tracks']['Source inside slab'].all()
    assert any('extends beyond the slab' in x for x in r['notes'])
    assert r['config']['offset_m'] == 6.


def test_contact_scope_requires_whole_patch_not_centroid_or_outer_girder_envelope():
    areas = [{'Area': name, 'X (m)': 10., 'Y (m)': y, 'L (mm)': 100., 'B (mm)': w,
              'Vu (kN, optional)': None} for name, y, w in [('Full', 2.5, 200.),
                  ('Partial', 2.5, 1000.), ('Clear', 1.9, 200.)]]
    rows = pd.DataFrame([{'Area': a['Area'], 'Status': 'REVIEW', 'D/C': np.nan,
                         'Vu (kN)': np.nan, 'Reason': 'Original support review'} for a in areas])
    p = {'rows': rows, 'areas': areas, 'paths': {a['Area']: {} for a in areas},
         'segments': pd.DataFrame(), 'status': 'REVIEW'}
    original = p['rows'].copy(deep=True)
    r = track.apply_contact_scope(p, bridge(), enabled())
    assert r['project_supported_areas'] == ['Full']
    assert r['status'] == 'REVIEW'
    assert r['rows'].set_index('Area').loc['Full', 'Status'] == 'OUTSIDE SLAB PUNCHING SCOPE'
    assert r['rows'].set_index('Area').loc['Partial', 'Reason'] == 'Original support review'
    assert 'Full' not in r['paths'] and 'Partial' in r['paths']
    pd.testing.assert_frame_equal(p['rows'], original, check_exact=True)


def test_full_contact_exclusion_never_becomes_pass_or_clears_a_different_failure():
    area = {'Area': 'Full', 'X (m)': 10., 'Y (m)': 2.5, 'L (mm)': 100.,
            'B (mm)': 200., 'Vu (kN, optional)': 500.}
    row = {'Area': 'Full', 'Status': 'REVIEW', 'D/C': np.nan, 'Vu (kN)': np.nan,
           'phiVn (kN)': 100., 'Reason': 'Support guard'}
    p = {'rows': pd.DataFrame([row]), 'areas': [area], 'paths': {'Full': {}},
         'segments': pd.DataFrame(), 'status': 'REVIEW'}
    r = track.apply_contact_scope(p, bridge(), enabled())
    assert r['status'] == 'OUTSIDE SLAB PUNCHING SCOPE'
    assert r['rows'][['Vu (kN)', 'D/C', 'phiVn (kN)']].isna().all().all()
    p['areas'].append({**area, 'Area': 'Other', 'Y (m)': 0.})
    p['rows'] = pd.concat((p['rows'], pd.DataFrame([{**row, 'Area': 'Other',
        'Status': 'FAIL', 'D/C': 5., 'Vu (kN)': 500., 'Reason': 'Actual failure'}])), ignore_index=True)
    r = track.apply_contact_scope(p, bridge(), enabled())
    assert r['status'] == 'FAIL' and r['rows'].set_index('Area').loc['Other', 'D/C'] == 5.


def test_discontinuous_girder_segments_do_not_fill_the_gap_between_them():
    b = bridge()
    b['supports'] = [{'Support': f'Girder {i}', 'Kind': 'Girder', 'a': np.array([a, 0.]),
                      'b': np.array([c, 0.]), 'half_width': .3} for i, a, c in [(1, 0., 8.), (2, 12., 20.)]]
    r = track.calculate(b, enabled(count=1, depth_mm=0.))
    assert not shape(r['zones'][track.SUPPORTED]).covers(Point(10., 0.))
    assert shape(r['zones'][track.DIRECT]).covers(Point(10., 0.))
    assert r['area_m2'][track.SUPPORTED] == pytest.approx(16*.6)
    assert sum(r['area_m2'].values()) == pytest.approx(220.)


def test_enabled_geometry_reuses_existing_sections_preserves_all_actions_and_json_inputs():
    s = state()
    before = active.calculate(s)
    s[active.RESULT_KEY] = before
    s[top.RESULT_KEY] = before['top65_result']
    original_forces = before['rows'].copy(deep=True)
    track.save(s, enabled(count=1, width_m=.2, spacing_m=5., depth_mm=100.))
    assert active.current(s) is None
    after = top.calculate(s, reuse=before['shear_result'])
    assert after['accepted_result_reused']
    pd.testing.assert_frame_equal(original_forces, after['rows'], check_exact=True)
    pd.testing.assert_frame_equal(before['summary'], after['summary'], check_exact=True)
    assert after['punching']['status'] == 'NOT CALCULATED'
    loaded = {}
    apply_project_to_session_state(project_from_json(project_to_json(project_from_session_state(s))), loaded)
    assert track.config(loaded) == track.config(s)
    assert top.RESULT_KEY not in loaded


def test_actual_app_apply_persists_inputs_keeps_page_and_renders_geometry_after_one_calculate():
    test = app(state())
    with patch.object(active, 'calculate', wraps=active.calculate) as solver:
        test.number_input(key='slab_shell55_track77_count').set_value(1)
        test.number_input(key='slab_shell55_track77_width').set_value(.2)
        next(b for b in test.button if b.label == 'Apply 45° track geometry').click().run()
        assert not test.exception
        assert solver.call_count == 0
        assert test.session_state['_nav_analysis_subpage'] == 'Slab Reinforcement'
        assert track.config({'project_metadata':test.session_state['project_metadata']})['enabled']
        test.button(key='slab_shell55_aashto62_calculate').click().run(timeout=60)
        assert not test.exception
        assert solver.call_count == 1 and len(test.get('plotly_chart')) == 2
        assert test.session_state[active.RESULT_KEY]['punching_screen78']['evaluated_records'] > 0
        r = test.session_state[active.RESULT_KEY]
        assert r['track_distribution']['status'] == 'GEOMETRY CALCULATED'
        assert r['punching']['rows'].empty and not r['punching']['status'].startswith('PASS')
        test.button(key='slab_shell55_punch76_oneway').click().run()
        assert not test.exception and solver.call_count == 1
        assert test.session_state['slab_shell55_shear64_group'] == 'One-way shear'


def test_report_uses_stored_geometry_after_inputs_change_and_never_runs_a_solver():
    s = state()
    track.save(s, enabled(count=1, width_m=.2))
    r = active.calculate(s)
    track.save(s, {'width_m': .3})
    with patch.object(track, 'calculate', side_effect=AssertionError('Report recalculated')):
        payload = active.report_zip(r)
    with ZipFile(BytesIO(payload)) as z:
        name = next(n for n in z.namelist() if n.endswith('Track45/Scope_and_Geometry.json'))
        saved = json.loads(z.read(name))
        assert saved['config']['width_m'] == .2
        assert not saved['code_exemption'] and not saved['full_deck_acceptance']
        review = json.loads(z.read(next(n for n in z.namelist() if n.endswith('Punching_Automatic_Review.json'))))
        assert review['route'] == 'actual_thickness_local_index'
        assert review['physical_perimeter_check_status'] == 'NOT CALCULATED'
        assert review['local_train_punching_status'] == 'NOT CALCULATED'
